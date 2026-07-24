"""
Unit tests for PipelineValidator module.
"""

from app.core.platform_detect import Platform
from app.core.validation import PipelineValidator, strip_markdown_fences


def test_strip_markdown_fences():
    raw = "```yaml\nname: CI\non: push\n```"
    assert strip_markdown_fences(raw) == "name: CI\non: push"

    raw_clean = "name: CI\non: push"
    assert strip_markdown_fences(raw_clean) == "name: CI\non: push"


def test_validate_valid_github_actions():
    validator = PipelineValidator()
    valid_yaml = """
name: CI
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest
"""
    result = validator.validate(Platform.GITHUB_ACTIONS, valid_yaml)
    assert result.passed is True
    assert len(result.errors) == 0


def test_validate_invalid_yaml_syntax():
    validator = PipelineValidator()
    invalid_yaml = "name: CI\non: [unclosed list"
    result = validator.validate(Platform.GITHUB_ACTIONS, invalid_yaml)
    assert result.passed is False
    assert any("YAML Syntax Error" in err for err in result.errors)


def test_validate_missing_schema_properties():
    validator = PipelineValidator()
    # Missing required 'jobs' field for GitHub Actions schema
    incomplete_yaml = """
name: CI
on: push
"""
    result = validator.validate(Platform.GITHUB_ACTIONS, incomplete_yaml)
    assert result.passed is False
    assert any("jobs" in err for err in result.errors)
