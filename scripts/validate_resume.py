#!/usr/bin/env python3
"""Validate resume facts plus optional PDF structure and text extraction."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ALLOWED_EVIDENCE = {
    "source_resume",
    "user_confirmed",
    "repository_verified",
    "document_verified",
    "conservative_estimate",
}
PLACEHOLDER_RE = re.compile(
    r"(?:待补充|待确认|待填写|示例文本|你的名字|姓名_[^_]|XXX|TBD|TODO|N/?A|lorem ipsum|\[[^\]]*(?:填|insert|placeholder)[^\]]*\])",
    re.IGNORECASE,
)
ESTIMATE_MARKER_RE = re.compile(r"(?:约|大约|近|超过|不少于|~|≈|\d+\s*[-–—]\s*\d+)")
DATE_RE = re.compile(r"^(\d{4})[.\-/](\d{1,2})$")

THEME_CHECKS = {
    "ats-classic": {"brand": "#6d2536", "paper": "#ffffff", "font": "Songti", "latin": "Palatino"},
    "kami": {"brand": "#1b365d", "paper": "#f5f4ed", "font": "TsangerJinKai02", "latin": "Palatino"},
    "swiss": {"brand": "#c63c32", "paper": "#fcfcfa", "font": "PingFang", "latin": "Avenir Next"},
    "tech": {"brand": "#00649a", "paper": "#f7f9fa", "font": "PingFang", "latin": "IBM Plex Sans"},
    "campus": {"brand": "#16745f", "paper": "#fffdf8", "font": "PingFang", "latin": "Avenir Next"},
    "compact": {"brand": "#2b4c6f", "paper": "#ffffff", "font": "Songti", "latin": "Palatino"},
}

REFERENCE_STYLE_CHECKS = {
    "rc-003": {"theme": "compact", "brand": "#173f63", "paper": "#ffffff", "font": "Songti", "latin": "Palatino"},
    "rc-071": {"theme": "swiss", "brand": "#17365d", "paper": "#ffffff", "font": "PingFang", "latin": "Avenir Next"},
    "rc-102": {"theme": "tech", "brand": "#244e73", "paper": "#ffffff", "font": "PingFang", "latin": "IBM Plex Sans"},
    "rc-109": {"theme": "ats-classic", "brand": "#203e5a", "paper": "#ffffff", "font": "Songti", "latin": "Palatino"},
    "rc-150": {"theme": "ats-classic", "brand": "#4e5963", "paper": "#ffffff", "font": "Songti", "latin": "Palatino"},
    "rc-214": {"theme": "campus", "brand": "#287eaa", "paper": "#ffffff", "font": "PingFang", "latin": "Avenir Next"},
}


def nonempty(value: Any) -> bool:
    return bool(str(value or "").strip())


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def date_value(raw: Any) -> tuple[int, int] | None:
    match = DATE_RE.match(str(raw or "").strip())
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    return (year, month) if 1 <= month <= 12 else None


def collect_texts(data: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key != "source_note":
                texts.extend(collect_texts(value))
    elif isinstance(data, list):
        for value in data:
            texts.extend(collect_texts(value))
    elif isinstance(data, str):
        texts.append(data)
    return texts


def validate_data(data: dict[str, Any]) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    counts = {"education": 0, "experience": 0, "projects": 0, "skills": 0, "bullets": 0}

    if data.get("version") != 1:
        errors.append("version 必须为 1")
    if data.get("language") not in {"zh-CN", "en"}:
        errors.append("language 必须为 zh-CN 或 en")
    if data.get("theme") not in THEME_CHECKS:
        errors.append(f"theme 必须为以下之一：{', '.join(THEME_CHECKS)}")
    reference_style = str(data.get("reference_style", "")).strip()
    if reference_style and reference_style not in REFERENCE_STYLE_CHECKS:
        errors.append(f"reference_style 必须为以下之一：{', '.join(REFERENCE_STYLE_CHECKS)}")
    filename = str(data.get("filename", ""))
    if not filename or re.search(r"[\\/:*?\"<>|]", filename):
        errors.append("filename 不能为空且不能包含路径分隔符或非法字符")

    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    basics = data.get("basics") if isinstance(data.get("basics"), dict) else {}
    for label, value in (("目标岗位", target.get("role")), ("姓名", basics.get("name")), ("邮箱", basics.get("email"))):
        if not nonempty(value):
            errors.append(f"缺少{label}")
    email = str(basics.get("email", ""))
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("邮箱格式无效")
    if not nonempty(basics.get("phone")) and not basics.get("links"):
        warnings.append("除邮箱外没有电话或个人链接")
    for index, link in enumerate(basics.get("links", []) or [], 1):
        if not isinstance(link, dict) or not valid_url(str(link.get("url", ""))):
            errors.append(f"basics.links[{index}] URL 无效")

    for section in ("education", "experience", "projects", "skills"):
        value = data.get(section, [])
        if not isinstance(value, list):
            errors.append(f"{section} 必须是数组")
            continue
        counts[section] = len(value)
    if counts["education"] == 0:
        errors.append("至少需要一条教育经历")
    if counts["experience"] + counts["projects"] == 0:
        errors.append("至少需要一条实践经历或项目经历")
    if counts["skills"] == 0:
        warnings.append("技能区为空")

    for section in ("experience", "projects"):
        for item_index, item in enumerate(data.get(section, []) or [], 1):
            if not isinstance(item, dict):
                errors.append(f"{section}[{item_index}] 必须是对象")
                continue
            if not nonempty(item.get("organization") or item.get("name")):
                errors.append(f"{section}[{item_index}] 缺少组织或项目名称")
            start = date_value(item.get("start"))
            raw_end = str(item.get("end", "")).strip()
            end = date_value(raw_end)
            if item.get("start") and not start:
                errors.append(f"{section}[{item_index}] 开始时间格式无效")
            if raw_end and raw_end.lower() not in {"至今", "present", "now"} and not end:
                errors.append(f"{section}[{item_index}] 结束时间格式无效")
            if start and end and start > end:
                errors.append(f"{section}[{item_index}] 时间线倒置")
            link = str(item.get("link", "")).strip()
            if link and not valid_url(link):
                errors.append(f"{section}[{item_index}] link URL 无效")
            bullets = item.get("bullets", [])
            if not isinstance(bullets, list) or not 1 <= len(bullets) <= 5:
                errors.append(f"{section}[{item_index}] 必须包含 1–5 条 bullets")
                continue
            for bullet_index, bullet in enumerate(bullets, 1):
                counts["bullets"] += 1
                path = f"{section}[{item_index}].bullets[{bullet_index}]"
                if not isinstance(bullet, dict):
                    errors.append(f"{path} 必须是带证据类型的对象，不能是纯字符串")
                    continue
                text = str(bullet.get("text", "")).strip()
                evidence = str(bullet.get("evidence_type", "")).strip()
                if len(text) < 12:
                    errors.append(f"{path}.text 过短或为空")
                if evidence not in ALLOWED_EVIDENCE:
                    errors.append(f"{path}.evidence_type 无效或缺失")
                if not nonempty(bullet.get("source_note")):
                    warnings.append(f"{path} 缺少私下复核备注")
                if evidence == "conservative_estimate" and not ESTIMATE_MARKER_RE.search(text):
                    errors.append(f"{path} 是保守估算，但正文没有约数或区间标记")

    for text in collect_texts(data):
        if PLACEHOLDER_RE.search(text):
            errors.append("公开内容中发现占位符或未确认字段")
            break
    summary = str(basics.get("summary", ""))
    if len(summary) > 280:
        warnings.append("summary 可能过长，建议控制在 2–3 行")
    return errors, warnings, counts


def inspect_html(
    html_path: Path,
    *,
    theme: str,
    reference_style: str | None = None,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    facts: dict[str, Any] = {"file": html_path.name, "bytes": html_path.stat().st_size if html_path.is_file() else 0}
    if not html_path.is_file():
        return ["HTML 文件不存在"], warnings, facts
    text = html_path.read_text(encoding="utf-8", errors="replace")
    separator_declarations = re.findall(r"\bborder-bottom\s*:", text, flags=re.IGNORECASE)
    radius_declarations = re.findall(r"\bborder-radius\s*:", text, flags=re.IGNORECASE)
    forbidden_box_declarations = re.findall(
        r"\b(?:border|border-top|border-right|border-left|outline)\s*:",
        text,
        flags=re.IGNORECASE,
    )
    pixel_measurements = re.findall(r"\d+(?:\.\d+)?px\b", text, flags=re.IGNORECASE)
    italic_declarations = re.findall(r"font-style\s*:\s*italic\b", text, flags=re.IGNORECASE)
    link_blocks = re.findall(r"\.entry-sub\s+a\s*\{([^}]*)\}", text, flags=re.IGNORECASE | re.DOTALL)
    link_chip_backgrounds = [block for block in link_blocks if re.search(r"\bbackground\s*:", block, flags=re.IGNORECASE)]
    facts["separator_border_bottom_declarations"] = len(separator_declarations)
    facts["border_radius_declarations"] = len(radius_declarations)
    facts["forbidden_box_border_declarations"] = len(forbidden_box_declarations)
    facts["pixel_measurements"] = len(pixel_measurements)
    facts["italic_declarations"] = len(italic_declarations)
    facts["link_chip_backgrounds"] = len(link_chip_backgrounds)
    if not separator_declarations:
        errors.append("HTML 缺少允许的横向 border-bottom 分割线")
    if radius_declarations:
        errors.append("HTML 中存在 border-radius；简历禁止圆角框")
    if forbidden_box_declarations:
        errors.append("HTML 中存在边框/侧边线/轮廓声明；只允许 border-bottom 分割线")
    if pixel_measurements:
        errors.append("HTML 中存在 px 打印尺寸；A4 排版必须使用 pt、mm 或相对单位")
    if italic_declarations:
        errors.append("HTML 中存在 italic；中文简历禁止浏览器合成斜体")
    if link_chip_backgrounds:
        errors.append("项目链接存在色块背景；链接必须保持为克制的纯文本")
    if '<meta name="resume-typography-system" content="1.4">' not in text:
        errors.append("HTML 缺少 1.4 排版系统标记")
    expected = REFERENCE_STYLE_CHECKS.get(reference_style) if reference_style else THEME_CHECKS.get(theme)
    if not expected:
        errors.append(f"未知主题：{theme}")
    else:
        if expected["paper"] not in text.lower() or expected["brand"] not in text.lower():
            errors.append(f"HTML 缺少 {theme} 的核心色令牌")
        if f'data-theme="{theme}"' not in text:
            errors.append(f"HTML 主题标记与预期不符：{theme}")
        if reference_style and f'data-reference-style="{reference_style}"' not in text:
            errors.append(f"HTML 参考风格标记与预期不符：{reference_style}")
        if expected["font"] not in text:
            errors.append(f"HTML 未声明 {theme} 的目标字体：{expected['font']}")
        if expected["latin"] not in text:
            errors.append(f"HTML 未声明 {theme} 的拉丁字体层：{expected['latin']}")
    if re.search(r"@font-face\s*\{[^}]*https?://", text, flags=re.IGNORECASE | re.DOTALL):
        errors.append("HTML 字体声明不应依赖远程 URL")
    facts["theme"] = theme
    facts["reference_style"] = reference_style
    facts["palette"] = f"{expected['paper']} + {expected['brand']}" if expected else "unknown"
    facts["font_declared"] = expected["font"] if expected and expected["font"] in text else "fallback-only"
    facts["latin_font_declared"] = expected["latin"] if expected and expected["latin"] in text else "fallback-only"
    return errors, warnings, facts


def inspect_pdf(pdf: Path, expected: list[str], *, theme: str, require_theme_font: bool) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    facts: dict[str, Any] = {"file": pdf.name, "bytes": pdf.stat().st_size if pdf.is_file() else 0}
    if not pdf.is_file():
        return ["PDF 文件不存在"], warnings, facts
    if pdf.read_bytes()[:5] != b"%PDF-":
        errors.append("文件头不是有效 PDF")
        return errors, warnings, facts

    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        completed = subprocess.run([pdfinfo, str(pdf)], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            errors.append("pdfinfo 无法读取 PDF")
        else:
            info = completed.stdout
            page_match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
            size_match = re.search(r"^Page size:\s+([\d.]+) x ([\d.]+) pts", info, re.MULTILINE)
            encrypted_match = re.search(r"^Encrypted:\s+(\w+)", info, re.MULTILINE)
            if page_match:
                facts["pages"] = int(page_match.group(1))
                if not 1 <= facts["pages"] <= 2:
                    errors.append("PDF 必须为 1–2 页")
            if size_match:
                width, height = float(size_match.group(1)), float(size_match.group(2))
                facts["page_size_points"] = [width, height]
                if abs(width - 595.28) > 15 or abs(height - 841.89) > 15:
                    errors.append("PDF 页面不是 A4 尺寸")
            if encrypted_match and encrypted_match.group(1).lower() != "no":
                errors.append("PDF 不应加密")
    else:
        warnings.append("未找到 pdfinfo；页数、A4 尺寸和加密状态为 missing evidence")

    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        completed = subprocess.run([pdftotext, "-layout", str(pdf), "-"], capture_output=True, text=True, check=False)
        extracted = completed.stdout.strip()
        facts["extracted_characters"] = len(extracted)
        if completed.returncode != 0 or len(extracted) < 100:
            errors.append("PDF 文本提取失败或文本过少")
        for value in expected:
            if value and value not in extracted:
                errors.append(f"PDF 文本中缺少关键字段：{value}")
    else:
        warnings.append("未找到 pdftotext；文本可提取性为 missing evidence")

    pdffonts = shutil.which("pdffonts")
    if pdffonts:
        completed = subprocess.run([pdffonts, str(pdf)], capture_output=True, text=True, check=False)
        font_output = completed.stdout
        expected_font = THEME_CHECKS.get(theme, {}).get("font", "")
        facts["theme"] = theme
        facts["font_check"] = expected_font if expected_font and expected_font.lower() in font_output.lower() else "not-detected"
        facts["fonts_embedded"] = "yes" if re.search(r"\byes\s+yes\s+yes\b", font_output) else "inspect-output"
        if completed.returncode != 0:
            errors.append("pdffonts 无法读取 PDF 字体信息")
        elif require_theme_font and expected_font and expected_font.lower() not in font_output.lower():
            errors.append(f"PDF 未实际嵌入 {theme} 目标字体：{expected_font}")
    elif require_theme_font:
        errors.append("未找到 pdffonts，无法证明 PDF 使用并嵌入目标字体")
    return errors, warnings, facts


def main() -> None:
    parser = argparse.ArgumentParser(description="检查大学生简历数据与可选 PDF 产物。")
    parser.add_argument("input", help="resume-data.json 路径")
    parser.add_argument("--html", help="同时检查生成的 HTML 样式与字体声明")
    parser.add_argument("--pdf", help="同时检查生成的 PDF")
    parser.add_argument("--theme", choices=tuple(THEME_CHECKS), help="检查渲染覆盖主题；默认读取 JSON theme")
    parser.add_argument("--reference-style", choices=tuple(REFERENCE_STYLE_CHECKS), help="检查 ResumeCollection 重构参考预设")
    parser.add_argument("--output", "-o", help="JSON 验证报告输出路径")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"无法读取简历 JSON：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if not isinstance(data, dict):
        parser.error("简历 JSON 根节点必须是对象")

    errors, warnings, counts = validate_data(data)
    language = data.get("language", "zh-CN")
    reference_style = args.reference_style or data.get("reference_style")
    theme = REFERENCE_STYLE_CHECKS[reference_style]["theme"] if reference_style else (args.theme or data.get("theme", "kami"))
    html_facts: dict[str, Any] | None = None
    if args.html:
        html_errors, html_warnings, html_facts = inspect_html(
            Path(args.html).expanduser().resolve(),
            theme=theme,
            reference_style=reference_style,
        )
        errors.extend(html_errors)
        warnings.extend(html_warnings)
    pdf_facts: dict[str, Any] | None = None
    if args.pdf:
        basics = data.get("basics") if isinstance(data.get("basics"), dict) else {}
        section_word = "教育经历" if language == "zh-CN" else "EDUCATION"
        pdf_errors, pdf_warnings, pdf_facts = inspect_pdf(
            Path(args.pdf).expanduser().resolve(),
            [str(basics.get("name", "")), str(basics.get("email", "")), section_word],
            theme=theme,
            require_theme_font=language != "en",
        )
        errors.extend(pdf_errors)
        warnings.extend(pdf_warnings)

    report = {
        "ok": not errors,
        "input": input_path.name,
        "counts": counts,
        "html": html_facts,
        "pdf": pdf_facts,
        "errors": errors,
        "warnings": warnings,
        "evidence_boundary": "deterministic structure/runtime checks only; visual quality requires page-by-page human or agent inspection",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
