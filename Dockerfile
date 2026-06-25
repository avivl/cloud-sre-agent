# syntax=docker/dockerfile:1
#
# Multi-stage build for the Cloud SRE Agent (Go).
#
# This image runs as a Cloud Run *worker pool* — there is no HTTP server and no
# inbound traffic, so we deliberately do NOT EXPOSE a port. The agent pulls work
# (logs routed through a Pub/Sub subscription) and runs the triage/remediation
# loop until SIGTERM.

# ---- Stage 1: build a fully static binary -----------------------------------
FROM golang:1.26 AS build

WORKDIR /src

# Cache module downloads independently of source changes.
COPY go.mod go.sum ./
RUN go mod download

# Build the agent. CGO_ENABLED=0 yields a self-contained binary that runs on the
# distroless static base (no libc, no dynamic loader). -trimpath/-s -w keep the
# binary small and reproducible.
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOFLAGS=-trimpath \
    go build -ldflags="-s -w" -o /out/sre-agent ./cmd/sre-agent

# ---- Stage 2: minimal runtime -----------------------------------------------
# distroless/static:nonroot — no shell, no package manager, runs as UID 65532.
FROM gcr.io/distroless/static:nonroot

WORKDIR /app

COPY --from=build /out/sre-agent /usr/local/bin/sre-agent

# Config strategy:
#   The binary reads its config from the path given by --config (default
#   "config.yaml" relative to the workdir). We bake the in-repo config.yaml in
#   as a sane default so the image runs standalone. In production, override per
#   environment WITHOUT rebuilding by either:
#     (a) setting SRE_-prefixed env vars (e.g. SRE_LLM__PROJECT, SRE_LLM__LOCATION,
#         SRE_LLM__BACKEND=vertex) — these override config-file keys at load time, or
#     (b) mounting a config file and passing --config /etc/sre-agent/config.yaml.
#   deploy.sh wires the LLM backend/project/location via SRE_ env vars (option a).
COPY config.yaml /app/config.yaml

USER nonroot:nonroot

ENTRYPOINT ["/usr/local/bin/sre-agent"]
# Worker pool: no ports, just run the consume loop. --config defaults to the
# baked-in /app/config.yaml (WORKDIR is /app).
CMD ["run"]
