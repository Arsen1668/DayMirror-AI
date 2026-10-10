"""Build an explicit allowlist archive; no Git, network, or user journals."""

import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.1"
RELEASE_FILES = (
    ".gitignore", "README.md", "LICENSE", "requirements.txt", "docs/v0.1-requirements.md",
    "daymirror/SKILL.md", "daymirror/LICENSE", "daymirror/requirements.txt", "daymirror/agents/openai.yaml",
    "daymirror/references/interview.md", "daymirror/references/schema.md", "daymirror/references/privacy.md",
    "daymirror/assets/demo_fixture.json", "daymirror/assets/journal_input_template.json",
    "daymirror/scripts/daymirror.py",
    *(f"daymirror/scripts/daymirror_core/{name}.py" for name in
      ("__init__", "constants", "errors", "validation", "storage", "render", "engine", "cli", "demo")),
    "tests/test_daymirror.py", "tests/test_packaging.py", "tools/__init__.py",
    "tools/validate_skill.py", "tools/package_release.py",
)
OPTIONAL_FILES = ("docs/verification.md", "daymirror/assets/example-journal.md")
FORBIDDEN_PARTS = {"private", "work", "outputs", "sessions", "journals", "inputs", "__pycache__", ".git", ".venv"}


def build_release(root=ROOT, destination=None):
    root = Path(root).resolve()
    destination = Path(destination or root / "outputs").resolve()
    if not destination.is_relative_to(root):
        raise ValueError("分发输出必须位于项目目录内。")
    names = list(RELEASE_FILES) + [name for name in OPTIONAL_FILES if (root / name).exists()]
    entries = []
    for name in names:
        source = root / name
        if set(Path(name).parts) & FORBIDDEN_PARTS or source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError(f"拒绝私密路径或符号链接：{name}")
        content = source.read_bytes()
        if name.endswith("demo_fixture.json") and json.loads(content).get("synthetic") is not True:
            raise ValueError("演示问答必须标为合成数据。")
        if name.endswith("example-journal.md"):
            frontmatter = content.decode("utf-8").split("---", 2)[1]
            if yaml.safe_load(frontmatter).get("synthetic") is not True:
                raise ValueError("示例日记必须标为合成数据。")
        entries.append((name, content))
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"daymirror-v{VERSION}.zip"
    fd, temporary = tempfile.mkstemp(prefix=".daymirror-package-", suffix=".zip", dir=destination)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as package:
            for name, content in entries:
                package.writestr(name, content)
        with zipfile.ZipFile(temporary) as package:
            if package.testzip() is not None or set(package.namelist()) != set(names):
                raise ValueError("ZIP 完整性检查失败。")
        os.replace(temporary, archive)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    manifest = {
        "version": VERSION, "archive": archive.name, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "policy": "fixed_allowlist", "private_directories_included": False,
        "files": [{"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()} for name, content in entries],
    }
    manifest_path = destination / f"daymirror-v{VERSION}-manifest.json"
    sys.path.insert(0, str(root / "daymirror" / "scripts"))
    from daymirror_core.storage import write_json
    write_json(manifest_path, manifest)
    return {"ok": True, "archive": str(archive), "manifest": str(manifest_path), "file_count": len(entries),
            "private_directories_included": False, "archive_sha256": manifest["archive_sha256"]}


if __name__ == "__main__":
    try:
        print(json.dumps(build_release(), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
