# Team Contribution Guide

## Automated Notion Sync

The Kanban board in Notion automatically tracks task progress:
- `[To Do] -> [In Progress]`: Triggers when pushing a working branch (`feat/**`, `fix/**`, `docs/**`, `refactor/**`) or commits containing a task ID.
- `[In Progress] -> [In Review]`: Triggers when opening a Pull Request linked to a task ID.
- `[In Review] -> [Done]`: Triggers when the Pull Request is merged into `main`.

## Branching

Work in branches created from `main`:
- Features: `feat/VALENIA-[id]-[short-description]`
- Bug fixes: `fix/VALENIA-[id]-[short-description]`
- Documentation: `docs/VALENIA-[id]-[short-description]`
- Refactoring: `refactor/VALENIA-[id]-[short-description]`

Example:
```bash
git checkout -b feat/VALENIA-06-router-skeleton
```

## Commits

Follow Conventional Commits with the Notion Task ID:
```text
<type>(<scope>): <subject> [#VALENIA-<id>]
```
Examples:
- `feat(auth): add login session guard [#VALENIA-08]`
- `fix(antrean): reset counter at midnight [#VALENIA-13]`

## Testing

Run unit tests locally before pushing changes or opening a PR:
```bash
python3 -m unittest discover tests -v
```

## Pull Requests

1. Open a PR using the repository template. Include `Closes #VALENIA-[id]` in the description.
2. Ensure code follows PSR-12 / PER-CS and contains no debug code (`var_dump`, `print_r`).
3. Run unit tests and verify against local database before requesting review.
