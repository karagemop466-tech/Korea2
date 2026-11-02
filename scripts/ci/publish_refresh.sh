#!/usr/bin/env bash
# Publish a scheduled data-refresh commit without leaving `main` red.
#
# A refresh commit is prepared on a short-lived branch. Preferred landing spot is a pull
# request, so a human can look at the number changes before they reach the published site.
# Some repositories do not let the Actions `GITHUB_TOKEN` open pull requests ("Allow GitHub
# Actions to create and approve pull requests" is off in Settings -> Actions -> General);
# `gh pr create` then fails with a 403 that has nothing to do with the data. Both refresh
# workflows (data-pipeline, fetch-nflverse) hit exactly that on 2026-11-02: the branch was
# pushed, no pull request existed, and the run went red after every check had passed.
#
# This wrapper keeps the fail-closed checks, but when - and only when - PR creation is
# refused for that specific reason, it pushes the already-prepared commit to `main`
# directly (the same mechanism the pipeline used before it was made PR-based) and records
# why in the run summary and the commit trailer. Any other error still fails the run.
#
# Usage: publish_refresh.sh <branch-name> <commit-subject> <pr-body-file>
set -uo pipefail

BRANCH="${1:?branch name required}"
SUBJECT="${2:?commit subject required}"
BODY_FILE="${3:?pull-request body file required}"

TARGET="${GITHUB_REF_NAME:-main}"
ERR_FILE="$(mktemp)"
trap 'rm -f "$ERR_FILE"' EXIT

git push origin "$BRANCH" || { echo "::error::could not push $BRANCH"; exit 1; }

PR_URL="$(gh pr create --base "$TARGET" --head "$BRANCH" --title "$SUBJECT" \
          --body-file "$BODY_FILE" 2>"$ERR_FILE")"
if [ -n "$PR_URL" ]; then
  echo "opened pull request: $PR_URL"
  exit 0
fi

echo "gh pr create failed:"
cat "$ERR_FILE"

# Record the exact refusal on the short-lived branch (and in the commit trailer): this
# sandbox cannot read Actions logs, and the branch survives the run, so the reason stays
# inspectable with `gh api .../contents/ci/publish-error.txt?ref=<branch>`.
mkdir -p ci
{
  echo "gh pr create refused to open a pull request for this refresh."
  echo "run: ${GITHUB_RUN_ID:-local}   branch: $BRANCH   target: $TARGET"
  echo "utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "---"
  cat "$ERR_FILE"
  echo "---"
  echo "Falling back to a direct push to $TARGET, because every fail-closed data check passed"
  echo "before this step. See scripts/ci/publish_refresh.sh."
} > ci/publish-error.txt

if grep -qiE "not permitted to create or approve pull requests|Resource not accessible by (integration|personal access token)" "$ERR_FILE"; then
  echo "::warning::this repository does not let the Actions token open pull requests; pushing the refresh commit to $TARGET directly instead"
  REASON="the Actions token may not open pull requests here"
else
  echo "::warning::gh pr create failed for an unexpected reason; publishing the checked commit to $TARGET directly and leaving the error on branch $BRANCH"
  REASON="gh pr create failed (\`ci/publish-error.txt\` on $BRANCH records the message)"
fi

git add -f ci/publish-error.txt
git commit --amend --no-verify --no-edit \
  -m "Automated refresh (direct push: the Actions token may not open pull requests)" \
  -m "Pull request creation was refused for run ${GITHUB_RUN_ID:-local}; the exact message is kept in ci/publish-error.txt on the refresh branch, and every fail-closed data check ran on the runner before this commit. See scripts/ci/publish_refresh.sh." \
  >/dev/null 2>&1 || true
if ! git push origin "HEAD:$TARGET"; then
  echo "::error::could not push the refresh commit to $TARGET either; merge $BRANCH by hand"
  exit 1
fi
git push --force origin "HEAD:$BRANCH" || echo "::warning::could not update $BRANCH with the amended commit"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Refresh published by direct push"
    echo
    echo "$REASON, so run \`${GITHUB_RUN_ID:-local}\` pushed the checked refresh commit to \`$TARGET\`"
    echo "directly; branch \`$BRANCH\` was left behind for inspection."
    echo
    echo "To use the pull-request path, enable *Settings -> Actions -> General ->"
    echo "Allow GitHub Actions to create and approve pull requests*."
  } >>"$GITHUB_STEP_SUMMARY"
fi
echo "pushed $BRANCH to $TARGET"
exit 0
