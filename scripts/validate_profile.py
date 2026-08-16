#!/usr/bin/env python3
"""校验长期事实档案与岗位投影之间的证据、隐私和版本边界。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


FACT_STATUSES = {"confirmed", "needs_review", "draft"}
VISIBILITIES = {"public", "private"}


def load_json(path: Path) -> dict[str, Any]:
    """以 UTF-8 读取 JSON 对象。"""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} 根节点必须是对象")
    return value


def validate_profile(profile: dict[str, Any]) -> tuple[list[str], list[str], set[str]]:
    """检查事实档案的结构、证据引用和公开边界。"""
    errors: list[str] = []
    warnings: list[str] = []
    fact_ids: set[str] = set()
    if profile.get("version") != 1:
        errors.append("profile.version 必须为 1")
    if not str(profile.get("updated_at", "")).strip():
        errors.append("profile.updated_at 不能为空")
    identity = profile.get("identity")
    if not isinstance(identity, dict) or not str(identity.get("name", "")).strip():
        errors.append("profile.identity.name 不能为空")
    facts = profile.get("facts")
    if not isinstance(facts, list):
        errors.append("profile.facts 必须是数组")
        facts = []
    for index, fact in enumerate(facts, 1):
        path = f"profile.facts[{index}]"
        if not isinstance(fact, dict):
            errors.append(f"{path} 必须是对象")
            continue
        fact_id = str(fact.get("id", "")).strip()
        if not fact_id:
            errors.append(f"{path}.id 不能为空")
        elif fact_id in fact_ids:
            errors.append(f"{path}.id 重复：{fact_id}")
        else:
            fact_ids.add(fact_id)
        if not str(fact.get("kind", "")).strip():
            errors.append(f"{path}.kind 不能为空")
        if not str(fact.get("summary", "")).strip():
            errors.append(f"{path}.summary 不能为空")
        status = str(fact.get("status", "")).strip()
        if status not in FACT_STATUSES:
            errors.append(f"{path}.status 无效：{status}")
        visibility = str(fact.get("visibility", "")).strip()
        if visibility not in VISIBILITIES:
            errors.append(f"{path}.visibility 无效：{visibility}")
        evidence = fact.get("evidence")
        if not isinstance(evidence, list) or not any(str(item).strip() for item in evidence):
            errors.append(f"{path}.evidence 至少需要一条引用")
        if status == "needs_review":
            warnings.append(f"{path} 尚未完成复核：{fact_id or index}")
    capabilities = profile.get("capabilities", [])
    if not isinstance(capabilities, list):
        errors.append("profile.capabilities 必须是数组")
        capabilities = []
    for index, capability in enumerate(capabilities, 1):
        path = f"profile.capabilities[{index}]"
        if not isinstance(capability, dict):
            errors.append(f"{path} 必须是对象")
            continue
        if not str(capability.get("id", "")).strip() or not str(capability.get("label", "")).strip():
            errors.append(f"{path} 必须包含 id 和 label")
        proven_by = capability.get("proven_by")
        if not isinstance(proven_by, list) or not proven_by:
            errors.append(f"{path}.proven_by 至少需要一条事实引用")
        else:
            for fact_id in proven_by:
                if str(fact_id).strip() not in fact_ids:
                    errors.append(f"{path}.proven_by 引用了不存在的事实：{fact_id}")
    return errors, warnings, fact_ids


def validate_projection(
    projection: dict[str, Any], profile: dict[str, Any], fact_ids: set[str]
) -> tuple[list[str], list[str]]:
    """检查岗位投影只能引用当前、公开且已确认的事实。"""
    errors: list[str] = []
    warnings: list[str] = []
    if projection.get("version") != 1:
        errors.append("projection.version 必须为 1")
    if projection.get("profile_version") != profile.get("updated_at"):
        errors.append("projection.profile_version 与 profile.updated_at 不一致，需要重新确认投影")
    target = projection.get("target")
    if not isinstance(target, dict) or not str(target.get("role", "")).strip():
        errors.append("projection.target.role 不能为空")
    selected = projection.get("selected_fact_ids")
    if not isinstance(selected, list) or not selected:
        errors.append("projection.selected_fact_ids 至少需要一条事实")
        selected = []
    facts = {str(fact.get("id")): fact for fact in profile.get("facts", []) if isinstance(fact, dict)}
    for fact_id in selected:
        key = str(fact_id).strip()
        if key not in fact_ids:
            errors.append(f"projection.selected_fact_ids 引用了不存在的事实：{key}")
            continue
        fact = facts[key]
        if fact.get("visibility") != "public":
            errors.append(f"投影不能选择 private 事实：{key}")
        if fact.get("status") != "confirmed":
            errors.append(f"投影不能选择未确认事实：{key}")
    excluded = projection.get("excluded_fact_ids", [])
    if not isinstance(excluded, list):
        errors.append("projection.excluded_fact_ids 必须是数组")
    if not projection.get("user_confirmed"):
        warnings.append("projection 尚未标记为用户确认，不能作为最终投递版本")
    if not str(projection.get("resume_data", "")).strip():
        errors.append("projection.resume_data 不能为空")
    return errors, warnings


def main() -> None:
    """执行事实档案和可选岗位投影的校验并输出 JSON 报告。"""
    parser = argparse.ArgumentParser(description="校验 Starline 简历事实档案和岗位投影。")
    parser.add_argument("profile", help="profile.json 路径")
    parser.add_argument("--projection", help="可选 projection.json 路径")
    parser.add_argument("--output", "-o", help="JSON 报告输出路径")
    args = parser.parse_args()
    profile_path = Path(args.profile).expanduser().resolve()
    try:
        profile = load_json(profile_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"无法读取事实档案：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    errors, warnings, fact_ids = validate_profile(profile)
    if args.projection:
        projection_path = Path(args.projection).expanduser().resolve()
        try:
            projection = load_json(projection_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"无法读取岗位投影：{exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        projection_errors, projection_warnings = validate_projection(projection, profile, fact_ids)
        errors.extend(projection_errors)
        warnings.extend(projection_warnings)
    report = {
        "ok": not errors,
        "profile": profile_path.name,
        "projection": Path(args.projection).name if args.projection else None,
        "fact_count": len(fact_ids),
        "errors": errors,
        "warnings": warnings,
        "evidence_boundary": "结构和引用检查不能证明事实真实，最终事实仍需用户确认",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
