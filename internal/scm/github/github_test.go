package github

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	gh "github.com/google/go-github/v88/github"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/scm"
)

const (
	testOwner = "acme"
	testRepo  = "widgets"
	baseSHA   = "abc123def456"
)

// newTestTarget wires a GitHubTarget at an httptest.Server via the BaseURL seam.
func newTestTarget(t *testing.T, srv *httptest.Server, base string) *GitHubTarget {
	t.Helper()
	target, err := New(Config{
		Owner:      testOwner,
		Repo:       testRepo,
		BaseBranch: base,
		Token:      "unused-in-tests",
		BaseURL:    srv.URL + "/",
		HTTPClient: srv.Client(),
	})
	require.NoError(t, err)
	return target
}

func decodeBody(t *testing.T, r *http.Request, v any) {
	t.Helper()
	body, err := io.ReadAll(r.Body)
	require.NoError(t, err)
	require.NoError(t, json.Unmarshal(body, v))
}

func TestDeliver_HappyPath_NewFile(t *testing.T) {
	var (
		createdRefPayload  gh.CreateRef
		contentPayload     gh.RepositoryContentFileOptions
		prPayload          gh.NewPullRequest
		sawCreateFilePUT   bool
		sawUpdateFilePUT   bool
		getContentsCount   int
		createBranchCalled bool
	)

	mux := http.NewServeMux()

	// (1) GET base ref.
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/git/ref/heads/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, gh.Reference{
				Ref:    gh.Ptr("refs/heads/main"),
				Object: &gh.GitObject{SHA: gh.Ptr(baseSHA)},
			})
		})

	// (2) POST new branch ref.
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/git/refs",
		func(w http.ResponseWriter, r *http.Request) {
			createBranchCalled = true
			decodeBody(t, r, &createdRefPayload)
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.Reference{Ref: gh.Ptr(createdRefPayload.Ref)})
		})

	// (3a) GET contents -> 404 (file does not exist yet).
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, _ *http.Request) {
			getContentsCount++
			w.WriteHeader(http.StatusNotFound)
			writeJSON(t, w, gh.ErrorResponse{Message: "Not Found"})
		})

	// (3b) PUT contents -> create or update.
	mux.HandleFunc("PUT /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, r *http.Request) {
			decodeBody(t, r, &contentPayload)
			// Distinguish create vs update by presence of SHA.
			if contentPayload.SHA != nil {
				sawUpdateFilePUT = true
			} else {
				sawCreateFilePUT = true
			}
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.RepositoryContentResponse{
				Content: &gh.RepositoryContent{SHA: gh.Ptr("newblob")},
			})
		})

	// (4) POST pulls.
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/pulls",
		func(w http.ResponseWriter, r *http.Request) {
			decodeBody(t, r, &prPayload)
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.PullRequest{
				Number:  gh.Ptr(42),
				HTMLURL: gh.Ptr("https://github.com/acme/widgets/pull/42"),
			})
		})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	target := newTestTarget(t, srv, "main")

	change := scm.Change{
		FilePath:    "src/api/handler.go",
		Patch:       "package api\n\nfunc Handler() {}\n",
		Description: "Fix nil deref in handler\n\nFull explanation here.",
		Severity:    domain.SeverityCritical,
	}

	ref, err := target.Deliver(context.Background(), change)
	require.NoError(t, err)

	// Returned Ref.
	assert.Equal(t, "42", ref.ID)
	assert.Equal(t, "https://github.com/acme/widgets/pull/42", ref.URL)

	// Branch shaping.
	assert.True(t, createBranchCalled)
	assert.Equal(t, "refs/heads/sre-agent/src-api-handler.go", createdRefPayload.Ref)
	assert.Equal(t, baseSHA, createdRefPayload.SHA)

	// File content == full patch body, on the new branch, create (no SHA).
	assert.True(t, sawCreateFilePUT)
	assert.False(t, sawUpdateFilePUT)
	assert.Equal(t, 1, getContentsCount)
	assert.Equal(t, change.Patch, string(contentPayload.Content))
	require.NotNil(t, contentPayload.Branch)
	assert.Equal(t, "sre-agent/src-api-handler.go", *contentPayload.Branch)
	assert.Nil(t, contentPayload.SHA)
	require.NotNil(t, contentPayload.Message)
	assert.Contains(t, *contentPayload.Message, "Fix nil deref in handler")

	// PR shaping.
	require.NotNil(t, prPayload.Head)
	require.NotNil(t, prPayload.Base)
	require.NotNil(t, prPayload.Title)
	require.NotNil(t, prPayload.Body)
	assert.Equal(t, "sre-agent/src-api-handler.go", *prPayload.Head)
	assert.Equal(t, "main", *prPayload.Base)
	assert.Contains(t, *prPayload.Title, "critical")
	assert.Contains(t, *prPayload.Title, "Fix nil deref in handler")
	assert.Equal(t, change.Description, *prPayload.Body)
}

