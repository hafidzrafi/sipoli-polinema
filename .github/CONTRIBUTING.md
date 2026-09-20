# Team Contribution Guide

## Branching

Work in branches created from `main`:
- Features: `feat/SIPOLI-[id]-[short-description]`
- Fixes: `fix/SIPOLI-[id]-[short-description]`

Example:
```bash
git checkout -b feat/SIPOLI-06-router-skeleton
```

## Commits

Follow Conventional Commits with the Notion Task ID:
```text
<type>(<scope>): <subject> [#SIPOLI-<id>]
```
Examples:
- `feat(auth): add login session guard [#SIPOLI-08]`
- `fix(antrean): reset counter at midnight [#SIPOLI-13]`

## Pull Requests

1. Open a PR using the repository template.
2. Ensure code follows PSR-12 and contains no debug code (`var_dump`, `print_r`).
3. Manually test against local database before requesting review.
