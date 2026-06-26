# Cloud SRE Agent

An LLM-driven SRE agent, written in Go. It ingests logs, detects incidents from
the log stream, and runs each incident through a triage -> analysis ->
remediation pipeline backed by a large language model. The output is a concrete
code patch, delivered either as a local file, a GitHub pull request, or a GitLab
merge request.

The agent is built for a HIPAA-sensitive environment: prompt input is sanitized
before it leaves the process, and the choice of LLM provider is fail-closed
behind explicit, auditable gates (see [HIPAA posture](docs/HIPAA.md)).

## What it does

```
log source ──> detector ──> pipeline (triage -> analysis -> remediation) ──> delivery
  (file,        (sliding-     (LLM provider, sanitizer, code validator)        (local patch,
   pubsub)       window                                                         GitHub PR,
                 thresholds)                                                    GitLab MR)
```

1. A **log source** streams normalized log events (`domain.LogEvent`).
2. The **detector** accumulates events over a sliding time window and emits a
   `domain.Incident` when an error-rate or critical-burst threshold is crossed.
3. The **pipeline** runs the incident through three LLM stages — triage
   (classify, decide if actionable), analysis (root cause), remediation
   (concrete code patch). Every prompt input is sanitized first; the generated
   patch is gated by a code validator before delivery.
4. The **delivery target** writes the patch locally, or opens a real PR / MR.

## Architecture

The codebase is **ports and adapters**. The core (`domain`, `detect`,
`pipeline`) depends only on interfaces — `ingest.LogSource`, `llm.Provider`,
`scm.PRTarget`, `pipeline.CodeValidator` — never on a concrete provider. Each
external system is an adapter behind one of those ports. `cmd/sre-agent`
hand-wires the spine at startup; there is no DI framework. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

### Package map

| Package | Role |
|---|---|
| `internal/domain` | Core types: `LogEvent`, `Incident`, `TriageResult`, `Analysis`, `RemediationPlan`. No I/O, no provider coupling. |
| `internal/ingest` | `LogSource` port + adapters: `file` (tail a file/glob), `pubsub` (pull Cloud Logging entries). |
| `internal/detect` | In-memory sliding-window threshold detector. |
| `internal/pipeline` | Triage -> analysis -> remediation orchestration + the `CodeValidator` port. |
| `internal/llm` | `Provider` port, `Request`/`Response` types, JSON-schema reflection (`SchemaFor`); adapters `gemini`, `openai`, `anthropic`, `ollama`, `stub`, and a `router` for primary + fallback chains. |
| `internal/scm` | `PRTarget` port + adapters: `local`, `github`, `gitlab`. |
| `internal/validate` | Local Go-toolchain `CodeValidator` (parse, gofmt, go vet). |
| `internal/security` | Sanitizer: redacts secrets/PII before any text leaves the process. |
| `internal/config` | Typed config (koanf): YAML + `SRE_`-prefixed env overrides + validation gates. |
| `internal/obs` | Structured logging (slog), OpenTelemetry tracing, flow-id propagation, log redaction. |
| `internal/resilience` | Retry / circuit-breaker helpers. |
| `cmd/sre-agent` | Entrypoint: the `run` subcommand wires the spine and drives the consume loop. |

## Quickstart — offline, no credentials

The `stub` LLM provider runs the whole pipeline with no API keys, no GCP
project, and no network calls. It returns deterministic, schema-valid canned
output — **NON-PRODUCTION**, but enough to exercise the spine end to end.

`examples/local-stub.yaml` wires a filesystem source -> `stub` provider ->
local delivery. Its source path is `./testdata/sample.log` (relative to the
working directory), so make that fixture available and run:

```sh
mkdir -p testdata out
cp internal/ingest/file/testdata/sample.log testdata/sample.log
go run ./cmd/sre-agent run --config examples/local-stub.yaml
```

The agent starts, tails the log file, and runs the consume loop. It exits
cleanly on Ctrl-C (SIGINT) or SIGTERM. Patches for incidents that pass triage
are written under `output.dir` (`./out`).

> Note: the detector uses production-leaning default thresholds (5+ events, and
> either a 50% error rate or 3 criticals over a 60s window). A short fixture may
> not cross them; append more error/critical lines to the log to trigger an
> incident.

## Build and run

```sh
make build      # build ./bin/sre-agent
make test       # go test ./...
make vet        # go vet ./...
make lint       # golangci-lint run
make cover      # tests with coverage, fails below 80%
make run        # go run ./cmd/sre-agent run --config config.yaml
```

Run a specific config directly:

```sh
go run ./cmd/sre-agent run --config examples/gemini-vertex.yaml
```

## Configuration

