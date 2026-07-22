# Git & Release Workflow — Follow Strictly

## 1. Branching
- Never commit or push directly to `main`.
- All work (features, bug fixes) happens on a dedicated branch off `main`:
  - `feature/<short-name>` for new features
  - `fix/<short-name>` for bug fixes
- Branch names should be short, lowercase, hyphenated.

## 2. During development
- Keep commits scoped to the branch's purpose.
- Test manually as we go, but do not consider the branch "done" until Section 3 is complete.

## 3. Before opening a Pull Request
Before I say "create a PR" / "let's PR this", you must:
1. Check whether test cases exist for the feature/fix being touched, **and** for any existing related features that currently lack tests. If missing, write them.
2. Run the full test suite locally and show me the results.
3. If GitHub Actions CI is configured, confirm the workflow/build passes (check `.github/workflows/`, and if possible, check the latest run status) before proceeding.
4. Only after tests + build are green, open the PR.
5. Do not silently skip any of steps 1–4. If something can't be run (e.g., no CI configured yet), tell me explicitly instead of assuming it's fine.

## 4. After PR approval & merge
- Once a PR is approved and merged into `main`, **ask me for confirmation before deleting the feature branch** (both local and remote, if applicable). Never delete it automatically.
- Wait for my explicit "yes, delete it" before running the delete.

## 5. General rule of thumb
- Test coverage first, PR second, merge third, branch cleanup last (with my confirmation).
- If any step is ambiguous or CI/test setup is missing in a given repo, flag it and ask rather than guessing.
