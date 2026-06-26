# Architecture

The Cloud SRE Agent is a **ports and adapters** (hexagonal) Go daemon. The core
domain logic depends only on a small set of interfaces; every external system —
log source, LLM, source-control destination, code validator — is an adapter
behind one of those ports. The result is that the pipeline, detector, and
domain types know nothing about Gemini, Pub/Sub, or GitHub.

See also: [CONFIGURATION.md](CONFIGURATION.md), [DEPLOYMENT.md](DEPLOYMENT.md),
[HIPAA.md](HIPAA.md), and the project [README](../README.md).

## Data flow

```
                                  ┌──────────────────────────────────────────┐
  ingest.LogSource                │            pipeline.Pipeline              │
  ┌──────────┐   domain.LogEvent  │                                          │
  │ file     │──┐                 │  triage ──> analysis ──> remediation     │
  │ pubsub   │──┼──> detect ──────┼─> (llm.Provider via router)              │
  └──────────┘  │   .Detector     │       │                                  │
                │   (sliding      │   sanitizer on every prompt input        │
                │    window)      │       │                                  │
                │                 │   CodeValidator gates the patch          │
   domain.Incident ───────────────>      │                                  │
                                  │       v                                  │
                                  │   scm.PRTarget.Deliver ──> scm.Ref       │
                                  └──────────────────────────────────────────┘
                                          local / github / gitlab
```

`cmd/sre-agent` (`run` subcommand) constructs each adapter from config, wires
them through the ports, merges the source channels, and drives the consume loop
until the sources drain or a signal arrives.

## Ports

All four ports live next to (or in) the package that owns the seam:

| Port | Package | Contract |
|---|---|---|
| `LogSource` | `internal/ingest` | `Name()`, `Stream(ctx) (<-chan domain.LogEvent, error)`, `Close()`. `Stream` is single-use and closes its channel on drain, cancel, or `Close`. |
| `Provider` | `internal/llm` | `Name()`, `Generate(ctx, Request) (Response, error)`. `Request` may carry a JSON `Schema` + `SchemaName` for structured output. |
| `PRTarget` | `internal/scm` | `Name()`, `Deliver(ctx, Change) (Ref, error)`. A `Change` is one file patch + reviewer context + severity. |
| `CodeValidator` | `internal/pipeline` | `Validate(ctx, patch, lang) (ValidationResult, error)`. `ValidationResult{OK, Diagnostics}`. |

The pipeline additionally depends on a small `Sanitizer` interface (matching
`*security.Sanitizer`) so it depends on behavior, not a concrete struct.

## Domain types

`internal/domain` is dependency-free and the shared vocabulary:

- `LogEvent` — a normalized log line: id, timestamp, `Severity`, message,
  source, labels.
- `Severity` — ordered enum (`unknown` < `debug` < `info` < `warning` <
  `error` < `critical`). Marshals to/from lowercase string labels, and exposes
  a `JSONSchema()` so structured-output schemas advertise a string enum.
- `Incident` — a correlated cluster the detector judged anomalous: id, pattern,
  severity score in [0,1], affected services, sample events, summary.
- `TriageResult`, `Analysis`, `RemediationPlan` — the three pipeline-stage
  artifacts. Each carries a server-owned `IncidentID` (`json:"-"`) the pipeline
  sets after decoding, so it is never requested from the model.

## The detector

`internal/detect` is an in-memory, single-goroutine sliding-window threshold
detector. `Observe(LogEvent)` appends the event, advances a monotonic
"window now" clock (a stale- or future-dated event never rewinds it), evicts
events older than `Window`, and evaluates two triggers:

- **Error rate** — fraction of events at `SeverityError`+ over the window,
  once `MinEvents` is reached, crossing `ErrorRateThreshold`.
- **Critical burst** — count of `SeverityCritical` events reaching
  `CriticalCount` (zero disables this trigger).

When a trigger fires and the `Cooldown` since the last incident has elapsed, it
emits a `domain.Incident` with a blended severity score, the distinct affected
sources, and up to five highest-severity sample events. `DefaultConfig` is a
60s window, 5 min events, 50% error rate, 3 criticals, 60s cooldown; `New`
fills unset fields from those defaults. The agent constructs it with
`detect.New(detect.Config{})`, i.e. all defaults.

## The pipeline

`internal/pipeline` orchestrates triage -> analysis -> remediation, wired
entirely through ports: an `llm.Provider`, a `Sanitizer`, a `CodeValidator`
(defaults to `NoopValidator`), and a `PRTarget`. `Process(ctx, Incident)`:

1. Validates the incident and attaches a flow id (`flow-<incidentID>`) to the
   context via `obs`, so every stage's logs correlate.