Config is a YAML file (default `config.yaml`), with every key overridable by an
`SRE_`-prefixed environment variable (`__` maps to nesting, e.g.
`SRE_LLM__MODEL=gemini-2.5-pro` -> `llm.model`). API keys and tokens are **never**
stored in config — they are read from named environment variables at startup and
never logged.

Worked examples live in `examples/`:

- `local-stub.yaml` — offline, no credentials (stub provider).
- `gemini-vertex.yaml` — Gemini via Vertex AI + GitHub PR delivery.
- `multi-provider.yaml` — primary + fallback chain with external providers.
- `pubsub-workerpool.yaml` — Pub/Sub ingestion + Cloud Trace export.

Full field reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## LLM providers

The primary provider plus an ordered fallback chain is selected in config; the
router tries each in turn and returns the first success.

| Kind | Backend / notes | HIPAA gate |
|---|---|---|
| `gemini` | Default. `backend: vertex` (Vertex AI, BAA-eligible) or `gemini-api` (consumer Developer API). | Vertex is the covered default. The `gemini-api` backend is refused unless `allow_non_baa` / `SRE_ALLOW_NON_BAA=1`. |
| `openai` | OpenAI; key from `OPENAI_API_KEY`. | External third party — refused unless `allow_external` / `SRE_ALLOW_EXTERNAL_LLM=1`. |
| `anthropic` | Anthropic; key from `ANTHROPIC_API_KEY`. | External third party — same `allow_external` gate. |
| `ollama` | Local / self-hosted model server; no API key. | Exempt from the external gate (content stays on infrastructure you control). |
| `stub` | NON-PRODUCTION, offline; no key, host, or network call. | Exempt — discloses nothing. |

The `allow_external` gate is fail-closed: selecting `openai` or `anthropic` as
primary **or** fallback is rejected at startup unless you explicitly opt in. See
[docs/HIPAA.md](docs/HIPAA.md).

## Delivery targets

| Target | Behavior | Required config / env |
|---|---|---|
| `local` (default) | Write the patch plus a JSON metadata sidecar under `output.dir`. | — |
| `github` | Open a real pull request. | `github.owner`, `github.repo`; token from `GITHUB_TOKEN`. |
| `gitlab` | Open a real merge request. | `gitlab.project`; token from `GITLAB_TOKEN`; optional `gitlab.base_url` for self-managed. |

## GCP deployment

The agent ships as a Cloud Run **worker pool** — no HTTP ingress. It pulls error
logs from a Pub/Sub pull subscription (fed by a Cloud Logging sink) and runs the
consume loop. `infra/gcloud_setup.sh` provisions the sink, topic, subscription,
service account, and Artifact Registry repo; `deploy.sh` builds, pushes, and
deploys the worker pool. Full walkthrough: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## HIPAA posture

- **Sanitizer gate**: every prompt input is run through the sanitizer before it
  leaves the process; the incident prompt deliberately omits raw log bodies and
  forwards only synthetic, PHI-free fields.
- **BAA gates** (fail-closed): Gemini via Vertex AI is the covered default; the
  consumer Gemini API and the external providers (OpenAI, Anthropic) are refused
  at startup unless explicitly opted in.

Details and the host-trust caveat for `ollama`: [docs/HIPAA.md](docs/HIPAA.md).

## Status

Built (phases #17–#22):

- Ports: `ingest.LogSource`, `llm.Provider`, `scm.PRTarget`,
  `pipeline.CodeValidator`.
- LLM adapters: `gemini` (Vertex + Developer API), `openai`, `anthropic`,
  `ollama`, `stub`; router for primary + fallback chains.
- Ingest adapters: `file`, `pubsub`.
- Delivery adapters: `local`, `github`, `gitlab`.
- Code validator: `none` (no-op) and `local` (Go toolchain).
- Detector, pipeline, typed config with HIPAA gates, observability
  (slog + OpenTelemetry, Cloud Trace exporter), `cmd/sre-agent` wiring.
- GCP worker-pool deploy (`deploy.sh`, `infra/gcloud_setup.sh`,
  `infra/terraform/`).

Deferred:

- ADK Go agent harness; Gemini Agent Platform.
- Cloud Run Sandbox code validator (run/compile patches in a sandbox).
- ML-heavy / pattern-based detection beyond the threshold detector.
- Cost / cache / strategy-based model selection.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — ports & adapters, pipeline,
  detector, router, runtime, package map.
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) — full `config.yaml` reference.
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — Cloud Run worker-pool deploy.
- [docs/HIPAA.md](docs/HIPAA.md) — sanitizer and BAA gates, host-trust caveat.

## License

MIT. See [LICENSE](LICENSE).
