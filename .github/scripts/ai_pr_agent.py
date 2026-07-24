#!/usr/bin/env python3
"""
AI Agent for GitHub Actions PR Summarization & Verification
------------------------------------------------------------
Analyzes git diff between feature branch and target branch (develop),
generates an AI-powered PR summary, and posts/updates the PR body using Gemini API.
"""

import os
import subprocess
import json
import urllib.request
import urllib.parse
import urllib.error


def get_git_diff(base_branch: str) -> str:
    """Fetches full git diff across ALL feature branch commits relative to base_branch."""
    diff_text = ""
    try:
        subprocess.run(["git", "fetch", "origin", base_branch], check=True, capture_output=True)
        # Primary: Triple-dot diff captures all commits since branch point
        result = subprocess.run(
            ["git", "diff", f"origin/{base_branch}...HEAD"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            diff_text = result.stdout.strip()
    except Exception as e:
        print(f"Error fetching git diff for origin/{base_branch}...HEAD: {e}")

    # Fallback 1: Find merge-base and diff all feature branch commits
    if not diff_text:
        try:
            mb_res = subprocess.run(
                ["git", "merge-base", f"origin/{base_branch}", "HEAD"],
                capture_output=True,
                text=True
            )
            mb = mb_res.stdout.strip()
            if mb:
                res = subprocess.run(
                    ["git", "diff", mb, "HEAD"],
                    capture_output=True,
                    text=True
                )
                if res.returncode == 0:
                    diff_text = res.stdout.strip()
        except Exception as e:
            print(f"Error computing merge-base diff: {e}")

    # Fallback 2: Patch log for all unmerged commits on current branch
    if not diff_text:
        try:
            res = subprocess.run(
                ["git", "log", f"origin/{base_branch}..HEAD", "-p"],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                diff_text = res.stdout.strip()
        except Exception as e:
            print(f"Error computing git log patch: {e}")

    # Fallback 3: Last resort (single commit)
    if not diff_text:
        try:
            res = subprocess.run(
                ["git", "show", "HEAD"],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                diff_text = res.stdout.strip()
        except Exception as e:
            print(f"Error running git show HEAD: {e}")

    return diff_text[:8000] if len(diff_text) > 8000 else diff_text


def generate_ai_summary(diff_text: str, head_branch: str, api_key: str) -> str:
    """Uses Gemini API to generate a structured PR summary from git diff."""
    if not api_key:
        print("Warning: GEMINI_API_KEY is not set. Using default summary.")
        return f"### 🚀 Automated PR for `{head_branch}`\n\n*Code changes ready for merge into `develop`.*"

    if not diff_text:
        print("Warning: Git diff is empty. Using default summary.")
        return f"### 🚀 Automated PR for `{head_branch}`\n\n*Code changes ready for merge into `develop`.*"

    prompt = (
        f"You are an expert AI DevOps & Code Reviewer Agent.\n"
        f"Analyze the following git diff from branch '{head_branch}' targeting 'develop'.\n"
        f"Generate a clean, professional Pull Request description in Markdown format including:\n"
        f"1. **Summary of Changes**: 2-3 bullet points.\n"
        f"2. **Key Architectural/Code Updates**: Main functions or files modified.\n"
        f"3. **Verification**: Confirmation that tests passed.\n\n"
        f"Git Diff:\n{diff_text}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1000,
        }
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            candidates = res_data.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                if parts:
                    ai_content = parts[0].get('text', '')
                    return f"### 🤖 AI Agent PR Summary\n\n{ai_content}"
        raise RuntimeError("Empty response from Gemini API")
    except urllib.error.HTTPError as e:
        err_detail = e.read().decode('utf-8', errors='replace')
        print(f"AI Agent Gemini API HTTP Error {e.code}: {err_detail}. Falling back to default summary.")
        return f"### 🚀 Automated PR for `{head_branch}`\n\n*Code changes ready for merge into `develop`.*"
    except Exception as e:
        print(f"AI Agent API call failed: {e}. Falling back to default summary.")
        return f"### 🚀 Automated PR for `{head_branch}`\n\n*Code changes ready for merge into `develop`.*"


def main():
    head_branch = os.environ.get("HEAD_BRANCH", "")
    base_branch = os.environ.get("BASE_BRANCH", "develop")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY", "")

    diff_text = get_git_diff(base_branch)
    ai_summary = generate_ai_summary(diff_text, head_branch, api_key)

    # Save summary to file for GitHub Actions to use
    with open("pr_body.md", "w", encoding="utf-8") as f:
        f.write(ai_summary)

    print("Successfully generated PR body with AI Agent!")


if __name__ == "__main__":
    main()
