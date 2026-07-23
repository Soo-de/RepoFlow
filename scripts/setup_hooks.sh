#!/usr/bin/env bash
# ==============================================================================
# Setup Script: Install Git Post-Push Hook for Automatic Local Develop Sync
# ==============================================================================
# Usage: ./scripts/setup_hooks.sh
# 
# What this does:
# Installs a .git/hooks/post-push hook that runs automatically after 'git push'.
# If your commit message contained [ship], [ready], or [merge], it waits for 
# GitHub Actions to finish merging into develop remotely, and fast-forwards
# your local 'develop' branch behind the scenes!
# ==============================================================================

set -e

HOOK_PATH=".git/hooks/post-push"

echo "Installing Git post-push hook to $HOOK_PATH..."

cat << 'EOF' > "$HOOK_PATH"
#!/usr/bin/env bash
# Git Post-Push Hook for Automatic Develop Sync

LAST_COMMIT_MSG=$(git log -1 --pretty=%B)

# Check if commit message contains release keywords
if echo "$LAST_COMMIT_MSG" | grep -iqE '\[ship\]|\[ready\]|\[merge\]'; then
    echo ""
    echo "'[ship]' keyword detected in push!"
    echo "Waiting for GitHub Actions AI Agent to test and merge into develop remotely..."
    
    # Poll remote develop in background
    (
        MAX_RETRIES=20
        RETRY_COUNT=0
        MERGED=false
        
        while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
            sleep 6
            RETRY_COUNT=$((RETRY_COUNT + 1))
            git fetch origin develop >/dev/null 2>&1
            
            HEAD_COMMIT=$(git rev-parse HEAD)
            if git merge-base --is-ancestor "$HEAD_COMMIT" origin/develop >/dev/null 2>&1; then
                MERGED=true
                break
            fi
        done
        
        if [ "$MERGED" = true ]; then
            CURRENT_FEATURE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
            git checkout develop >/dev/null 2>&1 || true
            git pull origin develop >/dev/null 2>&1 || git fetch origin develop:develop >/dev/null 2>&1
            if [ "$CURRENT_FEATURE_BRANCH" != "develop" ] && [ "$CURRENT_FEATURE_BRANCH" != "main" ]; then
                git branch -d "$CURRENT_FEATURE_BRANCH" >/dev/null 2>&1 || git branch -D "$CURRENT_FEATURE_BRANCH" >/dev/null 2>&1 || true
                echo "GitHub Action merged PR! Switched to 'develop' and auto-deleted branch '$CURRENT_FEATURE_BRANCH'."
            else
                echo "GitHub Action merged PR! Local 'develop' branch updated automatically."
            fi
        else
            echo "Timed out waiting for remote GitHub Action merge. Check GitHub Actions tab."
        fi
    ) &
fi
EOF

chmod +x "$HOOK_PATH"

echo "Git post-push hook installed successfully!"
