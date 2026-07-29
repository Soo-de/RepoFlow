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
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          pytest
          echo "test results" >> $GITHUB_STEP_SUMMARY
"""
    passed, errors = validator.validate(Platform.GITHUB_ACTIONS, valid_yaml)


    assert passed is True
    assert len(errors) == 0


def test_validate_invalid_yaml_syntax():
    validator = PipelineValidator()
    invalid_yaml = "name: CI\non: [unclosed list"
    passed, errors = validator.validate(Platform.GITHUB_ACTIONS, invalid_yaml)
    assert passed is False
    assert any("YAML Syntax Error" in err for err in errors)


def test_validate_missing_schema_properties():
    validator = PipelineValidator()
    # Missing required 'jobs' field for GitHub Actions schema
    incomplete_yaml = """
name: CI
on: push
"""
    passed, errors = validator.validate(Platform.GITHUB_ACTIONS, incomplete_yaml)
    assert passed is False
    assert any("jobs" in err for err in errors)


def test_validate_line_numbers():
    validator = PipelineValidator()
    invalid_yaml = """
name: CI
on: push
jobs:
  build:
    runs-on: 123
    steps:
      - uses: actions/checkout@v4
"""
    passed, errors = validator.validate(Platform.GITHUB_ACTIONS, invalid_yaml)
    assert passed is False
    # The 'runs-on' parent property starts on line 5
    assert any("line 5" in err for err in errors)



def test_validate_azure_pipelines_valid_structure():
    validator = PipelineValidator()

    valid_azure = """
trigger:
  - main
pr:
  - main
pool:
  vmImage: 'ubuntu-latest'
steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.12'
  - script: pip install -r requirements.txt
    displayName: 'Install dependencies'
  - script: pytest
    displayName: 'Run tests'
"""
    passed, errors = validator.validate(Platform.AZURE_PIPELINES, valid_azure)
    assert passed is True
    assert len(errors) == 0


def test_best_practices_validation_github_actions():
    validator = PipelineValidator()

    # GHA missing concurrency and permissions (platform-level structural rules)
    invalid_yaml = """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest
"""
    passed, errors = validator.validate(Platform.GITHUB_ACTIONS, invalid_yaml)
    assert passed is False
    assert any("Concurrency controls" in err for err in errors)
    assert any("Permissions" in err for err in errors)


def test_best_practices_validation_azure_pipelines():
    validator = PipelineValidator()

    # Azure Pipeline missing pr trigger (platform-level structural rule)
    invalid_yaml = """
trigger:
  - main
pool:
  vmImage: 'ubuntu-latest'
steps:
  - script: echo "hello"
    displayName: 'Test'
"""
    passed, errors = validator.validate(Platform.AZURE_PIPELINES, invalid_yaml)

    assert passed is False
    assert any("pr" in err.lower() for err in errors)


def test_valid_azure_with_all_required_keys():
    validator = PipelineValidator()

    valid_yaml = """
trigger:
  - main
pr:
  - main
pool:
  vmImage: 'ubuntu-latest'
steps:
  - script: echo "hello"
    displayName: 'Test'
"""
    passed, errors = validator.validate(Platform.AZURE_PIPELINES, valid_yaml)
    assert passed is True
    assert len(errors) == 0


def test_validate_azure_pipelines_invalid_script_and_cache_keys():
    validator = PipelineValidator()

    invalid_yaml = """
trigger:
  - main
pr:
  - main
pool:
  vmImage: 'ubuntu-latest'
steps:
  - task: Cache@2
    inputs:
      key: 'cache-key'
      paths:
        - '$(Pipeline.Workspace)/.cache'
  - task: Bash@3
    displayName: 'Install'
    script: pip install -e .
"""
    passed, errors = validator.validate(Platform.AZURE_PIPELINES, invalid_yaml)
    assert passed is False
    assert any("Cache@2" in err and "path" in err for err in errors)
    assert any("task" in err and "script" in err for err in errors)


