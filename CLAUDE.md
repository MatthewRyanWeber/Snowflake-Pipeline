# CLAUDE.md — Snowflake Pipeline Project

Working conventions for Claude Code on this repo. Read `PLAN.md` for the phased build plan.

## Build discipline
- Work **one phase at a time** (see `PLAN.md`). Build → verify against the phase's
  acceptance criteria → commit. Do not start the next phase until the current one passes.
- Every SQL deploy script must be **idempotent and re-runnable** — no manual clicks required
  to rebuild the environment from scratch.
- Prefer config-driven over hardcoded (table lists, mappings, schedules live in config files).

## Secrets & safety
- **No secrets in code or git history.** Credentials come from env vars or the SnowSQL config
  file only. Add anything sensitive to `.gitignore` before the first commit.
- Destructive operations (drops, overwrites, bulk loads) must support a `--dry-run` flag that
  reports intended changes without executing.
- All ingested PII/PHI is masked on load. This project uses fully synthetic data, but the
  masking controls are built and demonstrated as if it were real.

## Python standards (port from existing ETL framework)
- Structured logging, explicit versioning, `argparse` CLIs, file locking on shared resources.
- Incremental/idempotent loads (high-water-mark), safe to re-run without creating duplicates.
- Tests alongside code; keep them runnable with a single command.

## Honesty & rigor
- Flag assumptions with a `# ASSUMPTION:` comment rather than presenting a guess as settled.
- When something is uncertain, say so plainly — don't fill gaps with confident-sounding
  invention.
- If I push back on a technical point, hold your position if the evidence supports it rather
  than reflexively agreeing. Change your answer only when there's a real reason to.

## Hard rules
- **Never** include references to "Columbia University," "CUIT," or that institution anywhere
  — code, comments, templates, docs, or commit messages.

## Environment
- Development runs under **WSL2** with Claude Code. Assume a Linux shell for scripts; note any
  Windows-side steps explicitly (e.g. S3/SQS setup, SnowSQL config location).
