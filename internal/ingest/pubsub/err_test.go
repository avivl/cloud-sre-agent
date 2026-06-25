package pubsub

import (
	"errors"
	"testing"
)

// TestErr_FirstWins verifies the terminal-error contract: Err is nil until a
// fatal Receive error is recorded, and the first recorded error wins (later
// errors do not overwrite it). consume relies on this to decide its exit code.
func TestErr_FirstWins(t *testing.T) {
	var s PubSubSource

	if err := s.Err(); err != nil {
		t.Fatalf("Err() = %v, want nil before any failure", err)
	}

	first := errors.New("permission revoked")
	s.setErr(first)
	s.setErr(errors.New("subscription deleted")) // must not overwrite

	if got := s.Err(); !errors.Is(got, first) {
		t.Fatalf("Err() = %v, want first error %v", got, first)
	}
}
