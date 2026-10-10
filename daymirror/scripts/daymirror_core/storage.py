"""UTF-8 files, atomic writes, and short OS locks released on process exit."""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .errors import DayMirrorError


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise DayMirrorError("invalid_json", "JSON 文件无法解析；保留原文件。") from exc


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def atomic_write(path, content, *, replace=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".daymirror-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # A link publishes a fully written file while refusing an existing destination.
            os.link(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def write_json(path, value):
    atomic_write(path, json_text(value))


@contextmanager
def workspace_lock(root):
    """One-byte file lock. The lock file stays in place to avoid unlink races."""
    root = Path(root)
    if not root.is_dir():
        raise DayMirrorError("workspace_not_initialized", "工作空间不存在，请先执行 init。")
    lock_path = root / ".daymirror.lock"
    with lock_path.open("a+b") as stream:
        try:
            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DayMirrorError("workspace_busy", "另一个进程正在读写工作空间，请稍后重试。") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
