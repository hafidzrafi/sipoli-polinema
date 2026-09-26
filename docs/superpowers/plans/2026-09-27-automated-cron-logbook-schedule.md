# Automated Cron Logbook Schedule & Active Sprint Auto-Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate weekly sprint logbook extraction and PDF compilation via GitHub Actions `schedule` cron trigger, enabling dual-mode execution (automated weekly cron + manual `workflow_dispatch`) with automatic Notion Active Sprint detection and semester academic week calculation.

**Architecture:** Extend `export_logbook.py` with an auto-detection engine (`fetch_active_sprint` & `calculate_academic_week`) so the script can execute without human-supplied sprint/week numbers. Upgrade `.github/workflows/export-logbook.yml` to support both `schedule` (Sunday 23:00 WIB / 16:00 UTC) and `workflow_dispatch` (with optional overrides), uploading the generated PDF artifact via `actions/upload-artifact@v7`.

**Tech Stack:** Python 3.13 (stdlib only: `urllib.request`, `argparse`, `datetime`, `re`), Typst CLI 0.15.1, GitHub Actions (`workflow_dispatch`, `schedule` POSIX cron, `actions/checkout@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7`, `typst-community/setup-typst@v5`).

**Spec:** Issue VALENIA-12 & PBL Semester 3 Polinema Logbook Specification.

---

## Global Constraints

- Python Standard Library only — zero third-party pip dependencies in production scripts (`.github/scripts/`).
- English only for code, comments, docstrings, variable names, and commit messages.
- Backward compatibility: Existing manual CLI usage (`--sprint 1 --week 5`) must continue to work with identical output.
- All commits must follow Conventional Commits format and include the issue tag `[#VALENIA-12]`.
- All tests must run with `python3 -m unittest discover tests -v` with zero external network I/O (all API responses mocked).

---

## File Structure

```text
.github/
├── scripts/
│   ├── export_logbook.py        # Add auto-detect active sprint, week calculation, and optional CLI args
│   └── sync_notion.py          # Existing Notion API client & event parser (unchanged)
└── workflows/
    ├── export-logbook.yml       # Add schedule cron trigger, optional inputs, and conditional CLI flags
    └── notion-sync.yml          # Existing task sync workflow (unchanged)
tests/
└── test_export_logbook.py       # Add unit tests for auto-sprint, auto-week, and CLI without args
```

---

## Task Breakdown

### Task 1: Active Sprint Auto-Detection Engine

**Files:**
- Modify: `.github/scripts/export_logbook.py`
- Test: `tests/test_export_logbook.py`

**Interfaces:**
- Consumes: `call_notion_api(endpoint, token, method, payload)` from `sync_notion`
- Produces: `extract_sprint_number_from_title(title: str) -> int | None`
- Produces: `fetch_active_sprint(sprints_db_id: str, token: str) -> tuple[dict | None, int]`

- [ ] **Step 1: Write the failing unit tests for sprint number extractor and active sprint query**

```python
    def test_extract_sprint_number_from_title(self):
        self.assertEqual(export_logbook.extract_sprint_number_from_title("Sprint 1: Core Infrastructure"), 1)
        self.assertEqual(export_logbook.extract_sprint_number_from_title("Sprint 04 - Checkpoint 2"), 4)
        self.assertEqual(export_logbook.extract_sprint_number_from_title("Sprint 12"), 12)
        self.assertIsNone(export_logbook.extract_sprint_number_from_title("Backlog Exploration"))

    @patch("export_logbook.call_notion_api")
    def test_fetch_active_sprint_finds_active_status(self, mock_api):
        mock_api.return_value = {
            "results": [
                {
                    "id": "sprint-active-id",
                    "properties": {
                        "Sprint Name": {"title": [{"plain_text": "Sprint 2: Architecture"}]},
                        "Status": {"status": {"name": "Active"}},
                    },
                }
            ],
            "has_more": False,
        }
        sprint, sprint_num = export_logbook.fetch_active_sprint("sprints-db", "token")
        self.assertIsNotNone(sprint)
        self.assertEqual(sprint["id"], "sprint-active-id")
        self.assertEqual(sprint_num, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_export_logbook.py -k test_extract_sprint_number_from_title`  
