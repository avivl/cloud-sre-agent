# Plan: SRE Agent — Go Rewrite (MVP vertical slice)

_Date: 2026-06-25 | Linear: TBD (created on build approval) | Research ref: tasks/research-go-rewrite.md_

## Goal

Replace the ~124K-LOC Python agent with a thin, ports-and-adapters Go daemon, and prove the spine end-to-end with a runnable MVP: a filesystem log source flows through a triage -> analysis -> remediation pipeline (Gemini) and emits a local patch — wrapped in resilience, structured logging, and tracing. No GCP/cloud adapters and no agent harness in this slice.

## Done Criteria

Mechanical checklist — each verifiable without judgment:
- [ ] Builds: `go build ./...`
- [ ] Vets clean: `go vet ./...`
- [ ] Lints clean: `golangci-lint run`
- [ ] Tests pass: `go test ./...`
- [ ] Coverage >= 80%: `go test -cover ./... | awk '...'` (gate in CI; LLM calls mocked via the `LLMProvider` port)
- [ ] E2E smoke: `go test ./internal/pipeline -run TestE2E` feeds a sample `.log` and asserts a remediation artifact is written (mocked LLM, deterministic)
- [ ] Manual run: `./sre-agent run --config config.yaml` against `testdata/sample.log` produces a patch file in the output dir
- [ ] No Python source remains in the working tree (`find . -name '*.py' -not -path './tasks/*'` is empty); git history retains it
- [ ] Secret/PII sanitizer runs on every prompt input before it leaves the process (unit-tested)

## Scope

**In:** Go module scaffolding + Python teardown; `domain` types; ports (`LogSource`, `LLMProvider`, `PRTarget`, `CodeValidator`); config (koanf); MVP adapters (filesystem source, Gemini via `google.golang.org/genai`, local-patch target); minimal threshold-based detector; resilience (failsafe-go); security sanitizer; obs (slog + OTel); `cmd/sre-agent` wiring; e2e smoke test.

**Out (deferred to later phases, tracked as roadmap below):** Pub/Sub / Cloud Logging adapters; Cloud Run worker-pool deploy; GitHub/GitLab PR adapters; ADK Go harness; Cloud Run Sandbox `CodeValidator`; Gemini Agent Platform; ML-heavy pattern detection / Python sidecar; OpenAI/Anthropic/Ollama providers; cost/cache/strategy model selection.

## PR Strategy

- [x] Sequential regular PRs (no `av` stack — not requested). Three independently reviewable PRs; tests live in the same PR as the code they cover.
  - PR 1: scaffold + Python teardown + `domain` + ports + config + obs skeleton — `aviv/<TEAM-ID>-go-scaffold`
  - PR 2: MVP adapters (filesystem, Gemini, local-patch) + resilience + security sanitizer — `aviv/<TEAM-ID>-go-adapters`
  - PR 3: pipeline + threshold detector + `cmd/sre-agent` wiring + e2e smoke — `aviv/<TEAM-ID>-go-pipeline`
- Worktrees via `wt` (one per branch). Stacking (`av`) available if you'd prefer it — say so and I'll restructure.

## Steps

### PR 1 — Scaffold, teardown, domain, ports
- [ ] 1. Remove Python source from working tree; keep `docs/`, `tasks/`, `infra/`, `examples/*.yaml` as reference — `gemini_sre_agent/`, `tests/`, root `*.py` (~delete) (git history preserves)
- [ ] 2. `go mod init`, repo layout `cmd/sre-agent/`, `internal/{domain,ingest,detect,pipeline,llm,scm,resilience,security,config,obs}` — `go.mod`, dir skeleton
- [ ] 3. Tooling: `.golangci.yml`, `Makefile` (build/test/lint/cover targets), update `.github/workflows/` to Go CI — (~120 lines)
- [ ] 4. `internal/domain`: `LogEvent`, `Incident`, `TriageResult`, `Analysis`, `RemediationPlan` + tests — `internal/domain/*.go` (~250 lines)
- [ ] 5. Ports as interfaces: `LogSource`, `LLMProvider`, `PRTarget`, `CodeValidator` — `internal/*/port.go` (~80 lines)
- [ ] 6. `internal/config`: koanf YAML load + validate + tests — `internal/config/*.go` (~200 lines)
- [ ] 7. `internal/obs`: slog + OTel tracer/meter setup (no exporter yet, stdout) + flow_id propagation — `internal/obs/*.go` (~150 lines)

