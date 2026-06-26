# HIPAA posture

The agent processes operator log data that may contain PHI, and it sends prompt
content to an LLM. Two mechanisms keep that defensible: a **sanitizer gate** on
everything that leaves the process, and **fail-closed BAA gates** on the choice
of LLM provider. This document describes what the code actually enforces — and
where the operator, not the code, owns the risk.

See also: [ARCHITECTURE.md](ARCHITECTURE.md), [CONFIGURATION.md](CONFIGURATION.md),
[DEPLOYMENT.md](DEPLOYMENT.md), and the [README](../README.md).

## 1. Sanitize-before-LLM gate

`internal/security` provides a `Sanitizer` that redacts secrets and PII from any
text before it crosses a trust boundary. The pipeline applies it to **every**
system and user message before calling the provider. It is deliberately
conservative and prefers over-redaction to leaking.

It redacts:

- **Structured sensitive fields** — `key: value` / `key=value` shapes for names
  like `password`, `token`, `api_key`, `authorization`, `secret`, `ssn`, `dob`,
  `mrn` (medical record number), and more. The key is preserved; the value is
  replaced with `[REDACTED]`.
- **Provider credential shapes** — OpenAI `sk-` keys, Google `AIza…` keys,
  GitHub `ghp_`/`github_pat_` tokens, Slack tokens, AWS access key IDs, GCP
  OAuth client IDs, JWTs, `Bearer`/`Basic` header values, and PEM private-key
  blocks.
- **PHI in prose** — labeled MRN / member / patient identifiers, dates of birth,
  email addresses, and other PII patterns.

### Defense in depth: the prompt omits raw log bodies

The sanitizer is the *second* line of defense, not the first. The pipeline's
`incidentPrompt` builds the LLM prompt from only the detector's **synthetic,
PHI-free fields**: incident id, pattern, severity score, summary,
affected-service identifiers, and an aggregate severity *count* of the sample
events. The raw message/source bodies of the sample log events are deliberately
**never** included — the synthetic pattern/summary already convey what the model
needs. So even before the sanitizer runs, no free-text log content reaches the
model. The outer `Sanitize` call then catches anything that slips through.

### Logs and traces

Errors are logged with their type plus a **sanitized** detail string, never the
raw error (which may have wrapped log content). The `obs` package's slog handler
redacts sensitive keys, but OpenTelemetry spans bypass that handler: any span
attribute the agent records **must** be passed through the sanitizer first, since
raw log content, prompts, and error strings can carry PHI. This is a developer
requirement, not an automatically enforced gate; the agent currently records no
PHI-bearing span attributes.

## 2. BAA gates on the LLM provider (fail-closed)

The choice of provider determines who sees prompt content. All gates are
enforced at startup in `config.Validate`; an un-opted-in selection fails to
start with an explanatory error.

### Gemini via Vertex AI — the covered default

`provider: gemini`, `backend: vertex` is the safe default. Vertex AI is
BAA-eligible (HIPAA-covered under Google's BAA). It requires `project` and
`location`. No opt-in needed.

### Gemini Developer API — non-BAA, gated

`backend: gemini-api` is the **consumer** Gemini Developer API, which is **not**
covered by Google's BAA. It is refused unless you explicitly opt in via
`llm.allow_non_baa: true` or `SRE_ALLOW_NON_BAA=1`. The opt-in is an auditable
acknowledgement that the consumer API is not HIPAA-covered.

### OpenAI / Anthropic — external third parties, gated

`openai` and `anthropic` are external third parties not covered by Google's BAA.
Selecting either — as **primary or as any fallback** — is refused unless you opt
in via `llm.allow_external: true` or `SRE_ALLOW_EXTERNAL_LLM=1`. The opt-in is an
auditable acknowledgement that prompt content (which may include log data) is
disclosed to that provider, and it **presumes** you have:

- a signed BAA with the vendor, **and**
- zero-data-retention (ZDR) enabled on the account.

The code cannot verify ZDR — that part is on you.

### Ollama and stub — local posture

- `ollama` is a local / self-hosted model server. Prompt content stays on
  infrastructure you control, so it is **exempt** from the external-disclosure
  gate and needs no API key.
- `stub` is the NON-PRODUCTION, offline provider: it makes no network call and
  discloses nothing, so it is **exempt** too. It returns canned, meaningless
  output — never use it in production.

## The host-trust caveat (`ollama`)

The exemption for `ollama` rests on one assumption the **code cannot verify**:
that `llm.host` resolves to infrastructure within your HIPAA control boundary.
Pointing an `ollama` provider at a third-party "Ollama-compatible" endpoint
reintroduces external disclosure of PHI-bearing prompt content **without** the
`allow_external` gate firing — because to the agent it still looks local. Keep
the Ollama host inside your trust boundary; this is an operator responsibility,
not an enforced one.

## Summary

| Provider / backend | Disclosure | Gate |
|---|---|---|
| gemini + vertex | Google, BAA-covered | none (default) |
| gemini + gemini-api | Google consumer API, not BAA | `allow_non_baa` / `SRE_ALLOW_NON_BAA=1` |
| openai | External third party | `allow_external` / `SRE_ALLOW_EXTERNAL_LLM=1` |
| anthropic | External third party | `allow_external` / `SRE_ALLOW_EXTERNAL_LLM=1` |
| ollama | Local — *if the host is yours* | exempt (host trust is on you) |
| stub | None (offline) | exempt (NON-PRODUCTION) |

Secrets and tokens (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GITHUB_TOKEN`, `GITLAB_TOKEN`) are never stored in config and never logged —
they are read from named environment variables at startup.
