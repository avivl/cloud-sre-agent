# Cloud SRE Agent — Go build/test/lint tooling.

BINARY       := sre-agent
PKG          := ./...
CMD          := ./cmd/sre-agent
COVER_MIN    := 80
# Coverage gate scopes to the logic packages (matches CI). cmd/ is the thin
# composition root and dogfood/ is local tooling — neither is unit-covered, and
# including them would drag the threshold below a meaningful bar.
COVER_PKG    := ./internal/...
COVERPROFILE := coverage.out

GENERATOR    := ./dogfood/cmd/generator
DOGFOOD_DIR  := dogfood/out
DOGFOOD_LOG  := $(DOGFOOD_DIR)/dogfood.log
DOGFOOD_CFG  := dogfood/config.yaml
DOGFOOD_WAIT := 30

.PHONY: all build run test cover vet lint tidy clean dogfood

all: vet lint test

build:
	go build -o bin/$(BINARY) $(CMD)

run:
	go run $(CMD) run --config config.yaml

test:
	go test $(PKG)

vet:
	go vet $(PKG)

# lint scopes to $(PKG) (./...) so an unscoped run can't wander into sibling
# git worktrees via the shared module cache (which produces phantom findings).
lint:
	golangci-lint run $(PKG)

tidy:
	go mod tidy

# cover runs tests with coverage over the logic packages and fails if total
# coverage is below COVER_MIN (matches the CI gate).
cover:
	go test -coverprofile=$(COVERPROFILE) $(COVER_PKG)
	@total=$$(go tool cover -func=$(COVERPROFILE) | grep total: | awk '{print $$3}' | tr -d '%'); \
	echo "total coverage: $$total% (min $(COVER_MIN)%)"; \
	awk "BEGIN { exit !($$total >= $(COVER_MIN)) }" || \
		{ echo "coverage $$total% is below minimum $(COVER_MIN)%"; exit 1; }

clean:
	rm -rf bin $(COVERPROFILE)

# dogfood runs the agent fully locally with NO credentials: it builds the agent
# and the log generator, generates an ERROR burst, runs `sre-agent run` against
# the stub provider + local target until a remediation patch appears (or a
# bounded timeout), then prints the produced patch file. Exits 0 on success.
dogfood: build
	@set -e; \
	rm -rf $(DOGFOOD_DIR); \
	mkdir -p $(DOGFOOD_DIR); \
	echo "dogfood: building generator"; \
	go build -o bin/dogfood-generator $(GENERATOR); \
	echo "dogfood: generating ERROR burst -> $(DOGFOOD_LOG)"; \
	./bin/dogfood-generator -file $(DOGFOOD_LOG) -count 8; \
	echo "dogfood: running agent (stub provider, local target)"; \
	./bin/$(BINARY) run --config $(DOGFOOD_CFG) & \
	agent_pid=$$!; \
	trap 'kill $$agent_pid 2>/dev/null || true' EXIT; \
	patch=""; \
	for i in $$(seq 1 $(DOGFOOD_WAIT)); do \
		found=$$(ls $(DOGFOOD_DIR)/*.patch 2>/dev/null | head -n1 || true); \
		if [ -n "$$found" ]; then patch="$$found"; break; fi; \
		sleep 1; \
	done; \
	kill $$agent_pid 2>/dev/null || true; \
	wait $$agent_pid 2>/dev/null || true; \
	trap - EXIT; \
	if [ -z "$$patch" ]; then \
		echo "dogfood: FAILED — no patch produced within $(DOGFOOD_WAIT)s"; \
		exit 1; \
	fi; \
	echo "dogfood: SUCCESS — remediation patch written to $$patch"; \
	echo "----------------------------------------"; \
	cat "$$patch"; \
	echo "----------------------------------------"
