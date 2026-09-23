import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("notion-sync")

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"
TASK_REGEX = re.compile(r"\b(?:VALENIA|SIPOLI)-(\d+)\b", re.IGNORECASE)


def call_notion_api(endpoint: str, token: str, method: str = "GET", payload: dict | None = None) -> dict:
    url = f"{NOTION_BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Notion-Version", NOTION_API_VERSION)
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8")
        logger.error("Notion API HTTP error %d: %s", err.code, body)
        raise
    except urllib.error.URLError as err:
        logger.error("Notion API network error: %s", err.reason)
        raise


def extract_task_ids(text: str) -> list[str]:
    if not text:
        return []
    matches = TASK_REGEX.findall(text)
    task_ids = []
    for match in matches:
        formatted_id = f"VALENIA-{int(match):02d}"
        if formatted_id not in task_ids:
            task_ids.append(formatted_id)
    return task_ids


def find_notion_page_by_task_id(database_id: str, token: str, task_id: str) -> str | None:
    # 1. Primary: query via native Notion Unique ID property ("ID")
    digits_match = re.search(r"\d+", task_id)
    if digits_match:
        number = int(digits_match.group())
        query_payload = {
            "filter": {
                "property": "ID",
                "unique_id": {
                    "equals": number,
                },
            }
        }
        try:
            result = call_notion_api(f"/databases/{database_id}/query", token, method="POST", payload=query_payload)
            pages = result.get("results", [])
            if pages:
                return pages[0]["id"]
            logger.warning("No task card found in Notion for ID %s", task_id)
            return None
        except urllib.error.HTTPError as err:
            logger.debug("Unique ID query failed with HTTP error %d, trying fallback", err.code)

    # 2. Fallback: query via legacy rich_text property ("Task ID")
    fallback_payload = {
        "filter": {
            "property": "Task ID",
            "rich_text": {
                "equals": task_id,
            },
        }
    }
    try:
        result = call_notion_api(f"/databases/{database_id}/query", token, method="POST", payload=fallback_payload)
        pages = result.get("results", [])
        if pages:
            return pages[0]["id"]
    except urllib.error.HTTPError as err:
        logger.debug("Rich text fallback query failed with HTTP error %d", err.code)

    logger.warning("No task card found in Notion for ID %s", task_id)
    return None


def update_notion_task(page_id: str, token: str, status_name: str, link_url: str | None = None) -> None:
    properties: dict = {
        "Status": {
            "status": {
                "name": status_name,
            }
        }
    }
    if link_url:
        properties["PR / Commit Link"] = {
            "url": link_url,
        }

    call_notion_api(f"/pages/{page_id}", token, method="PATCH", payload={"properties": properties})
    logger.info("Successfully updated page %s status to '%s'", page_id, status_name)


def parse_github_event(event_path: str) -> tuple[list[str], str, str]:
    if not os.path.exists(event_path):
        logger.warning("GitHub event file not found at %s", event_path)
        return [], "", ""

    with open(event_path, "r", encoding="utf-8") as f:
        event = json.load(f)

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    target_tasks = []
    status_target = ""
    link_url = ""

    if event_name == "pull_request":
        pr = event.get("pull_request", {})
        action = event.get("action", "")
        pr_title = pr.get("title", "")
        pr_body = pr.get("body", "") or ""
        head_ref = pr.get("head", {}).get("ref", "")
        link_url = pr.get("html_url", "")
        is_merged = pr.get("merged", False)

        combined_text = f"{pr_title} {head_ref} {pr_body}"
        target_tasks = extract_task_ids(combined_text)

        if action in ("opened", "reopened", "edited"):
            status_target = "In review"
        elif action == "closed" and is_merged:
            status_target = "Done"

    elif event_name == "push":
        head_commit = event.get("head_commit") or {}
        link_url = head_commit.get("url", "")
        ref = event.get("ref", "")

        messages = [head_commit.get("message", "")]
        for c in event.get("commits", []):
            msg = c.get("message")
            if msg:
                messages.append(msg)
        combined_text = f"{' '.join(messages)} {ref}"
        target_tasks = extract_task_ids(combined_text)

        if ref == "refs/heads/main":
            status_target = "Done"
        else:
            status_target = "In progress"

    return target_tasks, status_target, link_url


def main() -> int:
    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_TASKS_DB_ID")

    if not token:
        logger.error("Missing NOTION_TOKEN environment variable")
        return 1

    if not database_id:
        logger.error("Missing NOTION_TASKS_DB_ID environment variable")
        return 1

    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    task_ids, status_target, link_url = parse_github_event(event_path)

    manual_task = os.environ.get("TASK_ID")
    if manual_task:
        manual_extracted = extract_task_ids(manual_task)
        for tid in manual_extracted:
            if tid not in task_ids:
                task_ids.append(tid)

    if not task_ids:
        logger.info("No VALENIA or SIPOLI task IDs detected in commit or pull request. Exiting cleanly.")
        return 0

    if not status_target:
        logger.info("No status transition specified for this event. Exiting cleanly.")
        return 0

    logger.info("Identified task IDs: %s. Setting status to '%s'", task_ids, status_target)
    for task_id in task_ids:
        try:
            page_id = find_notion_page_by_task_id(database_id, token, task_id)
            if page_id:
                update_notion_task(page_id, token, status_target, link_url)
        except (urllib.error.HTTPError, urllib.error.URLError) as err:
            logger.error("Failed to update task %s in Notion: %s", task_id, err)

    return 0


if __name__ == "__main__":
    sys.exit(main())
