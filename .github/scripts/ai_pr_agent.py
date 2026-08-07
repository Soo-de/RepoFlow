#!/usr/bin/env python3
import os
import subprocess
import json
import urllib.request
import urllib.parse
import urllib.error


def load_env_file(env_path: str = ".env") -> None:
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key, val = key.strip(), val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        print(f"DEBUG: Could not load {env_path}: {e}")


def get_git_diff(base_branch: str) -> str:
    diff_text = ""
    commands = [
        ["git", "diff", f"origin/{base_branch}...HEAD"],
        ["git", "log", f"origin/{base_branch}..HEAD", "-p"],
        ["git", "show", "HEAD"],
        ["git", "log", "-1", "--stat"],
    ]

    try:
        subprocess.run(["git", "fetch", "origin", base_branch], check=True, capture_output=True)
    except Exception as e:
        print(f"Error fetching base branch origin/{base_branch}: {e}")

    for cmd in commands:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                diff_text = res.stdout.strip()
                break
        except Exception:
            continue

    return diff_text[:8000] if len(diff_text) > 8000 else diff_text


def _make_http_post(url: str, headers: dict, payload: dict) -> dict:
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RepoFlow-AI-PR-Agent/1.0",
        "Content-Type": "application/json",
    }
    default_headers.update(headers)

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=default_headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _call_gemini_api(prompt: str, gemini_key: str) -> str:
    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    last_exception = None

    for model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1000}
        }
        try:
            res_data = _make_http_post(url, {}, payload)
            candidates = res_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
        except urllib.error.HTTPError as e:
            print(f"Gemini API ({model}) HTTP Error {e.code}")
            last_exception = e
            if e.code in (429, 404, 503):
                continue
            break
        except Exception as e:
            last_exception = e
            continue

    raise last_exception or RuntimeError("All Gemini models failed")


def _call_groq_api(prompt: str, groq_key: str) -> str:
    candidate_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {groq_key}"}
    last_exception = None

    for model in candidate_models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000,
        }
        try:
            res_data = _make_http_post(url, headers, payload)
            choices = res_data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    return content
        except urllib.error.HTTPError as e:
            print(f"Groq API ({model}) HTTP Error {e.code}")
            last_exception = e
            if e.code in (429, 404, 503):
                continue
            break
        except Exception as e:
            last_exception = e
            continue

    raise last_exception or RuntimeError("All Groq models failed")


def _call_openai_api(prompt: str, openai_key: str) -> str:
    candidate_models = ["gpt-4o-mini", "gpt-4o"]
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {openai_key}"}
    last_exception = None

    for model in candidate_models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000,
        }
        try:
            res_data = _make_http_post(url, headers, payload)
            choices = res_data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    return content
        except urllib.error.HTTPError as e:
            print(f"OpenAI API ({model}) HTTP Error {e.code}")
            last_exception = e
            if e.code in (429, 404, 503):
                continue
            break
        except Exception as e:
            last_exception = e
            continue

    raise last_exception or RuntimeError("All OpenAI models failed")


def generate_ai_summary(
    diff_text: str,
    head_branch: str,
    gemini_key: str,
    groq_key: str,
    openai_key: str = "",
    provider: str = "groq"
) -> str:
    provider = provider.lower().strip()
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

    providers = []
    if provider == "groq":
        providers = [("Groq", _call_groq_api, groq_key), ("OpenAI", _call_openai_api, openai_key)]
    elif provider == "openai":
        providers = [("OpenAI", _call_openai_api, openai_key)]
    elif provider == "gemini":
        providers = [("Gemini", _call_gemini_api, gemini_key)]
    else:
        providers = [
            ("Groq", _call_groq_api, groq_key),
            ("OpenAI", _call_openai_api, openai_key),
            ("Gemini", _call_gemini_api, gemini_key),
        ]

    for name, func, key in providers:
        if not key:
            continue
        try:
            content = func(prompt, key)
            print(f"SUCCESS: Generated PR summary using {name} API.")
            return f"### 🤖 AI Agent PR Summary ({name})\n\n{content}"
        except Exception as e:
            print(f"{name} API provider failed: {e}")

    print("WARNING: All AI providers failed. Falling back to default PR description.")
    return f"### 🚀 Automated PR for `{head_branch}`\n\n*Code changes ready for merge into `develop`.*"


def main():
    load_env_file()

    head_branch = os.environ.get("HEAD_BRANCH", "")
    base_branch = os.environ.get("BASE_BRANCH", "develop")
    provider = os.environ.get("LLM_PROVIDER", "groq")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    print(f"DEBUG: HEAD_BRANCH='{head_branch}', BASE_BRANCH='{base_branch}', LLM_PROVIDER='{provider}'")

    diff_text = get_git_diff(base_branch)
    print(f"DEBUG: Diff text length: {len(diff_text)} chars")

    ai_summary = generate_ai_summary(diff_text, head_branch, gemini_key, groq_key, openai_key, provider)

    with open("pr_body.md", "w", encoding="utf-8") as f:
        f.write(ai_summary)

    print("Successfully generated PR body with AI Agent!")


if __name__ == "__main__":
    main()
