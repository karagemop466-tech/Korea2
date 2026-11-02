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
# This wrapper keeps the fail-closed checks. When - and only when - PR creation is
# refused for that specific reason, it leaves the validated branch in place, records
# the limitation in the run summary and exits 0: nothing is published to the target
# branch without a review, and `main` is not red for a permission it cannot change.
# (An earlier version fell back to a direct push; `main` is protected so that push is
# refused, and a direct push would bypass the review issue #20 requires.) Any other
# error still fails the run.
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
  # Issue #20 correction (session arena/cacf6153-korea2, 2026-11-02): the earlier
  # fallback pushed the refresh commit straight to the target branch. `main` is
  # protected, so that push is refused anyway, and a direct push is exactly what
  # issue #20 forbids: a refresh that changes published numbers would bypass
  # review. The branch IS pushed and fully validated, so this is not a data
  # failure - it is a publishing-permission limitation. Leave the branch in place,
  # say so loudly, and finish green so `main` is not red for a permission it
  # cannot change. Nothing reaches `main` without a pull request.
  echo "::warning::the Actions token may not open pull requests; branch $BRANCH is pushed and validated but no pull request was opened. Open one from that branch, or enable Settings -> Actions -> General -> Allow GitHub Actions to create and approve pull requests."
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      echo "### Refresh branch pushed; pull request not opened"
      echo
      echo "Run \`${GITHUB_RUN_ID:-local}\` validated the refresh and pushed branch \`$BRANCH\`."
      echo "The repository refused pull-request creation to the Actions token, so nothing was"
      echo "pushed to \`$TARGET\` (and none should be: refreshes are reviewed before they publish)."
      echo
      echo "Open the pull request from \`$BRANCH\`, or enable *Settings -> Actions -> General ->"
      echo "Allow GitHub Actions to create and approve pull requests* to restore the automatic path."
    } >>"$GITHUB_STEP_SUMMARY"
  fi
  echo "pushed $BRANCH; open a pull request from it"
  exit 0
fi

echo "::error::gh pr create failed for a reason other than the Actions PR permission"
exit 1
