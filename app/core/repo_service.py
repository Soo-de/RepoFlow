import asyncio
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

CLONE_TIMEOUT_SECONDS = 120


class CloneError(Exception):
    """Raised when git clone fails for any reason."""


def _inject_pat(url: str, pat: str) -> str:
    """Embed PAT into HTTPS URL for authentication."""
    parsed = urlparse(url)
    netloc_with_pat = f"{pat}@{parsed.hostname}"
    if parsed.port:
        netloc_with_pat += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc_with_pat))


def _parse_clone_error(stderr: str) -> str:
    """Extract a user-friendly message from git stderr output and sanitize secrets."""
    lower = stderr.lower()

    if (
        "authentication failed" in lower
        or "could not read username" in lower
        or "could not read password" in lower
        or "terminal prompts disabled" in lower
    ):
        return "Authentication failed — check your GitHub PAT or repository permissions"

    if "repository not found" in lower or "does not exist" in lower:
        return "Repository not found — check the URL"

    if "could not resolve host" in lower:
        return "Could not resolve host — check your network connection"

    if "fatal:" in lower:
        for line in stderr.splitlines():
            if line.strip().lower().startswith("fatal:"):
                # Sanitize any embedded token/password in URL (e.g. https://token@github.com)
                sanitized_line = line.strip()
                if "@" in sanitized_line and "https://" in sanitized_line:
                    import re
                    sanitized_line = re.sub(r"https://[^@]+@", "https://***@", sanitized_line)
                return sanitized_line

    return f"Clone failed: {stderr.strip()[:200]}"



async def clone(repo_url: str, pat: str = "") -> Path:
    """Clone a repository into a temporary directory (shallow, depth=1).

    Returns the workspace Path on success.
    Raises CloneError with a user-friendly message on failure.
    """
    clone_url = _inject_pat(repo_url, pat) if pat else repo_url
    workspace = Path(tempfile.mkdtemp(prefix="repoflow_"))
    repo_dir = workspace / "repo"

    # Prevent git from prompting for credentials interactively
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""

    logger.info("Cloning %s into %s", repo_url, repo_dir)

    process = await asyncio.create_subprocess_exec(
        "git", "-c", "credential.helper=", "clone", "--depth", "1", clone_url, str(repo_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=CLONE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        process.kill()
        raise CloneError(f"Clone timed out after {CLONE_TIMEOUT_SECONDS}s")

    if process.returncode != 0:
        stderr_text = stderr.decode(errors="replace")
        logger.error("git clone failed (exit %d): %s", process.returncode, stderr_text)
        raise CloneError(_parse_clone_error(stderr_text))

    if not repo_dir.exists():
        raise CloneError("Clone completed but repository directory is missing")

    logger.info("Clone successful: %s", repo_dir)
    return repo_dir

