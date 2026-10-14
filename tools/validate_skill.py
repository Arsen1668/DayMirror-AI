"""Validate this Skill without changing it or contacting a service."""

import copy
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate(skill_root=None):
    skill = Path(skill_root or ROOT / "daymirror").resolve()
    content = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.S)
    if not match:
        raise ValueError("SKILL.md 缺少 YAML frontmatter。")
    metadata = yaml.safe_load(match.group(1))
    name = metadata.get("name") if isinstance(metadata, dict) else None
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        raise ValueError("Skill 名称不符合规范。")
    if name != skill.name:
        raise ValueError("Skill 名称必须与文件夹一致。")
    description = metadata.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        raise ValueError("description 必须为 1–1024 字符。")
    if "[TODO:" in content:
        raise ValueError("Skill 存在未完成脚手架。")
    citation = yaml.safe_load((skill / "CITATION.cff").read_text(encoding="utf-8"))
    details = metadata["metadata"]
    if (not isinstance(citation, dict) or citation.get("cff-version") != "1.2.0"
            or citation.get("version") != details["version"]
            or citation.get("license") != metadata.get("license")
            or citation.get("repository-code") != details["repository"]):
        raise ValueError("引用信息与 Skill 版本、许可证或仓库不一致。")
    authors = citation.get("authors")
    if not isinstance(authors, list) or not any(
            isinstance(author, dict) and author.get("family-names") == details["author"] for author in authors):
        raise ValueError("引用信息缺少项目作者署名。")
    refs = sorted(set(re.findall(r"(?:references|assets|scripts)/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", content)))
    for reference in refs:
        target = (skill / reference).resolve()
        if not target.is_relative_to(skill) or not target.is_file():
            raise ValueError(f"引用不存在或越界：{reference}")
    interface = yaml.safe_load((skill / "agents" / "openai.yaml").read_text(encoding="utf-8"))["interface"]
    if not 25 <= len(interface["short_description"]) <= 64 or "$daymirror" not in interface["default_prompt"]:
        raise ValueError("客户端界面元数据不符合约定。")
    sys.path.insert(0, str(skill / "scripts"))
    from daymirror_core.validation import validate_journal
    template = json.loads((skill / "assets" / "journal_input_template.json").read_text(encoding="utf-8"))
    validate_journal(template, {"content_revision": 0, "questions": []})
    fixture = json.loads((skill / "assets" / "demo_fixture.json").read_text(encoding="utf-8"))
    if (fixture.get("synthetic") is not True or len(fixture["answers"]) != 20
            or len(fixture["basic_questions"]) != 10 or len(fixture["deep_questions"]) != 10):
        raise ValueError("合成夹具缺少标记或题目。")
    payload = copy.deepcopy(fixture["journal"])
    payload["content_revision"] = 0
    validate_journal(payload, {"content_revision": 0, "questions": [
        {"id": key, "status": "answered" if value is not None else "skipped"}
        for key, value in fixture["answers"].items()]})
    return {"ok": True, "name": name, "version": details["version"], "checked_references": refs,
            "json_assets_valid": True, "citation_metadata_consistent": True}


if __name__ == "__main__":
    try:
        print(json.dumps(validate(), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
