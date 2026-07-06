"""Юнит-тесты валидатора базы знаний.

Запуск:  python -m unittest discover -s scripts -p "test_*.py"
Стандартная библиотека, без внешних зависимостей.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_memory_bank as v  # noqa: E402

TODAY = date(2026, 7, 5)


def fm(status: str = "active", version: str = '"1.0"', updated: str = "2026-07-05",
       extra: str = "") -> str:
    return f"---\nstatus: {status}\nversion: {version}\nupdated: {updated}\n{extra}---\n"


AGENTS_MINIMAL = "# Агентам\n\nПротокол.\n"
POLICY_MINIMAL = fm(extra="policy_push: never\n") + "# Политика\n"


class TreeCase(unittest.TestCase):
    """Базовый класс: сборка временного дерева и запуск валидатора."""

    def make_tree(self, files: dict[str, str]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def run_validator(self, root: Path, **cfg_overrides) -> list[v.Finding]:
        cfg = v.Config(**cfg_overrides) if cfg_overrides else v.Config()
        return list(v.validate(root, cfg, today=TODAY).findings)

    @staticmethod
    def rules(findings: list[v.Finding]) -> set[str]:
        return {f.rule for f in findings}

    def minimal(self, **docs: str) -> dict[str, str]:
        """Дерево: AGENTS.md + политика + индекс со ссылками на каждый документ."""
        files = {
            "AGENTS.md": AGENTS_MINIMAL,
            "memory-bank/_meta/policy.md": POLICY_MINIMAL,
        }
        index_links = ["- [policy](_meta/policy.md)"]
        for rel, text in docs.items():
            files[f"memory-bank/{rel}"] = text
            index_links.append(f"- [{rel}]({rel})")
        files["memory-bank/README.md"] = fm() + "# Индекс\n\n" + "\n".join(index_links) + "\n"
        return files


class FrontmatterSchemaTests(TreeCase):
    def test_valid_tree_is_clean(self):
        root = self.make_tree(self.minimal(**{"doc.md": fm() + "# Док\n"}))
        self.assertEqual(self.run_validator(root), [])

    def test_missing_frontmatter(self):
        root = self.make_tree(self.minimal(**{"doc.md": "# Без frontmatter\n"}))
        self.assertIn("MB010", self.rules(self.run_validator(root)))

    def test_unterminated_frontmatter(self):
        root = self.make_tree(self.minimal(**{"doc.md": "---\nstatus: active\n# нет закрытия\n"}))
        self.assertIn("MB011", self.rules(self.run_validator(root)))

    def test_invalid_status(self):
        root = self.make_tree(self.minimal(**{"doc.md": fm(status="frozen") + "x\n"}))
        self.assertIn("MB012", self.rules(self.run_validator(root)))

    def test_invalid_version(self):
        root = self.make_tree(self.minimal(**{"doc.md": fm(version='"v1"') + "x\n"}))
        self.assertIn("MB013", self.rules(self.run_validator(root)))

    def test_invalid_date(self):
        root = self.make_tree(self.minimal(**{"doc.md": fm(updated="05.07.2026") + "x\n"}))
        self.assertIn("MB014", self.rules(self.run_validator(root)))

    def test_future_date_is_warning(self):
        root = self.make_tree(self.minimal(**{"doc.md": fm(updated="2027-01-01") + "x\n"}))
        found = [f for f in self.run_validator(root) if f.rule == "MB015"]
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].severity, v.Severity.WARNING)

    def test_invalid_decision_status(self):
        root = self.make_tree(self.minimal(
            **{"doc.md": fm(extra="decision_status: maybe\n") + "x\n"}))
        self.assertIn("MB016", self.rules(self.run_validator(root)))

    def test_empty_file(self):
        root = self.make_tree(self.minimal(**{"doc.md": "  \n"}))
        self.assertIn("MB002", self.rules(self.run_validator(root)))


class LinkTests(TreeCase):
    def test_broken_link(self):
        root = self.make_tree(self.minimal(
            **{"doc.md": fm() + "см. [тут](missing.md)\n"}))
        self.assertIn("MB020", self.rules(self.run_validator(root)))

    def test_link_escaping_repo(self):
        root = self.make_tree(self.minimal(
            **{"doc.md": fm() + "см. [тут](../../outside.md)\n"}))
        self.assertIn("MB021", self.rules(self.run_validator(root)))

    def test_links_in_code_blocks_ignored(self):
        body = "```\n[не ссылка](missing.md)\n```\nи `[тоже нет](nope.md)` инлайн\n"
        root = self.make_tree(self.minimal(**{"doc.md": fm() + body}))
        self.assertEqual(self.run_validator(root), [])

    def test_external_urls_ignored(self):
        body = "[сайт](https://example.com) и [почта](mailto:a@b.c) и [якорь](#s)\n"
        root = self.make_tree(self.minimal(**{"doc.md": fm() + body}))
        self.assertEqual(self.run_validator(root), [])


class ReachabilityTests(TreeCase):
    def test_orphan_detected(self):
        files = self.minimal(**{"doc.md": fm() + "x\n"})
        files["memory-bank/orphan.md"] = fm() + "никто не ссылается\n"
        root = self.make_tree(files)
        orphaned = [f for f in self.run_validator(root) if f.rule == "MB030"]
        self.assertEqual([f.path for f in orphaned], ["memory-bank/orphan.md"])

    def test_directory_link_reaches_readme(self):
        files = {
            "AGENTS.md": AGENTS_MINIMAL,
            "memory-bank/README.md": fm() + "[раздел](ops/)\n",
            "memory-bank/ops/README.md": fm() + "[док](child.md)\n",
            "memory-bank/ops/child.md": fm() + "x\n",
        }
        root = self.make_tree(files)
        self.assertNotIn("MB030", self.rules(self.run_validator(root)))

    def test_missing_index(self):
        root = self.make_tree({
            "AGENTS.md": AGENTS_MINIMAL,
            "memory-bank/doc.md": fm() + "x\n",
        })
        self.assertIn("MB031", self.rules(self.run_validator(root)))


class StructureTests(TreeCase):
    def test_depth_limit(self):
        files = self.minimal(**{"doc.md": fm() + "x\n"})
        files["memory-bank/a/b/c/d/deep.md"] = fm() + "слишком глубоко\n"
        root = self.make_tree(files)
        self.assertIn("MB040", self.rules(self.run_validator(root)))

    def test_bank_missing_raises(self):
        root = self.make_tree({"AGENTS.md": AGENTS_MINIMAL})
        with self.assertRaises(v.BankNotFoundError):
            v.validate(root, today=TODAY)


class FreshnessTests(TreeCase):
    def test_stale_current_warns(self):
        root = self.make_tree(self.minimal(
            **{"current/active-context.md": fm(updated="2026-01-01") + "x\n"}))
        self.assertIn("MB050", self.rules(self.run_validator(root)))

    def test_stale_stable_warns(self):
        root = self.make_tree(self.minimal(
            **{"doc.md": fm(updated="2025-01-01") + "x\n"}))
        self.assertIn("MB051", self.rules(self.run_validator(root)))

    def test_archived_not_checked_for_staleness(self):
        root = self.make_tree(self.minimal(
            **{"doc.md": fm(status="archived", updated="2024-01-01") + "x\n"}))
        rules = self.rules(self.run_validator(root))
        self.assertNotIn("MB050", rules)
        self.assertNotIn("MB051", rules)


class CurrentLengthTests(TreeCase):
    def test_soft_limit_warning(self):
        body = "строка\n" * 100
        root = self.make_tree(self.minimal(**{"current/progress.md": fm() + body}))
        self.assertIn("MB052", self.rules(self.run_validator(root)))

    def test_hard_limit_error(self):
        body = "строка\n" * 200
        root = self.make_tree(self.minimal(**{"current/progress.md": fm() + body}))
        self.assertIn("MB053", self.rules(self.run_validator(root)))


class AgentsBudgetTests(TreeCase):
    def test_agents_missing_warns(self):
        files = self.minimal(**{"doc.md": fm() + "x\n"})
        del files["AGENTS.md"]
        root = self.make_tree(files)
        self.assertIn("MB062", self.rules(self.run_validator(root)))

    def test_agents_over_budget(self):
        files = self.minimal(**{"doc.md": fm() + "x\n"})
        files["AGENTS.md"] = "x" * (33 * 1024)
        root = self.make_tree(files)
        self.assertIn("MB060", self.rules(self.run_validator(root)))


class TodoMarkerTests(TreeCase):
    def test_todo_counted_across_bank_and_agents(self):
        files = self.minimal(**{"doc.md": fm() + "TODO(template): раз\n"})
        files["AGENTS.md"] = AGENTS_MINIMAL + "TODO(template): два\n"
        root = self.make_tree(files)
        todos = [f for f in self.run_validator(root) if f.rule == "MB070"]
        self.assertEqual(len(todos), 1)
        self.assertIn("2", todos[0].message)


class PolicyTests(TreeCase):
    def test_missing_policy_warns(self):
        root = self.make_tree({
            "AGENTS.md": AGENTS_MINIMAL,
            "memory-bank/README.md": fm() + "[док](doc.md)\n",
            "memory-bank/doc.md": fm() + "x\n",
        })
        found = [f for f in self.run_validator(root) if f.rule == "MB080"]
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].severity, v.Severity.WARNING)

    def test_invalid_policy_value_is_error(self):
        files = self.minimal(**{"doc.md": fm() + "x\n"})
        files["memory-bank/_meta/policy.md"] = fm(extra="policy_push: sometimes\n") + "# П\n"
        root = self.make_tree(files)
        found = [f for f in self.run_validator(root) if f.rule == "MB081"]
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].severity, v.Severity.ERROR)

    def test_custom_policy_flag_validated(self):
        files = self.minimal(**{"doc.md": fm() + "x\n"})
        files["memory-bank/_meta/policy.md"] = fm(
            extra="policy_push: never\npolicy_custom_thing: always\n") + "# П\n"
        root = self.make_tree(files)
        self.assertNotIn("MB081", self.rules(self.run_validator(root)))


class ParserUnitTests(unittest.TestCase):
    def test_scalar_quotes_and_comments(self):
        fm_ = v.parse_frontmatter('---\nversion: "1.0"\nowner: lead # комментарий\n---\nтело\n')
        self.assertEqual(fm_.data["version"], "1.0")
        self.assertEqual(fm_.data["owner"], "lead")

    def test_inline_and_block_lists(self):
        text = "---\ntags: [a, b]\nderived_from:\n  - ../x.md\n  - ../y.md\n---\n"
        fm_ = v.parse_frontmatter(text)
        self.assertEqual(fm_.data["tags"], ["a", "b"])
        self.assertEqual(fm_.data["derived_from"], ["../x.md", "../y.md"])

    def test_empty_quoted_value(self):
        fm_ = v.parse_frontmatter('---\nverified_commit: ""\n---\n')
        self.assertEqual(fm_.data["verified_commit"], "")

    def test_body_start_index(self):
        fm_ = v.parse_frontmatter("---\nstatus: active\n---\nпервая строка тела\n")
        self.assertEqual(fm_.body_start, 3)


class CliTests(TreeCase):
    def _run_main(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = v.main(argv)
        return code, out.getvalue()

    def test_exit_zero_on_clean_tree(self):
        root = self.make_tree(self.minimal(**{"doc.md": fm() + "x\n"}))
        code, _ = self._run_main(["--root", str(root)])
        self.assertEqual(code, 0)

    def test_exit_one_on_error(self):
        root = self.make_tree(self.minimal(**{"doc.md": "# без frontmatter\n"}))
        code, _ = self._run_main(["--root", str(root)])
        self.assertEqual(code, 1)

    def test_ignore_suppresses_rule(self):
        root = self.make_tree(self.minimal(**{"doc.md": "# без frontmatter\n"}))
        code, _ = self._run_main(["--root", str(root), "--ignore", "MB010"])
        self.assertEqual(code, 0)

    def test_strict_promotes_warnings(self):
        root = self.make_tree(self.minimal(
            **{"current/active-context.md": fm(updated="2026-01-01") + "x\n"}))
        self.assertEqual(self._run_main(["--root", str(root)])[0], 0)
        self.assertEqual(self._run_main(["--root", str(root), "--strict"])[0], 1)

    def test_json_contract(self):
        import json
        root = self.make_tree(self.minimal(**{"doc.md": fm() + "TODO(template): x\n"}))
        code, out = self._run_main(["--root", str(root), "--json"])
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(payload["schema"], v.JSON_SCHEMA_VERSION)
        self.assertEqual(payload["summary"]["error"], 0)
        self.assertEqual(payload["findings"][0]["rule"], "MB070")

    def test_unknown_ignore_rule_is_usage_error(self):
        root = self.make_tree(self.minimal(**{"doc.md": fm() + "x\n"}))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = v.main(["--root", str(root), "--ignore", "MB999"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
