# Cloud SRE Agent — Go build/test/lint tooling.

BINARY       := sre-agent
PKG          := ./...
CMD          := ./cmd/sre-agent
COVER_MIN    := 80
COVERPROFILE := coverage.out

.PHONY: all build run test cover vet lint tidy clean

all: vet lint test

build:
	go build -o bin/$(BINARY) $(CMD)

run:
	go run $(CMD) run --config config.yaml

test:
	go test $(PKG)

vet:
	go vet $(PKG)

lint:
	golangci-lint run

tidy:
	go mod tidy

# cover runs tests with coverage and fails if total coverage is below COVER_MIN.
cover:
	go test -coverprofile=$(COVERPROFILE) $(PKG)
	@total=$$(go tool cover -func=$(COVERPROFILE) | grep total: | awk '{print $$3}' | tr -d '%'); \
	echo "total coverage: $$total% (min $(COVER_MIN)%)"; \
	awk "BEGIN { exit !($$total >= $(COVER_MIN)) }" || \
		{ echo "coverage $$total% is below minimum $(COVER_MIN)%"; exit 1; }

clean:
	rm -rf bin $(COVERPROFILE)
