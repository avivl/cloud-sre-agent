package validate

import (
	"context"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/pipeline"
)

// Compile-time assertion mirrored in tests for documentation.
var _ pipeline.CodeValidator = (*LocalValidator)(nil)

// validGo is a syntactically correct, gofmt-formatted, vet-clean snippet.
const validGo = `package main

import "fmt"

func main() {
	fmt.Println("hello")
}
`

// brokenGo is missing the closing brace of main, so go/parser rejects it.
const brokenGo = `package main

func main() {
	x := 1
	_ = x
`

func TestValidate_ValidGo_OK(t *testing.T) {
	v := New()
	res, err := v.Validate(context.Background(), validGo, "go")
	require.NoError(t, err)
	assert.True(t, res.OK, "valid Go should pass: %v", res.Diagnostics)
	assert.Empty(t, res.Diagnostics)
}

func TestValidate_BrokenGo_NotOK(t *testing.T) {
	v := New()
	res, err := v.Validate(context.Background(), brokenGo, "go")
	require.NoError(t, err)
	assert.False(t, res.OK)
	require.NotEmpty(t, res.Diagnostics)
	assert.True(t,
		strings.Contains(res.Diagnostics[0], "syntax"),
		"expected a syntax diagnostic, got %v", res.Diagnostics)
}

func TestValidate_CaseInsensitiveLang(t *testing.T) {
	v := New()
	res, err := v.Validate(context.Background(), validGo, "GO")
	require.NoError(t, err)
	assert.True(t, res.OK, "uppercase GO should be treated as go: %v", res.Diagnostics)
	assert.Empty(t, res.Diagnostics)
}

func TestValidate_UnsupportedLang_SkippedOK(t *testing.T) {
	v := New()
	res, err := v.Validate(context.Background(), "print('hi')", "python")
	require.NoError(t, err)
	assert.True(t, res.OK)
	require.Len(t, res.Diagnostics, 1)
	assert.Contains(t, res.Diagnostics[0], "validation skipped")
	assert.Contains(t, res.Diagnostics[0], "python")
}

func TestValidate_UnformattedGo_NotOK(t *testing.T) {
	// Syntactically valid but not gofmt-formatted (leading spaces, no tabs).
	unformatted := "package main\n\nfunc main() {\n  x := 1\n  _ = x\n}\n"
	v := New()
	res, err := v.Validate(context.Background(), unformatted, "go")
	require.NoError(t, err)
	assert.False(t, res.OK)
	found := false
	for _, d := range res.Diagnostics {
		if strings.Contains(d, "format") {
			found = true
		}
	}
	assert.True(t, found, "expected a format diagnostic, got %v", res.Diagnostics)
}

func TestValidate_CgoPatch_FailsClosedNoExec(t *testing.T) {
	// A patch that pulls in cgo. Under the sandbox env CGO_ENABLED=0, so the
	// toolchain must refuse to build it (OK=false) rather than invoking a C
	// compiler on untrusted code. The malloc reference would not link if cgo
	// were ever enabled; with cgo disabled the build fails first.
	cgoPatch := `package main

// #include <stdlib.h>
import "C"

func main() {
	C.malloc(1)
}
`
	v := New()
	res, err := v.Validate(context.Background(), cgoPatch, "go")
	require.NoError(t, err)
	assert.False(t, res.OK, "cgo patch must fail closed under CGO_ENABLED=0")
	require.NotEmpty(t, res.Diagnostics)
}

func TestRunGofmt_GateCannotRun_FailsClosed(t *testing.T) {
	// When the gate cannot be INVOKED (here: a cancelled context kills the
	// subprocess before it can run), the helper surfaces an error. validateGo
	// turns that into an OK=false "gate could not run" diagnostic — a
	// pre-delivery gate fails closed, never silently passes.
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err := runGofmt(ctx, sandboxEnv(t.TempDir()), filepath.Join(t.TempDir(), patchFileName))
	require.Error(t, err, "gofmt gate must report an error when it cannot be invoked")
}

func TestRunVet_GateCannotRun_FailsClosed(t *testing.T) {
	// A cancelled context prevents `go mod init` from running; runVet must
	// return an error (recorded as an OK=false "gate could not run" diagnostic),
	// not a nil error that would let the patch through.
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err := New().runVet(ctx, sandboxEnv(t.TempDir()), t.TempDir())
	require.Error(t, err, "vet gate must report an error when it cannot be invoked")
}

func TestValidate_VetCatchesBadCode(t *testing.T) {
	// Syntactically valid and gofmt-formatted, but vet flags the Printf verb.
	vetBad := `package main

import "fmt"

func main() {
	fmt.Printf("%d", "not a number")
}
`
	v := New()
	res, err := v.Validate(context.Background(), vetBad, "go")
	require.NoError(t, err)
	assert.False(t, res.OK)
	found := false
	for _, d := range res.Diagnostics {
		if strings.Contains(d, "vet") {
			found = true
		}
	}
	assert.True(t, found, "expected a vet diagnostic, got %v", res.Diagnostics)
}
