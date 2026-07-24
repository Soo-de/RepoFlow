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


def normalize_parsed_yaml(parsed: object, line_map: dict[int, int] | None = None) -> object:
    """Normalize dictionary keys to handle YAML 1.1 boolean key conversion (e.g. `on:` parsed as True)."""
    if isinstance(parsed, dict):
        normalized = {}
        for key, value in parsed.items():
            norm_key = "on" if key is True else key
            normalized[norm_key] = normalize_parsed_yaml(value, line_map)
        if line_map is not None and id(parsed) in line_map:
            line_map[id(normalized)] = line_map[id(parsed)]
        return normalized
    if isinstance(parsed, list):
        normalized_list = [normalize_parsed_yaml(item, line_map) for item in parsed]
        if line_map is not None and id(parsed) in line_map:
            line_map[id(normalized_list)] = line_map[id(parsed)]
        return normalized_list
    return parsed


class SafeLineLoader(yaml.SafeLoader):
    """YAML safe loader that preserves line numbers of dictionary and list elements."""

    def __init__(self, stream) -> None:
        super().__init__(stream)
        self.line_map = {}

    def construct_object(self, node, deep=False) -> object:
        obj = super().construct_object(node, deep=deep)
        if isinstance(obj, (dict, list)):
            self.line_map[id(obj)] = node.start_mark.line + 1
        return obj




def get_step_script(step: dict) -> str | None:
    """Helper to extract script content from standard/custom script steps."""
    script = step.get("script") or step.get("run")
    if isinstance(script, str):
        return script

    task = step.get("task")
    if isinstance(task, str):
        task_lower = task.strip().lower()
        if task_lower.startswith("bash@") or task_lower.startswith("cmdline@") or task_lower.startswith("powershell@"):
            inputs = step.get("inputs")
            if isinstance(inputs, dict):
                inputs_script = inputs.get("script")
                if isinstance(inputs_script, str):
                    return inputs_script
    return None



def step_matches(step: dict, criteria: dict) -> bool:
    """Check if a step matches the given criteria."""
    if "key" in criteria:
        val = step.get(criteria["key"])
        if not isinstance(val, str):
            return False
        val_lower = val.strip().lower()
        if "starts_with" in criteria:
            return val_lower.startswith(criteria["starts_with"].lower())
        if "contains" in criteria:
            return criteria["contains"].lower() in val_lower

    if "script_contains" in criteria:
        script = get_step_script(step)
        if not script:
            return False
        script_lower = script.lower()
        return any(sub.lower() in script_lower for sub in criteria["script_contains"])

    return False


def check_required_root_keys(parsed: dict, rules: list[dict], errors: list[str]) -> None:
    """Ensure required top-level configuration keys exist."""
    for rule in rules:
        key = rule["key"]
        if key not in parsed:
            errors.append(f"Validation Error [root]: {rule['message']}")


def check_step_rules(steps: list[dict], rules: list[dict], line_map: dict[int, int], errors: list[str]) -> None:
    """Evaluate individual step rules (required properties, forbidden substrings, misplaced parameters)."""
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_line = line_map.get(id(step), "unknown")

        for rule in rules:
            if not step_matches(step, rule["match"]):
                continue

            rule_type = rule["type"]
            if rule_type == "required_property":
                target = step
                missing = False
                for part in rule["target_path"]:
                    if isinstance(target, dict) and part in target:
                        target = target[part]
                    else:
                        missing = True
                        break
                if missing:
                    errors.append(f"Validation Error [line {step_line}]: {rule['message']}")

            elif rule_type == "forbidden_substring":
                script = get_step_script(step)
                inverted = rule.get("inverted", False)
                if script:
                    has_sub = rule["substring"] in script
                    if (has_sub and not inverted) or (not has_sub and inverted):
                        errors.append(f"Validation Error [line {step_line}]: {rule['message']}")
                elif inverted:
                    errors.append(f"Validation Error [line {step_line}]: {rule['message']}")


            elif rule_type == "forbidden_input_property":
                inputs = step.get("inputs")
                if isinstance(inputs, dict) and rule["forbidden_property"] in inputs:
                    inputs_line = line_map.get(id(inputs), step_line)
                    errors.append(f"Validation Error [line {inputs_line}]: {rule['message']}")

            elif rule_type == "allowed_values":
                target = step
                missing = False
                for part in rule["target_path"]:
                    if isinstance(target, dict) and part in target:
                        target = target[part]
                    else:
                        missing = True
                        break
                if not missing:
                    val_lower = str(target).strip().lower()
                    allowed = [v.lower() for v in rule["values"]]
                    if val_lower not in allowed:
                        errors.append(f"Validation Error [line {step_line}]: {rule['message']}")

            elif rule_type == "property_type":
                target = step
                missing = False
                for part in rule["target_path"]:
                    if isinstance(target, dict) and part in target:
                        target = target[part]
                    else:
                        missing = True
                        break
                if not missing:
                    expected = rule["expected_type"]
                    is_valid_type = False
                    if expected == "string" and isinstance(target, str):
                        is_valid_type = True
                    elif expected == "string_or_number" and isinstance(target, (str, int, float)) and not isinstance(target, bool):
                        is_valid_type = True

                    if not is_valid_type:
                        errors.append(f"Validation Error [line {step_line}]: {rule['message']}")



