package gitlab

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	gitlab "gitlab.com/gitlab-org/api/client-go/v2"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/scm"
)

const (
	// testProject is a numeric project ID. A numeric ID keeps the test-server
	// URL paths free of the %2F-escaping a "group/repo" path would introduce.
	testProject = "123"
	baseCommit  = "abc123def456"
	// apiBase is the GitLab REST prefix every project path lives under.
	apiBase = "/api/v4/projects/" + testProject
)

// newTestTarget wires a GitLabTarget at an httptest.Server via the BaseURL seam.
func newTestTarget(t *testing.T, srv *httptest.Server, base string) *GitLabTarget {
	t.Helper()
	target, err := New(Config{
		Project:    testProject,
		BaseBranch: base,
		Token:      "unused-in-tests",
		BaseURL:    srv.URL,
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

func writeJSON(t *testing.T, w http.ResponseWriter, code int, v any) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	body, err := json.Marshal(v)
	require.NoError(t, err)
	_, err = w.Write(body)
	require.NoError(t, err)
}

func TestDeliver_HappyPath_NewFile(t *testing.T) {
	var (
		commitPayload gitlab.CreateCommitOptions
		mrPayload     gitlab.CreateMergeRequestOptions
		commitSeen    bool
		fileProbeRef  string
		getFileCount  int
	)

	mux := http.NewServeMux()

	// (1) GET base branch.
	mux.HandleFunc("GET "+apiBase+"/repository/branches/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusOK, gitlab.Branch{
				Name:   "main",
				Commit: &gitlab.Commit{ID: baseCommit},
			})
		})

	// (2) GET target branch -> 404 (does not exist yet, so this is a first run).
	mux.HandleFunc("GET "+apiBase+"/repository/branches/{branch...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 Branch Not Found"})
		})

	// (3a) GET file on the base branch -> 404 (file does not exist => create).
	mux.HandleFunc("GET "+apiBase+"/repository/files/{path...}",
		func(w http.ResponseWriter, r *http.Request) {
			getFileCount++
			fileProbeRef = r.URL.Query().Get("ref")
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 File Not Found"})
		})

	// (3b) POST commit -> creates the branch off start_branch and commits.
	mux.HandleFunc("POST "+apiBase+"/repository/commits",
		func(w http.ResponseWriter, r *http.Request) {
			commitSeen = true
			decodeBody(t, r, &commitPayload)
			writeJSON(t, w, http.StatusCreated, gitlab.Commit{ID: "newsha"})
		})

	// (4) POST merge request.
	mux.HandleFunc("POST "+apiBase+"/merge_requests",
		func(w http.ResponseWriter, r *http.Request) {
			decodeBody(t, r, &mrPayload)
			writeJSON(t, w, http.StatusCreated, gitlab.MergeRequest{
				BasicMergeRequest: gitlab.BasicMergeRequest{
					IID:    42,
					WebURL: "https://gitlab.com/group/repo/-/merge_requests/42",
				},
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
	assert.Equal(t, "https://gitlab.com/group/repo/-/merge_requests/42", ref.URL)

	// File existence is probed on the base branch (not the target branch), so the
	// create-vs-update decision reflects current base.
	assert.Equal(t, 1, getFileCount)
	assert.Equal(t, "main", fileProbeRef)

	// Commit shaping: branch taken off the base via start_branch, full body,
	// create action (file did not exist on base). First run => no force.
	assert.True(t, commitSeen)
	require.NotNil(t, commitPayload.Branch)
	require.NotNil(t, commitPayload.StartBranch)
	assert.Equal(t, "sre-agent/src-api-handler.go", *commitPayload.Branch)
	assert.Equal(t, "main", *commitPayload.StartBranch)
	assert.Nil(t, commitPayload.Force, "first run must not force-reset the branch")
	require.Len(t, commitPayload.Actions, 1)
	action := commitPayload.Actions[0]
	require.NotNil(t, action.Action)
	assert.Equal(t, gitlab.FileCreate, *action.Action)
	require.NotNil(t, action.FilePath)
	assert.Equal(t, "src/api/handler.go", *action.FilePath)
	require.NotNil(t, action.Content)
	assert.Equal(t, change.Patch, *action.Content)
	require.NotNil(t, commitPayload.CommitMessage)
	assert.Contains(t, *commitPayload.CommitMessage, "Fix nil deref in handler")

	// MR shaping.
	require.NotNil(t, mrPayload.SourceBranch)
	require.NotNil(t, mrPayload.TargetBranch)
	require.NotNil(t, mrPayload.Title)
	require.NotNil(t, mrPayload.Description)
	assert.Equal(t, "sre-agent/src-api-handler.go", *mrPayload.SourceBranch)
	assert.Equal(t, "main", *mrPayload.TargetBranch)
	assert.Contains(t, *mrPayload.Title, "critical")
	assert.Contains(t, *mrPayload.Title, "Fix nil deref in handler")
	assert.Equal(t, change.Description, *mrPayload.Description)
}

func TestDeliver_UpdatesExistingFile(t *testing.T) {
	var commitPayload gitlab.CreateCommitOptions
	sawCommit := false

	mux := http.NewServeMux()
	mux.HandleFunc("GET "+apiBase+"/repository/branches/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusOK, gitlab.Branch{Commit: &gitlab.Commit{ID: baseCommit}})
		})
	// Target branch does not exist yet.
	mux.HandleFunc("GET "+apiBase+"/repository/branches/{branch...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 Branch Not Found"})
		})
	// File already exists on the base branch => update action.
	mux.HandleFunc("GET "+apiBase+"/repository/files/{path...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusOK, gitlab.File{
				FilePath:     "README.md",
				BlobID:       "existingblob",
				LastCommitID: "lastcommit",
			})
		})
	mux.HandleFunc("POST "+apiBase+"/repository/commits",
		func(w http.ResponseWriter, r *http.Request) {
			sawCommit = true
			decodeBody(t, r, &commitPayload)
			writeJSON(t, w, http.StatusCreated, gitlab.Commit{ID: "newsha"})
		})
	mux.HandleFunc("POST "+apiBase+"/merge_requests",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusCreated, gitlab.MergeRequest{
				BasicMergeRequest: gitlab.BasicMergeRequest{
					IID:    7,
					WebURL: "https://gitlab.com/group/repo/-/merge_requests/7",
				},
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
	assert.True(t, sawCommit, "an existing file must be committed via the Commits API")
	require.Len(t, commitPayload.Actions, 1)
	action := commitPayload.Actions[0]
	require.NotNil(t, action.Action)
	assert.Equal(t, gitlab.FileUpdate, *action.Action, "an existing file must use the update action")
	require.NotNil(t, action.Content)
	assert.Equal(t, "# Widgets\n", *action.Content)
	require.NotNil(t, commitPayload.Branch)
	assert.Equal(t, "sre-agent/README.md", *commitPayload.Branch)
}

// TestDeliver_AlreadyExistsBranch_RebasesOnCurrentBase mirrors the GitHub
// already-exists test: when the target branch lingers from a prior run, the
// commit must be based on the current base (start_branch set) and force-reset
// the branch (force=true), so the MR never sits on a stale tree.
func TestDeliver_AlreadyExistsBranch_RebasesOnCurrentBase(t *testing.T) {
	var commitPayload gitlab.CreateCommitOptions
	mrOpened := false
	commitCalled := false

	mux := http.NewServeMux()
	mux.HandleFunc("GET "+apiBase+"/repository/branches/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusOK, gitlab.Branch{Commit: &gitlab.Commit{ID: baseCommit}})
		})
	// Target branch already exists (lingering from a prior delivery).
	mux.HandleFunc("GET "+apiBase+"/repository/branches/{branch...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusOK, gitlab.Branch{
				Name:   "sre-agent/main.go",
				Commit: &gitlab.Commit{ID: "stalesha"},
			})
		})
	mux.HandleFunc("GET "+apiBase+"/repository/files/{path...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 File Not Found"})
		})
	mux.HandleFunc("POST "+apiBase+"/repository/commits",
		func(w http.ResponseWriter, r *http.Request) {
			commitCalled = true
			decodeBody(t, r, &commitPayload)
			writeJSON(t, w, http.StatusCreated, gitlab.Commit{ID: "newsha"})
		})
	mux.HandleFunc("POST "+apiBase+"/merge_requests",
		func(w http.ResponseWriter, _ *http.Request) {
			mrOpened = true
			writeJSON(t, w, http.StatusCreated, gitlab.MergeRequest{
				BasicMergeRequest: gitlab.BasicMergeRequest{
					IID:    99,
					WebURL: "https://gitlab.com/group/repo/-/merge_requests/99",
				},
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
	assert.True(t, commitCalled, "delivery must continue and commit onto the existing branch")
	assert.True(t, mrOpened)

	// The commit must reconcile the stale branch to current base: start_branch
	// names the base and force resets the lingering branch to that point.
	require.NotNil(t, commitPayload.StartBranch)
	assert.Equal(t, "main", *commitPayload.StartBranch,
		"commit must be based on the current base branch, not the stale branch tree")
	require.NotNil(t, commitPayload.Force)
	assert.True(t, *commitPayload.Force,
		"a lingering branch must be force-reset to the current base")
}

// TestDeliver_BranchCreateBadRequest_NotSwallowed guards Fix 2: a genuine 400
// (e.g. an invalid branch name/ref) on the commit must NOT be mistaken for an
// "already exists" branch and swallowed — Deliver must return an error.
func TestDeliver_BranchCreateBadRequest_NotSwallowed(t *testing.T) {
	commitAttempts := 0

	mux := http.NewServeMux()
	mux.HandleFunc("GET "+apiBase+"/repository/branches/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusOK, gitlab.Branch{Commit: &gitlab.Commit{ID: baseCommit}})
		})
	// Target branch does not exist yet (first run path).
	mux.HandleFunc("GET "+apiBase+"/repository/branches/{branch...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 Branch Not Found"})
		})
	mux.HandleFunc("GET "+apiBase+"/repository/files/{path...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 File Not Found"})
		})
	// Commit fails with an unrelated 400 (invalid branch name): must propagate.
	mux.HandleFunc("POST "+apiBase+"/repository/commits",
		func(w http.ResponseWriter, _ *http.Request) {
			commitAttempts++
			writeJSON(t, w, http.StatusBadRequest, map[string]string{
				"message": "invalid branch name",
			})
		})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	target := newTestTarget(t, srv, "main")

	_, err := target.Deliver(context.Background(), scm.Change{
		FilePath:    "main.go",
		Patch:       "package main\n",
		Description: "retry delivery",
		Severity:    domain.SeverityError,
	})
	require.Error(t, err, "an unrelated 400 must not be swallowed as already-exists")
	assert.Contains(t, err.Error(), "commit file")
	assert.Equal(t, 1, commitAttempts,
		"an unrelated 400 must not trigger a force retry")
}

