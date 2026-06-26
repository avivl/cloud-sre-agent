# Configuration

The agent loads a YAML file (default `config.yaml`, override with `--config`),
applies `SRE_`-prefixed environment overrides, and validates the result before
starting. This reference is derived directly from `internal/config`.

See also: [ARCHITECTURE.md](ARCHITECTURE.md), [DEPLOYMENT.md](DEPLOYMENT.md),
[HIPAA.md](HIPAA.md), and the [README](../README.md).

## Loading order

1. Built-in defaults (`config.Default`) seed scalar fields.
2. The YAML file is loaded (if a path is given) and overlays the defaults.
3. `SRE_`-prefixed environment variables overlay the file.
4. The merged config is validated; an invalid config fails startup.

### Environment overrides

Every key is overridable by an env var: prefix `SRE_`, uppercase, and `__`
(double underscore) for nesting.

| Env var | Maps to |
|---|---|
| `SRE_LLM__MODEL` | `llm.model` |
| `SRE_LLM__BACKEND` | `llm.backend` |
| `SRE_LLM__PROJECT` | `llm.project` |
| `SRE_LLM__LOCATION` | `llm.location` |
| `SRE_OUTPUT__DIR` | `output.dir` |
| `SRE_TARGET` | `target` |

### Secrets and gates that are *not* config keys

These are read from the environment at startup, never stored in YAML, never
logged:

| Env var | Purpose |
|---|---|
| `GEMINI_API_KEY` (or whatever `llm.api_key_env` names) | Gemini Developer API key (gemini-api backend). |
| `OPENAI_API_KEY` | OpenAI key (openai provider). |
| `ANTHROPIC_API_KEY` | Anthropic key (anthropic provider). |
| `GITHUB_TOKEN` | GitHub access token (github target). |
| `GITLAB_TOKEN` | GitLab access token (gitlab target). |
| `SRE_ALLOW_NON_BAA=1` | Opt in to the non-BAA Gemini Developer API (alternative to `llm.allow_non_baa`). |
| `SRE_ALLOW_EXTERNAL_LLM=1` | Opt in to external providers openai/anthropic (alternative to `llm.allow_external`). |

## `sources` (required, at least one)

A list of log sources. Each entry needs a `type`.

| Field | Type | Applies to | Required | Notes |
|---|---|---|---|---|
| `type` | string | all | yes | `file` or `pubsub`. |
| `path` | string | `file` | yes (file) | File path or glob to tail. |
| `project_id` | string | `pubsub` | yes (pubsub) | GCP project. |
| `subscription_id` | string | `pubsub` | yes (pubsub) | Pub/Sub pull subscription. |

Validation: a missing `type` and unknown types are errors; `file` requires
`path`; `pubsub` requires both `project_id` and `subscription_id`.

## `llm` (primary provider + fallbacks)

The primary provider is expressed through the top-level `llm.*` fields; an
ordered list of `fallbacks` is tried after the primary (and preceding
fallbacks) fail.

| Field | Type | Default | Notes |
|---|---|---|---|
| `provider` | string | `gemini` | Primary kind: `gemini`, `openai`, `anthropic`, `ollama`, or `stub`. Required. |
| `model` | string | `gemini-2.5-flash` | Model name. Required. |
| `backend` | string | `vertex` | gemini only: `vertex` (BAA-eligible) or `gemini-api` (consumer Developer API). |
| `project` | string | — | gemini/vertex: GCP project (required for vertex). |
| `location` | string | `us-central1` | gemini/vertex: GCP region (required for vertex). |
| `api_key_env` | string | `GEMINI_API_KEY` | gemini-api: env var holding the key. |
| `allow_non_baa` | bool | `false` | Opt in to the non-BAA `gemini-api` backend. |
| `base_url` | string | — | openai/anthropic: override the API host. Ignored for gemini. |
| `host` | string | `http://localhost:11434` | ollama: daemon base URL. Ignored for other kinds. |
| `allow_external` | bool | `false` | Opt in to external providers (openai/anthropic) anywhere in the chain. |
| `fallbacks` | list | — | Ordered fallback providers (see below). |

### Provider kinds and their gates

