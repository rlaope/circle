# CLAUDE.md — circlelib

A pointer file for Claude Code sessions. Heavy context lives in `docs/`;
this file is kept short on purpose so it never bloats the prompt window.

## What this project is

A tiny custom DSL (`.crl`) for declaring 3D scenes, with a Lark grammar,
a tree-walking evaluator, and a ModernGL renderer. See
[README.md](README.md) for the public-facing intro.

## Where to look

- **Language reference (source of truth for `.crl` syntax)** → [docs/LANGUAGE.md](docs/LANGUAGE.md)
- **Strategy / market analysis** → [docs/STRATEGY.md](docs/STRATEGY.md)
- **Roadmap / milestones / 90-day plan** → [docs/ROADMAP.md](docs/ROADMAP.md)
- **Architecture / extension points** → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Contributor workflow** → [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)

Read the relevant doc(s) before doing non-trivial work; do not infer
context from this file alone.

## Working on a roadmap issue (closure protocol)

A roadmap issue is "done" only when **all** of these are true:

1. `gh issue view <N> --repo rlaope/circle` — read scope + acceptance.
2. Implement the change. New grammar / AST / primitive ships with at
   least one parser test, one evaluator test, and one example `.crl`.
3. **If the change touches user-visible syntax or semantics, update
   [docs/LANGUAGE.md](docs/LANGUAGE.md) in the same commit.**
4. Run `bash scripts/verify.sh` — it must exit 0.
5. Commit with `feat:` / `fix:` / `docs:` prefix, body ends with
   `Closes #<N>`. No `Co-Authored-By`, no Claude attribution.
6. `git push origin main:init` (the protected default branch).
7. `gh issue close <N> --comment "<short summary>"`.

## Working principles in this repo

- Code, comments, identifiers, commits, issues, and PRs are in **English**.
- Commit messages must not contain `Co-Authored-By`, `Generated-with`,
  or any AI attribution.
- When the user writes in Korean, reply in Korean using **존댓말**.
- New AST node / primitive / grammar rule ships with both example `.crl`
  and pytest cases in the same PR.
- Prefer editing existing files. Do not introduce architecture beyond
  what the current task needs.
- Avoid backwards-compatibility shims; the codebase is pre-v1.0.

## Quick commands

```sh
pip install -e ".[dev]"
pytest
python -m circlelib run examples/circles.crl
python -m circlelib run examples/circles.crl --check   # headless
```

## Things that are *not* on the roadmap

Do not propose: precision CAD (CadQuery territory), full PBR / film
rendering, GUI editors, or backwards-compatibility hacks. See
[docs/STRATEGY.md](docs/STRATEGY.md) §3 "Explicitly not targeting".