def check_step_ordering(steps: list[dict], rules: list[dict], line_map: dict[int, int], errors: list[str]) -> None:
    """Enforce step declaration order limits."""
    for rule in rules:
        first_indexes = []
        second_indexes = []
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            if step_matches(step, rule["first"]):
                first_indexes.append(idx)
            if step_matches(step, rule["second"]):
                second_indexes.append(idx)

        if first_indexes and second_indexes:
            if min(first_indexes) > min(second_indexes):
                bad_step = steps[min(first_indexes)]
                bad_line = line_map.get(id(bad_step), "unknown")
                errors.append(f"Validation Error [line {bad_line}]: {rule['message']}")


def check_service_rules(parsed: dict, rule: dict, line_map: dict[int, int], errors: list[str], services_needed: list[str] | None = None) -> None:
    """Audit service container definitions to ensure only required servers run."""
    jobs = parsed.get("jobs", {})
    if not isinstance(jobs, dict):
        return

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue

        job_services = job.get("services")
        if isinstance(job_services, dict):
            job_services_line = line_map.get(id(job_services), line_map.get(id(job), "unknown"))
            for service_name in job_services:
                if services_needed is None or service_name not in services_needed:
                    needed_str = ", ".join(services_needed) if services_needed else "none"
                    msg = rule["message"].format(service=service_name, job=job_name, needed=needed_str)
                    errors.append(f"Validation Error [line {job_services_line}]: {msg}")


class PipelineValidator:
    """Platform-agnostic structural pipeline validator using PyYAML and JSON Schema."""

    def __init__(self, schemas_dir: Path | None = None) -> None:
        self._schemas_dir = schemas_dir or DEFAULT_SCHEMAS_DIR
        self._rules_file = self._schemas_dir / "validation_rules.json"

    def validate(self, platform: Platform, raw_yaml: str, services_needed: list[str] | None = None) -> tuple[bool, list[str]]:
        """Validate pipeline YAML syntax and structural JSON schema for the given platform."""
        errors: list[str] = []
        cleaned = strip_markdown_fences(raw_yaml)

        # Step 1: Validate YAML syntax using PyYAML
        loader = SafeLineLoader(cleaned)
        try:
            parsed = loader.get_single_data()
        except yaml.YAMLError as err:
            errors.append(f"YAML Syntax Error: {err}")
            return False, errors

        if not isinstance(parsed, dict):
            errors.append("Invalid YAML output: root of generated file must be a dictionary/object.")
            return False, errors

        parsed = normalize_parsed_yaml(parsed, loader.line_map)

        # Step 2: Validate against JSON Schema
        schema_file = self._schemas_dir / f"{platform.value}.schema.json"
        if not schema_file.exists():
            logger.warning("No JSON schema found for platform '%s' at %s", platform.value, schema_file)
            return True, []

        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = json.load(f)

            validator_cls = jsonschema.validators.validator_for(schema)
            validator = validator_cls(schema)
            for err in validator.iter_errors(parsed):
                line = loader.line_map.get(id(err.instance))
                if line is None and err.path:
                    # Resolve parent line number
                    parent = parsed
                    for step_val in list(err.path)[:-1]:
                        parent = parent[step_val]
                    line = loader.line_map.get(id(parent))

                path_str = " -> ".join(str(p) for p in err.path) or "root"
                line_info = f" [line {line}]" if line is not None else ""
                errors.append(f"Schema Error{line_info} [{path_str}]: {err.message}")

        except Exception as err:
            logger.exception("Failed loading/running schema validation for %s", platform.value)
            errors.append(f"Validation System Error: {err}")


        # Step 4: Run rule-based best practices from configuration
        if self._rules_file.exists():
            try:
                with open(self._rules_file, "r", encoding="utf-8") as f:
                    all_rules = json.load(f)

                platform_rules = all_rules.get(platform.value)
                if platform_rules:
                    # Check root keys
                    if "required_root_keys" in platform_rules:
                        check_required_root_keys(parsed, platform_rules["required_root_keys"], errors)

                    # Find all step lists
                    def find_step_lists(obj: object) -> list[list]:
                        lists = []
                        if isinstance(obj, dict):
                            if "steps" in obj and isinstance(obj["steps"], list):
                                lists.append(obj["steps"])
                            for val in obj.values():
                                lists.extend(find_step_lists(val))
                        elif isinstance(obj, list):
                            for item in obj:
                                lists.extend(find_step_lists(item))
                        return lists

                    step_lists = find_step_lists(parsed)

                    # Run step rules
                    if "step_rules" in platform_rules:
                        for steps in step_lists:
                            check_step_rules(steps, platform_rules["step_rules"], loader.line_map, errors)

                    # Run step ordering rules
                    if "step_ordering_rules" in platform_rules:
                        for steps in step_lists:
                            check_step_ordering(steps, platform_rules["step_ordering_rules"], loader.line_map, errors)

                    # Run service checks
                    if "service_rules" in platform_rules:
                        check_service_rules(parsed, platform_rules["service_rules"], loader.line_map, errors, services_needed)

            except Exception as err:
                logger.exception("Failed running rule-based validation")
                errors.append(f"Validation System Error (Rules Engine): {err}")

        return len(errors) == 0, errors


