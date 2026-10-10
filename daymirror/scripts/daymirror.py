#!/usr/bin/env python3
"""Run with: python -X utf8 daymirror/scripts/daymirror.py --help"""

import json
import sys


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        from daymirror_core.cli import main
    except ModuleNotFoundError as exc:
        print(json.dumps({"ok": False, "error": {"code": "missing_dependency", "message":
            f"缺少依赖 {exc.name}。请安装 daymirror/requirements.txt 中的依赖。"}}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
    sys.exit(main())
