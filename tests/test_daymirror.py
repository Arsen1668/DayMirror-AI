import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "daymirror" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from daymirror_core.engine import Engine
from daymirror_core.errors import DayMirrorError
from daymirror_core.storage import read_json, write_json

FIXTURE = read_json(ROOT / "daymirror" / "assets" / "demo_fixture.json")
TEMPLATE = read_json(ROOT / "daymirror" / "assets" / "journal_input_template.json")


def frontmatter(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8").split("---", 2)[1])


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.work = (ROOT / "work" / "tests").resolve()
        self.work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.work)
        self.directory = Path(self.temp.name).resolve()
        self.assertTrue(self.directory.is_relative_to(self.work))
        self.workspace = self.directory / "workspace"
        self.engine = Engine(self.workspace)
        self.engine.initialize("Asia/Shanghai")
        self.state = self.engine.start("2026-10-10", synthetic=True)
        self.sid = self.state["session_id"]

    def tearDown(self):
        # Check the absolute target before TemporaryDirectory recursively removes it.
        if not self.directory.is_relative_to(self.work):
            raise RuntimeError("Unsafe cleanup target")
        self.temp.cleanup()

    def session(self):
        return self.engine.status(self.sid)["session"]

    def empty_payload(self):
        payload = copy.deepcopy(TEMPLATE)
        payload["content_revision"] = self.session()["content_revision"]
        return payload

    def answer(self, payload, session_id=None):
        session_id = session_id or self.sid
        question = self.engine.status(session_id)["current_question"]
        return self.engine.answer({"question_id": question["id"], **payload}, session_id)

    def skip(self, session_id=None):
        session_id = session_id or self.sid
        question = self.engine.status(session_id)["current_question"]
        return self.engine.skip(session_id, question["id"])

    def question(self, payload, session_id=None):
        session_id = session_id or self.sid
        question = self.engine.status(session_id)["current_question"]
        return self.engine.record_question({"question_id": question["id"], **payload}, session_id)

    def finish(self):
        for number in range(self.session()["current_question"] or 21, 21):
            if number > 10:
                self.question({"text": FIXTURE["deep_questions"][number - 11]}, self.sid)
            value = FIXTURE["answers"][f"q{number:02d}"]
            if value is None:
                self.state = self.skip(self.sid)
            else:
                self.state = self.answer({"answer": value}, self.sid)
        payload = copy.deepcopy(FIXTURE["journal"])
        payload["content_revision"] = self.state["content_revision"]
        return payload

    def cli(self, command, *extra, payload=None, expect=0):
        if command == "answer" and payload is not None and "question_id" not in payload:
            payload = {"question_id": self.engine.status(self.sid)["current_question"]["id"], **payload}
        invocation = [sys.executable, "-X", "utf8", str(SCRIPTS / "daymirror.py"), command,
                      "--workspace", str(self.workspace), *extra]
        if payload is not None:
            invocation += ["--input", "-"]
        completed = subprocess.run(invocation, input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                                   capture_output=True, encoding="utf-8", cwd=ROOT, timeout=30)
        self.assertEqual(completed.returncode, expect, completed.stderr)
        return json.loads(completed.stdout if expect == 0 else completed.stderr)


