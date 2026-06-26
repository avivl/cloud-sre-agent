// Command sre-agent is the entrypoint for the Cloud SRE Agent daemon. The run
// subcommand hand-wires the spine — filesystem source -> threshold detector ->
// triage/analysis/remediation pipeline -> local-patch delivery — and runs the
// consume loop until the source is exhausted or SIGINT/SIGTERM is received.
// There is no DI framework: every dependency is constructed explicitly here.
package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"sync"
	"syscall"

	"github.com/spf13/cobra"

	"github.com/avivl/cloud-sre-agent/internal/config"
	"github.com/avivl/cloud-sre-agent/internal/detect"
	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/ingest"
	"github.com/avivl/cloud-sre-agent/internal/ingest/file"
	"github.com/avivl/cloud-sre-agent/internal/ingest/pubsub"
	"github.com/avivl/cloud-sre-agent/internal/llm/gemini"
	"github.com/avivl/cloud-sre-agent/internal/obs"
	"github.com/avivl/cloud-sre-agent/internal/pipeline"
	"github.com/avivl/cloud-sre-agent/internal/scm"
	"github.com/avivl/cloud-sre-agent/internal/scm/github"
	"github.com/avivl/cloud-sre-agent/internal/scm/local"
	"github.com/avivl/cloud-sre-agent/internal/security"
	"github.com/avivl/cloud-sre-agent/internal/validate"
)

func main() {
	if err := newRootCmd().Execute(); err != nil {
		os.Exit(1)
	}
}

func newRootCmd() *cobra.Command {
	var configPath string

	root := &cobra.Command{
		Use:           "sre-agent",
		Short:         "Cloud SRE Agent — log-driven incident triage and remediation",
		SilenceUsage:  true,
		SilenceErrors: false,
	}
	root.PersistentFlags().StringVar(&configPath, "config", "config.yaml", "path to config file")

	root.AddCommand(&cobra.Command{
		Use:   "run",
		Short: "Run the agent loop: ingest logs, detect incidents, remediate",
		RunE: func(cmd *cobra.Command, _ []string) error {
			cfg, err := config.Load(configPath)
			if err != nil {
				return fmt.Errorf("load config: %w", err)
			}
			return run(cmd.Context(), cfg, cmd.OutOrStdout())
		},
	})

	return root
}

