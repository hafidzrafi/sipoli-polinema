#!/usr/bin/env python3
"""
Logbook automation tool for VALENIA PBL project.
Extracts task data per sprint from Notion, maps to structured JSON,
and builds Typst PDF logbook reports.
"""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error

from sync_notion import call_notion_api, logger

MEMBER_MAP = {
    "raditya": "Raditya",
    "findi": "Findi",
    "galuh": "Galuh",
    "hafidz": "Hafidz",
    "rafi": "Hafidz",
    "hapiss": "Hafidz",
}


def resolve_member_name(people_list: list[dict]) -> str:
    """Normalize assignee name from Notion people property, supporting multiple assignees."""
    if not people_list or not isinstance(people_list, list):
        return "Unassigned"
    resolved: list[str] = []
    for person in people_list:
        if not isinstance(person, dict):
            continue
        raw_val = person.get("name")
        if not isinstance(raw_val, str):
            continue
        raw_name = raw_val.strip()
        if not raw_name:
            continue
        lower_name = raw_name.lower()
        matched = raw_name
        for key, mapped in MEMBER_MAP.items():
            if key in lower_name:
                matched = mapped
                break
        if matched not in resolved:
            resolved.append(matched)

    return ", ".join(resolved) if resolved else "Unassigned"


def format_evidence_link(url: str | None) -> tuple[str, str]:
    """Parse evidence URL to extract clickable link and readable label."""
    if not url:
        return "", "-"
    url = url.strip()
    url_lower = url.lower()
    if not (url_lower.startswith("https://") or url_lower.startswith("http://")):
        return "", "-"
    pr_match = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", url, re.IGNORECASE)
    if pr_match:
        return url, f"PR #{pr_match.group(1)}"
    commit_match = re.search(r"github\.com/[^/]+/[^/]+/commit/([a-f0-9]{7})", url, re.IGNORECASE)
    if commit_match:
        return url, f"Commit {commit_match.group(1)}"
    if "figma.com" in url_lower:
        return url, "Figma Design"
    if "notion.so" in url_lower:
        return url, "Notion Doc"
    return url, "Tautan Bukti"


def estimate_hours(
    priority_name: str | None,
    notes_text: str | None,
    explicit_hours: int | None = None,
) -> int:
    """Estimate work hours from explicit Est. Hours property, notes override, or priority tier."""
    if explicit_hours is not None:
        return max(1, explicit_hours)

    if notes_text:
        match = re.search(r"\[hours:\s*(-?\d+)\]", notes_text, re.IGNORECASE)
        if match:
            h = int(match.group(1))
            return max(1, h)

    p_lower = (priority_name or "").lower()
    if "tier 1" in p_lower or "must" in p_lower:
        return 4
    if "tier 2" in p_lower or "should" in p_lower:
        return 3
    if "tier 3" in p_lower or "could" in p_lower:
        return 2

    return 2


def format_date(date_str: str | None) -> str:
    """Format ISO date string to Indonesian short date e.g. '24 Sep 2026'."""
    if not date_str or not isinstance(date_str, str) or not date_str.strip():
        return "-"
    try:
        clean_date = date_str.split("T")[0].strip()
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
        months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"
    except (ValueError, TypeError, AttributeError):
        return date_str.strip()


