import unittest
from unittest.mock import patch
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../.github/scripts")))
import export_logbook


class TestMemberResolver(unittest.TestCase):
    def test_resolve_known_members_with_whitespace(self):
        self.assertEqual(export_logbook.resolve_member_name([{"name": "Raditya "}]), "Raditya")
        self.assertEqual(export_logbook.resolve_member_name([{"name": "FINDI FINANDA ASZAHRA "}]), "Findi")
        self.assertEqual(export_logbook.resolve_member_name([{"name": "Galuh Pramu"}]), "Galuh")
        self.assertEqual(export_logbook.resolve_member_name([{"name": "Hafidz Rafi"}]), "Hapiss")

    def test_resolve_empty_or_unknown_member(self):
        self.assertEqual(export_logbook.resolve_member_name([]), "Unassigned")
        self.assertEqual(export_logbook.resolve_member_name([{"name": "Random Person"}]), "Random Person")

    def test_resolve_member_name_malformed_entries(self):
        self.assertEqual(export_logbook.resolve_member_name([None]), "Unassigned")
        self.assertEqual(export_logbook.resolve_member_name([{"name": None}]), "Unassigned")
        self.assertEqual(export_logbook.resolve_member_name([{"name": 123}]), "Unassigned")
        self.assertEqual(export_logbook.resolve_member_name([{"name": "   "}]), "Unassigned")
        self.assertEqual(export_logbook.resolve_member_name(["invalid-type"]), "Unassigned")


class TestEvidenceFormatter(unittest.TestCase):
    def test_github_pr_url(self):
        link, label = export_logbook.format_evidence_link("https://github.com/hafidzrafi/valenia/pull/3")
        self.assertEqual(link, "https://github.com/hafidzrafi/valenia/pull/3")
        self.assertEqual(label, "PR #3")

    def test_github_commit_url(self):
        link, label = export_logbook.format_evidence_link("https://github.com/hafidzrafi/valenia/commit/f7a4892718b7")
        self.assertEqual(label, "Commit f7a4892")

    def test_format_evidence_link_uppercase_commit_sha(self):
        link, label = export_logbook.format_evidence_link("https://github.com/hafidzrafi/valenia/commit/F7A4892718B7")
        self.assertEqual(label, "Commit F7A4892")

    def test_empty_or_generic_url(self):
        self.assertEqual(export_logbook.format_evidence_link("")[1], "-")
        self.assertEqual(export_logbook.format_evidence_link("https://figma.com/file/123")[1], "Figma Design")
        self.assertEqual(export_logbook.format_evidence_link("https://notion.so/doc")[1], "Notion Doc")

    def test_reject_unsafe_uri_schemes(self):
        self.assertEqual(export_logbook.format_evidence_link("javascript:alert(1)"), ("", "-"))
        self.assertEqual(export_logbook.format_evidence_link("file:///etc/passwd"), ("", "-"))
        self.assertEqual(export_logbook.format_evidence_link("data:text/html,test"), ("", "-"))


class TestHoursEstimator(unittest.TestCase):
    def test_priority_fallbacks(self):
        self.assertEqual(export_logbook.estimate_hours("Must", None), 4)
        self.assertEqual(export_logbook.estimate_hours("Should", None), 3)
        self.assertEqual(export_logbook.estimate_hours("Could", None), 2)
        self.assertEqual(export_logbook.estimate_hours(None, None), 2)

    def test_notes_override(self):
        self.assertEqual(export_logbook.estimate_hours("Must", "Refactoring auth [hours: 6]"), 6)

    def test_estimate_hours_clamps_zero_or_negative(self):
        # [hours: 0] should clamp to at least 1 hour or priority fallback
        self.assertGreaterEqual(export_logbook.estimate_hours("Must", "Quick fix [hours: 0]"), 1)
        self.assertGreaterEqual(export_logbook.estimate_hours("Could", "Quick fix [hours: -2]"), 1)