// run hand-wires the dependencies and drives the consume loop. It honors
// SIGINT/SIGTERM by cancelling the context, which stops the source and unwinds
// the loop cleanly.
func run(parent context.Context, cfg config.Config, out io.Writer) error {
	if parent == nil {
		parent = context.Background()
	}
	ctx, stop := signal.NotifyContext(parent, syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	prov := obs.Setup(obs.Options{
		Level:  cfg.Log.Level,
		Format: cfg.Log.Format,
		Writer: out,
		Tracing: obs.TracingOptions{
			Exporter: obs.TraceExporter(cfg.Tracing.Exporter),
			Project:  cfg.Tracing.Project,
		},
	})
	defer func() { _ = prov.Shutdown(context.Background()) }()
	log := prov.Logger

	// LLM provider. Vertex AI (BAA-eligible) is the default; the consumer Gemini
	// Developer API is gated behind an explicit opt-in in config.Validate.
	provider, err := buildProvider(ctx, cfg.LLM)
	if err != nil {
		return fmt.Errorf("build llm provider: %w", err)
	}

	// Delivery target: local patch directory or a GitHub pull request.
	target, err := buildTarget(cfg, log)
	if err != nil {
		return fmt.Errorf("build delivery target: %w", err)
	}

	// Sanitizer is the prompt-input scrubber and also the last line of defense
	// for any error string we log (errors may echo log content / PHI).
	sanitizer := security.New()

	// Code validator gating the generated patch before delivery.
	validator := buildValidator(cfg, log)

	// Pipeline: sanitizer + selected validator wired through the ports.
	pipe, err := pipeline.New(provider, sanitizer, target,
		pipeline.WithLogger(log),
		pipeline.WithValidator(validator),
	)
	if err != nil {
		return fmt.Errorf("build pipeline: %w", err)
	}

	// Detector with default thresholds.
	detector := detect.New(detect.Config{})

	// Build the configured log sources (file and pubsub).
	sources, err := buildSources(ctx, cfg, log)
	if err != nil {
		return err
	}
	defer func() {
		for _, s := range sources {
			_ = s.Close()
		}
	}()

	log.Info("sre-agent starting",
		"provider", cfg.LLM.Provider,
		"backend", cfg.LLM.Backend,
		"model", cfg.LLM.Model,
		"sources", len(sources),
		"output_dir", cfg.Output.Dir,
		"target", target.Name(),
		"validator", cfg.Validator,
	)

	return consume(ctx, sources, detector, pipe, sanitizer, log)
}

// buildProvider constructs the gemini provider for the configured backend.
// Vertex AI uses project/location; the gemini-api backend uses the API key from
// the configured env var. config.Validate has already enforced the BAA gate, so
// reaching the gemini-api branch means the operator opted in explicitly.
func buildProvider(ctx context.Context, l config.LLMConfig) (*gemini.Provider, error) {
	switch l.Backend {
	case config.BackendVertex:
		return gemini.New(ctx, gemini.Config{
			Model:    l.Model,
			Backend:  gemini.BackendVertexAI,
			Project:  l.Project,
			Location: l.Location,
		})
	case config.BackendGeminiAPI:
		apiKey := os.Getenv(l.APIKeyEnv)
		if apiKey == "" {
			return nil, fmt.Errorf("llm api key not set: env %s is empty", l.APIKeyEnv)
		}
		return gemini.New(ctx, gemini.Config{
			Model:   l.Model,
			Backend: gemini.BackendGeminiAPI,
			APIKey:  apiKey,
		})
	default:
		return nil, fmt.Errorf("unsupported llm backend %q", l.Backend)
	}
}

// buildTarget selects the delivery target from config. "local" writes patches
// to the output directory; "github" opens a real pull request, reading its
// access token from the GITHUB_TOKEN environment variable at wire time — the
// token is never stored in config and never logged. config.Validate has already
// enforced that the github target carries owner+repo.
func buildTarget(cfg config.Config, log *slog.Logger) (scm.PRTarget, error) {
	switch cfg.Target {
	case config.TargetLocal:
		return local.New(cfg.Output.Dir), nil
	case config.TargetGitHub:
		token := os.Getenv(config.GitHubTokenEnv)
		if token == "" {
			return nil, fmt.Errorf("github target selected but %s is empty", config.GitHubTokenEnv)
		}
		t, err := github.New(github.Config{
			Owner:      cfg.GitHub.Owner,
			Repo:       cfg.GitHub.Repo,
			BaseBranch: cfg.GitHub.BaseBranch,
			Token:      token,
		})
		if err != nil {
			return nil, err
		}
		// Token is held only inside the HTTP transport; log non-sensitive routing.
		log.Info("github delivery target configured",
			"owner", cfg.GitHub.Owner,
			"repo", cfg.GitHub.Repo,
			"base_branch", cfg.GitHub.BaseBranch,
		)
		return t, nil
	default:
		return nil, fmt.Errorf("unsupported delivery target %q", cfg.Target)
	}
}

// buildValidator selects the code validator from config. "none" is the no-op
// default; "local" gates Go patches with the local toolchain. config.Validate
// has already rejected unknown values, so the default arm should be unreachable;
// it falls back to the no-op validator rather than panic.
func buildValidator(cfg config.Config, log *slog.Logger) pipeline.CodeValidator {
	switch cfg.Validator {
	case config.ValidatorLocal:
		return validate.New(validate.WithLogger(log))
	case config.ValidatorNone:
		return pipeline.NoopValidator{}
	default:
		return pipeline.NoopValidator{}
	}
}

// buildSources constructs the ingest.LogSource list from config. The file and
// pubsub source types are supported; an unknown type is a configuration error.
// On a partial failure, sources already built are closed before returning.
func buildSources(ctx context.Context, cfg config.Config, log *slog.Logger) ([]ingest.LogSource, error) {
	var sources []ingest.LogSource
	closeAll := func() {
		for _, s := range sources {
			_ = s.Close()
		}
	}
	for i, sc := range cfg.Sources {
		switch sc.Type {
		case config.SourceTypeFile:
			fs, err := file.New(file.Config{Path: sc.Path, Watch: true, Logger: log})
			if err != nil {
				closeAll()
				return nil, fmt.Errorf("build source[%d] (file): %w", i, err)
			}
			sources = append(sources, fs)
		case config.SourceTypePubSub:
			ps, err := pubsub.New(ctx, pubsub.Config{
				ProjectID:      sc.ProjectID,
				SubscriptionID: sc.SubscriptionID,
				Logger:         log,
			})
			if err != nil {
				closeAll()
				return nil, fmt.Errorf("build source[%d] (pubsub): %w", i, err)
			}
			sources = append(sources, ps)
		default:
			closeAll()
			return nil, fmt.Errorf("build source[%d]: unsupported type %q", i, sc.Type)
		}
	}
	return sources, nil
}

// consume fans the sources' event streams into the detector and runs the
// pipeline on each emitted incident. It returns when the context is cancelled
// or all source streams close.
func consume(ctx context.Context, sources []ingest.LogSource, detector *detect.Detector, pipe *pipeline.Pipeline, sanitizer *security.Sanitizer, log *slog.Logger) error {
	merged, err := merge(ctx, sources)
	if err != nil {
		return err
	}

	for {
		select {
		case <-ctx.Done():
			log.Info("sre-agent stopping", "reason", ctx.Err())
			return nil
		case ev, ok := <-merged:
			if !ok {
				// A closed channel means either a clean drain or a source that
				// died. Distinguish them so a fatal source error (e.g. Pub/Sub
				// permission revoked) exits non-zero instead of looking like a
				// healthy shutdown to the worker pool.
				if e := sourcesErr(sources); e != nil {
					log.Error("sre-agent: source failed",
						"error_type", fmt.Sprintf("%T", e),
						"error_detail", sanitizer.Sanitize(e.Error()))
					return fmt.Errorf("source failed: %w", e)
				}
				log.Info("sre-agent: all sources exhausted")
				return nil
			}
			if inc := detector.Observe(ev); inc != nil {
				handleIncident(ctx, pipe, *inc, sanitizer, log)
			}
		}
	}
}

// sourcesErr returns the first terminal error reported by any source exposing
// an Err() method (e.g. the Pub/Sub source). A non-nil result means a source
// died rather than draining cleanly.
func sourcesErr(sources []ingest.LogSource) error {
	for _, s := range sources {
		if e, ok := s.(interface{ Err() error }); ok {
			if err := e.Err(); err != nil {
				return err
			}
		}
	}
	return nil
}

// handleIncident runs one incident through the pipeline, logging the outcome.
// A non-actionable incident is a benign skip, not an error. A failure is logged
// with its error type and a sanitized error string, never the raw error (which
// may have wrapped log content / PHI).
func handleIncident(ctx context.Context, pipe *pipeline.Pipeline, inc domain.Incident, sanitizer *security.Sanitizer, log *slog.Logger) {
	res, err := pipe.Process(ctx, inc)
	switch {
	case errors.Is(err, pipeline.ErrNotActionable):
		log.Info("incident not actionable, skipped", "incident_id", inc.ID)
	case err != nil:
		log.Error("incident processing failed",
			"incident_id", inc.ID,
			"error_type", fmt.Sprintf("%T", err),
			"error_detail", sanitizer.Sanitize(err.Error()),
		)
	default:
		log.Info("incident remediated", "incident_id", inc.ID, "ref", res.Ref.ID, "url", res.Ref.URL)
	}
}

// merge starts every source's stream and fans them into a single channel,
// closed when all upstream channels close or the context is cancelled.
func merge(ctx context.Context, sources []ingest.LogSource) (<-chan domain.LogEvent, error) {
	chans := make([]<-chan domain.LogEvent, 0, len(sources))
	for _, s := range sources {
		ch, err := s.Stream(ctx)
		if err != nil {
			return nil, fmt.Errorf("start source %q: %w", s.Name(), err)
		}
		chans = append(chans, ch)
	}
	return fanIn(ctx, chans), nil
}

// fanIn merges multiple event channels into one. The output channel closes when
// every input closes or the context is cancelled.
func fanIn(ctx context.Context, ins []<-chan domain.LogEvent) <-chan domain.LogEvent {
	out := make(chan domain.LogEvent)
	var wg sync.WaitGroup
	wg.Add(len(ins))
	for _, in := range ins {
		go func(in <-chan domain.LogEvent) {
			defer wg.Done()
			for {
				select {
				case <-ctx.Done():
					return
				case ev, ok := <-in:
					if !ok {
						return
					}
					select {
					case out <- ev:
					case <-ctx.Done():
						return
					}
				}
			}
		}(in)
	}
	go func() {
		wg.Wait()
		close(out)
	}()
	return out
}
