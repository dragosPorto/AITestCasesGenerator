import re

def format_numbered_steps(value):
    def clean_step(step):
        step = str(step).strip()

        while step and step[0] in ['"', "'"] and step[-1] in ['"', "'"]:
            step = step[1:-1].strip()

        return step

    if isinstance(value, list):
        steps = value
    elif isinstance(value, str):
        steps = re.split(r'\s*(?=\d+\.\s*)', value)
    else:
        steps = []

    formatted = "\n".join(
        f'{i}. "{clean_step(step)}"'
        for i, step in enumerate(steps, start=1)
        if str(step).strip()
    )

    # Safety: force newline before 2., 3., 4., etc.
    formatted = re.sub(r'(?<!^)(\d+\.\s")', r'\n\1', formatted)

    return formatted