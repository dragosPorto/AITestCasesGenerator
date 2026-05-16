import os
import re
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

QASE_API_KEY = os.getenv("QASE_API_KEY")
QASE_PROJECT_CODE = os.getenv("QASE_PROJECT_CODE", "AT")
QASE_BASE_URL = os.getenv("QASE_BASE_URL", "https://api.qase.io/v1").rstrip("/")

QASE_BULK_URL = f"{QASE_BASE_URL}/case/{QASE_PROJECT_CODE}/bulk"
QASE_SUITE_URL = f"{QASE_BASE_URL}/suite/{QASE_PROJECT_CODE}"
QASE_SYSTEM_FIELD_URL = f"{QASE_BASE_URL}/system_field"

# These case fields must be sent to Qase as integer option IDs.
# The actual IDs can be customized per workspace, so we fetch them from
# /system_field instead of hardcoding values.
SYSTEM_ENUM_FIELDS = {
    "priority",
    "severity",
    "type",
    "behavior",
    "status",
    "automation",
    "layer",
    "is_flaky",
}

FIELD_ALIASES = {
    "priority": {"priority"},
    "severity": {"severity"},
    "type": {"type"},
    "behavior": {"behavior"},
    "status": {"status"},
    "automation": {"automation", "automation-status", "automation status"},
    "layer": {"layer"},
    "is_flaky": {"is_flaky", "is-flaky", "is flaky", "flaky"},
}

VALUE_ALIASES = {
    "status": {
        "actual": "active",  # Qase UI/docs call this Active; old CSV imports often use actual.
    },
    "automation": {
        "manual": "is-not-automated",
        "not-automated": "is-not-automated",
        "not automated": "is-not-automated",
        "is not automated": "is-not-automated",
        "is-not-automated": "is-not-automated",
        "to be automated": "to-be-automated",
        "tobeautomated": "to-be-automated",
    },
    "is_flaky": {
        "no": "false",
        "false": "false",
        "0": "false",
        "not flaky": "false",
        "yes": "true",
        "true": "true",
        "1": "true",
        "flaky": "true",
    },
    "layer": {
        "e2e": "end-to-end",
        "end to end": "end-to-end",
        "end-to-end": "end-to-end",
    },
}


class QaseImportError(Exception):
    """Raised when Qase rejects or cannot process the CSV import."""


def clean_value(value: Any, default: str = "") -> str:
    if value is None or pd.isna(value):
        return default
    return str(value).strip()


def _key(value: Any) -> str:
    """Normalize labels/slugs so CSV text can be matched to Qase field options."""
    value = clean_value(value).lower()
    value = value.replace("_", "-")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def normalize_enum(value: Any, default: str = "") -> str:
    return _key(clean_value(value, default))


