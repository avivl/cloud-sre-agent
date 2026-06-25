# Research: Rewriting the SRE Agent in Go

_Date: 2026-06-25 | Requested by: Aviv | Decision needed by: open_

## TL;DR

- The current Python agent is ~124K LOC in the package (+52K tests) and carries ~35% bloat (duplicate `*_original`/`enhanced_*`/`*_v2` files, three stacked LLM abstraction layers). The irreducible domain logic is ~8-12K lines. A Go rewrite is justified primarily as a **deletion exercise**, not a translation.
- **Recommended stack:** Go, thin **ports-and-adapters** core on official SDKs, Gemini-first via `google.golang.org/genai`, resilience via `failsafe-go`, deployed as a **Cloud Run worker pool** (GA, pull-based Pub/Sub, always-on). Multi-cloud is achieved by keeping cloud calls behind ports from day one.
- **Harness:** Do NOT build the spine on a framework. Hand-roll the daemon + ports; pull in **Google ADK for Go** *behind a port* only for the triage->analysis->remediation orchestration if it genuinely earns it. Skip langchaingo (effectively unmaintained) and Eino (still 0.x).

## Decision Required

Choose the language, runtime, library stack, and whether to adopt an agent harness for a from-scratch rewrite of the SRE agent. GCP-first, designed so other clouds can be added later without a rewrite.

Locked by Aviv up front: **Go**; drivers = de-bloat + modernize LLM stack + production-grade on GCP + multi-cloud-ready; runtime = recommend in research.

## Scope

**In:** Architecture map of the existing code (keep/simplify/drop), Go ecosystem & harness selection (verified June 2026), target architecture, runtime/deployment recommendation, library stack.

**Out:** Migration/port plan (dropped per Aviv — this is a clean rewrite). Detailed cost modelling. Non-GCP cloud implementations (designed-for, not built now).

## Findings

### 1. What the current system actually is

End-to-end flow (`main.py`):

```
ingestion adapters (PubSub / CloudLogging / K8s / FS / AWS)
  -> LogManager (async fan-in, backpressure, health)
    -> pattern_detector (time windows -> thresholds -> classify -> confidence)
      -> Triage agent  (fast LLM classify)
      -> Analysis agent (deep LLM root-cause + validation)
      -> Remediation agent (LLM code-gen + validate)
        -> source_control (GitHub/GitLab PR) or LocalPatchManager
  -> metrics + structured logging (flow_id tracking)
```

Keep/simplify/drop verdict from the architecture deep-dive:

| Module | LOC | Verdict | Notes |
|---|---|---|---|
| agents | ~9.5K | KEEP | The triage/analysis/remediation pipeline — core value |
| llm | ~33.7K | SIMPLIFY (~30%) | 3 stacked abstraction layers (mirascope + litellm + direct), duplicate `cost_*`, `service`/`enhanced_service`/`optimized_service`. Compress to ~8 files |
| ml | ~17.8K | KEEP | Code-generation workflow; mostly clean. ML-heavy parts are sidecar candidates |
| pattern_detector | ~4.4K | KEEP | Tight, well-scoped anomaly detection |
| source_control | ~22.5K | KEEP (~85%) | GitHub/GitLab/local PR delivery; `enhanced_*_provider` pairs are bloat |
| ingestion | ~6.4K | KEEP | Clean adapter layer — the multi-cloud seam already exists here |
| core | ~21K | KEEP | DI, resilience, logging — shrinks hard in Go (stdlib + failsafe replace most of it) |
| config | ~4.5K | SIMPLIFY (~30%) | Over-modeled Pydantic; ~3-4 files in Go |
| security | ~2.3K | KEEP | PII/secret sanitization — keep as a hard guard |
| resilience | ~1.7K | KEEP-as-config | Becomes thin failsafe-go wrappers |
| metrics | ~0.5K | DROP/INLINE | Replaced by OTel |

GCP coupling is concentrated in three places: VertexAI/`aiplatform.init()` in main + LLM factory, Pub/Sub + Cloud Logging in ingestion adapters. All already sit behind interfaces — the rewrite formalizes that into explicit ports.

### 2. The harness decision (lead finding)

A long-running SRE daemon's hard problems are resilience, observability, provider failover, and graceful degradation — none of which a prompt-orchestration framework solves. Frameworks add an abstraction tax (their retry/streaming/tool model fights your circuit breaker and OTel spans) and lock-in (Genkit flows and ADK agents are not portable to each other).

Verified Go options (June 2026):