### PR 2 — MVP adapters + resilience + security
- [ ] 8. `internal/ingest/file`: `FileSystemSource` implementing `LogSource` (tail/watch, encoding) + tests — (~250 lines)
- [ ] 9. `internal/llm/gemini`: `GeminiProvider` implementing `LLMProvider` via `google.golang.org/genai` with JSON-schema structured output (`invopop/jsonschema`) + tests (mock transport) — (~300 lines)
- [ ] 10. `internal/scm/local`: `LocalPatch` implementing `PRTarget` (writes patch files) + tests — (~150 lines)
- [ ] 11. `internal/resilience`: failsafe-go retry + circuit-breaker + rate-limiter policy wrappers, applied to the Gemini adapter + tests — (~180 lines)
- [ ] 12. `internal/security`: secret/PII sanitizer (regex + structured field redaction) run on prompt inputs + tests — (~200 lines)

### PR 3 — Pipeline, detector, wiring, e2e
- [ ] 13. `internal/detect`: minimal threshold detector (error-rate / severity window) producing `Incident` + tests — (~250 lines)
- [ ] 14. `internal/pipeline`: triage -> analyze -> remediate as plain functions wired through ports, flow_id tracing + unit tests — (~300 lines)
- [ ] 15. `cmd/sre-agent`: cobra root + `run` command, config load, hand-wired DI, source -> detect -> pipeline -> patch loop — (~250 lines)
- [ ] 16. E2E smoke test: sample `.log` + mocked `LLMProvider` -> asserts patch artifact; `testdata/` fixtures — `internal/pipeline/e2e_test.go` (~200 lines)

## Roadmap (post-MVP, separate plans)

1. **GCP ingestion + deploy** — Pub/Sub-pull `LogSource`, Cloud Logging source; deploy to Cloud Run **worker pool** (GA); OTel Cloud Trace exporter.
2. **Real remediation delivery** — GitHub (`go-github/v88`) + GitLab (`gitlab.com/gitlab-org/api/client-go/v2`) `PRTarget` adapters; Cloud Run **Sandbox** `CodeValidator` (behind the port; preview).
3. **Multi-provider** — OpenAI / Anthropic / Ollama `LLMProvider` adapters + router + cost/cache (decide if model-selection strategy is worth porting).
4. **Harness decision point** — adopt **ADK Go** behind a `Pipeline` port iff the pipeline becomes genuinely multi-agent; else keep plain functions.
5. **ML pattern detection** — decide threshold-only (Go) vs Python sidecar behind gRPC (only if real clustering/anomaly ML is in use).

## Risk Flags

- HIPAA surface: **YES** — logs may contain PHI. Mitigation: `internal/security` sanitizer is a hard, tested gate on every prompt input before it leaves the process to any LLM provider; no raw log payloads in traces/logs (redact in `obs`). Run `hipaa-review` before PR.
- Migration required: No — clean rewrite, replace-in-place; no data migration.
- Reversibility: **Medium** — Python removed from working tree but fully recoverable from git history (commit `d56eaa7` and prior). MVP is additive Go; revert = `git revert`/checkout.

## Open Questions

<!-- Empty — repo layout (replace-in-place) and MVP scope (thin local slice) resolved at the plan gate. The harness/sidecar/multi-provider decisions are deliberately deferred to roadmap phases and do not block the MVP. -->

## Review

- Built via multi-agent workflow on branch `aviv/go-rewrite-mvp` (8 agents: scaffold -> 5 parallel adapters -> pipeline -> verify-fix loop).
- Result (independently re-verified, not just self-reported): `go build`/`go vet`/`golangci-lint`(0 issues)/`go test` all green; 91% overall coverage; e2e smoke passes; binary + CLI work. ~2.7K src + 2.2K test LOC vs 124K+52K Python (~27x smaller).
- What changed from the plan: planned 3 sequential PRs, executed as one branch (review/PR split still TODO). Deleted dead Python `examples/*.py` (referenced the removed package) beyond the planned teardown list.
- Known gaps: `cmd/sre-agent` 0% unit coverage (thin wiring); real-LLM manual run unproven (needs Gemini/Vertex creds) — only mocked e2e verified.
- Not yet committed (awaiting go-ahead). Pre-PR gates (code-review, simplify, hipaa-review) not yet run.
- Lessons captured in tasks/lessons.md: no (no corrections this run)
