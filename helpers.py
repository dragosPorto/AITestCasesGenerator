import re
from langchain_groq import ChatGroq

def format_numbered_steps(value):
    import re

    if not value:
        return ""

    if isinstance(value, list):
        steps = value
    else:
        steps = re.split(r'\s*(?=\d+\.\s*)', str(value))

    cleaned = []

    for step in steps:
        step = re.sub(r'^\d+\.\s*', '', str(step).strip())

        while step and step[0] in ['"', "'"] and step[-1] in ['"', "'"]:
            step = step[1:-1].strip()

        step = step.replace('"', '').replace("'", "")

        if step:
            cleaned.append(step)

    return "\n".join(
        f'{i}. "{step}"'
        for i, step in enumerate(cleaned, start=1)
    )

def align_steps(actions, results):
    actions = list(actions or [])
    results = list(results or [])

    max_len = max(len(actions), len(results))

    while len(results) < max_len:
        results.append("Expected result is verified.")

    while len(actions) < max_len:
        actions.append("Verify the expected result.")

    return actions, results

def create_llm(model_name):
    return ChatGroq(
        model=model_name,
        temperature=0.2
    )