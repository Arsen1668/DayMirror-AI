import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .engine import Engine
from .errors import DayMirrorError
from .validation import fail

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKSPACE = PROJECT_ROOT / "private" / "workspace"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise DayMirrorError("invalid_arguments", message)


def build_parser():
    parser = Parser(description="DayMirror v0.1：本地进度与日记工具；真实 AI 采访由客户端执行。")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    for command in ("init", "start", "status", "list", "question", "answer", "skip", "edit", "pause", "resume", "save", "demo"):
        p = sub.add_parser(command)
        p.add_argument("--workspace", default=None if command == "demo" else str(DEFAULT_WORKSPACE), help="本地数据目录")
        if command not in {"init", "start", "list", "demo"}:
            p.add_argument("--session", help="不指定时选择最近的未完成会话，或最近的完整会话")
        if command == "init":
            p.add_argument("--timezone", required=True, help="IANA 时区，例如 Asia/Shanghai")
        if command == "start":
            p.add_argument("--date", help="YYYY-MM-DD；不指定时使用工作空间时区的当天日期")
            p.add_argument("--synthetic", action="store_true", help="仅用于明确的合成示例")
        if command in {"question", "answer", "edit", "save"}:
            p.add_argument("--input", required=command != "save", help="UTF-8 JSON 文件；- 表示标准输入")
        if command == "edit":
            p.add_argument("--number", type=int, required=True, help="需要修正的题号，1–20")
        if command == "skip":
            p.add_argument("--question", required=True, help="当前问题编号，例如 q01；重复请求不会推进下一题")
    return parser


def load_payload(source):
    if source is None:
        return None
    if source == "-":
        if sys.stdin.isatty():
            fail("请通过标准输入提供 JSON，或使用 --input <文件>。")
        raw = sys.stdin.read()
    else:
        raw = Path(source).read_text(encoding="utf-8-sig")
    try:
        def invalid_constant(value):
            raise ValueError(value)
        return json.loads(raw.lstrip("\ufeff"), parse_constant=invalid_constant)
    except (json.JSONDecodeError, ValueError):
        fail("输入必须是有效 JSON，不能包含 NaN 或 Infinity。", "invalid_json")


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        if args.command == "demo":
            from .demo import run_demo
            result = run_demo(args.workspace)
        else:
            engine = Engine(args.workspace)
            command = args.command
            session = getattr(args, "session", None)
            if command == "init":
                result = engine.initialize(args.timezone)
            elif command == "start":
                result = engine.start(args.date, args.synthetic)
            elif command == "list":
                result = engine.list_sessions()
            elif command in {"status", "pause", "resume"}:
                result = getattr(engine, command)(session)
            elif command == "skip":
                result = engine.skip(session, args.question)
            elif command == "question":
                result = engine.record_question(load_payload(args.input), session)
            elif command == "answer":
                result = engine.answer(load_payload(args.input), session)
            elif command == "edit":
                result = engine.edit(args.number, load_payload(args.input), session)
            elif command == "save":
                result = engine.save(load_payload(args.input), session)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, allow_nan=False))
        return 0
    except DayMirrorError as exc:
        error = {"code": exc.code, "message": exc.message}
    except (OSError, UnicodeError) as exc:
        error = {"code": "io_error", "message": f"文件操作失败；保留原记录。原因：{exc}"}
    print(json.dumps({"ok": False, "error": error}, ensure_ascii=False), file=sys.stderr)
    return 2
