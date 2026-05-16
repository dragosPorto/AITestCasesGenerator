import requests
import os
from dotenv import load_dotenv
load_dotenv()

QASE_API_KEY = os.getenv('QASE_API_KEY')
url = "https://api.qase.io/v1/case/GA/bulk"
import requests

def add_bulk_to_qase(test_cases):
    test_case_payload = []

    for i, test_case in enumerate(test_cases, start=1):

        obj = {
            "v2.id": test_case.test_case_id,
            "title": test_case.test_title,
            "description": test_case.description,
            "preconditions": test_case.preconditions,
            "postconditions": test_case.postconditions,

            "tags": "",
            "priority": test_case.priority,
            "severity": test_case.severity,
            "type": "other",
            "behavior": "undefined",
            "automation": "is-not-automated",
            "status": "actual",
            "is_flaky": "no",
            "layer": "unknown",

            "steps_type": "classic",
            "steps_actions": test_case.test_steps,
            "steps_result": test_case.expected_result,
            "steps_data": "",

            "suite": "Default Suite",
            "suite_without_cases": "",
            "is_muted": "no"
        }

        test_case_payload.append(obj)

    payload = {"cases": test_case_payload}

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Token": QASE_API_KEY
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.status_code)
    print(response.text)