2. **Triage** — classify category/severity, decide `Actionable`, confidence,
   reasoning, next actions. If not actionable, returns `ErrNotActionable` (a
   benign skip; later stages and delivery are not called).
3. **Analysis** — root cause + proposed fix + key points + confidence.
4. **Remediation** — a concrete `RemediationPlan` (target file, code patch,
   proposed fix, priority, estimated effort). Priority defaults from the
   incident severity score when the model leaves it unset; the plan is
   validated (`code_patch` and `target_file` required).
5. **Validate** — the `CodeValidator` gates the patch; a rejection returns
   `ErrPatchRejected` with diagnostics.
6. **Deliver** — the `PRTarget` applies the change and returns a `scm.Ref`.

Each stage builds a JSON schema for its target type with `llm.SchemaFor[T]()`
and attaches it to the request via `Request.WithSchema(schema, "<name>")`. The
provider returns structured output that `Response.Decode` unmarshals into the
domain type.

### Prompt construction (HIPAA-relevant)

`incidentPrompt` renders only the detector's synthetic, PHI-free fields —
pattern, severity score, summary, affected-service identifiers, and an aggregate
severity breakdown of sample events. Raw sample-event message bodies are
**never** included. Every system and user message is also run through the
sanitizer before it is sent. This is a hard gate; details in [HIPAA.md](HIPAA.md).

## The router

`internal/llm/router` is itself an `llm.Provider` composed of an ordered list:
primary first, then fallbacks. `Generate` tries each in turn and returns the
first success; if all fail it returns an aggregated error (`errors.Join`) naming
each provider. Context cancellation is checked between attempts. Because the
router satisfies the port, the pipeline is unaware a chain exists; its `Name()`
reads e.g. `router[gemini->openai]`. `cmd/sre-agent` builds the chain from
`llm.Providers()` (primary + configured fallbacks).

## LLM adapters and schema

`internal/llm` defines the `Provider` port and the `Request`/`Response`/`Usage`
value types. `SchemaFor[T]()` reflects a self-contained JSON schema for `T`
(inlined `$defs`, no `$schema`/`$id`) and forces `required` to cover every
property at every object level — OpenAI's strict `json_schema` mode demands it,
and Gemini/Anthropic tolerate it, so one schema serves all three. Adapters:
`gemini` (Vertex AI or Developer API backends), `openai`, `anthropic`, `ollama`
(local/self-hosted), and `stub` (offline, deterministic, NON-PRODUCTION).

## Runtime (worker pool)

`cmd/sre-agent`'s `run`:

1. Loads and validates config (`config.Load`).
2. Sets up observability (`obs.Setup`): slog logger + OTel tracer/meter +
   selected span exporter.
3. Builds the provider chain (`buildProvider` -> router), delivery target
   (`buildTarget`), sanitizer, validator (`buildValidator`), and the pipeline.
4. Builds the detector and the configured log sources (`buildSources`).
5. `consume` merges every source's event channel (`fanIn`), feeds each event to
   the detector, and runs `pipeline.Process` on each emitted incident.

Signals (SIGINT/SIGTERM) cancel the root context, which stops the sources and
unwinds the loop cleanly. A closed merged channel is disambiguated: a clean
drain returns nil (healthy exit), but a source that died with a terminal error
(e.g. Pub/Sub permission revoked, surfaced via an `Err()` method) returns a
non-nil error so the process exits non-zero rather than looking healthy to the
worker pool. Errors are logged with their type and a **sanitized** detail
string, never the raw error (which may have wrapped log content).

In production this binary runs as a Cloud Run worker pool with no HTTP ingress;
see [DEPLOYMENT.md](DEPLOYMENT.md).

## Package map

| Package | Role |
|---|---|
| `internal/domain` | Core types; no I/O, no provider coupling. |
| `internal/ingest` | `LogSource` port. Adapters: `ingest/file`, `ingest/pubsub`. |
| `internal/detect` | Sliding-window threshold detector. |
| `internal/pipeline` | Triage/analysis/remediation orchestration + `CodeValidator` port + `NoopValidator`. |
| `internal/llm` | `Provider` port, `Request`/`Response`, `SchemaFor`. Adapters: `llm/gemini`, `llm/openai`, `llm/anthropic`, `llm/ollama`, `llm/stub`; chain in `llm/router`. |
| `internal/scm` | `PRTarget` port. Adapters: `scm/local`, `scm/github`, `scm/gitlab`. |
| `internal/validate` | Local Go-toolchain `CodeValidator`. |
| `internal/security` | Sanitizer (secret/PII redaction). |
| `internal/config` | koanf-based typed config + validation gates. |
| `internal/obs` | slog + OTel + flow-id propagation + log redaction. |
| `internal/resilience` | Retry / circuit-breaker helpers. |
| `cmd/sre-agent` | Entrypoint and spine wiring. |