def normalize_task_to_activity(page: dict) -> dict:
    """Normalize Notion task page to logbook activity dictionary."""
    props = page.get("properties") or {}
    id_obj = props.get("ID") or {}
    uid = (id_obj.get("unique_id") or {}).get("number") if isinstance(id_obj, dict) else None
    task_num = f"VALENIA-{uid:02d}" if uid is not None else "VALENIA-XX"

    name_obj = props.get("Task Name") or {}
    title_list = name_obj.get("title") or [] if isinstance(name_obj, dict) else []
    raw_title = "".join([(t.get("plain_text") or "") for t in title_list if isinstance(t, dict)]).strip()
    task_label = f"{task_num}: {raw_title}"

    # Notion Tasks DB uses 'Assignee' for people property, with 'Person' as fallback
    assignee_obj = props.get("Assignee") or props.get("Person") or {}
    people = assignee_obj.get("people") or [] if isinstance(assignee_obj, dict) else []
    member = resolve_member_name(people)

    link_obj = props.get("PR / Commit Link") or {}
    link_url = link_obj.get("url") if isinstance(link_obj, dict) else None
    link, label = format_evidence_link(link_url)

    notes_obj = props.get("Notes") or {}
    notes_list = notes_obj.get("rich_text") or [] if isinstance(notes_obj, dict) else []
    notes = "".join([(t.get("plain_text") or "") for t in notes_list if isinstance(t, dict)]).strip() or raw_title

    deadline_obj = props.get("Deadline") or {}
    date_val = deadline_obj.get("date") or {} if isinstance(deadline_obj, dict) else {}
    raw_date = date_val.get("start") if isinstance(date_val, dict) else None
    if not raw_date:
        raw_date = page.get("last_edited_time")
    formatted_date = format_date(raw_date)

    # Est. Hours extraction from Notion property (supporting select and number types)
    explicit_hours = None
    est_prop = props.get("Est. Hours") or props.get("Hours") or props.get("Jam") or {}
    if isinstance(est_prop, dict):
        p_type = est_prop.get("type")
        if p_type == "select":
            sel_obj = est_prop.get("select") or {}
            sel_name = sel_obj.get("name") if isinstance(sel_obj, dict) else None
            if sel_name:
                try:
                    explicit_hours = int(sel_name.strip())
                except ValueError:
                    pass
        elif p_type == "number":
            num_val = est_prop.get("number")
            if num_val is not None and isinstance(num_val, (int, float)):
                explicit_hours = int(round(num_val))
        else:
            sel_obj = est_prop.get("select")
            if isinstance(sel_obj, dict) and sel_obj.get("name"):
                try:
                    explicit_hours = int(sel_obj["name"].strip())
                except ValueError:
                    pass
            num_val = est_prop.get("number")
            if num_val is not None and isinstance(num_val, (int, float)):
                explicit_hours = int(round(num_val))

    priority_obj = props.get("Priority") or {}
    priority_select = priority_obj.get("select") or {} if isinstance(priority_obj, dict) else {}
    priority_name = priority_select.get("name") if isinstance(priority_select, dict) else None
    hours = estimate_hours(priority_name, notes, explicit_hours=explicit_hours)

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