Expected: FAIL with `AttributeError: module 'export_logbook' has no attribute 'extract_sprint_number_from_title'`

- [ ] **Step 3: Implement minimal code in `.github/scripts/export_logbook.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover tests -v`  
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/export_logbook.py tests/test_export_logbook.py
git commit -m "feat(export): add active sprint auto-detection engine [#VALENIA-12]"
```

---

### Task 2: Academic Week Number & Checkpoint Milestone Calculator

**Files:**
- Modify: `.github/scripts/export_logbook.py`
- Test: `tests/test_export_logbook.py`

**Interfaces:**
- Produces: `calculate_academic_week(reference_date: datetime | None = None, sprint_number: int | None = None) -> int`
- Produces: `derive_checkpoint_target(week_number: int) -> str`

- [ ] **Step 1: Write the failing unit tests for academic week calculation**

```python
    def test_calculate_academic_week_from_sprint_number(self):
        # In Polinema Semester 3, Sprint 1 corresponds to Week 5
        self.assertEqual(export_logbook.calculate_academic_week(sprint_number=1), 5)
        self.assertEqual(export_logbook.calculate_academic_week(sprint_number=2), 6)
        self.assertEqual(export_logbook.calculate_academic_week(sprint_number=4), 8)

    def test_derive_checkpoint_target(self):
        self.assertEqual(export_logbook.derive_checkpoint_target(5), "Checkpoint 2 (Minggu ke-8)")
        self.assertEqual(export_logbook.derive_checkpoint_target(8), "Checkpoint 2 (Minggu ke-8)")
        self.assertEqual(export_logbook.derive_checkpoint_target(9), "Checkpoint 3 (Minggu ke-12)")
        self.assertEqual(export_logbook.derive_checkpoint_target(13), "Checkpoint 4 (Minggu ke-16)")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_export_logbook.py -k test_calculate_academic_week`  
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Implement minimal code in `.github/scripts/export_logbook.py`**

```python
SEMESTER_START_DATE = datetime(2026, 8, 24)  # Polinema Semester 3 start (Monday Week 1)


