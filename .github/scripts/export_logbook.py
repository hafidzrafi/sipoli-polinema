#!/usr/bin/env python3
"""
Logbook automation tool for VALENIA PBL project.
Extracts task data per sprint from Notion, maps to structured JSON,
and builds Typst PDF logbook reports.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from sync_notion import call_notion_api, logger

MEMBER_MAP = {
    "raditya": "Raditya",
    "findi": "Findi",
    "galuh": "Galuh",
    "hafidz": "Hapiss",
    "rafi": "Hapiss",
    "hapiss": "Hapiss",
}


def resolve_member_name(people_list: list[dict]) -> str:
    """Normalize assignee name from Notion people property."""
    if not people_list:
        return "Unassigned"
    raw_name = (people_list[0].get("name") or "").strip()
    if not raw_name:
        return "Unassigned"
    lower_name = raw_name.lower()
    for key, mapped in MEMBER_MAP.items():
        if key in lower_name:
            return mapped
    return raw_name


def format_evidence_link(url: str | None) -> tuple[str, str]:
    """Parse evidence URL to extract clickable link and readable label."""
    if not url:
        return "", "-"
    url = url.strip()
    pr_match = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", url)
    if pr_match:
        return url, f"PR #{pr_match.group(1)}"
    commit_match = re.search(r"github\.com/[^/]+/[^/]+/commit/([a-f0-9]{7})", url)
    if commit_match:
        return url, f"Commit {commit_match.group(1)}"
    if "figma.com" in url:
        return url, "Figma Design"
    if "notion.so" in url:
        return url, "Notion Doc"
    return url, "Tautan Bukti"


def estimate_hours(priority_name: str | None, notes_text: str | None) -> int:
    """Estimate work hours from notes override [hours: N] or fallback priority."""
    if notes_text:
        match = re.search(r"\[hours:\s*(\d+)\]", notes_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    p_lower = (priority_name or "").lower()
    if "must" in p_lower:
        return 4
    if "should" in p_lower:
        return 3
    return 2


def format_date(date_str: str | None) -> str:
    """Format ISO date string to Indonesian short date e.g. '24 Sep 2026'."""
    if not date_str:
        return "-"
    try:
        clean_date = date_str.split("T")[0]
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
        months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"
    except Exception:
        return date_str


def normalize_task_to_activity(page: dict) -> dict:
    """Normalize Notion task page to logbook activity dictionary."""
    props = page.get("properties", {})
    uid = props.get("ID", {}).get("unique_id", {}).get("number")
    task_num = f"VALENIA-{uid:02d}" if uid is not None else "VALENIA-XX"
    title_list = props.get("Task Name", {}).get("title", [])
    raw_title = "".join([t.get("plain_text", "") for t in title_list]).strip()
    task_label = f"{task_num}: {raw_title}"

    # Notion Tasks DB uses 'Assignee' for people property, with 'Person' as fallback
    people = props.get("Assignee", {}).get("people", []) or props.get("Person", {}).get("people", [])
    member = resolve_member_name(people)

    link_url = props.get("PR / Commit Link", {}).get("url")
    link, label = format_evidence_link(link_url)

    notes_list = props.get("Notes", {}).get("rich_text", [])
    notes = "".join([t.get("plain_text", "") for t in notes_list]).strip() or raw_title

    deadline_obj = props.get("Deadline", {}).get("date")
    raw_date = deadline_obj.get("start") if deadline_obj else page.get("last_edited_time")
    formatted_date = format_date(raw_date)

    priority = props.get("Priority", {}).get("select")
    priority_name = priority.get("name") if priority else None
    hours = estimate_hours(priority_name, notes)

    return {
        "date": formatted_date,
        "member": member,
        "task": task_label,
        "deliverable": notes,
        "link": link,
        "evidence_label": label,
        "hours": hours,
        "issue": "-",
        "solution": "-",
    }


def fetch_sprint_by_number(sprints_db_id: str, token: str, sprint_number: int | None = None) -> dict | None:
    """Query Sprints DB to find a sprint by number or active status."""
    res = call_notion_api(f"/databases/{sprints_db_id}/query", token, method="POST", payload={"page_size": 50})
    sprints = res.get("results", [])
    if not sprints:
        return None
    if sprint_number is None:
        for s in sprints:
            if s.get("properties", {}).get("Status", {}).get("status", {}).get("name") == "Active":
                return s
        return sprints[0]

    pattern = rf"\b{sprint_number}\b"
    for s in sprints:
        title_list = s.get("properties", {}).get("Sprint Name", {}).get("title", [])
        title_text = "".join([t.get("plain_text", "") for t in title_list])
        if re.search(pattern, title_text):
            return s
    return None


def fetch_tasks_for_sprint(tasks_db_id: str, token: str, sprint_page_id: str, only_done: bool = True) -> list[dict]:
    """Query Tasks DB for tasks belonging to a sprint with automatic cursor pagination."""
    filter_conditions = [
        {
            "property": "🏃 Sprints",
            "relation": {"contains": sprint_page_id},
        }
    ]
    if only_done:
        filter_conditions.append({
            "property": "Status",
            "status": {"equals": "Done"},
        })

    payload = {
        "page_size": 100,
        "filter": {"and": filter_conditions} if len(filter_conditions) > 1 else filter_conditions[0],
    }

    all_tasks = []
    has_more = True
    next_cursor = None

    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor
        res = call_notion_api(f"/databases/{tasks_db_id}/query", token, method="POST", payload=payload)
        all_tasks.extend(res.get("results", []))
        has_more = res.get("has_more", False)
        next_cursor = res.get("next_cursor")

    return all_tasks


def build_sprint_payload(sprint_page: dict, task_pages: list[dict], week_number: int = 5) -> dict:
    """Build structured data payload for logbook report."""
    props = sprint_page.get("properties", {})
    title_list = props.get("Sprint Name", {}).get("title", [])
    sprint_name = "".join([t.get("plain_text", "") for t in title_list]).strip() or "Sprint Aktif"

    dates = props.get("Dates", {}).get("date")
    if dates and dates.get("start") and dates.get("end"):
        period = f"{format_date(dates['start'])} – {format_date(dates['end'])}"
    else:
        period = "18 September – 25 September 2026"

    activities = [normalize_task_to_activity(task) for task in task_pages]

    return {
        "week_number": week_number,
        "period": period,
        "sprint_name": sprint_name,
        "checkpoint_target": "Checkpoint 2 (Minggu ke-8)",
        "activities": activities,
        "evaluations": [],
        "summary": f"Pada {sprint_name}, tim pengembang VALENIA berhasil menyelesaikan seluruh aktivitas terencana dan mengintegrasikan luaran kerja ke repositori utama.",
    }


def generate_logbook_files(payload: dict, output_dir: str) -> tuple[str, str]:
    """Generate data.json and main.typ inside output_dir."""
    target_path = Path(output_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    json_path = target_path / "data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    typ_content = """#import "../_template/logbook.typ": pbl_logbook
#let data = json("data.json")

#show: pbl_logbook.with(
  week_number: data.week_number,
  period: data.period,
  sprint_name: data.sprint_name,
  checkpoint_target: data.checkpoint_target,
  activities: data.activities,
  evaluations: data.evaluations,
)

#data.summary
"""
    typ_path = target_path / "main.typ"
    with open(typ_path, "w", encoding="utf-8") as f:
        f.write(typ_content)

    return str(json_path), str(typ_path)


def compile_typst(main_typ_path: str, output_pdf_path: str) -> bool:
    """Compile Typst document with root sandboxing (--root .)."""
    try:
        cmd = ["typst", "compile", "--root", ".", main_typ_path, output_pdf_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error("Typst compilation failed: %s", res.stderr)
            return False
        logger.info("Successfully compiled %s to %s", main_typ_path, output_pdf_path)
        return True
    except FileNotFoundError:
        logger.warning("Typst CLI not found in PATH. Skipping PDF compilation.")
        return False