- **Google ADK for Go** — `google.golang.org/adk` (repo `google/adk-go`). v1.4.0 (~May 2026), ~8k stars, Google-maintained. Code-first multi-agent: `llmagent`, `runner`, `session`, MCP tools, A2A protocol. Gemini/Vertex first-class via `google.golang.org/genai`; other providers not first-class. **Best fit if the pipeline is modeled as cooperating agents.** Adopt behind a port.
- **Firebase Genkit (Go)** — `github.com/firebase/genkit/go`. Stable v1.x line. Flows + dotprompt structured output + OTel-native + `googlecloud` plugin to Cloud Trace/Monitoring/Logging. Caveat: Google only explicitly stamps "GA" on the JS/TS SDK; Go is production-grade-but-follower (new APIs land in JS/TS first). Strong alternative if you want flows + RAG + eval in one package.
- **Eino** — `github.com/cloudwego/eino` (ByteDance). Best pure-Go orchestration tech, ~12k stars, but **still v0.x** (no API-stability guarantee) and Ark/Chinese-docs-centric. Skip unless 0.x churn is acceptable.
- **langchaingo** — `github.com/tmc/langchaingo`. **Avoid for production:** stuck at v0.1.14 (Oct 2024), no 2026 releases, stalled governance. Prototype-only.

**Recommendation:** thin SDKs + your own ports as the spine. The durable contract is yours:

```go
type LLMProvider interface { Generate(ctx context.Context, req Request) (Response, error) }
type LogSource   interface { Stream(ctx context.Context) (<-chan LogEvent, error) }
type PRTarget    interface { OpenPR(ctx context.Context, c Change) (PRRef, error) }
```

If the triage->analysis->remediation pipeline grows genuinely multi-agent (handoffs, tool loops, sub-agents), wrap **ADK Go's `Runner` as an implementation of a `Pipeline` port** — ripping it out later is then a one-adapter change. Keep your resilience + OTel wrapping the provider adapters *underneath* the harness.

### 3. Target architecture

```
cmd/sre-agent/main.go            # cobra wiring, config load, DI by hand
internal/
  domain/      # LogEvent, Incident, TriageResult, Analysis, RemediationPlan
  ingest/      # LogSource port + adapters: cloudlogging, pubsub(v2), file  (k8s/aws later)
  detect/      # windows -> thresholds -> classify -> confidence
  pipeline/    # orchestrator: triage->analyze->remediate (optional ADK Runner behind port)
  llm/         # LLMProvider port + adapters (gemini/openai/anthropic/ollama) + router/cost/cache
  scm/         # PRTarget port + adapters: github, gitlab, local
  resilience/  # thin failsafe-go policy wrappers
  security/    # PII/secret sanitization (hard guard)
  config/      # koanf load + validate
  obs/         # slog + otel + cloud trace exporter
(optional) sidecar-ml/           # Python: ML-heavy pattern detection behind gRPC, if needed
```

LOC target: **~8-12K Go** vs 124K Python. Multi-cloud = add an adapter under `ingest/`, `llm/`, or `scm/`; the core never changes.

### 4. Runtime / deployment recommendation

**Cloud Run worker pool (GA 2026-04-15), pull-based Pub/Sub subscription.** This supersedes the earlier "Cloud Run service + Pub/Sub push" idea. Reasons:

- The agent is a non-HTTP, always-on background *consumer* of logs (Pub/Sub pull / Cloud Logging stream) — exactly the workload worker pools are built for. No HTTP server bolted onto a daemon.
- ~40% cheaper than request-driven services/jobs for continuous workloads.
- Always-on, so the pattern detector's in-memory sliding-window state survives (no scale-to-zero cold-start loss). Autoscale on Pub/Sub queue depth via CREMA/KEDA. (If windows must survive scale-out across instances, externalize to Memorystore/Redis; not needed for single-instance MVP.)
- GA — safe as the production foundation, unlike the preview features below.

**Escalate to GKE only when** you need in-cluster/node-level log access, an operator/controller pattern watching k8s resources, or horizontal scale with shared window state. Don't start there.

If a Python ML sidecar is kept (see Go weaknesses), it is a *separate* Cloud Run service behind a gRPC port.

#### Newer Cloud Run / Gemini agent features — verdicts

Scored against this agent (a shared, always-on background log-consumer that generates code remediations). Throughline: worker pools is the spine; everything else stays *behind a port* so a preview graduating or an org platform decision is an additive adapter, never a re-architecture.

| Feature | Verdict | Where it fits |
|---|---|---|
| **Worker pools** | **Adopt (GA)** | The runtime — replaces the push-service idea |
| **Sandboxes** (in-container code exec) | Adopt behind a `CodeValidator` port (preview) | Remediation step: run untrusted LLM-generated patches in isolation (compile / `go test` / lint). Until GA, the port's adapter is a local container exec |
| **Gemini Enterprise Agent Platform** (Registry / Identity / Gateway / Observability) | **Defer** | Real wins (Agent Identity for an agent that opens PRs / acts on infra; observability) but couples identity+obs to the Gemini platform — direct tension with the multi-cloud / no-lock-in goal. The OTel + scoped-service-account baseline gives ~80% portably. Adopt only if the org standardizes on it |
| **Instances** ("personal agents", singleton) | **Skip** | Wrong abstraction — built for per-user personal agents with their own identity; this is a shared production service. Worker pools cover the always-on-singleton need |
| **SSH + dev sync** | Optional / skip | Dev-debug convenience, not architecture. SSH is a handy incident-poking tool; dev sync targets interpreted languages (hot-reload synced source) and buys little for a compiled Go binary. Both private preview |