func TestDeliver_UpdatesExistingFile(t *testing.T) {
	var contentPayload gh.RepositoryContentFileOptions
	sawUpdate := false

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/git/ref/heads/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, gh.Reference{Object: &gh.GitObject{SHA: gh.Ptr(baseSHA)}})
		})
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/git/refs",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.Reference{})
		})
	// File already exists: return its blob SHA.
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, gh.RepositoryContent{
				Type: gh.Ptr("file"),
				SHA:  gh.Ptr("existingblob"),
				Path: gh.Ptr("README.md"),
			})
		})
	mux.HandleFunc("PUT /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, r *http.Request) {
			sawUpdate = true
			decodeBody(t, r, &contentPayload)
			w.WriteHeader(http.StatusOK)
			writeJSON(t, w, gh.RepositoryContentResponse{})
		})
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/pulls",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.PullRequest{
				Number:  gh.Ptr(7),
				HTMLURL: gh.Ptr("https://github.com/acme/widgets/pull/7"),
			})
		})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	target := newTestTarget(t, srv, "") // empty -> defaults to main

	ref, err := target.Deliver(context.Background(), scm.Change{
		FilePath:    "README.md",
		Patch:       "# Widgets\n",
		Description: "Update readme",
		Severity:    domain.SeverityInfo,
	})
	require.NoError(t, err)

	assert.Equal(t, "7", ref.ID)
	assert.True(t, sawUpdate)
	require.NotNil(t, contentPayload.SHA)
	assert.Equal(t, "existingblob", *contentPayload.SHA, "update must carry current blob SHA")
	assert.Equal(t, "# Widgets\n", string(contentPayload.Content))
}

func TestDeliver_AlreadyExistsBranch_Tolerated(t *testing.T) {
	prOpened := false
	var forceUpdatePayload gh.UpdateRef
	forceUpdateCalled := false

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/git/ref/heads/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, gh.Reference{Object: &gh.GitObject{SHA: gh.Ptr(baseSHA)}})
		})
	// Branch already exists -> 422.
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/git/refs",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusUnprocessableEntity)
			writeJSON(t, w, gh.ErrorResponse{Message: "Reference already exists"})
		})
	// A lingering branch must be force-reset to the freshly-resolved base SHA.
	mux.HandleFunc("PATCH /api/v3/repos/"+testOwner+"/"+testRepo+"/git/refs/heads/sre-agent/main.go",
		func(w http.ResponseWriter, r *http.Request) {
			forceUpdateCalled = true
			decodeBody(t, r, &forceUpdatePayload)
			writeJSON(t, w, gh.Reference{Object: &gh.GitObject{SHA: gh.Ptr(baseSHA)}})
		})
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusNotFound)
			writeJSON(t, w, gh.ErrorResponse{Message: "Not Found"})
		})
	mux.HandleFunc("PUT /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.RepositoryContentResponse{})
		})
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/pulls",
		func(w http.ResponseWriter, _ *http.Request) {
			prOpened = true
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.PullRequest{
				Number:  gh.Ptr(99),
				HTMLURL: gh.Ptr("https://github.com/acme/widgets/pull/99"),
			})
		})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	target := newTestTarget(t, srv, "main")

	ref, err := target.Deliver(context.Background(), scm.Change{
		FilePath:    "main.go",
		Patch:       "package main\n",
		Description: "retry delivery",
		Severity:    domain.SeverityError,
	})
	require.NoError(t, err, "an already-exists branch must not fail Deliver")
	assert.Equal(t, "99", ref.ID)
	assert.True(t, prOpened)
	// FIX 3: the stale branch is force-reset to the current base SHA.
	assert.True(t, forceUpdateCalled, "lingering branch must be force-updated to base")
	assert.Equal(t, baseSHA, forceUpdatePayload.SHA)
	require.NotNil(t, forceUpdatePayload.Force)
	assert.True(t, *forceUpdatePayload.Force, "branch reset must be a force update")
}

