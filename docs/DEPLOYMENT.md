# Deployment

The Cloud SRE Agent runs on GCP as a Cloud Run **worker pool**. A worker pool
has no HTTP ingress — it pulls work and runs the agent loop until SIGTERM, which
is exactly the agent's shape: it pulls error logs from a Pub/Sub subscription
and processes incidents. This is why deployment uses
`gcloud beta run worker-pools deploy`, not `gcloud run deploy`.

See also: [ARCHITECTURE.md](ARCHITECTURE.md), [CONFIGURATION.md](CONFIGURATION.md),
[HIPAA.md](HIPAA.md), and the [README](../README.md).

## The log flow

```
your services ──> Cloud Logging
                      │  sink filter: severity>=ERROR
                      v
                 Pub/Sub topic ──> Pub/Sub PULL subscription
                                        │  (the agent pulls from here)
                                        v
                              Cloud Run worker pool (sre-agent)
                                        │  Gemini via Vertex AI
                                        v
                              triage -> analysis -> remediation
```

A Cloud Logging sink routes `severity>=ERROR` entries to a Pub/Sub topic. The
agent subscribes to a **pull** subscription on that topic (a push subscription
would need an HTTP endpoint, which a worker pool does not have). Each delivered
`LogEntry` is parsed into a `domain.LogEvent` and fed to the detector.

## Prerequisites

- `gcloud` authenticated to a project you can deploy to.
- Docker, for building and pushing the image.
- A project with billing enabled.

## Step 1 — provision infrastructure

`infra/gcloud_setup.sh` is idempotent: each create is guarded so re-runs
converge. It is fully parameterized — no hardcoded project.

```sh
PROJECT_ID=my-proj REGION=us-central1 ./infra/gcloud_setup.sh
```

It provisions:

1. **Enabled APIs** — logging, pubsub, aiplatform (Vertex AI), artifactregistry,
   run, cloudtrace.
2. **Artifact Registry repo** (`AR_REPO`, default `sre-agent`) for the image.
3. **Pub/Sub topic** (`LOG_TOPIC_NAME`, default `sre-agent-logs`).
4. **Pub/Sub pull subscription** (`LOG_SUBSCRIPTION_NAME`, default
   `sre-agent-logs-sub`) with a 600s ack deadline and 7d retention.
5. **Dedicated service account** (`AGENT_SA_ID`, default `sre-agent-sa`) with
   least-privilege roles: `pubsub.subscriber`, `logging.logWriter`,
   `cloudtrace.agent`, `aiplatform.user`.
6. **Cloud Logging sink** (`LOG_SINK_NAME`, default `sre-agent-error-sink`,
   filter `severity>=ERROR`) routed to the topic, plus a `pubsub.publisher`
   grant to the sink's auto-provisioned writer identity so routing can deliver.

All names, the region, the sink filter, ack deadline, and retention are
overridable via env vars (see the script header).

## Step 2 — build, push, deploy

`deploy.sh` builds the image, pushes it to Artifact Registry, and deploys the
worker pool. Use the same `PROJECT_ID`/`REGION` as setup.

```sh
PROJECT_ID=my-proj REGION=us-central1 ./deploy.sh
```

It:

1. Configures Docker auth for `<region>-docker.pkg.dev`.
2. Builds the image (multi-stage `Dockerfile`: static binary on
   `distroless/static:nonroot`, no shell, runs as UID 65532, no exposed port).
   The tag defaults to the short git SHA, else `latest`.
3. Pushes to Artifact Registry.
4. Deploys the worker pool with `gcloud beta run worker-pools deploy`, running
   as the agent service account, and sets the LLM wiring via env overrides:
   `SRE_LLM__BACKEND=vertex`, `SRE_LLM__PROJECT=<project>`,
   `SRE_LLM__LOCATION=<region>`.

There are no `--port` or `--allow-unauthenticated` flags — a worker pool has no
ingress.

## Configuration in the image

The `Dockerfile` bakes the in-repo `config.yaml` into `/app/config.yaml` as a
default so the image runs standalone. Override per environment **without
rebuilding** by either:

- **(a)** setting `SRE_`-prefixed env vars (what `deploy.sh` does — sets the
  Vertex backend/project/location), or
- **(b)** mounting a config file and passing `--config /etc/sre-agent/config.yaml`.

To point the agent at the pull subscription in production, configure a `pubsub`
source — either by mounting a config (option b) or by templating it in. See
`examples/pubsub-workerpool.yaml` for the production ingestion shape (Pub/Sub
source + Vertex AI + Cloud Trace export).

## Terraform alternative

`infra/terraform/` (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`)
mirrors the `gcloud_setup.sh` provisioning declaratively for teams that prefer
IaC over the script.

## HIPAA note

The deploy keeps the BAA-eligible Vertex AI backend (`aiplatform.user` on the
agent SA) as the LLM. Raw Pub/Sub message payloads are never logged — only
message IDs and counts. Any span attribute the agent records must be sanitized
first (spans bypass the log redactor); the agent records none today. See
[HIPAA.md](HIPAA.md).
