#!/usr/bin/env bash
# Track a monitoring failure as a GitHub issue.
#
#   incident.sh open    "<title>" "<details>"   opens an issue, unless one with this title is already open
#   incident.sh resolve "<title>"               closes the open issue with this title, if any
#
# One issue per problem: repeated failures don't open duplicates, and the issue closes itself
# when the check passes again. Needs GH_TOKEN with issues: write.
set -euo pipefail

action="$1"
title="$2"
details="${3:-}"
label="monitoring"
run_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"

existing=$(gh issue list --state open --label "$label" --search "\"$title\" in:title" \
  --json number,title --jq ".[] | select(.title == \"$title\") | .number" | head -n1)

case "$action" in
  open)
    if [ -n "$existing" ]; then
      echo "Issue #$existing is already open for: $title"
      exit 0
    fi
    gh label create "$label" --color D93F0B --description "Raised by a monitoring workflow" --force > /dev/null
    gh issue create --label "$label" --title "$title" --body "$(cat <<EOF
A scheduled check failed: $run_url

\`\`\`
$details
\`\`\`

See [docs/RUNBOOK.md](../blob/main/docs/RUNBOOK.md) for how to diagnose and fix this.
This issue closes itself when the check passes again.
EOF
)"
    ;;
  resolve)
    if [ -n "$existing" ]; then
      gh issue close "$existing" --comment "Check passed again: $run_url"
    fi
    ;;
  *)
    echo "usage: $0 open|resolve <title> [details]" >&2
    exit 2
    ;;
esac
