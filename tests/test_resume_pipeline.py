from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResumePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads((ROOT / "assets/example-resume.json").read_text(encoding="utf-8"))
        cls.interview = json.loads((ROOT / "assets/example-interview-ledger.json").read_text(encoding="utf-8"))
        cls.validator = load_module("validate_resume", ROOT / "scripts/validate_resume.py")
        cls.renderer = load_module("render_resume", ROOT / "scripts/render_resume.py")
        cls.interview_validator = load_module("assess_interview", ROOT / "scripts/assess_interview.py")

    def test_example_data_passes(self) -> None:
        errors, _, counts = self.validator.validate_data(self.data)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(counts["bullets"], 4)

    def test_plain_string_bullet_is_rejected(self) -> None:
        broken = json.loads(json.dumps(self.data, ensure_ascii=False))
        broken["projects"][0]["bullets"] = ["没有证据字段的描述"]
        errors, _, _ = self.validator.validate_data(broken)
        self.assertTrue(any("不能是纯字符串" in error for error in errors))

    def test_confirmed_interview_ledger_is_ready(self) -> None:
        result = self.interview_validator.assess(self.interview)
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["counts"]["confirmed_evidence_items"], 2)

    def test_interview_requires_explicit_confirmation(self) -> None:
        broken = json.loads(json.dumps(self.interview, ensure_ascii=False))
        broken["confirmation"] = {"status": "pending"}
        result = self.interview_validator.assess(broken)
        self.assertFalse(result["ok"])
        self.assertTrue(any("明确确认" in error for error in result["errors"]))

    def test_interview_requires_two_evidence_loops(self) -> None:
        broken = json.loads(json.dumps(self.interview, ensure_ascii=False))
        broken["evidence_items"] = broken["evidence_items"][:1]
        result = self.interview_validator.assess(broken)
        self.assertFalse(result["ok"])
        self.assertTrue(any("至少需要两项" in error for error in result["errors"]))

    def test_interview_rejects_sensitive_fields(self) -> None:
        broken = json.loads(json.dumps(self.interview, ensure_ascii=False))
        broken["basics"]["id_card"] = "000000000000000000"
        result = self.interview_validator.assess(broken)
        self.assertFalse(result["ok"])
        self.assertTrue(any("敏感字段" in error for error in result["errors"]))

    def test_source_note_never_renders(self) -> None:
        rendered = self.renderer.make_html(self.data)
        self.assertNotIn("虚构测试夹具；非真实人物", rendered)
        self.assertNotIn("source_note", rendered)
        self.assertNotIn("https://fonts.", rendered)
        self.assertIn("border-bottom:", rendered.lower())
        self.assertNotRegex(rendered.lower(), r"\bborder-radius\s*:")
        self.assertNotRegex(rendered.lower(), r"\b(?:border|border-top|border-right|border-left|outline)\s*:")
        self.assertIn("TsangerJinKai02", rendered)
        self.assertIn("#f5f4ed", rendered.lower())
        self.assertIn("#1b365d", rendered.lower())
        self.assertIn("教育经历", rendered)

    def test_all_six_themes_are_distinct_and_border_safe(self) -> None:
        self.assertEqual(len(self.renderer.THEME_ORDER), 6)
        rendered_documents = []
        for theme in self.renderer.THEME_ORDER:
            themed = json.loads(json.dumps(self.data, ensure_ascii=False))
            themed["theme"] = theme
            errors, _, _ = self.validator.validate_data(themed)
            self.assertEqual(errors, [], theme)
            rendered = self.renderer.make_html(themed)
            rendered_documents.append(rendered)
            self.assertIn(f'data-theme="{theme}"', rendered)
            self.assertIn("border-bottom:", rendered.lower())
            self.assertNotRegex(rendered.lower(), r"\bborder-radius\s*:")
            self.assertNotRegex(rendered.lower(), r"\b(?:border|border-top|border-right|border-left|outline)\s*:")
        self.assertEqual(len(set(rendered_documents)), 6)

    def test_all_six_reference_styles_are_distinct_and_border_safe(self) -> None:
        self.assertEqual(len(self.renderer.REFERENCE_STYLE_ORDER), 6)
        rendered_documents = []
        for reference_style in self.renderer.REFERENCE_STYLE_ORDER:
            preset = self.renderer.REFERENCE_STYLES[reference_style]
            rendered = self.renderer.make_html(self.data, reference_style=reference_style)
            rendered_documents.append(rendered)
            self.assertIn(f'data-theme="{preset["base_theme"]}"', rendered)
            self.assertIn(f'data-reference-style="{reference_style}"', rendered)
            self.assertIn("border-bottom:", rendered.lower())
            self.assertNotRegex(rendered.lower(), r"\bborder-radius\s*:")
            self.assertNotRegex(rendered.lower(), r"\b(?:border|border-top|border-right|border-left|outline)\s*:")
        self.assertEqual(len(set(rendered_documents)), 6)

    def test_typography_baseline_is_print_safe(self) -> None:
        for theme in self.renderer.THEME_ORDER:
            rendered = self.renderer.make_html(self.data, theme_id=theme)
            self.assertNotRegex(rendered, r"\d+(?:\.\d+)?px\b", theme)
            self.assertNotIn("font-style: italic", rendered.lower(), theme)
            self.assertNotRegex(rendered, r"\.headline\s*\{[^}]*text-transform\s*:\s*uppercase", theme)
            self.assertIn("--name-size:", rendered, theme)
            self.assertIn("--section-weight:", rendered, theme)
            self.assertIn("tabular-nums lining-nums", rendered, theme)
            self.assertIn("text-underline-offset", rendered, theme)
            self.assertNotRegex(rendered, r"\.entry-sub a\s*\{[^}]*background\s*:", theme)
        formal = self.renderer.make_html(self.data, theme_id="ats-classic")
        self.assertLess(formal.index("Palatino"), formal.index("Songti SC"))
        self.assertIn('<span class="dot">·</span>', formal)

    def test_renderer_cli_emits_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/render_resume.py"),
                    str(ROOT / "assets/example-resume.json"),
                    "--output-dir",
                    temp_dir,
                    "--basename",
                    "resume",
                    "--html-only",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((Path(temp_dir) / "resume.html").is_file())

    def test_renderer_cli_emits_six_style_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/render_resume.py"),
                    str(ROOT / "assets/example-resume.json"),
                    "--output-dir",
                    temp_dir,
                    "--basename",
                    "resume",
                    "--all-themes",
                    "--html-only",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["theme_count"], 6)
            self.assertEqual(len(list(Path(temp_dir).glob("resume_*.html"))), 6)
            self.assertTrue((Path(temp_dir) / "resume_六风格清单.json").is_file())

    def test_renderer_cli_emits_reference_style_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/render_resume.py"),
                    str(ROOT / "assets/example-resume.json"),
                    "--output-dir",
                    temp_dir,
                    "--basename",
                    "resume",
                    "--all-reference-styles",
                    "--html-only",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["set_type"], "reference_styles")
            self.assertEqual(payload["theme_count"], 6)
            self.assertEqual({item["reference_style"] for item in payload["outputs"]}, set(self.renderer.REFERENCE_STYLE_ORDER))
            self.assertEqual(len(list(Path(temp_dir).glob("resume_*.html"))), 6)
            self.assertTrue((Path(temp_dir) / "resume_参考风格清单.json").is_file())

    def test_style_set_validator_rejects_incomplete_manifest(self) -> None:
        sys_path = str(ROOT / "scripts")
        import sys

        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        style_set = load_module("validate_style_set", ROOT / "scripts/validate_style_set.py")
        report = style_set.validate_set(self.data, {"theme_count": 0, "outputs": []})
        self.assertFalse(report["ok"])
        self.assertTrue(any("正好包含 6 个输出" in error for error in report["errors"]))

    def test_style_set_validator_rejects_incomplete_reference_manifest(self) -> None:
        sys_path = str(ROOT / "scripts")
        import sys

        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        style_set = load_module("validate_style_set_reference", ROOT / "scripts/validate_style_set.py")
        report = style_set.validate_set(
            self.data,
            {"set_type": "reference_styles", "theme_count": 0, "outputs": []},
        )
        self.assertFalse(report["ok"])
        self.assertTrue(any("rc-071" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
