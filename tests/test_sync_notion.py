import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure .github/scripts is importable
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".github", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import sync_notion


class TestExtractTaskIds(unittest.TestCase):
    def test_extract_standard_format(self):
        text = "feat: add login session guard [#VALENIA-08]"
        self.assertEqual(sync_notion.extract_task_ids_from_commit(text), ["VALENIA-08"])

    def test_extract_unpadded_format(self):
        text = "fix: reset counter [#VALENIA-6]"
        self.assertEqual(sync_notion.extract_task_ids_from_commit(text), ["VALENIA-06"])

    def test_extract_from_branch_ref(self):
        text = "refs/heads/feat/VALENIA-06-router-skeleton"
        self.assertEqual(sync_notion.extract_task_ids_from_ref(text), ["VALENIA-06"])

    def test_extract_multiple_distinct_tasks(self):
        text = "feat: [#VALENIA-06] and [#VALENIA-08]"
        self.assertEqual(sync_notion.extract_task_ids_from_commit(text), ["VALENIA-06", "VALENIA-08"])

    def test_extract_deduplicate_repeated_ids(self):
        text = "feat: [#VALENIA-06] also related to [#VALENIA-06]"
        self.assertEqual(sync_notion.extract_task_ids_from_commit(text), ["VALENIA-06"])

    def test_extract_legacy_sipoli_prefix(self):
        text = "fix: bug [#SIPOLI-03]"
        self.assertEqual(sync_notion.extract_task_ids_from_commit(text), ["VALENIA-03"])

    def test_extract_no_task_id_present(self):
        text = "chore: format code with prettier"
        self.assertEqual(sync_notion.extract_task_ids_from_commit(text), [])

    def test_extract_empty_string(self):
        self.assertEqual(sync_notion.extract_task_ids_from_commit(""), [])

    def test_extract_from_manual_bare_id(self):
        self.assertEqual(sync_notion.extract_task_ids_from_manual("VALENIA-06"), ["VALENIA-06"])

    def test_extract_from_manual_tagged_id(self):
        self.assertEqual(sync_notion.extract_task_ids_from_manual("[#VALENIA-06]"), ["VALENIA-06"])

    def test_casual_mention_in_commit_is_ignored(self):
        commit_msg = (
            "chore(frontend): add demo [#VALENIA-17]\n\n"
            "Temporary smoke-test; superseded by the real router (VALENIA-06)."
        )
        task_ids = sync_notion.extract_task_ids_from_commit(commit_msg)
        self.assertEqual(task_ids, ["VALENIA-17"])
        self.assertNotIn("VALENIA-06", task_ids)

    def test_extract_from_pr_text_with_closes(self):
        pr_body = "Closes #VALENIA-18\nResolves #VALENIA-06\nAlso [#VALENIA-11]"
        task_ids = sync_notion.extract_task_ids_from_pr_text(pr_body)
        self.assertEqual(task_ids, ["VALENIA-18", "VALENIA-06", "VALENIA-11"])


