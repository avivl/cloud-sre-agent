// Package gitlab implements the scm.PRTarget port by delivering a remediation
// as a real GitLab merge request. Each Deliver call commits change.Patch as the
// FULL file body onto a branch taken off the configured base branch via the
// Commits API, and opens a merge request from that branch into the base branch.
//
// The adapter treats change.Patch as the complete file body (per the port's
// "full file body" contract for this target), not a unified diff. It is the
// GitLab sibling of the GitHub target behind the same scm.PRTarget port.
package gitlab

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"

	gitlab "gitlab.com/gitlab-org/api/client-go/v2"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/scm"
)

// name is the adapter identifier reported by Name and used in logs/metrics.
const name = "gitlab"

// defaultBaseBranch is used when Config.BaseBranch is empty.
const defaultBaseBranch = "main"

// branchPrefix namespaces every branch this adapter creates.
const branchPrefix = "sre-agent/"

// Config configures a GitLabTarget. Token is never logged.
type Config struct {
	// Project is the project path ("group/repo") or numeric project ID.
	Project string
	// BaseBranch is the branch MRs target and branch from; defaults to "main".
	BaseBranch string
	// Token is the GitLab access token used for authentication.
	Token string
	// BaseURL overrides the GitLab API base URL (e.g. an httptest server in
	// tests, or a self-managed GitLab host). Empty means public gitlab.com.
	BaseURL string
	// HTTPClient overrides the transport used to reach GitLab. When nil, the
	// client's default transport (carrying Token) is used.
	HTTPClient *http.Client
}

// GitLabTarget delivers a Change as a GitLab merge request. It implements
// scm.PRTarget. Construct with New or NewWithClient.
//
//nolint:revive // "GitLab" stutter with the package name is the clearest name for the exported type.
type GitLabTarget struct {
	client     *gitlab.Client
	project    string
	baseBranch string
}

// New builds a GitLabTarget from cfg, constructing a *gitlab.Client wired with
// the configured token and (optional) base URL. The token is held only inside
// the HTTP transport and is never logged.
func New(cfg Config) (*GitLabTarget, error) {
	if strings.TrimSpace(cfg.Project) == "" {
		return nil, fmt.Errorf("%s: Project is required", name)
	}

	opts := []gitlab.ClientOptionFunc{}
	if cfg.HTTPClient != nil {
		opts = append(opts, gitlab.WithHTTPClient(cfg.HTTPClient))
	}
	if strings.TrimSpace(cfg.BaseURL) != "" {
		opts = append(opts, gitlab.WithBaseURL(cfg.BaseURL))
	}

	client, err := gitlab.NewClient(cfg.Token, opts...)
	if err != nil {
		return nil, fmt.Errorf("%s: build client: %w", name, err)
	}

	return NewWithClient(client, cfg.Project, cfg.BaseBranch), nil
}

// NewWithClient builds a GitLabTarget from an already-constructed *gitlab.Client.
// This is the test seam: callers point the client at an httptest.Server. An
// empty baseBranch defaults to "main".
func NewWithClient(client *gitlab.Client, project, baseBranch string) *GitLabTarget {
	if strings.TrimSpace(baseBranch) == "" {
		baseBranch = defaultBaseBranch
	}
	return &GitLabTarget{
		client:     client,
		project:    project,
		baseBranch: baseBranch,
	}
}

// Name identifies the adapter.
func (t *GitLabTarget) Name() string { return name }

