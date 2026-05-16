from helpers import align_steps, format_numbered_steps
import csv


def export_to_excel(test_cases):
    import pandas as pd

    rows = []

    for test_case in test_cases:
        actions, results = align_steps(
            test_case.test_steps,
            test_case.expected_result
        )
        rows.append({
            "v2.id": test_case.test_case_id,
            "title": test_case.test_title,
            "description": test_case.description,
            "preconditions": test_case.preconditions,
            "postconditions": test_case.postconditions,

            "tags": test_case.tags,
            "priority": test_case.priority,
            "severity": test_case.severity,
            "type": test_case.type,
            "behavior": test_case.behavior,
            "automation": test_case.automation,
            "status": test_case.status,
            "is_flaky": test_case.is_flaky,
            "layer": test_case.layer,

            "steps_type": test_case.steps_type,
            "steps_actions": format_numbered_steps(actions),
            "steps_result": format_numbered_steps(results),
            "steps_data": test_case.steps_data,

            "suite": test_case.suite,
            "suite_id": test_case.suite_id,
            "suite_without_cases": test_case.suite_without_cases_id,
            "is_muted": test_case.is_muted,
        })

    df = pd.DataFrame(rows)

    expected_columns = [
        "v2.id", "title", "description", "preconditions", "postconditions",
        "tags", "priority", "severity", "type", "behavior", "automation",
        "status", "is_flaky", "layer",
        "steps_type", "steps_actions", "steps_result", "steps_data",
        "suite", "suite_id", "suite_without_cases", "is_muted"
    ]

    df = df.reindex(columns=expected_columns)

    # Save as CSV
    
    df.to_csv(
        "test_cases.csv",
        index=False,
        encoding="utf-8"
)