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
	"github.com/avivl/cloud-sre-agent/internal/llm/gemini"
	"github.com/avivl/cloud-sre-agent/internal/obs"
	"github.com/avivl/cloud-sre-agent/internal/pipeline"
	"github.com/avivl/cloud-sre-agent/internal/scm/local"
	"github.com/avivl/cloud-sre-agent/internal/security"
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

	prov := obs.Setup(obs.Options{Level: cfg.Log.Level, Format: cfg.Log.Format, Writer: out})
	defer func() { _ = prov.Shutdown(context.Background()) }()
	log := prov.Logger

	// LLM provider. Vertex AI (BAA-eligible) is the default; the consumer Gemini
	// Developer API is gated behind an explicit opt-in in config.Validate.
	provider, err := buildProvider(ctx, cfg.LLM)
	if err != nil {
		return fmt.Errorf("build llm provider: %w", err)
	}

	// Delivery target: local patch directory.
	target := local.New(cfg.Output.Dir)

	// Sanitizer is the prompt-input scrubber and also the last line of defense
	// for any error string we log (errors may echo log content / PHI).
	sanitizer := security.New()

	// Pipeline: sanitizer + noop validator wired through the ports.
	pipe, err := pipeline.New(provider, sanitizer, target, pipeline.WithLogger(log))
	if err != nil {
		return fmt.Errorf("build pipeline: %w", err)
	}

	// Detector with default thresholds.
	detector := detect.New(detect.Config{})

	// Build the configured log sources. The MVP supports the file source.
	sources, err := buildSources(cfg, log)
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

// buildSources constructs the ingest.LogSource list from config. Only the file
// source is supported in the MVP; an unknown type is a configuration error.
func buildSources(cfg config.Config, log *slog.Logger) ([]ingest.LogSource, error) {
	var sources []ingest.LogSource
	for i, sc := range cfg.Sources {
		switch sc.Type {
		case "file":
			fs, err := file.New(file.Config{Path: sc.Path, Watch: true, Logger: log})
			if err != nil {
				return nil, fmt.Errorf("build source[%d] (file): %w", i, err)
			}
			sources = append(sources, fs)
		default:
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
				log.Info("sre-agent: all sources exhausted")
				return nil
			}
			if inc := detector.Observe(ev); inc != nil {
				handleIncident(ctx, pipe, *inc, sanitizer, log)
			}
		}
	}
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
