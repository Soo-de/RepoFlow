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



def test_validate_azure_pipelines_custom_tasks():
    validator = PipelineValidator()

    # 1. Valid Azure Pipeline with correct tasks
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
  - task: PublishTestResults@2
    inputs:
      testResultsFormat: 'JUnit'
      testResultsFiles: '**/test-*.xml'
"""
    passed, errors = validator.validate(Platform.AZURE_PIPELINES, valid_azure)
    assert passed is True
    assert len(errors) == 0

    # 2. Invalid Azure Pipeline with incorrect tasks
    invalid_azure = """
trigger:
  - main
pr:
  - main
pool:
  vmImage: 'ubuntu-latest'
steps:
  - task: UsePythonVersion@0
    inputs:
      addToPath: true
  - task: PublishTestResults@2
    inputs:
      testResultsFormat: 'InvalidFormat'
      testResultsFiles: 123
"""
    passed, errors = validator.validate(Platform.AZURE_PIPELINES, invalid_azure)


    assert passed is False
    # Check for specific missing parameter in UsePythonVersion
    assert any("versionSpec" in err for err in errors)
    # Check for invalid format in PublishTestResults
    assert any("testResultsFormat" in err for err in errors)
    # Check for type error in testResultsFiles (should be string)
    assert any("testResultsFiles" in err for err in errors)


def test_best_practices_validation_github_actions():
    validator = PipelineValidator()

    # GHA missing concurrency, permissions, setup-python version, unwanted postgres service, and missing test summary
    invalid_yaml = """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          cache: 'pip'
      - name: Run tests
        run: pytest
"""
    passed, errors = validator.validate(Platform.GITHUB_ACTIONS, invalid_yaml, services_needed=[])
    assert passed is False
    assert any("Concurrency controls" in err for err in errors)
    assert any("Permissions" in err for err in errors)
    assert any("postgres" in err and "not needed" in err for err in errors)
    assert any("setup-python" in err and "python-version" in err for err in errors)
    assert any("GITHUB_STEP_SUMMARY" in err for err in errors)


def test_best_practices_validation_azure_pipelines():
    validator = PipelineValidator()

    # Azure Pipeline with incorrect caching order, pip --target, misplaced condition (with triggers configured to avoid unrelated failures)
    invalid_yaml = """
trigger:
  - main
pr:
  - main
pool:
  vmImage: 'ubuntu-latest'
steps:
  - script: |
      pip install --target=$(PIP_CACHE_DIR) -r requirements.txt
    displayName: 'Install'
  - task: Cache@2
    inputs:
      key: 'key'
      path: '$(PIP_CACHE_DIR)'
  - task: PublishTestResults@2
    inputs:
      testRunner: 'JUnit'
      testResultsFiles: 'junit/test-results.xml'
      condition: succeededOrFailed()
"""
    passed, errors = validator.validate(Platform.AZURE_PIPELINES, invalid_yaml)

    assert passed is False
    assert any("Cache@2 task must be defined BEFORE" in err for err in errors)
    assert any("pip install --target" in err for err in errors)
    assert any("condition" in err and "outside" in err for err in errors)



