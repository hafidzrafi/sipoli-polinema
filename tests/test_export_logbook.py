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


class TestEvidenceFormatter(unittest.TestCase):
    def test_github_pr_url(self):
        link, label = export_logbook.format_evidence_link("https://github.com/hafidzrafi/valenia/pull/3")
        self.assertEqual(link, "https://github.com/hafidzrafi/valenia/pull/3")
        self.assertEqual(label, "PR #3")

    def test_github_commit_url(self):
        link, label = export_logbook.format_evidence_link("https://github.com/hafidzrafi/valenia/commit/f7a4892718b7")
        self.assertEqual(label, "Commit f7a4892")

    def test_empty_or_generic_url(self):
        self.assertEqual(export_logbook.format_evidence_link("")[1], "-")
        self.assertEqual(export_logbook.format_evidence_link("https://figma.com/file/123")[1], "Figma Design")
        self.assertEqual(export_logbook.format_evidence_link("https://notion.so/doc")[1], "Notion Doc")


class TestHoursEstimator(unittest.TestCase):
    def test_priority_fallbacks(self):
        self.assertEqual(export_logbook.estimate_hours("Must", None), 4)
        self.assertEqual(export_logbook.estimate_hours("Should", None), 3)
        self.assertEqual(export_logbook.estimate_hours("Could", None), 2)
        self.assertEqual(export_logbook.estimate_hours(None, None), 2)

    def test_notes_override(self):
        self.assertEqual(export_logbook.estimate_hours("Must", "Refactoring auth [hours: 6]"), 6)


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