func TestDeliver_DuplicatePR_ResolvesExisting(t *testing.T) {
	listCalled := false

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/git/ref/heads/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, gh.Reference{Object: &gh.GitObject{SHA: gh.Ptr(baseSHA)}})
		})
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/git/refs",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.Reference{})
		})
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusNotFound)
			writeJSON(t, w, gh.ErrorResponse{Message: "Not Found"})
		})
	mux.HandleFunc("PUT /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.RepositoryContentResponse{})
		})
	// Create the PR -> 422 "already exists".
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/pulls",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusUnprocessableEntity)
			writeJSON(t, w, gh.ErrorResponse{Message: "A pull request already exists for acme:sre-agent/main.go."})
		})
	// List the open PR for the head branch -> resolve the existing one.
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/pulls",
		func(w http.ResponseWriter, r *http.Request) {
			listCalled = true
			assert.Equal(t, "open", r.URL.Query().Get("state"))
			assert.Equal(t, testOwner+":sre-agent/main.go", r.URL.Query().Get("head"))
			writeJSON(t, w, []gh.PullRequest{{
				Number:  gh.Ptr(123),
				HTMLURL: gh.Ptr("https://github.com/acme/widgets/pull/123"),
			}})
		})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	target := newTestTarget(t, srv, "main")

	ref, err := target.Deliver(context.Background(), scm.Change{
		FilePath:    "main.go",
		Patch:       "package main\n",
		Description: "retry delivery",
		Severity:    domain.SeverityError,
	})
	require.NoError(t, err, "a duplicate PR must not fail Deliver")
	assert.True(t, listCalled, "must list existing PRs after a 422 on create")
	assert.Equal(t, "123", ref.ID)
	assert.Equal(t, "https://github.com/acme/widgets/pull/123", ref.URL)
}

func TestDeliver_PathIsDirectory_Errors(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/git/ref/heads/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, gh.Reference{Object: &gh.GitObject{SHA: gh.Ptr(baseSHA)}})
		})
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/git/refs",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusCreated)
			writeJSON(t, w, gh.Reference{})
		})
	// GetContents on a directory returns a JSON array (no error, but no file
	// entry): go-github yields fileContent==nil.
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/contents/",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, []gh.RepositoryContent{
				{Type: gh.Ptr("file"), Name: gh.Ptr("a.go"), Path: gh.Ptr("src/a.go")},
			})
		})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	target := newTestTarget(t, srv, "main")

	_, err := target.Deliver(context.Background(), scm.Change{
		FilePath:    "src",
		Patch:       "package main\n",
		Description: "x",
		Severity:    domain.SeverityCritical,
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "is a directory")
}

func TestDeliver_BaseRefNotFound(t *testing.T) {
	pullsCalled := false

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v3/repos/"+testOwner+"/"+testRepo+"/git/ref/heads/main",
		func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusNotFound)
			writeJSON(t, w, gh.ErrorResponse{Message: "Not Found"})
		})
	mux.HandleFunc("POST /api/v3/repos/"+testOwner+"/"+testRepo+"/pulls",
		func(w http.ResponseWriter, _ *http.Request) {
			pullsCalled = true
			w.WriteHeader(http.StatusCreated)
		})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	target := newTestTarget(t, srv, "main")

	_, err := target.Deliver(context.Background(), scm.Change{
		FilePath:    "main.go",
		Patch:       "package main\n",
		Description: "x",
		Severity:    domain.SeverityCritical,
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "get base ref")
	assert.False(t, pullsCalled, "must not open a PR when the base ref is missing")
}

// bareClient builds a default *github.Client for tests that never hit the network.
func bareClient(t *testing.T) *gh.Client {
	t.Helper()
	c, err := gh.NewClient()
	require.NoError(t, err)
	return c
}

func TestDeliver_ValidatesInput(t *testing.T) {
	// No server contact needed: validation happens before any HTTP call.
	target := NewWithClient(bareClient(t), testOwner, testRepo, "main")

	_, err := target.Deliver(context.Background(), scm.Change{Patch: "body"})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "FilePath is required")

	_, err = target.Deliver(context.Background(), scm.Change{FilePath: "a.go"})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "Patch is empty")
}

func TestName(t *testing.T) {
	assert.Equal(t, "github", NewWithClient(bareClient(t), testOwner, testRepo, "main").Name())
}

func TestNew_RequiresOwnerAndRepo(t *testing.T) {
	_, err := New(Config{Repo: "r"})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "Owner is required")

	_, err = New(Config{Owner: "o"})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "Repo is required")
}

// TestTarget_ImplementsPRTarget is a compile-time assertion.
func TestTarget_ImplementsPRTarget(_ *testing.T) {
	var _ scm.PRTarget = (*GitHubTarget)(nil)
}

func writeJSON(t *testing.T, w http.ResponseWriter, v any) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json")
	body, err := json.Marshal(v)
	require.NoError(t, err)
	_, err = w.Write(body)
	require.NoError(t, err)
}
