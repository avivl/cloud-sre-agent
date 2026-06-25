package pubsub

import (
	"context"
	"testing"
	"time"

	gpubsub "cloud.google.com/go/pubsub/v2"
	"cloud.google.com/go/pubsub/v2/apiv1/pubsubpb"
	"cloud.google.com/go/pubsub/v2/pstest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"google.golang.org/api/option"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"github.com/avivl/cloud-sre-agent/internal/domain"
)

const (
	testProject = "test-project"
	testTopic   = "projects/test-project/topics/logs"
	testSub     = "projects/test-project/subscriptions/logs-sub"
)

// newTestServer starts an in-memory pstest server with a topic + subscription
// and returns the server, the client options to dial it, and a cleanup func.
// No network or credentials are used.
func newTestServer(t *testing.T) (*pstest.Server, []option.ClientOption) {
	t.Helper()

	srv := pstest.NewServer()
	t.Cleanup(func() { _ = srv.Close() })

	conn, err := grpc.NewClient(srv.Addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	require.NoError(t, err)
	t.Cleanup(func() { _ = conn.Close() })

	opts := []option.ClientOption{option.WithGRPCConn(conn)}

	ctx := context.Background()
	admin, err := gpubsub.NewClient(ctx, testProject, opts...)
	require.NoError(t, err)
	t.Cleanup(func() { _ = admin.Close() })

	_, err = admin.TopicAdminClient.CreateTopic(ctx, &pubsubpb.Topic{Name: testTopic})
	require.NoError(t, err)
	_, err = admin.SubscriptionAdminClient.CreateSubscription(ctx, &pubsubpb.Subscription{
		Name:  testSub,
		Topic: testTopic,
	})
	require.NoError(t, err)

	return srv, opts
}

// collect runs the source and gathers up to want events, returning early once
// they arrive or when the deadline elapses.
func collect(t *testing.T, src *PubSubSource, want int, timeout time.Duration) []domain.LogEvent {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	ch, err := src.Stream(ctx)
	require.NoError(t, err)

	var got []domain.LogEvent
	deadline := time.After(timeout)
	for len(got) < want {
		select {
		case ev, ok := <-ch:
			if !ok {
				return got
			}
			got = append(got, ev)
		case <-deadline:
			return got
		}
	}
	return got
}

func TestPubSubSource_MapsLogEntry(t *testing.T) {
	srv, opts := newTestServer(t)

	body := `{
		"severity": "ERROR",
		"timestamp": "2026-01-02T15:04:05.123Z",
		"textPayload": "connection refused",
		"logName": "projects/test-project/logs/syslog",
		"insertId": "abc123",
		"labels": {"env": "prod"},
		"resource": {"type": "gce_instance", "labels": {"zone": "us-central1-a", "env": "staging"}}
	}`
	srv.Publish(testTopic, []byte(body), nil)

	src, err := New(context.Background(), Config{
		ProjectID:      testProject,
		SubscriptionID: testSub,
		ClientOptions:  opts,
	})
	require.NoError(t, err)
	defer func() { _ = src.Close() }()

	got := collect(t, src, 1, 5*time.Second)
	require.Len(t, got, 1)

	ev := got[0]
	assert.Equal(t, domain.SeverityError, ev.Severity)
	assert.Equal(t, "connection refused", ev.Message)
	assert.Equal(t, "gce_instance:projects/test-project/logs/syslog", ev.Source)
	// Entry labels override resource labels on collision.
	assert.Equal(t, "prod", ev.Labels["env"])
	assert.Equal(t, "us-central1-a", ev.Labels["zone"])
	assert.Equal(t, 2026, ev.Timestamp.Year())
	assert.NotEmpty(t, ev.ID)
}

func TestPubSubSource_JSONPayloadMessage(t *testing.T) {
	srv, opts := newTestServer(t)

	body := `{"severity":"WARNING","jsonPayload":{"message":"disk almost full","disk":"/dev/sda1"},"resource":{"type":"k8s_container"}}`
	srv.Publish(testTopic, []byte(body), nil)

	src, err := New(context.Background(), Config{ProjectID: testProject, SubscriptionID: testSub, ClientOptions: opts})
	require.NoError(t, err)
	defer func() { _ = src.Close() }()

	got := collect(t, src, 1, 5*time.Second)
	require.Len(t, got, 1)
	assert.Equal(t, domain.SeverityWarning, got[0].Severity)
	assert.Equal(t, "disk almost full", got[0].Message)
	assert.Equal(t, "k8s_container", got[0].Source)
}

func TestPubSubSource_JSONPayloadRawFallback(t *testing.T) {
	srv, opts := newTestServer(t)

	body := `{"severity":"INFO","jsonPayload":{"code":500,"path":"/api"}}`
	srv.Publish(testTopic, []byte(body), nil)

	src, err := New(context.Background(), Config{ProjectID: testProject, SubscriptionID: testSub, ClientOptions: opts})
	require.NoError(t, err)
	defer func() { _ = src.Close() }()

	got := collect(t, src, 1, 5*time.Second)
	require.Len(t, got, 1)
	// No message field in jsonPayload: the raw JSON is preserved as the message.
	assert.Contains(t, got[0].Message, `"code":500`)
	assert.Equal(t, domain.SeverityInfo, got[0].Severity)
}

func TestPubSubSource_SeverityMapping(t *testing.T) {
	cases := map[string]domain.Severity{
		"DEFAULT":   domain.SeverityInfo,
		"":          domain.SeverityInfo,
		"DEBUG":     domain.SeverityDebug,
		"INFO":      domain.SeverityInfo,
		"NOTICE":    domain.SeverityInfo,
		"WARNING":   domain.SeverityWarning,
		"ERROR":     domain.SeverityError,
		"CRITICAL":  domain.SeverityCritical,
		"ALERT":     domain.SeverityCritical,
		"EMERGENCY": domain.SeverityCritical,
		"weird":     domain.SeverityInfo,
	}
	for in, want := range cases {
		assert.Equalf(t, want, mapSeverity(in), "severity %q", in)
	}
}

func TestPubSubSource_MalformedMessageDropped(t *testing.T) {
	srv, opts := newTestServer(t)

	// One malformed (not JSON) and one valid message. The valid one must still
	// be delivered; the malformed one is acked-and-dropped, not redelivered.
	srv.Publish(testTopic, []byte("this is not json"), nil)
	srv.Publish(testTopic, []byte(`{"severity":"ERROR","textPayload":"boom","insertId":"ok-1"}`), nil)

	src, err := New(context.Background(), Config{ProjectID: testProject, SubscriptionID: testSub, ClientOptions: opts})
	require.NoError(t, err)
	defer func() { _ = src.Close() }()

	got := collect(t, src, 1, 5*time.Second)
	require.Len(t, got, 1)
	assert.Equal(t, "boom", got[0].Message)
}

func TestPubSubSource_ContextCancellation(t *testing.T) {
	_, opts := newTestServer(t)

	src, err := New(context.Background(), Config{ProjectID: testProject, SubscriptionID: testSub, ClientOptions: opts})
	require.NoError(t, err)
	defer func() { _ = src.Close() }()

	ctx, cancel := context.WithCancel(context.Background())
	ch, err := src.Stream(ctx)
	require.NoError(t, err)

	cancel()

	// The channel must close once the context is cancelled.
	select {
	case _, ok := <-ch:
		// Either a drained value (none expected) or a closed channel; loop until closed.
		for ok {
			_, ok = <-ch
		}
	case <-time.After(5 * time.Second):
		t.Fatal("stream did not close after context cancellation")
	}
}

func TestPubSubSource_SingleUseStream(t *testing.T) {
	_, opts := newTestServer(t)

	src, err := New(context.Background(), Config{ProjectID: testProject, SubscriptionID: testSub, ClientOptions: opts})
	require.NoError(t, err)
	defer func() { _ = src.Close() }()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	_, err = src.Stream(ctx)
	require.NoError(t, err)
	_, err = src.Stream(ctx)
	require.Error(t, err)
}

func TestPubSubSource_RequiresConfig(t *testing.T) {
	_, err := New(context.Background(), Config{SubscriptionID: testSub})
	require.Error(t, err)
	_, err = New(context.Background(), Config{ProjectID: testProject})
	require.Error(t, err)
}

func TestPubSubSource_Name(t *testing.T) {
	_, opts := newTestServer(t)
	src, err := New(context.Background(), Config{ProjectID: testProject, SubscriptionID: testSub, ClientOptions: opts})
	require.NoError(t, err)
	defer func() { _ = src.Close() }()
	assert.Equal(t, "pubsub", src.Name())
}
