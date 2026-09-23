# Team Contribution Guide

## Branching

Work in branches created from `main`:
- Features: `feat/VALENIA-[id]-[short-description]`
- Fixes: `fix/VALENIA-[id]-[short-description]`

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

## Pull Requests

1. Open a PR using the repository template.
2. Ensure code follows PSR-12 and contains no debug code (`var_dump`, `print_r`).
3. Manually test against local database before requesting review.