class InterviewTests(WorkspaceTest):
    def test_full_interview_and_structured_journal(self):
        payload = self.finish()
        self.assertTrue(self.state["ready_to_save"])
        self.assertEqual(self.state["next_action"], "generate_summary_and_save")
        saved = self.engine.save(payload, self.sid)
        self.assertEqual(saved["status"], "completed")
        metadata = frontmatter(saved["journal_path"])
        self.assertTrue(metadata["interview_complete"])
        self.assertEqual((metadata["answered_questions"], metadata["skipped_questions"]), (18, 2))
        self.assertIsNone(metadata["stress"])
        self.assertEqual(metadata["metric_sources"]["stress"], [])
        self.assertEqual(metadata["focus_minutes"], 90)
        journal = Path(saved["journal_path"]).read_text(encoding="utf-8")
        for qid, answer in FIXTURE["answers"].items():
            self.assertIn(qid, journal)
            if answer is not None:
                self.assertIn(answer, journal)
        self.assertIn("AI 假设，待验证", journal)
        self.assertIn("AI 建议", journal)
        self.assertIn("用户表达的行动意向", journal)

    def test_resume_in_new_process_preserves_transcript(self):
        for number in range(1, 4):
            self.cli("answer", "--session", self.sid, payload={"answer": FIXTURE["answers"][f"q{number:02d}"]})
        self.cli("pause", "--session", self.sid)
        before = self.session()
        restored = self.cli("resume", "--session", self.sid)["result"]
        self.assertEqual(restored["current_question"]["number"], 4)
        self.assertEqual(restored["session"]["questions"], before["questions"])
        self.assertEqual(restored["date"], "2026-10-10")
        self.assertEqual(restored["status"], "active")

    def test_close_without_pause_is_recoverable(self):
        self.answer({"answer": "写了提纲。"}, self.sid)
        restored = Engine(self.workspace).resume(self.sid)
        self.assertEqual(restored["current_question"]["number"], 2)
        self.assertEqual(restored["session"]["questions"][0]["answer"], "写了提纲。")

    def test_deep_pending_question_survives_resume(self):
        for _ in range(10):
            self.skip(self.sid)
        question = "你想深入回顾哪一个具体时刻？"
        self.question({"text": question}, self.sid)
        self.engine.pause(self.sid)
        restored = Engine(self.workspace).resume(self.sid)
        self.assertEqual(restored["current_question"]["number"], 11)
        self.assertEqual(restored["current_question"]["text"], question)
        with self.assertRaises(DayMirrorError):
            self.question({"text": "替换问题"}, self.sid)

    def test_skip_stays_null(self):
        self.skip(self.sid)
        q = self.session()["questions"][0]
        self.assertEqual(q["status"], "skipped")
        self.assertIsNone(q["answer"])
        self.assertEqual(self.session()["current_question"], 2)

    def test_partial_save_can_resume_and_retains_nulls(self):
        self.answer({"answer": "今天很累，但没有给任何评分。"}, self.sid)
        saved = self.engine.save(self.empty_payload(), self.sid)
        metadata = frontmatter(saved["journal_path"])
        self.assertFalse(metadata["interview_complete"])
        self.assertEqual(metadata["pending_questions"], 19)
        self.assertEqual(saved["status"], "paused")
        for metric in TEMPLATE["metrics"]:
            self.assertIsNone(metadata[metric])
        restored = self.engine.resume(self.sid)
        self.assertEqual(restored["current_question"]["number"], 2)

    def test_zero_answers_does_not_create_content(self):
        saved = self.engine.save(self.empty_payload(), self.sid)
        metadata = frontmatter(saved["journal_path"])
        self.assertEqual(metadata["answered_questions"], 0)
        self.assertFalse(metadata["interview_complete"])
        self.assertIn("暂无足够回答生成概览", Path(saved["journal_path"]).read_text(encoding="utf-8"))

    def test_partial_to_complete_keeps_partial_version(self):
        self.answer({"answer": FIXTURE["answers"]["q01"]}, self.sid)
        partial = self.engine.save(self.empty_payload(), self.sid)
        before = Path(partial["journal_path"]).read_bytes()
        self.engine.resume(self.sid)
        complete = self.engine.save(self.finish(), self.sid)
        self.assertTrue(frontmatter(complete["journal_path"])["interview_complete"])
        self.assertFalse(frontmatter(partial["journal_path"])["interview_complete"])
        self.assertEqual(Path(partial["journal_path"]).read_bytes(), before)
        self.assertEqual(complete["journal_version"], 2)

    def test_repeated_partial_save_pauses_resumed_session(self):
        first = self.engine.save(self.empty_payload(), self.sid)
        self.engine.resume(self.sid)
        second = self.engine.save(session_id=self.sid)
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["status"], "paused")
        self.assertEqual(second["journal_path"], first["journal_path"])

    def test_all_skipped_is_complete_but_empty(self):
        for number in range(1, 21):
            if number > 10:
                self.question({"text": f"合成测试深入问题 {number}"}, self.sid)
            self.skip(self.sid)
        saved = self.engine.save(self.empty_payload(), self.sid)
        metadata = frontmatter(saved["journal_path"])
        self.assertTrue(metadata["interview_complete"])
        self.assertEqual(metadata["answered_questions"], 0)
        self.assertEqual(metadata["skipped_questions"], 20)
        self.assertTrue(all(metadata[key] is None for key in TEMPLATE["metrics"]))

    def test_edit_updates_summary_and_keeps_old_version(self):
        payload = self.finish()
        first = self.engine.save(payload, self.sid)
        old = Path(first["journal_path"]).read_bytes()
        self.engine.edit(4, {"answer": "修正：上午连续深度专注60分钟。"}, self.sid)
        with self.assertRaises(DayMirrorError) as caught:
            self.engine.save(payload, self.sid)
        self.assertEqual(caught.exception.code, "stale_summary")
        payload["content_revision"] = self.session()["content_revision"]
        payload["metrics"]["focus_minutes"] = 60
        payload["summary"]["events"][0]["text"] = "上午连续深度专注60分钟。"
        second = self.engine.save(payload, self.sid)
        self.assertNotEqual(first["journal_path"], second["journal_path"])
        self.assertEqual(Path(first["journal_path"]).read_bytes(), old)
        self.assertEqual(frontmatter(second["journal_path"])["focus_minutes"], 60)
        self.assertEqual(second["journal_version"], 2)

    def test_edit_base_after_deep_answers_preserves_deep_transcript(self):
        self.finish()
        before = copy.deepcopy(self.session()["questions"][10:])
        self.engine.edit(1, {"answer": "补充：还进行了整理。"}, self.sid)
        self.assertEqual(self.session()["questions"][10:], before)

    def test_repeated_save_is_idempotent(self):
        saved = self.engine.save(self.finish(), self.sid)
        first = Path(saved["journal_path"]).stat().st_mtime_ns
        again = self.engine.save(session_id=self.sid)
        self.assertTrue(again["idempotent"])
        self.assertEqual(saved["journal_path"], again["journal_path"])
        self.assertEqual(Path(saved["journal_path"]).stat().st_mtime_ns, first)
        self.assertEqual(len(list((self.workspace / "journals").glob("*.md"))), 1)

    def test_same_day_sessions_do_not_overwrite(self):
        second = self.engine.start("2026-10-10", synthetic=True)
        self.assertNotEqual(second["session_id"], self.sid)
        self.assertEqual(len(list((self.workspace / "sessions").glob("*.json"))), 2)
        self.assertEqual(self.engine.resume()["session_id"], second["session_id"])

    def test_timezone_date_and_resume_keeps_date(self):
        from datetime import datetime, timezone
        fixed = datetime(2026, 10, 9, 18, 30, tzinfo=timezone.utc)
        with patch("daymirror_core.engine.datetime") as mocked:
            mocked.now.side_effect = lambda tz=None: fixed.astimezone(tz) if tz else fixed
            state = self.engine.start(synthetic=True)
        self.assertEqual(state["date"], "2026-10-10")
        self.engine.pause(state["session_id"])
        self.assertEqual(self.engine.resume(state["session_id"])["date"], "2026-10-10")

    def test_chinese_multiline_and_backticks_preserved(self):
        value = "中文换行\n```python\nprint('你好')\n```\n---\n# 这是原话，不是新章节"
        self.answer({"answer": value}, self.sid)
        saved = self.engine.save(self.empty_payload(), self.sid)
        content = Path(saved["journal_path"]).read_text(encoding="utf-8")
        self.assertIn(value, content)
        self.assertIn("````text", content)
        self.assertEqual(frontmatter(saved["journal_path"])["date"], "2026-10-10")