class TestParseGithubEvent(unittest.TestCase):
    def setUp(self):
        self.original_event_name = os.environ.get("GITHUB_EVENT_NAME")

    def tearDown(self):
        if self.original_event_name is not None:
            os.environ["GITHUB_EVENT_NAME"] = self.original_event_name
        else:
            os.environ.pop("GITHUB_EVENT_NAME", None)

    def test_push_feature_branch_with_commit_id(self):
        os.environ["GITHUB_EVENT_NAME"] = "push"
        payload = {
            "ref": "refs/heads/feat/router-skeleton",
            "head_commit": {
                "message": "feat(router): setup routes [#VALENIA-06]",
                "url": "https://github.com/test/commit/abc123",
            },
            "commits": [],
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, ["VALENIA-06"])
        self.assertEqual(status, "In progress")
        self.assertEqual(link, "https://github.com/test/commit/abc123")
        self.assertFalse(is_rejected)

    def test_push_feature_branch_with_branch_ref_only(self):
        os.environ["GITHUB_EVENT_NAME"] = "push"
        payload = {
            "ref": "refs/heads/feat/VALENIA-06-router-skeleton",
            "head_commit": {
                "message": "initial router commit",
                "url": "https://github.com/test/commit/abc124",
            },
            "commits": [],
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, ["VALENIA-06"])
        self.assertEqual(status, "In progress")
        self.assertEqual(link, "https://github.com/test/commit/abc124")
        self.assertFalse(is_rejected)

    def test_push_multiple_commits_in_batch(self):
        os.environ["GITHUB_EVENT_NAME"] = "push"
        payload = {
            "ref": "refs/heads/feat/multi-work",
            "head_commit": {
                "message": "feat(auth): add guard [#VALENIA-08]",
                "url": "https://github.com/test/commit/abc125",
            },
            "commits": [
                {"message": "feat(router): setup routes [#VALENIA-06]"},
                {"message": "feat(auth): add guard [#VALENIA-08]"},
            ],
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, ["VALENIA-08", "VALENIA-06"])
        self.assertEqual(status, "In progress")
        self.assertEqual(link, "https://github.com/test/commit/abc125")
        self.assertFalse(is_rejected)

    def test_push_to_main_branch(self):
        os.environ["GITHUB_EVENT_NAME"] = "push"
        payload = {
            "ref": "refs/heads/main",
            "head_commit": {
                "message": "Merge PR #5 [#VALENIA-06]",
                "url": "https://github.com/test/commit/merge001",
            },
            "commits": [],
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, ["VALENIA-06"])
        self.assertEqual(status, "Done")
        self.assertEqual(link, "https://github.com/test/commit/merge001")
        self.assertFalse(is_rejected)

    def test_pull_request_opened(self):
        os.environ["GITHUB_EVENT_NAME"] = "pull_request"
        payload = {
            "action": "opened",
            "pull_request": {
                "title": "feat(router): add router skeleton [#VALENIA-06]",
                "body": "Closes #VALENIA-06",
                "head": {"ref": "feat/VALENIA-06-router"},
                "html_url": "https://github.com/test/pull/1",
                "merged": False,
            },
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, ["VALENIA-06"])
        self.assertEqual(status, "In review")
        self.assertEqual(link, "https://github.com/test/pull/1")
        self.assertFalse(is_rejected)

    def test_pull_request_merged(self):
        os.environ["GITHUB_EVENT_NAME"] = "pull_request"
        payload = {
            "action": "closed",
            "pull_request": {
                "title": "feat(router): add router skeleton [#VALENIA-06]",
                "body": "Closes #VALENIA-06",
                "head": {"ref": "feat/VALENIA-06-router"},
                "html_url": "https://github.com/test/pull/1",
                "merged": True,
            },
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, ["VALENIA-06"])
        self.assertEqual(status, "Done")
        self.assertEqual(link, "https://github.com/test/pull/1")
        self.assertFalse(is_rejected)

    def test_pull_request_closed_without_merge(self):
        os.environ["GITHUB_EVENT_NAME"] = "pull_request"
        payload = {
            "action": "closed",
            "pull_request": {
                "title": "feat(router): add router skeleton [#VALENIA-06]",
                "body": "Closes #VALENIA-06",
                "head": {"ref": "feat/VALENIA-06-router"},
                "html_url": "https://github.com/test/pull/1",
                "merged": False,
            },
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, ["VALENIA-06"])
        self.assertEqual(status, "In progress")
        self.assertTrue(is_rejected)

    def test_push_branch_deletion_is_ignored(self):
        os.environ["GITHUB_EVENT_NAME"] = "push"
        payload = {
            "deleted": True,
            "ref": "refs/heads/feat/VALENIA-18-notion-sync",
            "head_commit": None,
            "commits": [],
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, [])
        self.assertEqual(status, "")
        self.assertEqual(link, "")
        self.assertFalse(is_rejected)

    def test_event_without_task_id(self):
        os.environ["GITHUB_EVENT_NAME"] = "push"
        payload = {
            "ref": "refs/heads/chore/clean-docs",
            "head_commit": {
                "message": "docs: update readme text",
                "url": "https://github.com/test/commit/abc999",
            },
            "commits": [],
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            task_ids, status, link, is_rejected = sync_notion.parse_github_event(f.name)

        self.assertEqual(task_ids, [])
        self.assertEqual(status, "In progress")
        self.assertFalse(is_rejected)

    def test_event_file_not_found(self):
        task_ids, status, link, is_rejected = sync_notion.parse_github_event("/non/existent/event.json")
        self.assertEqual(task_ids, [])
        self.assertEqual(status, "")
        self.assertEqual(link, "")
        self.assertFalse(is_rejected)


class TestStateGuard(unittest.TestCase):
    @patch("sync_notion.call_notion_api")
    def test_done_task_blocks_regression_to_in_progress(self, mock_api):
        page = {
            "id": "page-123",
            "properties": {
                "Status": {"status": {"name": "Done"}},
                "PR / Commit Link": {"url": "https://github.com/test/commit/main123"},
            },
        }
        sync_notion.update_notion_task(
            page,
            token="dummy-token",
            status_name="In progress",
            link_url="https://github.com/test/commit/branch456",
            is_pr_rejected=False,
        )
        mock_api.assert_not_called()

    @patch("sync_notion.call_notion_api")
    def test_in_review_task_preserves_review_status_on_push(self, mock_api):
        page = {
            "id": "page-123",
            "properties": {
                "Status": {"status": {"name": "In review"}},
                "PR / Commit Link": {"url": "https://github.com/test/pull/1"},
            },
        }
        sync_notion.update_notion_task(
            page,
            token="dummy-token",
            status_name="In progress",
            link_url="https://github.com/test/commit/new456",
            is_pr_rejected=False,
        )
        mock_api.assert_called_once_with(
            "/pages/page-123",
            "dummy-token",
            method="PATCH",
            payload={"properties": {"PR / Commit Link": {"url": "https://github.com/test/commit/new456"}}},
        )

    @patch("sync_notion.call_notion_api")
    def test_in_review_task_allows_regression_on_pr_rejection(self, mock_api):
        page = {
            "id": "page-123",
            "properties": {
                "Status": {"status": {"name": "In review"}},
                "PR / Commit Link": {"url": "https://github.com/test/pull/1"},
            },
        }
        sync_notion.update_notion_task(
            page,
            token="dummy-token",
            status_name="In progress",
            link_url="https://github.com/test/pull/1",
            is_pr_rejected=True,
        )
        mock_api.assert_called_once_with(
            "/pages/page-123",
            "dummy-token",
            method="PATCH",
            payload={
                "properties": {
                    "Status": {"status": {"name": "In progress"}},
                    "PR / Commit Link": {"url": "https://github.com/test/pull/1"},
                }
            },
        )

    @patch("sync_notion.call_notion_api")
    def test_todo_task_allows_progression_to_in_progress(self, mock_api):
        page = {
            "id": "page-123",
            "properties": {
                "Status": {"status": {"name": "To do"}},
            },
        }
        sync_notion.update_notion_task(
            page,
            token="dummy-token",
            status_name="In progress",
            link_url="https://github.com/test/commit/feature001",
        )
        mock_api.assert_called_once_with(
            "/pages/page-123",
            "dummy-token",
            method="PATCH",
            payload={
                "properties": {
                    "Status": {"status": {"name": "In progress"}},
                    "PR / Commit Link": {"url": "https://github.com/test/commit/feature001"},
                }
            },
        )

    @patch("sync_notion.call_notion_api")
    def test_in_progress_allows_progression_to_done(self, mock_api):
        page = {
            "id": "page-123",
            "properties": {
                "Status": {"status": {"name": "In progress"}},
            },
        }
        sync_notion.update_notion_task(
            page,
            token="dummy-token",
            status_name="Done",
            link_url="https://github.com/test/commit/merge001",
        )
        mock_api.assert_called_once_with(
            "/pages/page-123",
            "dummy-token",
            method="PATCH",
            payload={
                "properties": {
                    "Status": {"status": {"name": "Done"}},
                    "PR / Commit Link": {"url": "https://github.com/test/commit/merge001"},
                }
            },
        )

    @patch("sync_notion.call_notion_api")
    def test_status_none_handled_gracefully(self, mock_api):
        page = {
            "id": "page-123",
            "properties": {
                "Status": {"status": None},
            },
        }
        sync_notion.update_notion_task(
            page,
            token="dummy-token",
            status_name="In progress",
            link_url="https://github.com/test/commit/abc001",
        )
        mock_api.assert_called_once_with(
            "/pages/page-123",
            "dummy-token",
            method="PATCH",
            payload={
                "properties": {
                    "Status": {"status": {"name": "In progress"}},
                    "PR / Commit Link": {"url": "https://github.com/test/commit/abc001"},
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