class TestDateFormatter(unittest.TestCase):
    def test_iso_date_format(self):
        self.assertEqual(export_logbook.format_date("2026-09-24T12:00:00.000Z"), "24 Sep 2026")
        self.assertEqual(export_logbook.format_date("2026-09-20"), "20 Sep 2026")

    def test_empty_date(self):
        self.assertEqual(export_logbook.format_date(None), "-")


class TestTaskNormalization(unittest.TestCase):
    def test_normalize_complete_task(self):
        page = {
            "last_edited_time": "2026-09-24T10:00:00.000Z",
            "properties": {
                "ID": {"unique_id": {"number": 12}},
                "Task Name": {"title": [{"plain_text": "Automate Logbook"}]},
                "Person": {"people": [{"name": "Hafidz Rafi"}]},
                "PR / Commit Link": {"url": "https://github.com/hafidzrafi/valenia/pull/4"},
                "Notes": {"rich_text": [{"plain_text": "Script export_logbook.py teruji"}]},
                "Deadline": {"date": {"start": "2026-09-25"}},
                "Priority": {"select": {"name": "Must"}},
            }
        }
        activity = export_logbook.normalize_task_to_activity(page)
        self.assertEqual(activity["task"], "VALENIA-12: Automate Logbook")
        self.assertEqual(activity["member"], "Hapiss")
        self.assertEqual(activity["date"], "25 Sep 2026")
        self.assertEqual(activity["deliverable"], "Script export_logbook.py teruji")
        self.assertEqual(activity["link"], "https://github.com/hafidzrafi/valenia/pull/4")
        self.assertEqual(activity["evidence_label"], "PR #4")
        self.assertEqual(activity["hours"], 4)


class TestNotionExtractor(unittest.TestCase):
    @patch("export_logbook.call_notion_api")
    def test_fetch_tasks_handles_pagination(self, mock_api):
        mock_api.side_effect = [
            {"results": [{"id": "page-1"}], "has_more": True, "next_cursor": "cur-1"},
            {"results": [{"id": "page-2"}], "has_more": False, "next_cursor": None},
        ]
        tasks = export_logbook.fetch_tasks_for_sprint("tasks-db", "fake-token", "sprint-id", only_done=False)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(mock_api.call_count, 2)
        # Verify second call used start_cursor
        second_call_payload = mock_api.call_args_list[1][1]["payload"]
        self.assertEqual(second_call_payload.get("start_cursor"), "cur-1")

    @patch("export_logbook.call_notion_api")
    def test_fetch_sprint_by_number(self, mock_api):
        mock_api.return_value = {
            "results": [
                {
                    "id": "sprint-1-id",
                    "properties": {
                        "Sprint Name": {"title": [{"plain_text": "Sprint 1: Core Setup"}]},
                        "Status": {"status": {"name": "Active"}},
                    },
                },
                {
                    "id": "sprint-2-id",
                    "properties": {
                        "Sprint Name": {"title": [{"plain_text": "Sprint 2: UI Design"}]},
                        "Status": {"status": {"name": "Planned"}},
                    },
                },
            ]
        }
        sprint = export_logbook.fetch_sprint_by_number("sprints-db", "fake-token", 1)
        self.assertIsNotNone(sprint)
        self.assertEqual(sprint["id"], "sprint-1-id")

        sprint_none = export_logbook.fetch_sprint_by_number("sprints-db", "fake-token", 99)
        self.assertIsNone(sprint_none)