class ValidationTests(WorkspaceTest):
    def test_invalid_dates_and_timezones_rejected(self):
        for value in ("2026-02-30", "20261010", "../../file", "2026-13-01"):
            with self.subTest(value=value), self.assertRaises(DayMirrorError):
                self.engine.start(value)
        with self.assertRaises(DayMirrorError):
            Engine(self.directory / "other").initialize("Not/AZone")
        self.assertEqual(len(list((self.workspace / "sessions").glob("*.json"))), 1)

    def test_invalid_metrics_rejected_without_export(self):
        self.answer({"answer": "情绪7分，计划3项，完成2项。"}, self.sid)
        for key, value in (("mood", 11), ("mood", 0), ("mood", 7.5), ("energy", True),
                           ("planned_tasks", -1), ("planned_tasks", 2.5),
                           ("sleep_hours", 25), ("focus_minutes", -1), ("stress", float("nan")),
                           ("exercise_minutes", float("inf"))):
            payload = self.empty_payload()
            payload["metrics"][key] = value
            payload["metric_sources"][key] = ["q01"]
            with self.subTest(key=key, value=value), self.assertRaises(DayMirrorError):
                self.engine.save(payload, self.sid)
        self.assertEqual(list((self.workspace / "journals").glob("*.md")), [])

    def test_completed_cannot_exceed_planned(self):
        self.answer({"answer": "任务说明。"}, self.sid)
        payload = self.empty_payload()
        payload["metrics"].update(planned_tasks=2, completed_tasks=3)
        payload["metric_sources"].update(planned_tasks=["q01"], completed_tasks=["q01"])
        with self.assertRaises(DayMirrorError):
            self.engine.save(payload, self.sid)

    def test_source_must_refer_to_answered_question(self):
        self.answer({"answer": "情绪7分。"}, self.sid)
        self.skip(self.sid)
        for sources in ([], ["q02"], ["q03"], ["q99"], ["q01", "q01"]):
            payload = self.empty_payload()
            payload["metrics"]["mood"] = 7
            payload["metric_sources"]["mood"] = sources
            with self.subTest(sources=sources), self.assertRaises(DayMirrorError):
                self.engine.save(payload, self.sid)

    def test_null_must_have_no_sources(self):
        self.answer({"answer": "没有评分。"}, self.sid)
        payload = self.empty_payload()
        payload["metric_sources"]["mood"] = ["q01"]
        with self.assertRaises(DayMirrorError):
            self.engine.save(payload, self.sid)

    def test_summary_and_action_kind_and_evidence_required(self):
        self.answer({"answer": "写了报告。"}, self.sid)
        cases = [
            {"text": "写了报告", "kind": "reported_fact", "source_questions": []},
            {"text": "感觉不错", "kind": "fact", "source_questions": ["q01"]},
            {"text": "猜测", "kind": [], "source_questions": ["q01"]},
        ]
        for item in cases:
            payload = self.empty_payload()
            payload["summary"]["overview"] = item
            with self.subTest(item=item), self.assertRaises(DayMirrorError):
                self.engine.save(payload, self.sid)
        payload = self.empty_payload()
        payload["summary"]["actions"] = [{"text": "行动", "kind": "reported_fact", "source_questions": ["q01"]}]
        with self.assertRaises(DayMirrorError):
            self.engine.save(payload, self.sid)

    def test_deep_question_must_be_recorded_before_answer(self):
        for _ in range(10):
            self.skip(self.sid)
        with self.assertRaises(DayMirrorError):
            self.answer({"answer": "回答"}, self.sid)
        with self.assertRaises(DayMirrorError):
            self.skip(self.sid)
        self.assertEqual(self.session()["current_question"], 11)

    def test_paused_session_requires_resume_before_answer(self):
        self.engine.pause(self.sid)
        with self.assertRaises(DayMirrorError):
            self.answer({"answer": "不能直接回答"}, self.sid)
        self.assertEqual(self.session()["current_question"], 1)

    def test_future_question_edit_and_traversal_rejected(self):
        for number in (0, 21, 1):
            with self.subTest(number=number), self.assertRaises(DayMirrorError):
                self.engine.edit(number, {"answer": "不应更新"}, self.sid)
        with self.assertRaises(DayMirrorError):
            self.engine.status("../../other")

    def test_unknown_schema_and_corrupt_json_not_reset(self):
        path = self.workspace / "sessions" / (self.sid + ".json")
        value = read_json(path)
        value["schema_version"] = 99
        write_json(path, value)
        before = path.read_bytes()
        with self.assertRaises(DayMirrorError):
            self.engine.resume(self.sid)
        self.assertEqual(path.read_bytes(), before)
        path.write_text("{坏 JSON", encoding="utf-8")
        with self.assertRaises(DayMirrorError):
            self.engine.resume(self.sid)
        self.assertEqual(path.read_text(encoding="utf-8"), "{坏 JSON")

    def test_fractional_minutes_are_not_rounded(self):
        self.answer({"answer": "专注了30秒。"}, self.sid)
        payload = self.empty_payload()
        payload["metrics"]["focus_minutes"] = 0.5
        payload["metric_sources"]["focus_minutes"] = ["q01"]
        saved = self.engine.save(payload, self.sid)
        self.assertEqual(frontmatter(saved["journal_path"])["focus_minutes"], 0.5)

    def test_cli_errors_are_json(self):
        result = self.cli("edit", "--number", "99", "--session", self.sid, payload={"answer": "答案"}, expect=2)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_input")

    def test_initialization_is_idempotent_and_preserves_timezone(self):
        self.engine.initialize("Asia/Shanghai")
        self.assertEqual(self.session()["session_id"], self.sid)
        with self.assertRaises(DayMirrorError):
            self.engine.initialize("UTC")
        self.assertEqual(read_json(self.workspace / "config.json")["timezone"], "Asia/Shanghai")

    def test_corrupt_export_path_is_not_followed(self):
        self.engine.save(self.finish(), self.sid)
        path = self.workspace / "sessions" / (self.sid + ".json")
        session = read_json(path)
        session["exports"][0]["path"] = "../../other.md"
        write_json(path, session)
        before = path.read_bytes()
        with self.assertRaises(DayMirrorError):
            self.engine.save(session_id=self.sid)
        self.assertEqual(path.read_bytes(), before)