def parse_numbered_steps(value: Any) -> List[str]:
    text = clean_value(value)

    if not text:
        return []

    parts = re.split(r"(?:^|\n)\s*\d+\.\s+", text)

    cleaned: List[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # export_to_excel stores each step as: 1. "Step text"
        if len(part) >= 2 and part[0] in {"'", '"'} and part[-1] == part[0]:
            part = part[1:-1].strip()

        if part:
            cleaned.append(part)

    return cleaned


def _qase_headers() -> Dict[str, str]:
    if not QASE_API_KEY:
        raise QaseImportError("Missing QASE_API_KEY in .env")

    return {
        "accept": "application/json",
        "content-type": "application/json",
        "Token": QASE_API_KEY,
    }


def _request_json(method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
    try:
        response = requests.request(
            method,
            url,
            headers=_qase_headers(),
            timeout=30,
            **kwargs,
        )
    except requests.RequestException as exc:
        raise QaseImportError(f"Could not connect to Qase: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}

    if response.status_code >= 400:
        raise QaseImportError(
            f"Qase API returned HTTP {response.status_code}: {body}"
        )

    return body


def _extract_entities(response_body: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = response_body.get("result", response_body)

    if isinstance(result, dict):
        entities = result.get("entities", result.get("suites", []))
        if isinstance(entities, list):
            return [item for item in entities if isinstance(item, dict)]

    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    return []


def _extract_field_options(field: Dict[str, Any]) -> List[Dict[str, Any]]:
    for option_key in ("values", "value", "options", "items"):
        options = field.get(option_key)
        if isinstance(options, list):
            return [option for option in options if isinstance(option, dict)]
    return []


def _field_matches(field: Dict[str, Any], wanted_field: str) -> bool:
    aliases = FIELD_ALIASES.get(wanted_field, {wanted_field})
    field_keys = {
        _key(field.get("slug", "")),
        _key(field.get("code", "")),
        _key(field.get("title", "")),
        _key(field.get("name", "")),
        _key(field.get("system_name", "")),
        _key(field.get("entity", "")),
    }
    alias_keys = {_key(alias) for alias in aliases}
    return bool(field_keys & alias_keys)


def _option_matches(option: Dict[str, Any], wanted_value: str) -> bool:
    wanted = _key(wanted_value)
    option_keys = {
        _key(option.get("slug", "")),
        _key(option.get("title", "")),
        _key(option.get("name", "")),
        _key(option.get("label", "")),
        _key(option.get("value", "")),
    }
    return wanted in option_keys


def _option_id(option: Dict[str, Any]) -> Optional[int]:
    for id_key in ("id", "value", "option_id"):
        raw_id = option.get(id_key)
        if isinstance(raw_id, bool):
            continue
        try:
            return int(raw_id)
        except (TypeError, ValueError):
            continue
    return None


def _get_system_field_map() -> Dict[str, Dict[str, int]]:
    response_body = _request_json("GET", QASE_SYSTEM_FIELD_URL)
    fields = _extract_entities(response_body)

    field_map: Dict[str, Dict[str, int]] = {field: {} for field in SYSTEM_ENUM_FIELDS}

    for wanted_field in SYSTEM_ENUM_FIELDS:
        matched_field = next(
            (field for field in fields if _field_matches(field, wanted_field)),
            None,
        )
        if not matched_field:
            continue

        for option in _extract_field_options(matched_field):
            option_id = _option_id(option)
            if option_id is None:
                continue

            for option_label_key in ("slug", "title", "name", "label", "value"):
                option_label = option.get(option_label_key)
                option_key = _key(option_label)
                if option_key:
                    field_map[wanted_field][option_key] = option_id

    return field_map


def _resolve_system_enum(
    field_name: str,
    raw_value: Any,
    default_value: str,
    system_field_map: Dict[str, Dict[str, int]],
) -> Optional[int]:
    value = normalize_enum(raw_value, default_value)
    aliases = VALUE_ALIASES.get(field_name, {})

    candidate_values = [value]
    alias_value = aliases.get(value) or aliases.get(clean_value(raw_value).lower())
    if alias_value:
        candidate_values.insert(0, normalize_enum(alias_value))

    options = system_field_map.get(field_name, {})
    for candidate in candidate_values:
        if candidate in options:
            return options[candidate]

    # Some Qase workspaces have disabled fields. In that case, omitting the field
    # is safer than sending text and getting a 422 validation error.
    if not options:
        return None

    allowed = ", ".join(sorted(options))
    raise QaseImportError(
        f"Unsupported Qase value for '{field_name}': '{raw_value}'. "
        f"Allowed values from your workspace are: {allowed}"
    )


def _get_existing_suites() -> Dict[str, int]:
    suites_by_title: Dict[str, int] = {}
    offset = 0
    limit = 100

    while True:
        response_body = _request_json(
            "GET",
            QASE_SUITE_URL,
            params={"limit": limit, "offset": offset},
        )
        entities = _extract_entities(response_body)

        for suite in entities:
            title = clean_value(suite.get("title", ""))
            suite_id = suite.get("id")
            if title and suite_id is not None:
                suites_by_title[title.lower()] = int(suite_id)

        if len(entities) < limit:
            break

        offset += limit

    return suites_by_title


def _create_suite(title: str) -> int:
    response_body = _request_json("POST", QASE_SUITE_URL, json={"title": title})
    result = response_body.get("result", response_body)

    if isinstance(result, dict):
        suite_id = result.get("id")
    else:
        suite_id = None

    if suite_id is None:
        raise QaseImportError(f"Qase created suite '{title}' but did not return an id: {response_body}")

    return int(suite_id)


def _get_or_create_suite_id(title: str, cache: Dict[str, int]) -> Optional[int]:
    normalized_title = clean_value(title)

    if not normalized_title or normalized_title.lower() in {"default suite", "default"}:
        return None

    key = normalized_title.lower()
    if key not in cache:
        cache[key] = _create_suite(normalized_title)

    return cache[key]


def _build_case_from_row(
    row: pd.Series,
    suite_cache: Dict[str, int],
    system_field_map: Dict[str, Dict[str, int]],
) -> Optional[Dict[str, Any]]:
    title = clean_value(row.get("title", ""))

    if not title:
        return None

    actions = parse_numbered_steps(row.get("steps_actions", ""))
    results = parse_numbered_steps(row.get("steps_result", ""))
    max_len = max(len(actions), len(results))

    qase_steps = []
    for i in range(max_len):
        qase_steps.append({
            "action": actions[i] if i < len(actions) else "",
            "expected_result": results[i] if i < len(results) else "",
            "data": clean_value(row.get("steps_data", "")),
        })

    test_case: Dict[str, Any] = {
        "title": title,
        "description": clean_value(row.get("description", "")),
        "preconditions": clean_value(row.get("preconditions", "")),
        "postconditions": clean_value(row.get("postconditions", "")),
        "steps_type": normalize_enum(row.get("steps_type", "classic"), "classic"),
        "steps": qase_steps,
    }

    defaults = {
        "severity": "normal",
        "priority": "medium",
        "type": "other",
        "behavior": "positive",
        "automation": "is-not-automated",
        "status": "actual",
        "layer": "e2e",
        "is_flaky": "no",
    }

    for field_name, default_value in defaults.items():
        resolved_id = _resolve_system_enum(
            field_name,
            row.get(field_name, default_value),
            default_value,
            system_field_map,
        )
        if resolved_id is not None:
            test_case[field_name] = resolved_id

    tags = clean_value(row.get("tags", ""))
    if tags:
        test_case["tags"] = [tag.strip() for tag in tags.split(",") if tag.strip()]

    # Do not trust the LLM-generated suite_id from the CSV. Qase expects a real
    # existing suite id. Use the suite title from the CSV and create it if needed.
    suite_id = _get_or_create_suite_id(clean_value(row.get("suite", "")), suite_cache)
    if suite_id is not None:
        test_case["suite_id"] = suite_id

    return test_case


def add_csv_to_qase(
    csv_path: str = "test_cases.csv",
    project_code: str = "AT"
) -> Dict[str, Any]:

    project_code = project_code.strip().upper()

    if not project_code:
        raise QaseImportError("Qase project code is required.")

    qase_bulk_url = (
        f"https://api.qase.io/v1/case/"
        f"{project_code}/bulk"
    )

    df = pd.read_csv(csv_path).fillna("")

    suite_cache = _get_existing_suites()
    system_field_map = _get_system_field_map()
    test_case_payload = []

    for _, row in df.iterrows():
        test_case = _build_case_from_row(
            row,
            suite_cache,
            system_field_map
        )

        if test_case is not None:
            test_case_payload.append(test_case)

    if not test_case_payload:
        raise QaseImportError("No valid test cases found in CSV.")

    payload = {
        "cases": test_case_payload
    }
    try:
        response_body = _request_json(
            "POST",
            qase_bulk_url,
            json=payload
        )
    except Exception as e:
        error_text = str(e)
        
        if "Project not found" in error_text:
            raise QaseImportError(
                f"Qase project '{project_code}' not found. "
                "Please check the project code and try again."
            )
        raise QaseImportError(f"Failed to import test cases to Qase: {error_text}") from e

    return {
        "success": True,
        "imported_count": len(test_case_payload),
        "project_code": project_code,
        "qase_response": response_body,
    }
