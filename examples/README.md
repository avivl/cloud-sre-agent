# Example configurations

Ready-to-run config files for the Cloud SRE Agent. Each validates against the
current config schema (`internal/config`). Point the agent at one with:

```
sre-agent run --config examples/<file>.yaml
```

All configs use the `SRE_` env-override convention (double underscore for
nesting, e.g. `SRE_LLM__MODEL=gemini-2.5-pro` overrides `llm.model`). API keys
and delivery tokens are NEVER stored in config — they are read from the
environment at startup and never logged.

| Example | Demonstrates | Credentials needed |
|---|---|---|
| `local-stub.yaml` | Fully offline spine: filesystem source -> `stub` LLM -> local delivery. The stub provider is NON-PRODUCTION and returns deterministic, schema-valid output so the pipeline runs end to end with no LLM. | None |
| `gemini-vertex.yaml` | Production default: Gemini via Vertex AI (BAA-eligible) with GitHub PR delivery and local Go patch validation. | GCP ADC (Vertex AI) + `GITHUB_TOKEN` |
| `multi-provider.yaml` | Primary + ordered fallbacks router and the `allow_external` HIPAA gate: Gemini primary, Gemini fallback, then external OpenAI and Anthropic fallbacks (gated). | GCP ADC; `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` only if the external fallbacks are reached |
| `pubsub-workerpool.yaml` | Production ingestion: Pub/Sub log source + Gemini on Vertex + Cloud Trace span export. | GCP ADC (Pub/Sub subscriber, Vertex AI, Cloud Trace write) |

## Credential and gate notes

- **Stub** (`local-stub.yaml`) is the only example that runs with zero setup. It
  is NON-PRODUCTION — output is canned, not reasoned. Do not ship it.
- **Vertex AI** is the HIPAA-covered Google backend and requires `project` +
  `location`. It is not an external third party, so it needs no opt-in.
- **`allow_external`** (`multi-provider.yaml`) is a mandatory, auditable opt-in
  for OpenAI/Anthropic — external services NOT covered by Google's BAA. Set
  `llm.allow_external: true` (as the example does) or `SRE_ALLOW_EXTERNAL_LLM=1`.
  Opting in presumes a signed BAA with the vendor and zero-data-retention
  enabled; the code cannot verify ZDR.
- **GitHub / GitLab tokens** are read from `GITHUB_TOKEN` / `GITLAB_TOKEN`.
- **Cloud Trace** (`pubsub-workerpool.yaml`) requires `tracing.project`; any span
  attribute the agent records must be sanitized first (raw log content can carry
  PHI). The agent records none today.