def extract_sprint_number_from_title(title: str) -> int | None:
    """Extract integer sprint number from sprint title (e.g. 'Sprint 1: Core' -> 1)."""
    if not title:
        return None
    match = re.search(r"Sprint\s*(\d+)", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def fetch_active_sprint(sprints_db_id: str, token: str) -> tuple[dict | None, int]:
    """Query Sprints DB to find the sprint with Status 'Active' and extract its number."""
    payload = {
        "page_size": 10,
        "filter": {
            "property": "Status",
            "status": {
                "equals": "Active",
            },
        },
    }
    res = call_notion_api(f"/databases/{sprints_db_id}/query", token, method="POST", payload=payload)
    results = res.get("results", [])
    if not results:
        sprint = fetch_sprint_by_number(sprints_db_id, token, None)
        if sprint:
            props = sprint.get("properties") or {}
            title_list = (props.get("Sprint Name") or {}).get("title") or []
            title = "".join([(t.get("plain_text") or "") for t in title_list if isinstance(t, dict)])
            num = extract_sprint_number_from_title(title) or 1
            return sprint, num
        return None, 1

    sprint = results[0]
    props = sprint.get("properties") or {}
    title_list = (props.get("Sprint Name") or {}).get("title") or []
    title = "".join([(t.get("plain_text") or "") for t in title_list if isinstance(t, dict)])
    num = extract_sprint_number_from_title(title) or 1
    return sprint, num


def fetch_sprint_by_number(sprints_db_id: str, token: str, sprint_number: int | None = None) -> dict | None:
    """Query Sprints DB to find a sprint by number or active status with cursor pagination."""
    all_sprints: list[dict] = []
    has_more = True
    next_cursor = None
    payload: dict = {"page_size": 100}

    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor
        res = call_notion_api(f"/databases/{sprints_db_id}/query", token, method="POST", payload=payload)
        all_sprints.extend(res.get("results", []))
        has_more = res.get("has_more", False)
        next_cursor = res.get("next_cursor")

    if not all_sprints:
        return None

    if sprint_number is None:
        for s in all_sprints:
            props = s.get("properties") or {} if isinstance(s, dict) else {}
            status_obj = (props.get("Status") or {}).get("status") or {} if isinstance(props.get("Status"), dict) else {}
            if status_obj.get("name") == "Active":
                return s
        return all_sprints[0]

    pattern = rf"\b{sprint_number}\b"
    for s in all_sprints:
        props = s.get("properties") or {} if isinstance(s, dict) else {}
        name_obj = props.get("Sprint Name") or {}
        title_list = name_obj.get("title") or [] if isinstance(name_obj, dict) else []
        title_text = "".join([(t.get("plain_text") or "") for t in title_list if isinstance(t, dict)])
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


def build_sprint_payload(
    sprint_page: dict,
    task_pages: list[dict],
    week_number: int = 5,
    checkpoint_target: str = "Checkpoint 2 (Minggu ke-8)",
) -> dict:
    """Build structured data payload for logbook report."""
    props = sprint_page.get("properties") or {}
    name_obj = props.get("Sprint Name") or {}
    title_list = name_obj.get("title") or [] if isinstance(name_obj, dict) else []
    sprint_name = "".join([(t.get("plain_text") or "") for t in title_list if isinstance(t, dict)]).strip() or "Sprint Aktif"

    dates_obj = props.get("Dates") or {}
    dates = dates_obj.get("date") if isinstance(dates_obj, dict) else {}
    if isinstance(dates, dict) and dates.get("start") and dates.get("end"):
        period = f"{format_date(dates['start'])} – {format_date(dates['end'])}"
    elif isinstance(dates, dict) and dates.get("start"):
        period = f"{format_date(dates['start'])} – Selesai"
    else:
        period = "18 Sep 2026 – 25 Sep 2026"

    activities = [normalize_task_to_activity(task) for task in task_pages]

    return {
        "week_number": week_number,
        "period": period,
        "sprint_name": sprint_name,
        "checkpoint_target": checkpoint_target,
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
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            logger.error("Typst compilation failed: %s", res.stderr.strip())
            return False
        logger.info("Successfully compiled %s to %s", main_typ_path, output_pdf_path)
        return True
    except subprocess.TimeoutExpired:
        logger.error("Typst compilation timed out after 60 seconds")
        return False
    except FileNotFoundError:
        logger.warning("Typst CLI not found in PATH. Skipping PDF compilation.")
        return False


def main() -> int:
    """CLI entry point for exporting sprint logbook."""
    parser = argparse.ArgumentParser(description="Export Notion Sprint to Typst Logbook")
    parser.add_argument("--sprint", type=int, default=1, help="Sprint number to export (default: 1)")
    parser.add_argument("--week", type=int, default=5, help="Academic week number (default: 5)")
    parser.add_argument("--checkpoint", type=str, default="Checkpoint 2 (Minggu ke-8)", help="Target milestone")
    parser.add_argument("--all-tasks", action="store_true", help="Include non-Done tasks")
    parser.add_argument("--no-compile", action="store_true", help="Skip PDF compilation")
    args = parser.parse_args()

    if args.sprint < 1:
        logger.error("--sprint must be a positive integer (>= 1), got %d", args.sprint)
        return 1
    if args.week < 1:
        logger.error("--week must be a positive integer (>= 1), got %d", args.week)
        return 1

    token = os.environ.get("NOTION_TOKEN") or os.environ.get("NOTION_API_KEY")
    tasks_db = os.environ.get("NOTION_TASKS_DB_ID")
    sprints_db = os.environ.get("NOTION_SPRINTS_DB_ID")

    if not token:
        logger.error("Missing NOTION_TOKEN or NOTION_API_KEY environment variable")
        return 1

    if not tasks_db:
        logger.error("Missing NOTION_TASKS_DB_ID environment variable")
        return 1

    if not sprints_db:
        logger.error("Missing NOTION_SPRINTS_DB_ID environment variable")
        return 1

    try:
        sprint = fetch_sprint_by_number(sprints_db, token, args.sprint)
    except (urllib.error.HTTPError, urllib.error.URLError) as err:
        logger.error("Failed to query sprint %d from Notion: %s", args.sprint, err)
        return 1

    if not sprint:
        logger.error("Sprint %d not found in Notion", args.sprint)
        return 1

    try:
        tasks = fetch_tasks_for_sprint(tasks_db, token, sprint["id"], only_done=not args.all_tasks)
    except (urllib.error.HTTPError, urllib.error.URLError) as err:
        logger.error("Failed to query tasks for sprint %d from Notion: %s", args.sprint, err)
        return 1

    logger.info("Fetched %d tasks for sprint %d", len(tasks), args.sprint)

    payload = build_sprint_payload(sprint, tasks, week_number=args.week, checkpoint_target=args.checkpoint)
    out_dir = f"logbook/sprint-{args.sprint:02d}"
    json_path, typ_path = generate_logbook_files(payload, out_dir)
    logger.info("Generated %s and %s", json_path, typ_path)

    if not args.no_compile:
        pdf_path = f"{out_dir}/logbook-sprint-{args.sprint:02d}.pdf"
        success = compile_typst(typ_path, pdf_path)
        if not success:
            logger.error("PDF compilation failed for %s", pdf_path)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())



