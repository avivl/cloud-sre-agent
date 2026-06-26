// Package github implements the scm.PRTarget port by delivering a remediation
// as a real GitHub pull request. Each Deliver call branches off the configured
// base branch, writes change.Patch as the FULL file body via the Contents API,
// and opens a PR from the new branch into the base branch.
//
// The adapter treats change.Patch as the complete file body (per the port's
// "full file body" contract for this target), not a unified diff.
package github

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"

	gh "github.com/google/go-github/v88/github"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/scm"
)

// name is the adapter identifier reported by Name and used in logs/metrics.
const name = "github"

// defaultBaseBranch is used when Config.BaseBranch is empty.
const defaultBaseBranch = "main"

// branchPrefix namespaces every branch this adapter creates.
const branchPrefix = "sre-agent/"

// Config configures a GitHubTarget. Token is never logged.
type Config struct {
	// Owner is the repository owner (user or org).
	Owner string
	// Repo is the repository name.
	Repo string
	// BaseBranch is the branch PRs target and branch from; defaults to "main".
	BaseBranch string
	// Token is the GitHub access token used for authentication.
	Token string
	// BaseURL overrides the GitHub API base URL (e.g. an httptest server in
	// tests, or a GitHub Enterprise host). Empty means public github.com.
	BaseURL string
	// HTTPClient overrides the transport used to reach GitHub. When nil, an
	// oauth2 client carrying Token is used.
	HTTPClient *http.Client
}

// GitHubTarget delivers a Change as a GitHub pull request. It implements
// scm.PRTarget. Construct with New or NewWithClient.
//
//nolint:revive // "GitHub" stutter with the package name is the clearest name for the exported type.
type GitHubTarget struct {
	client     *gh.Client
	owner      string
	repo       string
	baseBranch string
}

// New builds a GitHubTarget from cfg, constructing a *github.Client wired with
// the configured token and (optional) base URL. The token is held only inside
// the HTTP transport and is never logged.
func New(cfg Config) (*GitHubTarget, error) {
	if strings.TrimSpace(cfg.Owner) == "" {
		return nil, fmt.Errorf("%s: Owner is required", name)
	}
	if strings.TrimSpace(cfg.Repo) == "" {
		return nil, fmt.Errorf("%s: Repo is required", name)
	}

	opts := []gh.ClientOptionsFunc{gh.WithAuthToken(cfg.Token)}
	if cfg.HTTPClient != nil {
		opts = append(opts, gh.WithHTTPClient(cfg.HTTPClient))
	}
	if strings.TrimSpace(cfg.BaseURL) != "" {
		// Same host serves API and uploads in tests / enterprise single-host setups.
		opts = append(opts, gh.WithEnterpriseURLs(cfg.BaseURL, cfg.BaseURL))
	}

	client, err := gh.NewClient(opts...)
	if err != nil {
		return nil, fmt.Errorf("%s: build client: %w", name, err)
	}

	return NewWithClient(client, cfg.Owner, cfg.Repo, cfg.BaseBranch), nil
}

// NewWithClient builds a GitHubTarget from an already-constructed *github.Client.
// This is the test seam: callers point the client at an httptest.Server. An
// empty baseBranch defaults to "main".
func NewWithClient(client *gh.Client, owner, repo, baseBranch string) *GitHubTarget {
	if strings.TrimSpace(baseBranch) == "" {
		baseBranch = defaultBaseBranch
	}
	return &GitHubTarget{
		client:     client,
		owner:      owner,
		repo:       repo,
		baseBranch: baseBranch,
	}
}

// Name identifies the adapter.
func (t *GitHubTarget) Name() string { return name }

// Deliver opens a pull request carrying change.Patch as the full body of
// change.FilePath:
//
//  1. read the base branch ref to find its commit SHA;
//  2. create a new branch ref off that SHA (tolerating an already-exists branch);
//  3. create-or-update change.FilePath via the Contents API with the full body;
//  4. open a PR from the new branch into the base branch.
//
// It returns scm.Ref{ID: PR number, URL: PR html_url}.
func (t *GitHubTarget) Deliver(ctx context.Context, change scm.Change) (scm.Ref, error) {
	if strings.TrimSpace(change.FilePath) == "" {
		return scm.Ref{}, fmt.Errorf("%s: change.FilePath is required", name)
	}
	if change.Patch == "" {
		return scm.Ref{}, fmt.Errorf("%s: change.Patch is empty", name)
	}

	// (1) Base branch commit SHA.
	baseRef, _, err := t.client.Git.GetRef(ctx, t.owner, t.repo, "refs/heads/"+t.baseBranch)
	if err != nil {
		return scm.Ref{}, fmt.Errorf("%s: get base ref %q: %w", name, t.baseBranch, err)
	}
	baseSHA := baseRef.GetObject().GetSHA()
	if baseSHA == "" {
		return scm.Ref{}, fmt.Errorf("%s: base ref %q has no commit SHA", name, t.baseBranch)
	}

	// (2) New branch off the base SHA. Tolerate "already exists" (HTTP 422): on a
	// re-run the branch lingers from a prior delivery, so force-reset it to the
	// freshly-resolved base SHA. Otherwise the PR would sit on a stale tree
	// rather than current base.
	branch := branchName(change)
	newRef := "refs/heads/" + branch
	if _, _, err = t.client.Git.CreateRef(ctx, t.owner, t.repo, gh.CreateRef{
		Ref: newRef,
		SHA: baseSHA,
	}); err != nil {
		if !isAlreadyExists(err) {
			return scm.Ref{}, fmt.Errorf("%s: create branch %q: %w", name, branch, err)
		}
		if _, _, err = t.client.Git.UpdateRef(ctx, t.owner, t.repo, newRef, gh.UpdateRef{
			SHA:   baseSHA,
			Force: gh.Ptr(true),
		}); err != nil {
			return scm.Ref{}, fmt.Errorf("%s: reset branch %q to base: %w", name, branch, err)
		}
	}

	// (3) Create-or-update the file on the new branch with the full body.
	if err = t.putFile(ctx, branch, change); err != nil {
		return scm.Ref{}, err
	}

	// (4) Open the PR. On a re-run an open PR for this head branch may already
	// exist; GitHub answers Create with a 422 "A pull request already exists".
	// Treat that as success by resolving and returning the existing PR.
	pr, _, err := t.client.PullRequests.Create(ctx, t.owner, t.repo, &gh.NewPullRequest{
		Title: gh.Ptr(prTitle(change)),
		Head:  gh.Ptr(branch),
		Base:  gh.Ptr(t.baseBranch),
		Body:  gh.Ptr(change.Description),
	})
	if err != nil {
		if isAlreadyExists(err) {
			return t.existingPR(ctx, branch)
		}
		return scm.Ref{}, fmt.Errorf("%s: open pull request: %w", name, err)
	}

	return prRef(pr), nil
}

