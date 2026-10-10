"""Shape/range/evidence-reference checks; semantic judgment stays with the AI."""

import copy
import math
import re
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .constants import CLAIM_KINDS, METRIC_RULES, SCHEMA_VERSION, SUMMARY_LISTS
from .errors import DayMirrorError


def fail(message, code="invalid_input"):
    raise DayMirrorError(code, message)


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}必须是非空字符串。")
    return value


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        fail(f"{label}必须是大于等于 {minimum} 的整数。")
    return value


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail("日期必须为 YYYY-MM-DD。")
    try:
        date.fromisoformat(value)
    except ValueError:
        fail("日期不存在。")
    return value


def valid_timezone(value):
    text(value, "时区")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        fail("时区必须是有效的 IANA 时区，例如 Asia/Shanghai。请确认已安装 tzdata。")
    return value


def valid_session_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        fail("会话编号必须为工具生成的 32 位小写十六进制编号。")
    return value


def valid_question_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"q(?:0[1-9]|1[0-9]|20)", value):
        fail("问题编号必须为 q01–q20。")
    return value


def exact_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail(f"{label}必须且只能包含字段：{', '.join(keys)}。")


def validate_sources(value, answered, label, required=True):
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        fail(f"{label}必须是问题编号数组。")
    if len(set(value)) != len(value):
        fail(f"{label}不能重复引用问题。")
    if required and not value:
        fail(f"{label}至少需要引用一个已回答的问题。")
    if any(qid not in answered for qid in value):
        fail(f"{label}引用了不存在、未回答或已跳过的问题。")


def validate_claim(value, answered, label, action=False):
    exact_keys(value, ("text", "kind", "source_questions"), label)
    text(value["text"], label + ".text")
    kinds = {"suggestion", "user_commitment"} if action else CLAIM_KINDS
    if not isinstance(value["kind"], str) or value["kind"] not in kinds:
        fail(f"{label}.kind 必须是 {', '.join(sorted(kinds))} 之一。")
    validate_sources(value["source_questions"], answered, label + ".source_questions")


def validate_journal(payload, session):
    exact_keys(payload, ("content_revision", "summary", "metrics", "metric_sources", "tags"), "日记输入")
    integer(payload["content_revision"], "content_revision")
    if payload["content_revision"] != session["content_revision"]:
        fail("回答或问题已发生变化。请重新读取会话并生成总结。", "stale_summary")
    answered = {q["id"] for q in session["questions"] if q["status"] == "answered"}
    exact_keys(payload["metrics"], METRIC_RULES, "metrics")
    exact_keys(payload["metric_sources"], METRIC_RULES, "metric_sources")
    for key, (kind, minimum, maximum) in METRIC_RULES.items():
        value = payload["metrics"][key]
        sources = payload["metric_sources"][key]
        validate_sources(sources, answered, "metric_sources." + key, required=value is not None)
        if value is None:
            if sources:
                fail(f"{key} 为 null 时来源必须为空数组。")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            fail(f"{key}必须是数值或 null。")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            fail(f"{key}不能是 NaN 或无穷大。")
        if kind == "integer" and type(value) is not int:
            fail(f"{key}必须是整数或 null。")
        if value < minimum or (maximum is not None and value > maximum):
            fail(f"{key}超出允许范围。")
    planned = payload["metrics"]["planned_tasks"]
    completed = payload["metrics"]["completed_tasks"]
    if planned is not None and completed is not None and completed > planned:
        fail("completed_tasks 不能超过 planned_tasks；请核对是否把计划外任务算入完成数。")
    summary = payload["summary"]
    exact_keys(summary, ("overview", *SUMMARY_LISTS, "actions"), "summary")
    if summary["overview"] is not None:
        validate_claim(summary["overview"], answered, "summary.overview")
    for key in SUMMARY_LISTS:
        if not isinstance(summary[key], list):
            fail(f"summary.{key}必须是数组。")
        for item in summary[key]:
            validate_claim(item, answered, "summary." + key)
    if not isinstance(summary["actions"], list):
        fail("summary.actions 必须是数组。")
    for item in summary["actions"]:
        validate_claim(item, answered, "summary.actions", action=True)
    tags = payload["tags"]
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        fail("tags 必须是非空字符串组成的数组，也可为空数组。")
    if len(set(tags)) != len(tags):
        fail("tags 不能重复。")
    return copy.deepcopy(payload)


def validate_session(session):
    """Reject corrupt progress before mutation; do not silently reset a journal."""
    if not isinstance(session, dict) or session.get("schema_version") != SCHEMA_VERSION:
        fail("会话格式版本不受支持；保留原文件。", "invalid_session")
    try:
        valid_session_id(session["session_id"])
        valid_date(session["date"])
        valid_timezone(session["timezone"])
        integer(session["revision"], "revision", 1)
        integer(session["content_revision"], "content_revision")
        if session["status"] not in {"active", "paused", "completed"}:
            fail("会话状态无效。")
        questions = session["questions"]
        if not isinstance(questions, list) or len(questions) != 20:
            fail("会话必须包含 20 个问题槽位。")
        for number, q in enumerate(questions, 1):
            if q["number"] != number or q["id"] != f"q{number:02d}":
                fail("问题编号不连续。")
            if q["round"] != ("basic" if number <= 10 else "deep"):
                fail("问题轮次无效。")
            if q["text"] is not None:
                text(q["text"], "问题文本")
            if q["status"] not in {"pending", "answered", "skipped"}:
                fail("问题状态无效。")
            if q["status"] == "answered":
                text(q["answer"], "回答")
            elif q["answer"] is not None:
                fail("未回答的问题不能包含答案。")
            if q["status"] != "pending" and q["text"] is None:
                fail("已回答或跳过的问题必须有问题文本。")
        current = next((q["number"] for q in questions if q["status"] == "pending"), None)
        if session["current_question"] != current:
            fail("保存的进度与问答记录不一致。")
        if current is not None and any(q["status"] != "pending" for q in questions[current:]):
            fail("问答记录存在跳序。")
        if session["status"] == "completed" and current is not None:
            fail("未完成访谈不能标记为 completed。")
        if not isinstance(session["exports"], list):
            fail("导出记录格式无效。")
        if type(session["synthetic"]) is not bool:
            fail("合成数据标记无效。")
        for version, record in enumerate(session["exports"], 1):
            expected_path = f"journals/{session['date']}--{session['session_id']}--v{version}.md"
            if record["version"] != version or record["path"] != expected_path:
                fail("导出版本或路径无效。")
            for key in ("sha256", "payload_hash"):
                if not isinstance(record[key], str) or not re.fullmatch(r"[0-9a-f]{64}", record[key]):
                    fail("导出完整性信息无效。")
            integer(record["content_revision"], "导出内容版本")
            if type(record["complete"]) is not bool:
                fail("导出完成状态无效。")
        if session["journal_payload"] is not None:
            payload = copy.deepcopy(session["journal_payload"])
            # A stored summary may be stale after an edit, but its shape still needs checking.
            payload["content_revision"] = session["content_revision"]
            validate_journal(payload, session)
    except (KeyError, TypeError, ValueError) as exc:
        fail("会话文件损坏或字段缺失；保留原文件。", "invalid_session")
    return session
