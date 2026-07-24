#!/usr/bin/env bash
# ==============================================================================
# GitHub Actions Helper Script: PR Creation and Squash Auto-Merge
# ==============================================================================
# What this script does:
# 1. Ensures pr_body.md exists (created by AI Agent or fallback).
# 2. Checks if an open PR exists from HEAD_BRANCH to BASE_BRANCH.
# 3. Creates PR if none exists, or updates PR body if already open.
# 4. Merges PR into BASE_BRANCH using squash merge with AI body summary.
# ==============================================================================

set -e

# Fallback: Ensure pr_body.md exists
if [ ! -f pr_body.md ]; then
  echo "### Automated PR for \`$HEAD_BRANCH\`" > pr_body.md
fi

# Step 1: Search for existing open PR
PR_NUM=$(gh pr list --head "$HEAD_BRANCH" --base "$BASE_BRANCH" --json number --jq '.[0].number // empty')

if [ -z "$PR_NUM" ]; then
  echo "Creating Pull Request from $HEAD_BRANCH to $BASE_BRANCH..."
  CREATE_OUTPUT=$(gh pr create --base "$BASE_BRANCH" --head "$HEAD_BRANCH" --title "feat($HEAD_BRANCH): auto-merge into develop" --body-file pr_body.md 2>&1) || true
  echo "GH PR CREATE LOG: $CREATE_OUTPUT"
  PR_NUM=$(gh pr list --head "$HEAD_BRANCH" --base "$BASE_BRANCH" --json number --jq '.[0].number // empty')
else
  echo "Existing PR #$PR_NUM found. Updating description with AI summary..."
  gh pr edit "$PR_NUM" --body-file pr_body.md || true
fi

# Step 2: Merge PR into develop using AI Agent summary as squash commit message
if [ -n "$PR_NUM" ]; then
  echo "Merging PR #$PR_NUM into $BASE_BRANCH..."
  gh pr merge "$PR_NUM" --squash --body-file pr_body.md --admin || \
  gh pr merge "$PR_NUM" --squash --body-file pr_body.md --auto || \
  gh pr merge "$PR_NUM" --squash --body-file pr_body.md || \
  echo "PR merge request submitted to GitHub."
else
  echo "Warning: No open PR found for branch $HEAD_BRANCH."
fi
