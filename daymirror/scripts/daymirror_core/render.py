import re

import yaml

from .constants import KIND_LABELS, SCHEMA_VERSION


def fenced(value):
    runs = re.findall(r"`+", value)
    marker = "`" * max(3, 1 + max((len(run) for run in runs), default=0))
    return f"{marker}text\n{value}\n{marker}"


def claim_line(item, action=False):
    label = KIND_LABELS[item["kind"]]
    sources = ", ".join(item["source_questions"])
    marker = "- [ ]" if action else "-"
    body = item["text"].replace("\n", "\n  ")
    return f"{marker} 【{label}；来源 {sources}】{body}"


def render_journal(session, payload, version):
    questions = session["questions"]
    complete = session["current_question"] is None
    answered = sum(q["status"] == "answered" for q in questions)
    skipped = sum(q["status"] == "skipped" for q in questions)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "date": session["date"],
        "timezone": session["timezone"],
        "session_id": session["session_id"],
        "journal_version": version,
        "content_revision": session["content_revision"],
        "interview_complete": complete,
        "answered_questions": answered,
        "skipped_questions": skipped,
        "pending_questions": 20 - answered - skipped,
        "synthetic": session["synthetic"],
        **payload["metrics"],
        "metric_sources": payload["metric_sources"],
        "tags": payload["tags"],
    }
    frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).rstrip()
    lines = ["---", frontmatter, "---", "", f"# {session['date']} 每日记录", ""]
    if session["synthetic"]:
        lines += ["> 合成示例：问答为演示数据，不代表任何真实个人经历。", ""]
    lines += [f"访谈状态：{'已完成' if complete else '未完成，可继续'}；已回答 {answered} 题，跳过 {skipped} 题。", ""]
    summary = payload["summary"]
    lines += ["## 今日概览", ""]
    lines += [claim_line(summary["overview"]) if summary["overview"] else "暂无足够回答生成概览。", ""]
    for key, title in (("events", "关键事件"), ("reflections", "深度反思"),
                       ("learnings", "今日收获"), ("obstacles", "存在的问题"),
                       ("actions", "明日行动")):
        lines += [f"## {title}", ""]
        lines += [claim_line(item, action=key == "actions") for item in summary[key]] or ["暂无记录。"]
        lines += [""]
    lines += ["## 原始问答记录", ""]
    for number, q in enumerate(questions, 1):
        if number in (1, 11):
            lines += ["### 第一轮：基础问题" if number == 1 else "### 第二轮：深入问题", ""]
        label = {"pending": "未回答", "answered": "已回答", "skipped": "已跳过"}[q["status"]]
        lines += [f"#### {q['id']} · {label}", "", "问题：", "",
                  fenced(q["text"]) if q["text"] is not None else "尚未生成问题。", "", "回答：", ""]
        if q["status"] == "answered":
            lines += [fenced(q["answer"])]
        else:
            lines += ["用户跳过；答案为空。" if q["status"] == "skipped" else "尚未回答；答案为空。"]
        lines += [""]
    return "\n".join(lines).rstrip() + "\n"