// existingPR resolves the open PR whose head is branch and returns its ref. It
// is the recovery path when PullRequests.Create reports the PR already exists.
func (t *GitHubTarget) existingPR(ctx context.Context, branch string) (scm.Ref, error) {
	prs, _, err := t.client.PullRequests.List(ctx, t.owner, t.repo, &gh.PullRequestListOptions{
		State: "open",
		Head:  t.owner + ":" + branch,
	})
	if err != nil {
		return scm.Ref{}, fmt.Errorf("%s: list existing pull requests for %q: %w", name, branch, err)
	}
	if len(prs) == 0 {
		return scm.Ref{}, fmt.Errorf("%s: pull request reported as existing for %q but none found", name, branch)
	}
	return prRef(prs[0]), nil
}

// prRef projects a PR into the scm.Ref returned by Deliver.
func prRef(pr *gh.PullRequest) scm.Ref {
	return scm.Ref{
		ID:  fmt.Sprintf("%d", pr.GetNumber()),
		URL: pr.GetHTMLURL(),
	}
}

// putFile creates change.FilePath, or updates it (supplying the current blob
// SHA) when it already exists on the branch. change.Patch is the full body.
func (t *GitHubTarget) putFile(ctx context.Context, branch string, change scm.Change) error {
	opts := &gh.RepositoryContentFileOptions{
		Message: gh.Ptr(commitMessage(change)),
		Content: []byte(change.Patch),
		Branch:  gh.Ptr(branch),
	}

	existing, _, _, err := t.client.Repositories.GetContents(
		ctx, t.owner, t.repo, change.FilePath,
		&gh.RepositoryContentGetOptions{Ref: branch},
	)
	switch {
	case err == nil && existing == nil:
		// GetContents returns a nil file entry (with no error) when the path
		// resolves to a directory. Falling through to CreateFile would surface a
		// confusing GitHub error, so reject it explicitly.
		return fmt.Errorf("%s: path %q is a directory, expected a file", name, change.FilePath)
	case err == nil && existing.GetSHA() != "":
		opts.SHA = gh.Ptr(existing.GetSHA())
		if _, _, err = t.client.Repositories.UpdateFile(ctx, t.owner, t.repo, change.FilePath, opts); err != nil {
			return fmt.Errorf("%s: update file %q: %w", name, change.FilePath, err)
		}
	case err == nil || isNotFound(err):
		if _, _, err = t.client.Repositories.CreateFile(ctx, t.owner, t.repo, change.FilePath, opts); err != nil {
			return fmt.Errorf("%s: create file %q: %w", name, change.FilePath, err)
		}
	default:
		return fmt.Errorf("%s: read file %q: %w", name, change.FilePath, err)
	}
	return nil
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

// prTitle builds a PR title from the severity and change description.
func prTitle(change scm.Change) string {
	subject := firstLine(change.Description)
	if subject == "" {
		subject = "remediate " + change.FilePath
	}
	return fmt.Sprintf("[%s] %s", severityLabel(change.Severity), subject)
}

// severityLabel renders a Severity for a PR title, defaulting to "remediation"
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

// isAlreadyExists reports whether err is a GitHub 422 (reference already exists).
func isAlreadyExists(err error) bool {
	return hasStatus(err, http.StatusUnprocessableEntity)
}

// isNotFound reports whether err is a GitHub 404.
func isNotFound(err error) bool {
	return hasStatus(err, http.StatusNotFound)
}

// hasStatus reports whether err is a *github.ErrorResponse with the given HTTP
// status code.
func hasStatus(err error, code int) bool {
	var ghErr *gh.ErrorResponse
	if errors.As(err, &ghErr) && ghErr.Response != nil {
		return ghErr.Response.StatusCode == code
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