class TestPayloadBuilder(unittest.TestCase):
    def test_build_sprint_payload(self):
        sprint = {
            "properties": {
                "Sprint Name": {"title": [{"plain_text": "Sprint 1: Core Infra"}]},
                "Dates": {"date": {"start": "2026-09-18", "end": "2026-09-25"}},
            }
        }
        task = {
            "properties": {
                "ID": {"unique_id": {"number": 1}},
                "Task Name": {"title": [{"plain_text": "Setup Repo"}]},
                "Assignee": {"people": [{"name": "Raditya"}]},
                "PR / Commit Link": {"url": "https://github.com/hafidzrafi/valenia/pull/1"},
                "Notes": {"rich_text": []},
                "Deadline": {"date": {"start": "2026-09-20"}},
                "Priority": {"select": {"name": "Must"}},
            }
        }
        payload = export_logbook.build_sprint_payload(sprint, [task], week_number=5)
        self.assertEqual(payload["sprint_name"], "Sprint 1: Core Infra")
        self.assertEqual(payload["week_number"], 5)
        self.assertEqual(payload["period"], "18 Sep 2026 – 25 Sep 2026")
        self.assertEqual(len(payload["activities"]), 1)
        self.assertEqual(payload["activities"][0]["member"], "Raditya")

    def test_build_sprint_payload_date_range_start_only(self):
        sprint = {
            "properties": {
                "Sprint Name": {"title": [{"plain_text": "Sprint 3: Services"}]},
                "Dates": {"date": {"start": "2026-10-01", "end": None}},
            }
        }
        payload = export_logbook.build_sprint_payload(sprint, [], week_number=7)
        self.assertIn("1 Okt 2026", payload["period"])
        self.assertNotIn("18 September", payload["period"])


class TestLogbookFileGenerator(unittest.TestCase):
    def test_generate_logbook_files(self):
        import tempfile
        import json
        from pathlib import Path

        payload = {
            "week_number": 5,
            "period": "18 Sep 2026 – 25 Sep 2026",
            "sprint_name": "Sprint 1",
            "checkpoint_target": "Checkpoint 2",
            "activities": [],
            "evaluations": [],
            "summary": "Summary text",
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path, typ_path = export_logbook.generate_logbook_files(payload, tmp_dir)
            self.assertTrue(Path(json_path).exists())
            self.assertTrue(Path(typ_path).exists())

            with open(json_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded["week_number"], 5)

            with open(typ_path, "r", encoding="utf-8") as f:
                typ_code = f.read()
            self.assertIn("pbl_logbook", typ_code)
            self.assertIn("data.json", typ_code)


class TestTypstCompilerRunner(unittest.TestCase):
    @patch("subprocess.run")
    def test_compile_typst_success(self, mock_run):
        mock_run.return_value.returncode = 0
        success = export_logbook.compile_typst("logbook/sprint-01/main.typ", "logbook/sprint-01/output.pdf")
        self.assertTrue(success)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "typst")
        self.assertEqual(args[1], "compile")
        self.assertIn("--root", args)

    @patch("subprocess.run")
    def test_compile_typst_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Typst syntax error"
        success = export_logbook.compile_typst("logbook/sprint-01/main.typ", "logbook/sprint-01/output.pdf")
        self.assertFalse(success)

    @patch("subprocess.run", side_effect=FileNotFoundError("typst not found"))
    def test_compile_typst_not_found(self, mock_run):
        success = export_logbook.compile_typst("logbook/sprint-01/main.typ", "logbook/sprint-01/output.pdf")
        self.assertFalse(success)

    @patch("subprocess.run")
    def test_compile_typst_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["typst"], timeout=60)
        success = export_logbook.compile_typst("logbook/sprint-01/main.typ", "logbook/sprint-01/output.pdf")
        self.assertFalse(success)


DEFAULT_CLI_ENV = {
    "NOTION_TOKEN": "token-xyz",
    "NOTION_TASKS_DB_ID": "tasks-db-123",
    "NOTION_SPRINTS_DB_ID": "sprints-db-456",
}


