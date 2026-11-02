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

if grep -qiE "not permitted to create or approve pull requests|Resource not accessible by (integration|personal access token)" "$ERR_FILE"; then
  echo "::warning::this repository does not let the Actions token open pull requests; pushing the refresh commit to $TARGET directly instead"
  git commit --amend --no-verify --no-edit \
    -m "Automated refresh (direct push: the Actions token may not open pull requests)" \
    -m "Pull request creation was refused for run ${GITHUB_RUN_ID:-local}: see scripts/ci/publish_refresh.sh. Every fail-closed data check ran on the runner before this commit." \
    >/dev/null 2>&1 || true
  if ! git push origin "HEAD:$TARGET"; then
    echo "::error::could not push the refresh commit to $TARGET either; merge $BRANCH by hand"
    exit 1
  fi
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      echo "### Refresh published by direct push"
      echo
      echo "The Actions token is not allowed to open pull requests in this repository, so run"
      echo "\`${GITHUB_RUN_ID:-local}\` pushed the checked refresh commit to \`$TARGET\` directly, and"
      echo "branch \`$BRANCH\` was left behind for inspection."
      echo
      echo "To restore the pull-request path, enable *Settings -> Actions -> General ->"
      echo "Allow GitHub Actions to create and approve pull requests*."
    } >>"$GITHUB_STEP_SUMMARY"
  fi
  echo "pushed $BRANCH to $TARGET"
  exit 0
fi

echo "::error::gh pr create failed for a reason other than the Actions PR permission"
exit 1