// Deliver opens a merge request carrying change.Patch as the full body of
// change.FilePath:
//
//  1. read the base branch to confirm it exists and has a commit;
//  2. detect whether the target branch already lingers from a prior run;
//  3. commit change.FilePath (create or update) onto the target branch via the
//     Commits API, taking the branch off the base branch in the same call and
//     force-resetting it to the current base when it already existed;
//  4. open a merge request from the target branch into the base branch.
//
// It returns scm.Ref{ID: MR IID, URL: MR web_url}. An already-existing merge
// request is tolerated: the existing MR is resolved and returned.
func (t *GitLabTarget) Deliver(ctx context.Context, change scm.Change) (scm.Ref, error) {
	if strings.TrimSpace(change.FilePath) == "" {
		return scm.Ref{}, fmt.Errorf("%s: change.FilePath is required", name)
	}
	if change.Patch == "" {
		return scm.Ref{}, fmt.Errorf("%s: change.Patch is empty", name)
	}

	// (1) Base branch must exist (gives a clear error before any mutation, and
	// confirms the branch-off ref is valid).
	base, _, err := t.client.Branches.GetBranch(t.project, t.baseBranch, gitlab.WithContext(ctx))
	if err != nil {
		return scm.Ref{}, fmt.Errorf("%s: get base branch %q: %w", name, t.baseBranch, err)
	}
	if base.Commit == nil || base.Commit.ID == "" {
		return scm.Ref{}, fmt.Errorf("%s: base branch %q has no commit", name, t.baseBranch)
	}

	// (2) Detect a lingering branch from a prior delivery. On a re-run the
	// commit must force-reset it to the freshly-resolved base, mirroring the
	// GitHub force-reset, so the MR sits on current base rather than a stale tree.
	branch := branchName(change)
	branchExists, err := t.branchExists(ctx, branch)
	if err != nil {
		return scm.Ref{}, err
	}

	// (3) Commit the file onto the target branch with the full body. CreateCommit
	// takes the branch off StartBranch (the base) and commits in one call; Force
	// reconciles a lingering branch back to that start point on a re-run.
	if err = t.commitFile(ctx, branch, branchExists, change); err != nil {
		return scm.Ref{}, err
	}

	// (4) Open the MR. On a re-run an open MR for this source branch may already
	// exist; GitLab answers Create with a 409 "merge request already exists".
	// Treat that as success by resolving and returning the existing MR.
	mr, _, err := t.client.MergeRequests.CreateMergeRequest(t.project, &gitlab.CreateMergeRequestOptions{
		Title:        gitlab.Ptr(mrTitle(change)),
		Description:  gitlab.Ptr(change.Description),
		SourceBranch: gitlab.Ptr(branch),
		TargetBranch: gitlab.Ptr(t.baseBranch),
	}, gitlab.WithContext(ctx))
	if err != nil {
		if isMergeRequestExists(err) {
			return t.existingMR(ctx, branch)
		}
		return scm.Ref{}, fmt.Errorf("%s: open merge request: %w", name, err)
	}

	return scm.Ref{ID: fmt.Sprintf("%d", mr.IID), URL: mr.WebURL}, nil
}

// existingMR resolves the open MR whose source branch is branch and returns its
// ref. It is the recovery path when CreateMergeRequest reports the MR already
// exists.
func (t *GitLabTarget) existingMR(ctx context.Context, branch string) (scm.Ref, error) {
	mrs, _, err := t.client.MergeRequests.ListProjectMergeRequests(t.project, &gitlab.ListProjectMergeRequestsOptions{
		State:        gitlab.Ptr("opened"),
		SourceBranch: gitlab.Ptr(branch),
		TargetBranch: gitlab.Ptr(t.baseBranch),
	}, gitlab.WithContext(ctx))
	if err != nil {
		return scm.Ref{}, fmt.Errorf("%s: list existing merge requests for %q: %w", name, branch, err)
	}
	if len(mrs) == 0 {
		return scm.Ref{}, fmt.Errorf("%s: merge request reported as existing for %q but none found", name, branch)
	}
	return scm.Ref{ID: fmt.Sprintf("%d", mrs[0].IID), URL: mrs[0].WebURL}, nil
}

// branchExists reports whether branch already exists in the project. A 404 means
// it does not (the common first-run case); any other error is propagated.
func (t *GitLabTarget) branchExists(ctx context.Context, branch string) (bool, error) {
	_, _, err := t.client.Branches.GetBranch(t.project, branch, gitlab.WithContext(ctx))
	switch {
	case err == nil:
		return true, nil
	case isNotFound(err):
		return false, nil
	default:
		return false, fmt.Errorf("%s: check branch %q: %w", name, branch, err)
	}
}

// commitFile commits change.FilePath onto branch with change.Patch as the full
// body, via the Commits API. CreateCommit takes the branch off StartBranch (the
// base branch) and commits in a single call. When the branch already existed
// (branchExists), Force resets it to the start point so the commit is based on
// current base rather than a stale prior tree.
//
// The action is create or update depending on whether the file already exists on
// the base branch: GitLab rejects a "create" for an existing path and an "update"
// for a missing one.
func (t *GitLabTarget) commitFile(ctx context.Context, branch string, branchExists bool, change scm.Change) error {
	action := gitlab.FileCreate
	exists, err := t.fileExistsOnBase(ctx, change.FilePath)
	if err != nil {
		return err
	}
	if exists {
		action = gitlab.FileUpdate
	}

	opts := &gitlab.CreateCommitOptions{
		Branch:        gitlab.Ptr(branch),
		StartBranch:   gitlab.Ptr(t.baseBranch),
		CommitMessage: gitlab.Ptr(commitMessage(change)),
		Actions: []*gitlab.CommitActionOptions{{
			Action:   gitlab.Ptr(action),
			FilePath: gitlab.Ptr(change.FilePath),
			Content:  gitlab.Ptr(change.Patch),
		}},
	}
	// Force only matters on the re-run/existing-branch path: it reconciles the
	// lingering branch to StartBranch (current base) before applying the commit.
	if branchExists {
		opts.Force = gitlab.Ptr(true)
	}

	if _, _, err := t.client.Commits.CreateCommit(t.project, opts, gitlab.WithContext(ctx)); err != nil {
		// A branch can appear between our existence probe and this commit (a
		// concurrent re-run). When it does, GitLab rejects the implicit branch
		// creation with a narrow 400 "already exists"; retry with Force to
		// reconcile it to the start point. Any other 400 (e.g. an invalid branch
		// name or ref) is a genuine bad request and must propagate.
		if !branchExists && isBranchExists(err) {
			opts.Force = gitlab.Ptr(true)
			if _, _, err = t.client.Commits.CreateCommit(t.project, opts, gitlab.WithContext(ctx)); err == nil {
				return nil
			}
		}
		return fmt.Errorf("%s: commit file %q: %w", name, change.FilePath, err)
	}
	return nil
}

