"""An explicitly synthetic replay using a fresh Python process for every step."""

import copy
import json
import subprocess
import sys
import uuid
from pathlib import Path

from .errors import DayMirrorError
from .storage import read_json


def run_demo(workspace=None):
    skill_root = Path(__file__).resolve().parents[2]
    project_root = skill_root.parent
    target = Path(workspace).resolve() if workspace else project_root / "work" / "demo" / uuid.uuid4().hex
    if target.exists() and any(target.iterdir()):
        raise DayMirrorError("demo_workspace_exists", "演示需要全新的空目录，以免混入已有日记。")
    fixture = read_json(skill_root / "assets" / "demo_fixture.json")
    if fixture.get("synthetic") is not True:
        raise DayMirrorError("invalid_fixture", "演示数据必须明确标记为 synthetic。")
    script = skill_root / "scripts" / "daymirror.py"
    pids = []

    def invoke(command, *options, payload=None):
        invocation = [sys.executable, "-X", "utf8", str(script), command, "--workspace", str(target), *options]
        if payload is not None:
            invocation += ["--input", "-"]
        process = subprocess.Popen(invocation, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, encoding="utf-8", cwd=project_root)
        pids.append(process.pid)
        try:
            output, error = process.communicate(json.dumps(payload, ensure_ascii=False) if payload is not None else None, timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise DayMirrorError("demo_failed", f"演示步骤 {command} 超时，子进程已结束。")
        if process.returncode:
            raise DayMirrorError("demo_failed", f"演示步骤 {command} 失败：{error.strip()}")
        return json.loads(output)["result"]

    invoke("init", "--timezone", "Asia/Shanghai")
    state = invoke("start", "--date", fixture["date"], "--synthetic")
    sid = state["session_id"]
    for number in range(1, 4):
        invoke("question", "--session", sid, payload={"question_id": f"q{number:02d}", "text": fixture["basic_questions"][number - 1]})
        invoke("answer", "--session", sid, payload={"question_id": f"q{number:02d}", "answer": fixture["answers"][f"q{number:02d}"]})
    invoke("question", "--session", sid, payload={"question_id": "q04", "text": fixture["basic_questions"][3]})
    before = invoke("pause", "--session", sid)
    pause_pid = pids[-1]
    snapshot = invoke("status", "--session", sid)["session"]
    restored = invoke("resume", "--session", sid)
    resume_pid = pids[-1]
    if restored["session"]["questions"] != snapshot["questions"] or restored["current_question"]["number"] != 4:
        raise DayMirrorError("demo_failed", "跨进程恢复没有保留原始问题、回答与进度。")
    for number in range(4, 21):
        if number != 4:
            question = fixture["basic_questions"][number - 1] if number <= 10 else fixture["deep_questions"][number - 11]
            invoke("question", "--session", sid, payload={"question_id": f"q{number:02d}", "text": question})
        answer = fixture["answers"][f"q{number:02d}"]
        if answer is None:
            state = invoke("skip", "--session", sid, "--question", f"q{number:02d}")
        else:
            state = invoke("answer", "--session", sid, payload={"question_id": f"q{number:02d}", "answer": answer})
    if not state["ready_to_save"]:
        raise DayMirrorError("demo_failed", "20 题完成后没有进入等待总结保存状态。")
    payload = copy.deepcopy(fixture["journal"])
    payload["content_revision"] = state["content_revision"]
    saved = invoke("save", "--session", sid, payload=payload)
    repeated = invoke("save", "--session", sid)
    if not repeated["idempotent"] or repeated["journal_path"] != saved["journal_path"]:
        raise DayMirrorError("demo_failed", "重复保存没有保持幂等。")
    return {
        "synthetic": True,
        "notice": "离线合成回放验证保存与恢复；真实两轮问题均由 AI 客户端参考回答逐题生成。",
        "steps": [
            {"phase": "采访", "answered": 3},
            {"phase": "暂停并退出进程", "status": before["status"], "next_question": 4},
            {"phase": "新进程恢复", "status": restored["status"], "next_question": 4, "transcript_preserved": True},
            {"phase": "完成并保存", "status": saved["status"], "answered": saved["answered"], "skipped": saved["skipped"]},
        ],
        "workspace": str(target), "session_id": sid, "journal_path": saved["journal_path"],
        "subprocess_count": len(pids), "pause_process_pid": pause_pid,
        "resume_process_pid": resume_pid, "repeated_save_idempotent": True,
    }