func TestDeliver_DuplicateMR_ResolvesExisting(t *testing.T) {
	listCalled := false

	mux := http.NewServeMux()
	mux.HandleFunc("GET "+apiBase+"/repository/branches/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusOK, gitlab.Branch{Commit: &gitlab.Commit{ID: baseCommit}})
		})
	mux.HandleFunc("GET "+apiBase+"/repository/branches/{branch...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 Branch Not Found"})
		})
	mux.HandleFunc("GET "+apiBase+"/repository/files/{path...}",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 File Not Found"})
		})
	mux.HandleFunc("POST "+apiBase+"/repository/commits",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusCreated, gitlab.Commit{ID: "newsha"})
		})
	// Create the MR -> 409 "already exists".
	mux.HandleFunc("POST "+apiBase+"/merge_requests",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusConflict, map[string]string{
				"message": "Another open merge request already exists for this source branch",
			})
		})
	// List the open MR for the source branch -> resolve the existing one.
	mux.HandleFunc("GET "+apiBase+"/merge_requests",
		func(w http.ResponseWriter, r *http.Request) {
			listCalled = true
			assert.Equal(t, "opened", r.URL.Query().Get("state"))
			assert.Equal(t, "sre-agent/main.go", r.URL.Query().Get("source_branch"))
			assert.Equal(t, "main", r.URL.Query().Get("target_branch"))
			writeJSON(t, w, http.StatusOK, []gitlab.MergeRequest{{
				BasicMergeRequest: gitlab.BasicMergeRequest{
					IID:    123,
					WebURL: "https://gitlab.com/group/repo/-/merge_requests/123",
				},
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
	require.NoError(t, err, "a duplicate MR must not fail Deliver")
	assert.True(t, listCalled, "must list existing MRs after a 409 on create")
	assert.Equal(t, "123", ref.ID)
	assert.Equal(t, "https://gitlab.com/group/repo/-/merge_requests/123", ref.URL)
}

func TestDeliver_BaseBranchNotFound(t *testing.T) {
	commitCalled := false

	mux := http.NewServeMux()
	mux.HandleFunc("GET "+apiBase+"/repository/branches/main",
		func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(t, w, http.StatusNotFound, map[string]string{"message": "404 Branch Not Found"})
		})
	mux.HandleFunc("POST "+apiBase+"/repository/commits",
		func(w http.ResponseWriter, _ *http.Request) {
			commitCalled = true
			writeJSON(t, w, http.StatusCreated, gitlab.Commit{ID: "newsha"})
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
	assert.Contains(t, err.Error(), "get base branch")
	assert.False(t, commitCalled, "must not commit when the base branch is missing")
}

func TestDeliver_ValidatesInput(t *testing.T) {
	// No server contact needed: validation happens before any HTTP call.
	target := NewWithClient(bareClient(t), testProject, "main")

	_, err := target.Deliver(context.Background(), scm.Change{Patch: "body"})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "FilePath is required")

	_, err = target.Deliver(context.Background(), scm.Change{FilePath: "a.go"})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "Patch is empty")
}

func TestName(t *testing.T) {
	assert.Equal(t, "gitlab", NewWithClient(bareClient(t), testProject, "main").Name())
}

func TestNew_RequiresProject(t *testing.T) {
	_, err := New(Config{Token: "t"})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "Project is required")
}

// bareClient builds a default *gitlab.Client for tests that never hit the network.
func bareClient(t *testing.T) *gitlab.Client {
	t.Helper()
	c, err := gitlab.NewClient("unused")
	require.NoError(t, err)
	return c
}

// TestTarget_ImplementsPRTarget is a compile-time assertion.
func TestTarget_ImplementsPRTarget(_ *testing.T) {
	var _ scm.PRTarget = (*GitLabTarget)(nil)
}
