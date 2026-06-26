// Command generator appends realistic, varied ERROR-level JSON-lines log
// records to a target file so the local dogfooding loop has an error burst to
// detect. The generation logic lives in the dogfood/generator library; this
// binary is a thin flag-parsing wrapper. It makes no network call and needs no
// credentials.
package main

import (
	"flag"
	"fmt"
	"os"

	generator "github.com/avivl/cloud-sre-agent/dogfood/generator"
)

func main() {
	var (
		path  string
		count int
	)
	flag.StringVar(&path, "file", "", "target log file to append to (required)")
	flag.IntVar(&count, "count", 8, "number of ERROR-level lines to append")
	flag.Parse()

	if err := generator.AppendToFile(path, count); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
