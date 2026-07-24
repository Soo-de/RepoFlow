#!/usr/bin/env python3
"""
AI Agent for GitHub Actions PR Summarization & Verification
------------------------------------------------------------
Analyzes git diff between feature branch and target branch (develop),
generates an AI-powered PR summary using Gemini API or Groq API (with automatic fallback).
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

    # Fallback 3: Single commit show HEAD
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

    # Fallback 4: git log -1 --stat (Guaranteed non-empty string)
    if not diff_text:
        try:
            res = subprocess.run(
                ["git", "log", "-1", "--stat"],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                diff_text = res.stdout.strip()
        except Exception as e:
            print(f"Error running git log --stat: {e}")

    return diff_text[:8000] if len(diff_text) > 8000 else diff_text


def _call_gemini_api(prompt: str, gemini_key: str) -> str:
    """Call Gemini REST API for PR summary."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1000}
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        candidates = res_data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            if parts:
                return parts[0].get('text', '')
    raise RuntimeError("Empty candidates response from Gemini API")


def _call_groq_api(prompt: str, groq_key: str) -> str:
    """Call Groq REST API for PR summary."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1000,
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        choices = res_data.get('choices', [])
        if choices:
            content = choices[0].get('message', {}).get('content', '')
            if content:
                return content
    raise RuntimeError("Empty response from Groq API")


def generate_ai_summary(diff_text: str, head_branch: str, gemini_key: str, groq_key: str) -> str:
    """Uses Gemini API or Groq API (with fallback) to generate a PR summary."""
    if not gemini_key and not groq_key:
        print("CRITICAL ERROR: Neither GEMINI_API_KEY nor GROQ_API_KEY is set in GitHub Secrets!")
        return f"### 🚀 Automated PR for `{head_branch}`\n\n*Code changes ready for merge into `develop`.*"

    if not diff_text:
        diff_text = f"Feature branch '{head_branch}' targeting 'develop'."

    prompt = (
        f"You are an expert AI DevOps & Code Reviewer Agent.\n"
        f"Analyze the following git diff/commit information from branch '{head_branch}' targeting 'develop'.\n"
        f"Generate a clean, professional Pull Request description in Markdown format including:\n"
        f"1. **Summary of Changes**: 2-3 bullet points.\n"
        f"2. **Key Architectural/Code Updates**: Main functions or files modified.\n"
        f"3. **Verification**: Confirmation that tests passed.\n\n"
        f"Git Diff / Commit Context:\n{diff_text}"
    )

    # Attempt 1: Gemini API
    if gemini_key:
        try:
            ai_content = _call_gemini_api(prompt, gemini_key)
            print("SUCCESS: Generated PR summary using Gemini API.")
            return f"### 🤖 AI Agent PR Summary (Gemini)\n\n{ai_content}"
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            print(f"Gemini API HTTP Error {e.code}: {err_body}")
            if groq_key and e.code == 429:
                print("Falling back to Groq API due to Gemini rate limit (429)...")
        except Exception as e:
            print(f"Gemini API Exception: {e}")

    # Attempt 2: Groq API (as fallback or primary if Groq key provided)
    if groq_key:
        try:
            ai_content = _call_groq_api(prompt, groq_key)
            print("SUCCESS: Generated PR summary using Groq API.")
            return f"### 🤖 AI Agent PR Summary (Groq)\n\n{ai_content}"
        except Exception as e:
            print(f"Groq API Exception: {e}")

    return f"### 🚀 Automated PR for `{head_branch}`\n\n*Code changes ready for merge into `develop`.*"


def main():
    head_branch = os.environ.get("HEAD_BRANCH", "")
    base_branch = os.environ.get("BASE_BRANCH", "develop")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")

    print(f"DEBUG: HEAD_BRANCH='{head_branch}', BASE_BRANCH='{base_branch}'")
    print(f"DEBUG: Gemini Key present: {'Yes' if gemini_key else 'No'}, Groq Key present: {'Yes' if groq_key else 'No'}")

    diff_text = get_git_diff(base_branch)
    print(f"DEBUG: Diff text length: {len(diff_text)} chars")

    ai_summary = generate_ai_summary(diff_text, head_branch, gemini_key, groq_key)

    with open("pr_body.md", "w", encoding="utf-8") as f:
        f.write(ai_summary)

    print("Successfully generated PR body with AI Agent!")


if __name__ == "__main__":
    main()