def calculate_academic_week(
    reference_date: datetime | None = None,
    sprint_number: int | None = None,
) -> int:
    """Calculate academic week number from sprint offset or current date."""
    if sprint_number is not None and sprint_number >= 1:
        # Academic calibration: Sprint 1 starts at Week 5
        return sprint_number + 4

    ref = reference_date or datetime.now()
    delta_days = (ref - SEMESTER_START_DATE).days
    week = max(1, (delta_days // 7) + 1)
    return min(16, week)


def derive_checkpoint_target(week_number: int) -> str:
    """Derive official checkpoint milestone from academic week number."""
    if week_number <= 8:
        return "Checkpoint 2 (Minggu ke-8)"
    if week_number <= 12:
        return "Checkpoint 3 (Minggu ke-12)"
    return "Checkpoint 4 (Minggu ke-16)"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover tests -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/export_logbook.py tests/test_export_logbook.py
git commit -m "feat(export): add academic week and checkpoint milestone calculator [#VALENIA-12]"
```

---

### Task 3: CLI Argument Optionality & Auto-Resolution

**Files:**
- Modify: `.github/scripts/export_logbook.py:main`
- Test: `tests/test_export_logbook.py:TestCliMain`

**Interfaces:**
- Changes CLI flags:
  `--sprint` defaults to `None` (auto-detects Active Sprint if omitted)
  `--week` defaults to `None` (auto-calculates week if omitted)
  `--checkpoint` defaults to `None` (auto-derives milestone from week if omitted)

- [ ] **Step 1: Write failing CLI tests for auto-resolution when flags are omitted**

```python
    @patch("export_logbook.compile_typst", return_value=True)
    @patch("export_logbook.generate_logbook_files", return_value=("data.json", "main.typ"))
    @patch("export_logbook.fetch_tasks_for_sprint", return_value=[])
    @patch("export_logbook.fetch_active_sprint")
    def test_main_auto_resolves_active_sprint_and_week(self, mock_active, mock_tasks, mock_gen, mock_compile):
        mock_active.return_value = ({"id": "active-sprint-id", "properties": {}}, 1)
        with patch.dict(os.environ, {
            "NOTION_TOKEN": "token-xyz",
            "NOTION_TASKS_DB_ID": "db-tasks",
            "NOTION_SPRINTS_DB_ID": "db-sprints",
        }, clear=True):
            with patch("sys.argv", ["export_logbook.py"]):
                code = export_logbook.main()
                self.assertEqual(code, 0)
                mock_active.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_export_logbook.py -k test_main_auto_resolves_active_sprint_and_week`  
Expected: FAIL

- [ ] **Step 3: Update `main()` in `.github/scripts/export_logbook.py`**

Refactor `main()` argument parser to treat `--sprint`, `--week`, and `--checkpoint` as optional, resolving them through `fetch_active_sprint()`, `calculate_academic_week()`, and `derive_checkpoint_target()`.

- [ ] **Step 4: Run full test suite to verify all tests pass**

Run: `python3 -m unittest discover tests -v`  
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/export_logbook.py tests/test_export_logbook.py
git commit -m "feat(export): support zero-arg auto-resolution in CLI entrypoint [#VALENIA-12]"
```

---

### Task 4: GitHub Actions Workflow Dual-Trigger (Cron Schedule + Manual)

**Files:**
- Modify: `.github/workflows/export-logbook.yml`

**Interfaces:**
- Trigger 1: `schedule: - cron: '0 16 * * 0'` (Sunday 23:00 WIB / 16:00 UTC)
- Trigger 2: `workflow_dispatch` with optional `sprint` and `week` inputs
- Execution step: Pass `--sprint` and `--week` flags conditionally only when user explicitly inputs them.

- [ ] **Step 1: Update `.github/workflows/export-logbook.yml`**

Add `schedule` block, make `sprint` and `week` inputs optional (default empty), and structure the bash invocation:

```yaml
on:
  workflow_dispatch:
    inputs:
      sprint:
        description: "Sprint number to export (leave empty to auto-detect Active Sprint)"
        required: false
        type: string
      week:
        description: "Academic week number (leave empty to auto-calculate)"
        required: false
        type: string
      all_tasks:
        description: "Include non-Done tasks"
        required: false
        default: false
        type: boolean

  schedule:
    # Run every Sunday at 16:00 UTC (23:00 WIB) before Monday academic checkpoint
    - cron: '0 16 * * 0'
```

- [ ] **Step 2: Validate YAML syntax and linting**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/export-logbook.yml'))"`  
Expected: Clean exit (code 0)

- [ ] **Step 3: Test local CLI execution in auto-mode**

Run: `NOTION_TOKEN="..." NOTION_TASKS_DB_ID="..." NOTION_SPRINTS_DB_ID="..." python3 .github/scripts/export_logbook.py`  
Expected: Successfully detects `Sprint 1: Core Infrastructure`, week 5, and compiles PDF.

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/export-logbook.yml
git commit -m "ci(workflow): add automated weekly cron schedule to logbook export [#VALENIA-12]"
git push origin feat/VALENIA-12-automate-logbook
```

---

## Self-Review Checklist

1. **Spec Coverage:**
   - [x] Dual-mode triggering (manual `workflow_dispatch` + automated `schedule` cron).
   - [x] Auto-detection of Active Sprint from Notion Sprints database.
   - [x] Academic week number calculation with Polinema semester offset.
   - [x] Checkpoint milestone determination.
   - [x] 100% backward compatibility for manual overrides.
2. **Zero Dependency Footprint:**
   - [x] Python standard library only (`argparse`, `datetime`, `re`, `urllib`).
   - [x] Pinned toolchain (`typst-version: '0.15.1'`, `actions/*@v7`).
3. **Failure Isolation:**
   - [x] If no sprint is active, graceful fallback to earliest sprint.
   - [x] Non-interactive execution in CI does not crash on missing inputs.
