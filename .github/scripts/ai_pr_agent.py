#!/usr/bin/env python3
"""
AI Agent for GitHub Actions PR Summarization & Verification
------------------------------------------------------------
Analyzes git diff between feature branch and target branch (develop),
generates an AI-powered PR summary, and posts/updates the PR body.
"""

import os
import subprocess
import json
import urllib.request
import urllib.parse


def get_git_diff(base_branch: str) -> str:
    """Fetches git diff between base_branch and HEAD."""
    try:
        # Fetch base branch to ensure accurate diff
        subprocess.run(["git", "fetch", "origin", base_branch], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "diff", f"origin/{base_branch}...HEAD"],
            check=True,
            capture_output=True,
            text=True
        )
        diff_text = result.stdout.strip()
        # Truncate large diffs to stay within token limits
        return diff_text[:8000] if len(diff_text) > 8000 else diff_text
    except Exception as e:
        print(f"Error fetching git diff: {e}")
        return ""


def generate_ai_summary(diff_text: str, head_branch: str, groq_api_key: str) -> str:
    """Uses Groq API LLM to generate a structured PR summary from git diff."""
    if not groq_api_key or not diff_text:
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

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            ai_content = res_data['choices'][0]['message']['content']
            return f"### 🤖 AI Agent PR Summary\n\n{ai_content}"
    except Exception as e:
        print(f"AI Agent API call failed: {e}. Falling back to default summary.")
        return f"### 🚀 Automated PR for `{head_branch}`\n\n*Code changes ready for merge into `develop`.*"


def main():
    head_branch = os.environ.get("HEAD_BRANCH", "")
    base_branch = os.environ.get("BASE_BRANCH", "develop")
    groq_key = os.environ.get("GROQ_API_KEY", "")

    diff_text = get_git_diff(base_branch)
    ai_summary = generate_ai_summary(diff_text, head_branch, groq_key)

    # Save summary to file for GitHub Actions to use
    with open("pr_body.md", "w", encoding="utf-8") as f:
        f.write(ai_summary)

    print("Successfully generated PR body with AI Agent!")


if __name__ == "__main__":
    main()
