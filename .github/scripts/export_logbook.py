#!/usr/bin/env python3
"""
Logbook automation tool for VALENIA PBL project.
Extracts task data per sprint from Notion, maps to structured JSON,
and builds Typst PDF logbook reports.
"""

from datetime import datetime
import os
import re
import sys

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
