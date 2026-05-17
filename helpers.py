import re
from typing import Any, Dict, List, Optional

import pandas as pd
from langchain_groq import ChatGroq


# -----------------------------
# CSV / step formatting helpers
# -----------------------------
def format_numbered_steps(value: Any) -> str:
    """Format a list/string of steps into numbered CSV-friendly lines.

    Example output:
    1. "Open login page"
    2. "Enter valid credentials"
    """
    if not value:
        return ""

    if isinstance(value, list):
        steps = value
    else:
        steps = re.split(r"\s*(?=\d+\.\s*)", str(value))

    cleaned = []

    for step in steps:
        step = re.sub(r"^\d+\.\s*", "", str(step).strip())

        while step and len(step) >= 2 and step[0] in {"'", '"'} and step[-1] == step[0]:
            step = step[1:-1].strip()

        step = step.replace('"', "").replace("'", "")

        if step:
            cleaned.append(step)

    return "\n".join(
        f'{i}. "{step}"'
        for i, step in enumerate(cleaned, start=1)
    )


def align_steps(actions: List[str], results: List[str]) -> tuple[List[str], List[str]]:
    """Make sure actions/results have the same length without mutating originals."""
    actions = list(actions or [])
    results = list(results or [])

    max_len = max(len(actions), len(results))

    while len(results) < max_len:
        results.append("Expected result is verified.")

    while len(actions) < max_len:
        actions.append("Verify the expected result.")

    return actions, results


def parse_numbered_steps(value: Any) -> List[str]:
    """Parse numbered CSV step text back into a list of steps.

    Example input:
    1. "Open login page"
    2. "Enter valid credentials"
    """
    text = clean_value(value)

    if not text:
        return []

    parts = re.split(r"(?:^|\n)\s*\d+\.\s+", text)

    cleaned: List[str] = []

    for part in parts:
        part = part.strip()

        if not part:
            continue

        if len(part) >= 2 and part[0] in {"'", '"'} and part[-1] == part[0]:
            part = part[1:-1].strip()

        if part:
            cleaned.append(part)

    return cleaned


# -----------------------------
# Data cleaning / normalization
# -----------------------------
def clean_value(value: Any, default: str = "") -> str:
    """Convert None/NaN to default and strip regular values."""
    if value is None or pd.isna(value):
        return default
    return str(value).strip()


def normalize_key(value: Any) -> str:
    """Normalize labels/slugs for safe matching.

    Converts values like:
    - "Automation Status" -> "automation-status"
    - "is_flaky" -> "is-flaky"
    - "End to End" -> "end-to-end"
    """
    value = clean_value(value).lower()
    value = value.replace("_", "-")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def normalize_enum(value: Any, default: str = "") -> str:
    """Clean and normalize enum-like values."""
    return normalize_key(clean_value(value, default))


# -----------------------------
# Generic API response helpers
# -----------------------------
def extract_entities(response_body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract list-like entities from common API response shapes."""
    result = response_body.get("result", response_body)

    if isinstance(result, dict):
        entities = result.get("entities", result.get("suites", []))
        if isinstance(entities, list):
            return [item for item in entities if isinstance(item, dict)]

    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    return []


def extract_field_options(field: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract option dictionaries from common API field-option keys."""
    for option_key in ("values", "value", "options", "items"):
        options = field.get(option_key)
        if isinstance(options, list):
            return [option for option in options if isinstance(option, dict)]
    return []


def option_id(option: Dict[str, Any]) -> Optional[int]:
    """Extract a numeric option id from common option id keys."""
    for id_key in ("id", "value", "option_id"):
        raw_id = option.get(id_key)

        if isinstance(raw_id, bool):
            continue

        try:
            return int(raw_id)
        except (TypeError, ValueError):
            continue

    return None


# -----------------------------
# AI / Groq helper
# -----------------------------
def create_llm(model_name: str) -> ChatGroq:
    """Create a configured Groq chat model instance."""
    return ChatGroq(
        model=model_name,
        temperature=0.2,
        max_tokens=4096,
        timeout=60,
        max_retries=1,
    )
