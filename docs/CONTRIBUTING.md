# Contributing to circlelib

## Before you start
- Strategic context: [STRATEGY.md](STRATEGY.md)
- Roadmap and priorities: [ROADMAP.md](ROADMAP.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

## Local setup

```sh
git clone https://github.com/rlaope/circle.git
cd circle
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m circlelib run examples/circles.crl --check
```

## Picking work

- Look for issues labelled `good first issue` first.
- Issues are scoped to milestones (`v0.2`, `v0.3`, …) — pick one in the
  current milestone unless you have a strong reason.
- Comment on the issue to claim it before you start.

## Making changes

- Add tests next to your code change. Parser/evaluator changes need
  pytest cases; new primitives need at least one example `.crl`.
- Run `pytest` and `python -m circlelib run examples/circles.crl --check`
  before opening a PR.
- One feature per PR. No drive-by refactors.
- Code, comments, and identifiers are English. Commit messages are
  English. Korean only inside user-facing docs that are explicitly
  Korean.
- Commits must not contain `Co-Authored-By`, `Generated-with`, or
  similar AI-tool attribution.

## Pull request

- Title: `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`.
- Describe **what** changed and **why** in 2–4 lines. Link the issue.
- If you add a new primitive or grammar rule, add a screenshot or `.crl`
  snippet to the PR body.

## Asking questions

Open a Discussion or comment on an existing issue. New issues should be
either bug reports or roadmap-aligned feature proposals — not "what
should I work on" (that's what `good first issue` exists for).