| Kind | Backend / fields | Gate |
|---|---|---|
| `gemini` | `backend: vertex` needs `project` + `location`. `backend: gemini-api` reads `api_key_env`. | gemini-api is refused unless `allow_non_baa` or `SRE_ALLOW_NON_BAA=1`. |
| `openai` | `model`, optional `base_url`; key from `OPENAI_API_KEY`. | Refused unless `allow_external` or `SRE_ALLOW_EXTERNAL_LLM=1`. |
| `anthropic` | `model`, optional `base_url`; key from `ANTHROPIC_API_KEY`. | Same `allow_external` gate. |
| `ollama` | `model`, optional `host`; no key. | Exempt from the external gate. |
| `stub` | `model` (ignored); no key/host/network. | Exempt. NON-PRODUCTION. |

Validation enforces: a known kind, a non-empty model, the kind-specific
requirements above, and the BAA / external gates. The gates are fail-closed —
selecting `gemini-api`, `openai`, or `anthropic` without the matching opt-in
fails startup with an explanatory error.

### `llm.fallbacks[]`

Each fallback is a full provider entry.

| Field | Applies to | Notes |
|---|---|---|
| `kind` | all | `gemini`, `openai`, `anthropic`, `ollama`, or `stub`. |
| `model` | all | Required. |
| `backend`, `project`, `location`, `api_key_env`, `allow_non_baa` | gemini | Mirror the primary's gemini fields. |
| `base_url` | openai/anthropic | Optional host override. |
| `host` | ollama | Optional daemon URL. |

The `allow_external` opt-in is a single `llm`-level flag and covers external
providers wherever they appear (primary or any fallback).

## `output`

| Field | Type | Default | Notes |
|---|---|---|---|
| `dir` | string | `./out` | Where local-target artifacts are written. Required (non-empty). |

## `target`

The delivery target selector.

| Value | Behavior | Requires |
|---|---|---|
| `local` (default) | Write patch + JSON sidecar under `output.dir`. | — |
| `github` | Open a pull request. | `github.owner`, `github.repo`; `GITHUB_TOKEN`. |
| `gitlab` | Open a merge request. | `gitlab.project`; `GITLAB_TOKEN`. |

### `github` (used when `target: github`)

| Field | Type | Default | Notes |
|---|---|---|---|
| `owner` | string | — | Repo owner (user/org). Required. |
| `repo` | string | — | Repo name. Required. |
| `base_branch` | string | `main` | Branch PRs target and branch from. |

### `gitlab` (used when `target: gitlab`)

| Field | Type | Default | Notes |
|---|---|---|---|
| `project` | string | — | `group/repo` path or numeric project ID. Required. |
| `base_branch` | string | `main` | Branch MRs target and branch from. |
| `base_url` | string | — | API base URL for self-managed GitLab; empty means gitlab.com. |

## `validator`

Gates an LLM-generated patch before delivery.

| Value | Behavior |
|---|---|
| `none` (default) | Accept every patch (`NoopValidator`). |
| `local` | Validate Go patches with the local toolchain: parse, gofmt, go vet, in a throwaway temp module. Unsupported languages are skipped (not an error). |

## `log`

| Field | Type | Default | Notes |
|---|---|---|---|
| `level` | string | `info` | `debug`, `info`, `warn`, or `error`. |
| `format` | string | `json` | `json` or `text`. |

## `tracing`

Selects the OpenTelemetry span exporter.

| Field | Type | Default | Notes |
|---|---|---|---|
| `exporter` | string | `none` | `none` (record, don't export), `stdout` (write to the log writer), or `cloudtrace` (Google Cloud Trace). |
| `project` | string | — | Required for the `cloudtrace` exporter. |

HIPAA note: spans bypass the log redactor, so any span attribute the agent
records must be sanitized first — raw log content, prompts, and error strings can
carry PHI. (The agent records no PHI-bearing span attributes today.) See
[HIPAA.md](HIPAA.md).

## Minimal offline config

```yaml
sources:
  - type: file
    path: ./testdata/sample.log
llm:
  provider: stub
  model: stub
output:
  dir: ./out
target: local
validator: none
```

This is `examples/local-stub.yaml` — no credentials, no network. More worked
configs live in `examples/`.
