# Dogfooding the Cloud SRE Agent (fully local, no credentials)

This directory runs the agent's entire spine end to end on your machine with
**no GCP, no API keys, and no network access**:

```
generator -> log file -> filesystem source -> threshold detector
          -> pipeline (triage -> analysis -> remediation, stub provider)
          -> local-patch delivery (writes a patch + JSON sidecar)
```

The LLM stages use the **stub** provider: a NON-PRODUCTION, offline provider
that returns deterministic, schema-valid canned output and makes no network
call. That lets the pipeline flow to a delivered remediation artifact with zero
setup.

## Run it

From the repository root:

```sh
make dogfood
```

That target:

1. Builds the agent (`bin/sre-agent`) and the log generator
   (`bin/dogfood-generator`).
2. Generates a deterministic ERROR/CRITICAL burst into
   `dogfood/out/dogfood.log` (8 JSON-lines records — enough to trip the
   detector's default 5-event / 50%-error-rate threshold).
3. Runs `sre-agent run --config dogfood/config.yaml` until a remediation patch
   appears under `dogfood/out/` (or a 30s timeout).
4. Prints the produced patch file and exits `0`.

Output artifacts land in `dogfood/out/`:

- `dogfood.log` — the generated input log.
- `stub.txt.patch` — the delivered remediation patch (the stub plan targets
  `stub.txt`).
- `stub.txt.meta.json` — the delivery metadata sidecar (file path, description,
  severity, timestamp).

## What's here

| File | Purpose |
|---|---|
| `config.yaml` | Wires the filesystem source + `stub` provider + `local` target. No creds. |
| `generator/generator.go` | Library: deterministic ERROR-burst JSON-lines generation (seeded by index, not time/random). |
| `cmd/generator/main.go` | Thin binary wrapper: `generator -file <path> -count <n>`. |
| `dogfood_test.go` | Hermetic integration test driving the whole flow in-process; runs in `go test ./...`. |

## Run just the integration test

```sh
go test ./dogfood/...
```

It is deterministic, offline, and sub-second — it is intentionally **not**
build-tagged, so it also runs as part of `go test ./...`.

## Swapping the stub for a real provider

Change the `llm` block in `dogfood/config.yaml`. The rest of the config is
unchanged.

**Ollama** (local/self-hosted; no API key, no external-disclosure gate):

```yaml
llm:
  provider: ollama
  model: llama3.1
  host: http://localhost:11434   # optional; this is the default
```

Then `ollama serve` and `ollama pull llama3.1` before running.

**Gemini via Vertex AI** (BAA-eligible default; needs a GCP project + ADC):

```yaml
llm:
  provider: gemini
  model: gemini-2.5-flash
  backend: vertex
  project: my-gcp-project
  location: us-central1
```

Run `gcloud auth application-default login` first. External third-party
providers (`openai`, `anthropic`) additionally require an explicit opt-in
(`allow_external: true` or `SRE_ALLOW_EXTERNAL_LLM=1`) — see the root
`config.yaml` for the full provider-kind documentation.
