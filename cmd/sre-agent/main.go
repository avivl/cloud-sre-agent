// Command sre-agent is the entrypoint for the Cloud SRE Agent daemon. This file
// is a thin shell: it parses flags, loads config, sets up logging/tracing and
// signal handling, then hands off to internal/app.Run, which owns the wiring of
// the spine — log source -> detector -> pipeline -> delivery target — and the
// consume loop. All testable logic lives in internal/app.
package main

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"

	"github.com/avivl/cloud-sre-agent/internal/app"
	"github.com/avivl/cloud-sre-agent/internal/config"
	"github.com/avivl/cloud-sre-agent/internal/obs"
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

// run sets up signal handling, logging/tracing, and delegates to app.Run. It
// honors SIGINT/SIGTERM by cancelling the context, which stops the source and
// unwinds the loop cleanly.
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

	return app.Run(ctx, cfg, prov.Logger)
}
