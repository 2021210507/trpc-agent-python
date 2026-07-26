---
name: code-review
description: Deterministic, sandbox-ready Python code-review workflow for issue #92.
---

# Code Review

Use this Skill to parse one controlled review input and run the deterministic
rule pack. It is deliberately not an arbitrary-command interface: callers may
select only a `script_id` declared in `scripts/manifest.json`, with the
structured arguments accepted by that entry.

## Workflow

1. Stage the controlled input as `work/inputs/diff.json` in an isolated
   workspace. The input object contains `source_kind` and a unified `diff`.
2. Run `parse_diff` when a metadata-only parse summary is required. It writes
   `out/parsed.json` and never copies code lines into that result.
3. Run `run_checks` to execute the shared deterministic rule modules. It
   writes `out/findings.json`; finding text is redacted before it is written.
4. The host must apply Filter governance before execution, then apply its
   second redaction and final-output scan before report or database storage.

## Rule pack

The rule documents in `rules/` describe supported detections and their blind
spots. The scripts import the single implementations from `scripts/lib/`; no
host-side duplicate rule pack is permitted.

## Invocation contract

The manifest pins each entrypoint by SHA-256, requires no network access, and
sets a 30-second / 1 MiB per-script budget. Production execution uses the SDK
container runtime after Filter approval. Explicit local execution is a
development or evaluation fallback and must be reported as a warning by the
host pipeline; `dry-run` changes model behavior only, never sandbox policy.