// fileExistsOnBase reports whether filePath already exists on the base branch.
// A 404 means it does not (a create); any other error is propagated.
func (t *GitLabTarget) fileExistsOnBase(ctx context.Context, filePath string) (bool, error) {
	_, _, err := t.client.RepositoryFiles.GetFile(t.project, filePath, &gitlab.GetFileOptions{
		Ref: gitlab.Ptr(t.baseBranch),
	}, gitlab.WithContext(ctx))
	switch {
	case err == nil:
		return true, nil
	case isNotFound(err):
		return false, nil
	default:
		return false, fmt.Errorf("%s: read file %q: %w", name, filePath, err)
	}
}

// branchName derives a safe, namespaced branch name from the change. It uses
// the target file path as the discriminator so repeated deliveries for the same
// file reuse a branch (the already-exists path handles that gracefully).
func branchName(change scm.Change) string {
	return branchPrefix + slugify(change.FilePath)
}

// commitMessage builds a one-line commit subject from the change description,
// falling back to the file path.
func commitMessage(change scm.Change) string {
	subject := firstLine(change.Description)
	if subject == "" {
		subject = "update " + change.FilePath
	}
	return "fix: " + subject
}

// mrTitle builds an MR title from the severity and change description.
func mrTitle(change scm.Change) string {
	subject := firstLine(change.Description)
	if subject == "" {
		subject = "remediate " + change.FilePath
	}
	return fmt.Sprintf("[%s] %s", severityLabel(change.Severity), subject)
}

// severityLabel renders a Severity for an MR title, defaulting to "remediation"
// for the unknown level.
func severityLabel(s domain.Severity) string {
	if s == domain.SeverityUnknown {
		return "remediation"
	}
	return s.String()
}

// firstLine returns the first non-empty trimmed line of s.
func firstLine(s string) string {
	for line := range strings.SplitSeq(s, "\n") {
		if t := strings.TrimSpace(line); t != "" {
			return t
		}
	}
	return ""
}

// isMergeRequestExists reports whether err signals that an open merge request
// for the source branch already exists. GitLab answers CreateMergeRequest with
// HTTP 409 in that case.
func isMergeRequestExists(err error) bool {
	return hasStatus(err, http.StatusConflict)
}

// isBranchExists reports whether err signals that the branch already exists.
// GitLab returns HTTP 400 for this, but a 400 alone is too broad — an invalid
// branch name or ref also yields 400. So it must also carry an "already exists"
// message. This keeps genuine bad-request errors from being swallowed.
func isBranchExists(err error) bool {
	if !hasStatus(err, http.StatusBadRequest) {
		return false
	}
	var glErr *gitlab.ErrorResponse
	if errors.As(err, &glErr) {
		return strings.Contains(strings.ToLower(glErr.Message), "already exists")
	}
	return false
}

// isNotFound reports whether err is a GitLab 404.
func isNotFound(err error) bool {
	return hasStatus(err, http.StatusNotFound)
}

// hasStatus reports whether err is a *gitlab.ErrorResponse with the given HTTP
// status code.
func hasStatus(err error, code int) bool {
	var glErr *gitlab.ErrorResponse
	if errors.As(err, &glErr) {
		return glErr.StatusCode == code
	}
	return false
}

// slugSeparators matches any run of characters that are not safe in a git
// branch component; each run collapses to a single hyphen.
var slugSeparators = regexp.MustCompile(`[^a-zA-Z0-9._-]+`)

// slugify turns an arbitrary file path into a single safe branch component,
// e.g. "src/api/handler.go" -> "src-api-handler.go".
func slugify(path string) string {
	s := slugSeparators.ReplaceAllString(path, "-")
	s = strings.Trim(s, "-")
	if s == "" {
		return "change"
	}
	return s
}
