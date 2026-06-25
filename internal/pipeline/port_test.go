package pipeline

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNoopValidator(t *testing.T) {
	var v CodeValidator = NoopValidator{}
	res, err := v.Validate(context.Background(), "any patch", "go")
	require.NoError(t, err)
	assert.True(t, res.OK)
	assert.Empty(t, res.Diagnostics)
}