class ReliabilityTests(WorkspaceTest):
    def test_repeated_answer_does_not_advance_another_question(self):
        payload = {"question_id": "q01", "answer": "合成回答。"}
        first = self.engine.answer(payload, self.sid)
        second = self.engine.answer(payload, self.sid)
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["revision"], first["revision"])
        self.assertEqual(second["current_question"]["number"], 2)
        self.assertEqual(second["answered"], 1)

    def test_repeated_skip_does_not_skip_another_question(self):
        first = self.engine.skip(self.sid, "q01")
        second = self.engine.skip(self.sid, "q01")
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["revision"], first["revision"])
        self.assertEqual(second["current_question"]["number"], 2)
        self.assertEqual(second["skipped"], 1)

    def test_repeated_question_is_not_attached_to_next_slot(self):
        for _ in range(10):
            self.skip(self.sid)
        payload = {"question_id": "q11", "text": "合成深入问题。"}
        self.engine.record_question(payload, self.sid)
        self.engine.answer({"question_id": "q11", "answer": "合成回答。"}, self.sid)
        repeated = self.engine.record_question(payload, self.sid)
        self.assertEqual(repeated["current_question"]["number"], 12)
        self.assertIsNone(repeated["current_question"]["text"])

    def test_wrong_question_identity_rejected_without_progress_change(self):
        with self.assertRaises(DayMirrorError) as caught:
            self.engine.answer({"question_id": "q02", "answer": "不能写到未来题目"}, self.sid)
        self.assertEqual(caught.exception.code, "stale_question")
        self.assertEqual(self.session()["current_question"], 1)

    def test_failed_answer_write_keeps_original_file(self):
        path = self.workspace / "sessions" / (self.sid + ".json")
        before = path.read_bytes()
        with patch("daymirror_core.engine.write_json", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                self.answer({"answer": "不应持久化"}, self.sid)
        self.assertEqual(path.read_bytes(), before)

    def test_atomic_replace_failure_preserves_original_and_cleans_temp(self):
        path = self.workspace / "sessions" / (self.sid + ".json")
        before = path.read_bytes()
        with patch("daymirror_core.storage.os.replace", side_effect=OSError("synthetic rename failure")):
            with self.assertRaises(OSError):
                self.answer({"answer": "不应持久化"}, self.sid)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(path.parent.glob(".daymirror-*.tmp")), [])

    def test_journal_write_failure_keeps_prior_export(self):
        payload = self.finish()
        saved = self.engine.save(payload, self.sid)
        before = Path(saved["journal_path"]).read_bytes()
        payload["tags"] = ["修改后的标签"]
        with patch("daymirror_core.engine.atomic_write", side_effect=OSError("synthetic export failure")):
            with self.assertRaises(OSError):
                self.engine.save(payload, self.sid)
        self.assertEqual(Path(saved["journal_path"]).read_bytes(), before)
        self.assertEqual(len(self.session()["exports"]), 1)

    def test_export_then_session_failure_is_retryable(self):
        payload = self.finish()
        path = self.workspace / "sessions" / (self.sid + ".json")
        before = path.read_bytes()
        with patch("daymirror_core.engine.write_json", side_effect=OSError("synthetic state failure")):
            with self.assertRaises(OSError):
                self.engine.save(payload, self.sid)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(list((self.workspace / "journals").glob("*.md"))), 1)
        saved = self.engine.save(payload, self.sid)
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(len(list((self.workspace / "journals").glob("*.md"))), 1)

    def test_manual_edit_is_not_overwritten(self):
        saved = self.engine.save(self.finish(), self.sid)
        path = Path(saved["journal_path"])
        path.write_text(path.read_text(encoding="utf-8") + "\n手工补充。\n", encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(DayMirrorError) as caught:
            self.engine.save(session_id=self.sid)
        self.assertEqual(caught.exception.code, "export_changed")
        self.assertEqual(path.read_bytes(), before)

    def test_process_lock_blocks_other_writes_and_releases(self):
        code = "import sys; sys.path.insert(0, sys.argv[1]); from daymirror_core.storage import workspace_lock; lock=workspace_lock(sys.argv[2]); lock.__enter__(); print('LOCKED', flush=True); sys.stdin.read(); lock.__exit__(None,None,None)"
        process = subprocess.Popen([sys.executable, "-X", "utf8", "-c", code, str(SCRIPTS), str(self.workspace)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", cwd=ROOT)
        try:
            self.assertEqual(process.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(DayMirrorError) as caught:
                self.answer({"answer": "应被阻止"}, self.sid)
            self.assertEqual(caught.exception.code, "workspace_busy")
            process.communicate("release", timeout=10)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        self.assertEqual(self.answer({"answer": "锁已释放"}, self.sid)["answered"], 1)


if __name__ == "__main__":
    unittest.main()