## Tradeoffs

| | Go (recommended) | Python (modern rewrite) |
|---|---|---|
| De-bloat potential | High — single binary, stdlib replaces `core/` | High but familiar gravity pulls bloat back |
| LLM/ML ecosystem | Good for daemon; weaker for ML/embeddings/RAG | Best-in-class (instructor, pydantic-ai, litellm) |
| Long-running concurrency | Native strength | Weaker (asyncio + GIL) |
| Deploy/ops | Single static binary, fast cold start | Heavier image, slower start |
| Multi-cloud abstraction | Clean interfaces, no framework lock-in | Same pattern, achievable |
| HIPAA/PII control | Explicit, compile-time typed boundaries | Mature libs, runtime-typed |

## Recommendation

**Confidence: High.** Rewrite in Go as a ports-and-adapters daemon on thin official SDKs; deploy on a **Cloud Run worker pool** (GA) with pull-based Pub/Sub; adopt Google ADK for Go *behind a port* only if the pipeline is genuinely multi-agent; run LLM-generated remediation code in a **Cloud Run Sandbox behind a `CodeValidator` port** (defer Gemini Agent Platform, skip Instances/dev-sync); keep ML-heavy pattern detection as an optional Python sidecar behind a gRPC port. Treat the rewrite as a chance to drop ~90% of the line count.

### Verified library stack (June 2026)

| Concern | Primary | Notes |
|---|---|---|
| Gemini/Vertex | `google.golang.org/genai` | GA. One client, both backends via `ClientConfig.Backend`. Supersedes deprecated `vertexai/genai` (removal ~2026-06-24) |
| OpenAI | `github.com/openai/openai-go/v3` | `/v3` suffix required |
| Anthropic | `github.com/anthropics/anthropic-sdk-go` | GA, no suffix |
| Ollama | `github.com/ollama/ollama/api` | Pre-1.0; pulls server module |
| Structured output | native SDK JSON-schema + `github.com/invopop/jsonschema` | instructor-go only if a cross-provider wrapper is wanted |
| Cloud Logging | `cloud.google.com/go/logging` | stable |
| Pub/Sub | `cloud.google.com/go/pubsub/v2` | **v2 — v1 deprecated (fixes only thru 2026-12-31)** |
| Secrets | `cloud.google.com/go/secretmanager/apiv1` | |
| Resilience | `github.com/failsafe-go/failsafe-go` | one stack (retry+CB+RL+timeout). Pre-1.0; fallback: `sony/gobreaker/v2` + `cenkalti/backoff/v6` + `golang.org/x/time/rate` |
| Config | `github.com/knadh/koanf/v2` | lean; viper if batteries-included wanted |
| CLI | `github.com/spf13/cobra` | urfave/cli **v3** as lighter alt |
| Observability | `log/slog` + `go.opentelemetry.io/otel` + `github.com/GoogleCloudPlatform/opentelemetry-operations-go/exporter/trace` | OTel traces/metrics GA; logs beta |
| Git | `github.com/go-git/go-git/v5` | v6 still alpha — stay v5 |
| GitHub | `github.com/google/go-github/v88/github` | current major v88; pin it |
| GitLab | `gitlab.com/gitlab-org/api/client-go/v2` | **xanzy/go-gitlab archived Dec 2024**; this is the official successor (note: gitlab.com host) |

## Open Questions

- Is the ML-heavy pattern detection (clustering/embeddings/time-series anomaly) actually used today, or is the `pattern_detector/` threshold logic enough? Determines whether the Python sidecar is needed at all. _Owner: Aviv._
- Is the pipeline truly multi-agent (worth ADK Go) or a fixed 3-step chain (plain functions)? Determines harness adoption. _Owner: Aviv._
- Which LLM providers must ship in v1 vs later? (Gemini is certain; OpenAI/Anthropic/Ollama optional.) _Owner: Aviv._
- HIPAA: confirm no PHI flows through prompts/logs; the `security/` sanitizer becomes a hard, tested boundary in the rewrite. _Owner: Aviv._

## If We Proceed

Plan mode would scope a thin vertical slice first: one `LogSource` (filesystem), one `LLMProvider` (Gemini via genai), the 3-step pipeline as plain functions, one `PRTarget` (local patch), wrapped in failsafe + slog/OTel, deployed to Cloud Run. That proves the spine end-to-end at ~2K LOC before any second adapter or harness is added. Everything else is additive adapters.

## Subagent Sources

- Architecture deep-dive (Explore agent): module-by-module keep/simplify/drop, end-to-end flow, GCP coupling, ~65% essential / ~35% bloat estimate.
- Go ecosystem + harness research (general-purpose agent, web + Context7 verified June 2026): harness comparison (ADK Go / Genkit / Eino / langchaingo), verified import paths and version/deprecation facts for the library stack, Go-vs-Python weakness analysis.
