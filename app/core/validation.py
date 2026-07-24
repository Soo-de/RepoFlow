import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
import yaml
import jsonschema

from app.core.platform_detect import Platform

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMAS_DIR = BASE_DIR / "schemas"


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    cleaned_yaml: str = ""


def strip_markdown_fences(text: str) -> str:
    """Strip markdown code block fences (```yaml ... ```) if present in LLM response."""
    text = text.strip()
    pattern = r"^```(?:yaml|yml)?\s*\n(.*?)\n```$"
    match = re.match(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def normalize_parsed_yaml(parsed: object) -> object:
    """Normalize dictionary keys to handle YAML 1.1 boolean key conversion (e.g. `on:` parsed as True)."""
    if isinstance(parsed, dict):
        normalized = {}
        for key, value in parsed.items():
            norm_key = "on" if key is True else key
            normalized[norm_key] = normalize_parsed_yaml(value)
        return normalized
    if isinstance(parsed, list):
        return [normalize_parsed_yaml(item) for item in parsed]
    return parsed


class PipelineValidator:
    """Platform-agnostic structural pipeline validator using PyYAML and JSON Schema."""

    def __init__(self, schemas_dir: Path | None = None) -> None:
        self._schemas_dir = schemas_dir or DEFAULT_SCHEMAS_DIR

    def validate(self, platform: Platform, raw_yaml: str) -> ValidationResult:
        """Validate pipeline YAML syntax and structural JSON schema for the given platform."""
        errors: list[str] = []
        cleaned = strip_markdown_fences(raw_yaml)

        # Step 1: Validate YAML syntax using PyYAML
        try:
            parsed = yaml.safe_load(cleaned)
        except yaml.YAMLError as err:
            errors.append(f"YAML Syntax Error: {err}")
            return ValidationResult(passed=False, errors=errors, cleaned_yaml=cleaned)

        if not isinstance(parsed, dict):
            errors.append("Invalid YAML output: root of generated file must be a dictionary/object.")
            return ValidationResult(passed=False, errors=errors, cleaned_yaml=cleaned)

        parsed = normalize_parsed_yaml(parsed)

        # Step 2: Validate against JSON Schema
        schema_file = self._schemas_dir / f"{platform.value}.schema.json"
        if not schema_file.exists():
            logger.warning("No JSON schema found for platform '%s' at %s", platform.value, schema_file)
            return ValidationResult(passed=True, errors=[], cleaned_yaml=cleaned)

        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = json.load(f)

            validator = jsonschema.Draft202012Validator(schema)
            for err in validator.iter_errors(parsed):
                path_str = " -> ".join(str(p) for p in err.path) or "root"
                errors.append(f"Schema Error [{path_str}]: {err.message}")

        except Exception as err:
            logger.exception("Failed loading/running schema validation for %s", platform.value)
            errors.append(f"Validation System Error: {err}")

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            cleaned_yaml=cleaned,
        )
