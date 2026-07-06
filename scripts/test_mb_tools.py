"""Юнит-тесты инструментов Фазы 0: mb_lib, bump_frontmatter, mb_log,
check_session_close, kb_log_read.

Запуск: python -m unittest discover -s scripts -p "test_*.py"
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bump_frontmatter as bump  # noqa: E402
import check_session_close as scc  # noqa: E402
import kb_log_read  # noqa: E402
import mb_lib  # noqa: E402
import mb_log  # noqa: E402

TODAY = date(2026, 7, 5)

DOC_V1 = '---\nstatus: active\nversion: "1.0"\nupdated: 2026-06-01\n---\n\n# Док\n\nстарое тело\n'


class MbLibTests(unittest.TestCase):
    def test_split_document(self):
        fm, body = mb_lib.split_document(DOC_V1)
        self.assertTrue(fm.startswith("---") and fm.rstrip().endswith("---"))
        self.assertIn("# Док", body)

    def test_split_without_frontmatter(self):
        self.assertEqual(mb_lib.split_document("# Просто текст\n"), (None, "# Просто текст\n"))

    def test_get_set_scalar(self):
        fm, _ = mb_lib.split_document(DOC_V1)
        self.assertEqual(mb_lib.get_scalar(fm, "version"), "1.0")
        fm2 = mb_lib.set_scalar(fm, "version", '"1.1"')
        self.assertEqual(mb_lib.get_scalar(fm2, "version"), "1.1")
        fm3 = mb_lib.set_scalar(fm, "new_key", "x")  # добавление отсутствующего ключа
        self.assertEqual(mb_lib.get_scalar(fm3, "new_key"), "x")
        self.assertTrue(fm3.rstrip().endswith("---"))

    def test_bump_minor(self):
        self.assertEqual(mb_lib.bump_minor("1.9"), "1.10")
        self.assertEqual(mb_lib.bump_minor("2.0"), "2.1")
        self.assertEqual(mb_lib.bump_minor(None), "1.0")
        self.assertEqual(mb_lib.bump_minor("кривая"), "1.0")

    def test_touch(self):
        touched = mb_lib.touch(DOC_V1, TODAY)
        fm, body = mb_lib.split_document(touched)
        self.assertEqual(mb_lib.get_scalar(fm, "version"), "1.1")
        self.assertEqual(mb_lib.get_scalar(fm, "updated"), "2026-07-05")
        self.assertIn("старое тело", body)


class BumpLogicTests(unittest.TestCase):
    def _edited(self, version='"1.0"', updated="2026-06-01"):
        return (f'---\nstatus: active\nversion: {version}\nupdated: {updated}\n---\n'
                f'\n# Док\n\nновое тело\n')

    def test_body_changed_nothing_bumped(self):
        self.assertEqual(bump.stale_fields(DOC_V1, self._edited()), ["version", "updated"])

    def test_body_unchanged(self):
        self.assertEqual(bump.stale_fields(DOC_V1, DOC_V1), [])

    def test_already_bumped(self):
        self.assertEqual(bump.stale_fields(DOC_V1, self._edited('"1.1"', "2026-07-05")), [])

    def test_partial_manual_bump_respected(self):
        # автор поднял version вручную, но забыл updated — чиним только updated
        self.assertEqual(bump.stale_fields(DOC_V1, self._edited('"2.0"')), ["updated"])
        fixed = bump.fix_text(self._edited('"2.0"'), ["updated"], TODAY)
        fm, _ = mb_lib.split_document(fixed)
        self.assertEqual(mb_lib.get_scalar(fm, "version"), "2.0")  # ручной bump не задублирован
        self.assertEqual(mb_lib.get_scalar(fm, "updated"), "2026-07-05")

    def test_fix_text_bumps_both(self):
        fixed = bump.fix_text(self._edited(), ["version", "updated"], TODAY)
        fm, _ = mb_lib.split_document(fixed)
        self.assertEqual(mb_lib.get_scalar(fm, "version"), "1.1")
        self.assertEqual(mb_lib.get_scalar(fm, "updated"), "2026-07-05")


@unittest.skipUnless(shutil.which("git"), "git недоступен")
class BumpGitIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "test@test")
        self._git("config", "user.name", "test")
        self.doc = self.root / "memory-bank" / "doc.md"
        self.doc.parent.mkdir(parents=True)
        self.doc.write_text(DOC_V1, encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "v1")

    def _git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True,
                       capture_output=True, text=True)

    def test_check_then_fix_against_base(self):
        self.doc.write_text(DOC_V1.replace("старое тело", "новое тело"), encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "edit without bump")
        self.assertEqual(bump.main(["--base", "HEAD~1", "--check", "--root", str(self.root)]), 1)
        self.assertEqual(bump.main(["--base", "HEAD~1", "--root", str(self.root)]), 0)
        fm, _ = mb_lib.split_document(self.doc.read_text(encoding="utf-8"))
        self.assertEqual(mb_lib.get_scalar(fm, "version"), "1.1")
        self.assertEqual(mb_lib.get_scalar(fm, "updated"), date.today().isoformat())
        # идемпотентность: повторный check уже чист
        self.assertEqual(bump.main(["--base", "HEAD~1", "--check", "--root", str(self.root)]), 0)

    def test_precommit_mode_fixes_staged(self):
        self.doc.write_text(DOC_V1.replace("старое тело", "новое тело"), encoding="utf-8")
        self._git("add", ".")
        self.assertEqual(bump.main(["--root", str(self.root)]), 0)
        staged = subprocess.run(
            ["git", "show", ":memory-bank/doc.md"], cwd=self.root,
            capture_output=True, text=True, encoding="utf-8", check=True).stdout
        fm, _ = mb_lib.split_document(staged)
        self.assertEqual(mb_lib.get_scalar(fm, "version"), "1.1")


class MbLogTests(unittest.TestCase):
    ACTIVE = (
        '---\nstatus: active\nversion: "1.0"\nupdated: 2026-07-01\n---\n\n'
        "# Активный контекст\n\n"
        "## Текущий фокус\n\n- 2026-07-01 — старый фокус\n\n"
        "## Последние решения и договорённости\n\n- 2026-07-01 — старое решение\n\n"
        "## Следующие шаги\n\n- шаг\n\n"
        "## Открытые вопросы к команде\n\n- вопрос\n\n"
        "---\n\nПравила ведения файла.\n"
    )
    PROGRESS = (
        '---\nstatus: active\nversion: "1.0"\nupdated: 2026-07-01\n---\n\n'
        "# Статус\n\n"
        "## Работает\n\n- ок\n\n"
        "## Известные проблемы\n\n| Проблема | Влияние | Обходной путь | Issue |\n|---|---|---|---|\n"
        "| старая | — | — | — |\n\n"
        "## Расхождения база↔код\n\n| Документ | Что расходится | Кто заметил | Дата |\n|---|---|---|---|\n\n"
        "## Технический долг\n\n- долг\n\n"
        "---\n\nПравила.\n"
    )

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        current = self.root / "memory-bank" / "current"
        current.mkdir(parents=True)
        (current / "active-context.md").write_text(self.ACTIVE, encoding="utf-8")
        (current / "progress.md").write_text(self.PROGRESS, encoding="utf-8")

    def _read(self, name):
        return (self.root / "memory-bank" / "current" / name).read_text(encoding="utf-8")

    def test_done_appends_dated_bullet_and_bumps(self):
        code = mb_log.main(["--root", str(self.root), "--date", "2026-07-05",
                            "done", "готова оплата картой"])
        self.assertEqual(code, 0)
        text = self._read("active-context.md")
        section = text.split("## Последние решения")[1].split("## Следующие шаги")[0]
        self.assertIn("- 2026-07-05 — готова оплата картой", section)
        fm, _ = mb_lib.split_document(text)
        self.assertEqual(mb_lib.get_scalar(fm, "version"), "1.1")
        self.assertEqual(mb_lib.get_scalar(fm, "updated"), "2026-07-05")

    def test_discrepancy_appends_table_row(self):
        code = mb_log.main(["--root", str(self.root), "--date", "2026-07-05",
                            "discrepancy", "architecture/overview.md", "слои разошлись"])
        self.assertEqual(code, 0)
        section = self._read("progress.md").split("## Расхождения")[1].split("## Технический долг")[0]
        self.assertIn("| architecture/overview.md | слои разошлись | agent | 2026-07-05 |", section)

    def test_problem_appends_after_last_row(self):
        code = mb_log.main(["--root", str(self.root), "--date", "2026-07-05",
                            "problem", "дубль номера заказа", "--issue", "#142"])
        self.assertEqual(code, 0)
        section = self._read("progress.md").split("## Известные проблемы")[1].split("## Расхождения")[0]
        rows = [line for line in section.splitlines() if line.startswith("|")]
        self.assertIn("2026-07-05 — дубль номера заказа", rows[-1])
        self.assertIn("#142", rows[-1])

    def test_missing_section_is_error(self):
        (self.root / "memory-bank" / "current" / "active-context.md").write_text(
            '---\nstatus: active\nversion: "1.0"\nupdated: 2026-07-01\n---\n\n# Пусто\n',
            encoding="utf-8")
        self.assertEqual(mb_log.main(["--root", str(self.root), "done", "x"]), 1)

    def test_bad_date_is_usage_error(self):
        self.assertEqual(mb_log.main(["--root", str(self.root), "--date", "05.07.2026",
                                      "done", "x"]), 2)


class SessionCloseTests(unittest.TestCase):
    TODAY_ISO = "2026-07-05"

    def test_no_changes_allows(self):
        self.assertIsNone(scc.decide("", "", self.TODAY_ISO))

    def test_only_bank_changes_allows(self):
        porcelain = " M memory-bank/current/progress.md\n M .claude/settings.json\n"
        self.assertIsNone(scc.decide(porcelain, "", self.TODAY_ISO))

    def test_code_changed_without_log_blocks(self):
        verdict = scc.decide(" M src/main.py\n", "", self.TODAY_ISO)
        self.assertEqual(verdict["decision"], "block")
        self.assertIn("mb_log", verdict["reason"])

    def test_code_changed_with_dated_log_allows(self):
        diff = "+++ b/memory-bank/current/active-context.md\n+- 2026-07-05 — сделано\n"
        self.assertIsNone(scc.decide(" M src/main.py\n?? src/new.py\n", diff, self.TODAY_ISO))

    def test_stale_dated_log_still_blocks(self):
        diff = "+- 2026-07-01 — старая запись\n"
        self.assertEqual(scc.decide(" M src/main.py\n", diff, self.TODAY_ISO)["decision"], "block")

    def test_rename_uses_new_path(self):
        self.assertEqual(scc.porcelain_paths("R  old.py -> src/new.py\n"), ["src/new.py"])


class KbLogReadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "memory-bank").mkdir()

    def test_tracked_paths(self):
        self.assertEqual(
            kb_log_read.tracked_rel_path(str(self.root / "memory-bank" / "doc.md"), self.root),
            "memory-bank/doc.md")
        self.assertEqual(
            kb_log_read.tracked_rel_path(str(self.root / "AGENTS.md"), self.root), "AGENTS.md")
        self.assertIsNone(
            kb_log_read.tracked_rel_path(str(self.root / "src" / "main.py"), self.root))
        self.assertIsNone(kb_log_read.tracked_rel_path("C:/другое/место/x.md", self.root))

    def test_append_and_rotation(self):
        log = self.root / ".claude" / "kb-usage.log"
        kb_log_read.append_line(log, "строка")
        self.assertEqual(log.read_text(encoding="utf-8"), "строка\n")
        big = "x" * 300
        for i in range(5000):
            kb_log_read.append_line(log, f"{i}\t{big}")
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), kb_log_read.ROTATE_KEEP_LINES)


if __name__ == "__main__":
    unittest.main()
