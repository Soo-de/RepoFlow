"""
Unit tests for repo_service module (git clone functionality, PAT authentication, error parsing).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.repo_service import (
    CloneError,
    _inject_pat,
    _parse_clone_error,
    clone,
)


def test_inject_pat_https():
    url = "https://github.com/org/private-repo.git"
    pat = "ghp_secret_token_123"
    injected = _inject_pat(url, pat)
    assert injected == "https://ghp_secret_token_123@github.com/org/private-repo.git"


def test_inject_pat_with_port():
    url = "https://git.mycompany.com:8443/org/repo.git"
    pat = "token123"
    injected = _inject_pat(url, pat)
    assert injected == "https://token123@git.mycompany.com:8443/org/repo.git"


def test_parse_clone_error_auth_failed():
    stderr = "fatal: Authentication failed for 'https://github.com/org/repo.git/'"
    parsed = _parse_clone_error(stderr)
    assert parsed == "Authentication failed — check your GitHub PAT or repository permissions"


def test_parse_clone_error_auth_failed_generic():
    stderr = "fatal: Authentication failed for 'https://custom-git.internal/org/repo.git/'"
    parsed = _parse_clone_error(stderr)
    assert parsed == "Authentication failed — check your PAT or repository permissions"


def test_parse_clone_error_could_not_read_username():
    stderr = "fatal: could not read Username for 'https://github.com': terminal prompts disabled"
    parsed = _parse_clone_error(stderr)
    assert "Authentication failed" in parsed


def test_parse_clone_error_could_not_read_password():
    stderr = "fatal: could not read Password for 'https://gsk_secret123@github.com': terminal prompts disabled"
    parsed = _parse_clone_error(stderr)
    assert "Authentication failed" in parsed
    assert "gsk_secret123" not in parsed



def test_parse_clone_error_repo_not_found():
    stderr = "remote: Repository not found.\nfatal: repository 'https://github.com/org/nonexistent.git/' not found"
    parsed = _parse_clone_error(stderr)
    assert parsed == "Repository not found — check the URL"


def test_parse_clone_error_host_unreachable():
    stderr = "fatal: unable to access 'https://github.com/org/repo.git/': Could not resolve host: github.com"
    parsed = _parse_clone_error(stderr)
    assert parsed == "Could not resolve host — check your network connection"


@pytest.mark.asyncio
async def test_clone_public_repo_success(tmp_path):
    repo_url = "https://github.com/org/public-repo.git"

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("tempfile.mkdtemp", return_value=str(tmp_path)):
            repo_dir = tmp_path / "repo"
            repo_dir.mkdir(parents=True, exist_ok=True)

            result_dir = await clone(repo_url)
            assert result_dir == repo_dir
            assert result_dir.exists()


@pytest.mark.asyncio
async def test_clone_private_repo_no_pat():
    repo_url = "https://github.com/org/private-repo.git"

    mock_process = AsyncMock()
    mock_process.returncode = 128
    mock_process.communicate.return_value = (
        b"",
        b"fatal: could not read Username for 'https://github.com': terminal prompts disabled",
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(CloneError, match="Authentication failed — check your GitHub PAT or repository permissions"):
            await clone(repo_url, pat="")


@pytest.mark.asyncio
async def test_clone_private_repo_invalid_pat():
    repo_url = "https://github.com/org/private-repo.git"
    invalid_pat = "invalid_token_xyz"

    mock_process = AsyncMock()
    mock_process.returncode = 128
    mock_process.communicate.return_value = (
        b"",
        b"remote: Invalid username or password.\nfatal: Authentication failed for 'https://invalid_token_xyz@github.com/org/private-repo.git/'",
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(CloneError, match="Authentication failed — check your GitHub PAT or repository permissions"):
            await clone(repo_url, pat=invalid_pat)


@pytest.mark.asyncio
async def test_clone_invalid_repo_url():
    invalid_url = "https://github.com/nonexistent_user_12345/nonexistent_repo.git"

    mock_process = AsyncMock()
    mock_process.returncode = 128
    mock_process.communicate.return_value = (
        b"",
        b"remote: Repository not found.\nfatal: repository 'https://github.com/nonexistent_user_12345/nonexistent_repo.git/' not found",
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(CloneError, match="Repository not found — check the URL"):
            await clone(invalid_url)


@pytest.mark.asyncio
async def test_clone_timeout():
    repo_url = "https://github.com/org/large-repo.git"

    mock_process = AsyncMock()
    mock_process.kill = MagicMock()
    mock_process.communicate.side_effect = asyncio.TimeoutError()

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("app.core.repo_service.CLONE_TIMEOUT_SECONDS", 0.1):
            with pytest.raises(CloneError, match="Clone timed out"):
                await clone(repo_url)

