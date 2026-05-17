import os
from typing import Any, Dict, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

from helpers import (
    clean_value,
    extract_entities,
    extract_field_options,
    normalize_enum,
    normalize_key,
    option_id,
    parse_numbered_steps,
)

# Load environment variables from .env file in the current directory (if it exists).
load_dotenv()

QASE_API_KEY = os.getenv("QASE_API_KEY")
QASE_BASE_URL = os.getenv("QASE_BASE_URL", "https://api.qase.io/v1").rstrip("/")
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

# These aliases allow Qase system fields to be matched even if Qase returns
# slightly different names/slugs for them.
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

# These aliases allow common CSV values to be mapped to Qase option values.
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


def get_qase_bulk_url(project_code: str) -> str:
    return f"{QASE_BASE_URL}/case/{project_code}/bulk"


def get_qase_suite_url(project_code: str) -> str:
    return f"{QASE_BASE_URL}/suite/{project_code}"


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
        raise QaseImportError(
            f"Could not connect to Qase: {exc}"
        ) from exc

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}

    error_message = ""

    if isinstance(body, dict):
        error_message = str(body.get("errorMessage", ""))

    if (
        response.status_code == 404
        and "Project not found" in error_message
    ):
        raise QaseImportError(
            "The Qase project code is incorrect or the project does not exist."
        )

    if response.status_code == 401:
        raise QaseImportError(
            "Qase authentication failed. Please check your API key."
        )

    if response.status_code >= 400:
        raise QaseImportError(
            f"Qase API error ({response.status_code}): "
            f"{error_message or body}"
        )

    return body


def _field_matches(field: Dict[str, Any], wanted_field: str) -> bool:
    aliases = FIELD_ALIASES.get(wanted_field, {wanted_field})

    field_keys = {
        normalize_key(field.get("slug", "")),
        normalize_key(field.get("code", "")),
        normalize_key(field.get("title", "")),
        normalize_key(field.get("name", "")),
        normalize_key(field.get("system_name", "")),
        normalize_key(field.get("entity", "")),
    }

    alias_keys = {normalize_key(alias) for alias in aliases}

    return bool(field_keys & alias_keys)


def _get_system_field_map() -> Dict[str, Dict[str, int]]:
    response_body = _request_json("GET", QASE_SYSTEM_FIELD_URL)
    fields = extract_entities(response_body)

    field_map: Dict[str, Dict[str, int]] = {field: {} for field in SYSTEM_ENUM_FIELDS}

    for wanted_field in SYSTEM_ENUM_FIELDS:
        matched_field = next(
            (field for field in fields if _field_matches(field, wanted_field)),
            None,
        )

        if not matched_field:
            continue

        for option in extract_field_options(matched_field):
            resolved_option_id = option_id(option)

            if resolved_option_id is None:
                continue

            for option_label_key in ("slug", "title", "name", "label", "value"):
                option_label = option.get(option_label_key)
                option_key = normalize_key(option_label)

                if option_key:
                    field_map[wanted_field][option_key] = resolved_option_id

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


def _get_existing_suites(project_code: str) -> Dict[str, int]:
    suites_by_title: Dict[str, int] = {}
    offset = 0
    limit = 100

    while True:
        response_body = _request_json(
            "GET",
            get_qase_suite_url(project_code),
            params={"limit": limit, "offset": offset},
        )
        entities = extract_entities(response_body)

        for suite in entities:
            title = clean_value(suite.get("title", ""))
            suite_id = suite.get("id")

            if title and suite_id is not None:
                suites_by_title[title.lower()] = int(suite_id)

        if len(entities) < limit:
            break

        offset += limit

    return suites_by_title


def _create_suite(title: str, project_code: str) -> int:
    response_body = _request_json(
        "POST",
        get_qase_suite_url(project_code),
        json={"title": title},
    )
    result = response_body.get("result", response_body)

    suite_id = result.get("id") if isinstance(result, dict) else None

    if suite_id is None:
        raise QaseImportError(
            f"Qase created suite '{title}' but did not return an id: {response_body}"
        )

    return int(suite_id)


def _get_or_create_suite_id(
    title: str,
    cache: Dict[str, int],
    project_code: str,
) -> Optional[int]:
    normalized_title = clean_value(title)

    if not normalized_title or normalized_title.lower() in {"default suite", "default"}:
        return None

    key = normalized_title.lower()

    if key not in cache:
        cache[key] = _create_suite(normalized_title, project_code)

    return cache[key]


def _build_case_from_row(
    row: pd.Series,
    suite_cache: Dict[str, int],
    system_field_map: Dict[str, Dict[str, int]],
    project_code: str,
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
    suite_id = _get_or_create_suite_id(
        clean_value(row.get("suite", "")),
        suite_cache,
        project_code,
    )

    if suite_id is not None:
        test_case["suite_id"] = suite_id

    return test_case


def add_csv_to_qase(
    csv_path: str = "test_cases.csv",
    project_code: str = "",
) -> Dict[str, Any]:
    project_code = clean_value(project_code).upper()

    if not project_code:
        raise QaseImportError("Qase project code is required.")

    df = pd.read_csv(csv_path).fillna("")

    suite_cache = _get_existing_suites(project_code)
    system_field_map = _get_system_field_map()
    test_case_payload = []

    for _, row in df.iterrows():
        test_case = _build_case_from_row(
            row,
            suite_cache,
            system_field_map,
            project_code,
        )

        if test_case is not None:
            test_case_payload.append(test_case)

    if not test_case_payload:
        raise QaseImportError("No valid test cases found in CSV.")

    payload = {"cases": test_case_payload}

    try:
        response_body = _request_json(
            "POST",
            get_qase_bulk_url(project_code),
            json=payload,
        )
    except Exception as e:
        error_text = str(e)

        if "Project not found" in error_text:
            raise QaseImportError(
                f"Qase project '{project_code}' not found. "
                "Please check the project code and try again."
            ) from e

        raise QaseImportError(
            f"Failed to import test cases to Qase: {error_text}"
        ) from e

    return {
        "success": True,
        "imported_count": len(test_case_payload),
        "project_code": project_code,
        "qase_response": response_body,
    }
