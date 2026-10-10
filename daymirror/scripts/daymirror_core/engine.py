import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from .constants import BASIC_QUESTIONS, SCHEMA_VERSION
from .errors import DayMirrorError
from .render import render_journal
from .storage import atomic_write, read_json, workspace_lock, write_json
from .validation import (fail, integer, text, valid_date, valid_question_id, valid_session_id,
                         valid_timezone, validate_journal, validate_session)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def locked(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with workspace_lock(self.root):
            self._config()
            return method(self, *args, **kwargs)
    return wrapped


class Engine:
    def __init__(self, workspace):
        self.root = Path(workspace).expanduser().resolve()

    def initialize(self, timezone_name):
        valid_timezone(timezone_name)
        self.root.mkdir(parents=True, exist_ok=True)
        with workspace_lock(self.root):
            config_path = self.root / "config.json"
            if config_path.exists():
                config = self._config()
                if config["timezone"] != timezone_name:
                    fail("工作空间已初始化为另一个时区。请选择新工作空间，避免改变既有日期语义。", "workspace_exists")
            else:
                if any((self.root / name).exists() for name in ("sessions", "journals", "inputs")):
                    fail("目录包含已有数据但缺少配置，拒绝重新初始化。", "workspace_exists")
                config = {"schema_version": SCHEMA_VERSION, "timezone": timezone_name, "created_at": now_utc()}
                write_json(config_path, config)
            for name in ("sessions", "journals", "inputs"):
                (self.root / name).mkdir(exist_ok=True)
            return {"workspace": str(self.root), "timezone": config["timezone"]}

    def _config(self):
        try:
            config = read_json(self.root / "config.json")
        except FileNotFoundError:
            fail("工作空间未初始化，请先执行 init --timezone <用户时区>。", "workspace_not_initialized")
        if not isinstance(config, dict) or config.get("schema_version") != SCHEMA_VERSION:
            fail("工作空间配置格式不受支持。", "invalid_workspace")
        valid_timezone(config.get("timezone"))
        return config

    def _path(self, session_id):
        valid_session_id(session_id)
        path = self.root / "sessions" / f"{session_id}.json"
        if path.resolve().parent != (self.root / "sessions").resolve():
            fail("会话文件路径越界。")
        return path

    def _load(self, session_id=None):
        if session_id is None:
            sessions = [validate_session(read_json(path)) for path in (self.root / "sessions").glob("*.json")]
            candidates = [s for s in sessions if s["status"] != "completed"] or sessions
            if not candidates:
                fail("没有会话，请先执行 start。", "session_not_found")
            session = max(candidates, key=lambda s: (s["updated_at"], s["session_id"]))
        else:
            try:
                session = validate_session(read_json(self._path(session_id)))
            except FileNotFoundError:
                fail("指定会话不存在。", "session_not_found")
        if session_id is not None and session["session_id"] != session_id:
            fail("会话文件名与内容编号不一致。", "invalid_session")
        return session

    def _persist(self, session, *, content_changed=False):
        session["current_question"] = next((q["number"] for q in session["questions"] if q["status"] == "pending"), None)
        session["revision"] += 1
        if content_changed:
            session["content_revision"] += 1
        session["updated_at"] = now_utc()
        validate_session(session)
        write_json(self._path(session["session_id"]), session)

    def _view(self, session, transcript=False):
        number = session["current_question"]
        q = session["questions"][number - 1] if number else None
        ready = number is None and session["status"] != "completed"
        result = {
            "workspace": str(self.root), "session_id": session["session_id"],
            "date": session["date"], "timezone": session["timezone"],
            "status": session["status"], "revision": session["revision"],
            "content_revision": session["content_revision"],
            "answered": sum(q["status"] == "answered" for q in session["questions"]),
            "skipped": sum(q["status"] == "skipped" for q in session["questions"]),
            "current_question": copy.deepcopy(q), "ready_to_save": ready,
            "summary_stale": session["journal_payload"] is not None and session["journal_payload"]["content_revision"] != session["content_revision"],
            "next_action": "generate_summary_and_save" if ready else (
                "resume" if session["status"] == "paused" else (
                    "finished" if session["status"] == "completed" else (
                        "generate_and_record_question" if q and q["text"] is None else "ask_current_question"))),
            "latest_journal": str(self.root / session["exports"][-1]["path"]) if session["exports"] else None,
        }
        if transcript:
            result["session"] = copy.deepcopy(session)
        return result

    def _active(self, session):
        if session["status"] != "active":
            fail("会话未处于采访状态；暂停后请先 resume，已完成记录可用 edit 修正。", "inactive_session")

    def _pending(self, session):
        self._active(session)
        if session["current_question"] is None:
            fail("20 题已经完成，请生成总结并执行 save。", "interview_finished")
        return session["questions"][session["current_question"] - 1]

    @locked
    def start(self, date_value=None, synthetic=False):
        config = self._config()
        local_date = date_value or datetime.now(ZoneInfo(config["timezone"])).date().isoformat()
        valid_date(local_date)
        if type(synthetic) is not bool:
            fail("synthetic 必须是布尔值。")
        timestamp = now_utc()
        session = {
            "schema_version": SCHEMA_VERSION, "session_id": uuid.uuid4().hex,
            "date": local_date, "timezone": config["timezone"],
            "created_at": timestamp, "updated_at": timestamp,
            "status": "active", "revision": 1, "content_revision": 0,
            "current_question": 1, "synthetic": synthetic,
            "questions": [{"id": f"q{n:02d}", "number": n, "round": "basic" if n <= 10 else "deep",
                           "text": BASIC_QUESTIONS[n - 1] if n <= 10 else None,
                           "status": "pending", "answer": None} for n in range(1, 21)],
            "journal_payload": None, "exports": [],
        }
        validate_session(session)
        atomic_write(self._path(session["session_id"]), json.dumps(session, ensure_ascii=False, indent=2) + "\n", replace=False)
        return self._view(session)

    @locked
    def status(self, session_id=None):
        return self._view(self._load(session_id), transcript=True)

    @locked
    def list_sessions(self):
        sessions = [validate_session(read_json(path)) for path in (self.root / "sessions").glob("*.json")]
        return {"sessions": [self._view(s) for s in sorted(sessions, key=lambda s: s["updated_at"], reverse=True)]}

    @locked
    def record_question(self, payload, session_id=None):
        if not isinstance(payload, dict) or set(payload) != {"question_id", "text"}:
            fail("question 输入必须且只能包含 question_id、text。")
        qid = valid_question_id(payload["question_id"])
        proposed = text(payload["text"], "问题")
        session = self._load(session_id)
        q = session["questions"][int(qid[1:]) - 1]
        if q["text"] is not None:
            if q["text"] != proposed:
                fail("当前问题已保存，不能重新生成；请沿用原问题。", "question_exists")
            return self._view(session)
        if self._pending(session)["id"] != qid:
            fail("输入题号不是当前题目，请读取最新进度。", "stale_question")
        if any(other["text"] == proposed for other in session["questions"]):
            fail("深入问题与已有问题完全重复，请生成新的问题。")
        q["text"] = proposed
        self._persist(session, content_changed=True)
        return self._view(session)

    @locked
    def answer(self, payload, session_id=None):
        if not isinstance(payload, dict) or set(payload) != {"question_id", "answer"}:
            fail("answer 输入必须且只能包含 question_id、answer。")
        qid = valid_question_id(payload["question_id"])
        value = text(payload["answer"], "回答")
        session = self._load(session_id)
        target = session["questions"][int(qid[1:]) - 1]
        if target["status"] == "answered" and target["answer"] == value:
            return {**self._view(session), "idempotent": True}
        q = self._pending(session)
        if q["id"] != qid:
            fail("输入题号不是当前题目；已回答题目的修正请用 edit。", "stale_question")
        if q["text"] is None:
            fail("请先保存深入问题，再记录回答。", "question_not_recorded")
        q.update(status="answered", answer=value)
        self._persist(session, content_changed=True)
        return {**self._view(session), "idempotent": False}

    @locked
    def skip(self, session_id=None, question_id=None):
        qid = valid_question_id(question_id)
        session = self._load(session_id)
        target = session["questions"][int(qid[1:]) - 1]
        if target["status"] == "skipped":
            return {**self._view(session), "idempotent": True}
        q = self._pending(session)
        if q["id"] != qid:
            fail("输入题号不是当前题目，请读取最新进度。", "stale_question")
        if q["text"] is None:
            fail("请先保存当前问题，再执行跳过。", "question_not_recorded")
        q.update(status="skipped", answer=None)
        self._persist(session, content_changed=True)
        return {**self._view(session), "idempotent": False}

    @locked
    def edit(self, number, payload, session_id=None):
        integer(number, "题号", 1)
        if number > 20:
            fail("题号必须在 1–20 之间。")
        if not isinstance(payload, dict) or set(payload) != {"answer"}:
            fail("edit 输入必须且只能包含 answer。")
        value = text(payload["answer"], "修正后的回答")
        session = self._load(session_id)
        q = session["questions"][number - 1]
        if q["status"] == "pending":
            fail("不能修改尚未回答的问题；请按顺序采访。")
        if q["status"] == "answered" and q["answer"] == value:
            return self._view(session)
        q.update(status="answered", answer=value)
        if session["status"] == "completed":
            session["status"] = "active"
        self._persist(session, content_changed=True)
        return self._view(session)

    @locked
    def pause(self, session_id=None):
        session = self._load(session_id)
        if session["status"] == "completed":
            fail("记录已完成，不能暂停；可使用 edit 修正。", "inactive_session")
        if session["status"] != "paused":
            session["status"] = "paused"
            self._persist(session)
        return self._view(session)

    @locked
    def resume(self, session_id=None):
        session = self._load(session_id)
        if session["status"] == "completed":
            fail("记录已完成，可用 status 查看或用 edit 修正。", "inactive_session")
        if session["status"] == "paused":
            session["status"] = "active"
            self._persist(session)
        return self._view(session, transcript=True)

    @locked
    def save(self, payload=None, session_id=None):
        session = self._load(session_id)
        if payload is None:
            if session["journal_payload"] is None:
                fail("尚无总结。AI 需要读取回答并提供 save 输入。", "summary_required")
            payload = session["journal_payload"]
        payload = validate_journal(payload, session)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        complete = session["current_question"] is None
        if session["exports"] and session["exports"][-1]["payload_hash"] == payload_hash:
            record = session["exports"][-1]
            path = self.root / record["path"]
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                fail("已导出的文件被修改或删除；保留现有文件，请检查后再生成新版本。", "export_changed")
            target_status = "completed" if complete else "paused"
            if session["status"] != target_status:
                session["status"] = target_status
                self._persist(session)
            return {**self._view(session), "journal_path": str(path), "journal_version": record["version"], "idempotent": True}
        version = len(session["exports"]) + 1
        filename = f"{session['date']}--{session['session_id']}--v{version}.md"
        path = self.root / "journals" / filename
        content = render_journal(session, payload, version)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if path.exists():
            if path.read_bytes() != content.encode("utf-8"):
                fail("目标日记文件已存在且内容不同，拒绝覆盖。", "export_conflict")
        else:
            atomic_write(path, content, replace=False)
        record = {"version": version, "path": "journals/" + filename, "sha256": digest,
                  "payload_hash": payload_hash, "content_revision": session["content_revision"], "complete": complete}
        session["exports"].append(record)
        session["journal_payload"] = payload
        session["status"] = "completed" if complete else "paused"
        # The journal is deterministic: if this write fails, retry can reuse the intact file.
        self._persist(session)
        return {**self._view(session), "journal_path": str(path), "journal_version": version, "idempotent": False}
