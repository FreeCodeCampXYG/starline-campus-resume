#!/usr/bin/env python3
"""校验 Starline 简历 Skill 的基础结构、身份一致性和推广资源边界。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_FILES = ("SKILL.md", "manifest.json", "agents/interface.yaml")
FORBIDDEN_TERMS = ("qiaomu-" + "campus-resume", "向阳" + "乔木", "joe" + "seesun", "x.com/" + "vista8")
PROMOTIONAL_NAMES = {"qr", "qrcode", "wechat", "promo", "promotion", "avatar"}


def validate(root: Path) -> list[str]:
    """返回 Skill 目录中发现的结构或身份问题。"""
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"缺少必需文件：{relative}")
    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"manifest.json 无法读取：{exc}")
        else:
            if manifest.get("name") != root.name:
                errors.append("manifest.name 必须与目录名一致")
            if not str(manifest.get("version", "")).strip():
                errors.append("manifest.version 不能为空")
    promo_names = {name.casefold() for name in PROMOTIONAL_NAMES}
    for path in root.rglob("*"):
        if path.is_file() and path.stem.casefold() in promo_names:
            errors.append(f"不应包含推广资源：{path.relative_to(root)}")
        if path.is_file() and path.name not in {"LICENSE", "LICENSE.txt"} and path.suffix.casefold() in {".md", ".json", ".yaml", ".yml"}:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"文件不是 UTF-8：{path.relative_to(root)}")
                continue
            for term in FORBIDDEN_TERMS:
                if term.casefold() in content.casefold():
                    errors.append(f"发现旧品牌或旧仓库标识 {term}：{path.relative_to(root)}")
    return errors


def main() -> int:
    """执行命令行校验并输出机器可读结果。"""
    parser = argparse.ArgumentParser(description="校验 Starline 简历 Skill")
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    errors = validate(root)
    print(json.dumps({"ok": not errors, "root": str(root), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