class TestCliMain(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_main_missing_token_returns_1(self):
        with patch("sys.argv", ["export_logbook.py"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 1)

    @patch.dict(os.environ, {"NOTION_TOKEN": "token-xyz"}, clear=True)
    def test_main_missing_tasks_db_returns_1(self):
        with patch("sys.argv", ["export_logbook.py"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 1)

    @patch.dict(os.environ, {"NOTION_TOKEN": "token-xyz", "NOTION_TASKS_DB_ID": "db-1"}, clear=True)
    def test_main_missing_sprints_db_returns_1(self):
        with patch("sys.argv", ["export_logbook.py"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 1)

    @patch.dict(os.environ, DEFAULT_CLI_ENV, clear=True)
    @patch("export_logbook.fetch_sprint_by_number")
    @patch("export_logbook.fetch_tasks_for_sprint")
    @patch("export_logbook.generate_logbook_files")
    @patch("export_logbook.compile_typst")
    def test_main_success_invokes_pipeline(self, mock_compile, mock_gen, mock_tasks, mock_sprint):
        mock_sprint.return_value = {"id": "sprint-1-id", "properties": {}}
        mock_tasks.return_value = []
        mock_gen.return_value = ("logbook/sprint-01/data.json", "logbook/sprint-01/main.typ")
        mock_compile.return_value = True

        with patch("sys.argv", ["export_logbook.py", "--sprint", "1", "--week", "5"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 0)
            mock_sprint.assert_called_once()
            mock_tasks.assert_called_once()
            mock_gen.assert_called_once()
            mock_compile.assert_called_once()

    @patch.dict(os.environ, {
        "NOTION_API_KEY": "token-from-api-key",
        "NOTION_TASKS_DB_ID": "tasks-db",
        "NOTION_SPRINTS_DB_ID": "sprints-db",
    }, clear=True)
    @patch("export_logbook.fetch_sprint_by_number", return_value={"id": "s1", "properties": {}})
    @patch("export_logbook.fetch_tasks_for_sprint", return_value=[])
    @patch("export_logbook.generate_logbook_files", return_value=("data.json", "main.typ"))
    @patch("export_logbook.compile_typst", return_value=True)
    def test_main_supports_notion_api_key_env_var(self, mock_compile, mock_gen, mock_tasks, mock_sprint):
        with patch("sys.argv", ["export_logbook.py", "--sprint", "1"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 0)

    @patch.dict(os.environ, DEFAULT_CLI_ENV, clear=True)
    @patch("export_logbook.fetch_sprint_by_number", return_value={"id": "s1", "properties": {}})
    @patch("export_logbook.fetch_tasks_for_sprint", return_value=[])
    @patch("export_logbook.generate_logbook_files", return_value=("data.json", "main.typ"))
    @patch("export_logbook.compile_typst", return_value=False)
    def test_main_export_logbook_returns_1_when_typst_fails(self, mock_compile, mock_gen, mock_tasks, mock_sprint):
        with patch("sys.argv", ["export_logbook.py", "--sprint", "1"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 1, "main() must return 1 when Typst compilation fails")

    @patch.dict(os.environ, DEFAULT_CLI_ENV, clear=True)
    def test_main_rejects_non_positive_sprint_or_week(self):
        with patch("sys.argv", ["export_logbook.py", "--sprint", "0"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 1)

        with patch("sys.argv", ["export_logbook.py", "--sprint", "-2"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 1)

        with patch("sys.argv", ["export_logbook.py", "--sprint", "1", "--week", "0"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 1)

    @patch.dict(os.environ, DEFAULT_CLI_ENV, clear=True)
    @patch("export_logbook.fetch_sprint_by_number")
    def test_main_handles_api_http_error_gracefully(self, mock_fetch_sprint):
        import io
        from urllib.error import HTTPError
        mock_fetch_sprint.side_effect = HTTPError("url", 401, "Unauthorized", {}, io.BytesIO(b"{}"))

        with patch("sys.argv", ["export_logbook.py", "--sprint", "1"]):
            exit_code = export_logbook.main()
            self.assertEqual(exit_code, 1)


class TestTaskNormalizationRobustness(unittest.TestCase):
    def test_normalize_task_with_none_properties_does_not_crash(self):
        page = {
            "id": "page-none-props",
            "properties": {
                "ID": None,
                "Task Name": None,
                "Assignee": None,
                "Person": None,
                "PR / Commit Link": None,
                "Notes": None,
                "Deadline": None,
                "Priority": None,
            },
        }
        activity = export_logbook.normalize_task_to_activity(page)
        self.assertEqual(activity["task"], "VALENIA-XX: ")
        self.assertEqual(activity["member"], "Unassigned")
        self.assertEqual(activity["date"], "-")
        self.assertEqual(activity["hours"], 2)




