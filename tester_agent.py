from typing import TypedDict, List, Literal, Union
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from pydantic import BaseModel
from groq import BadRequestError

load_dotenv()

class TestCaseGenerationError(Exception):
    pass

class TestCase(BaseModel):
    test_case_id: str = ""
    test_title: str
    description: str
    preconditions: str = ""
    postconditions: str = ""
    tags: str = ""
    type: str = "other"
    behavior: Literal["Positive", "Negative", "Destructive"] = "Positive"
    automation: str = "is-not-automated"
    status: str = "actual"
    is_flaky: str = "No"
    layer: str = ""
    steps_type: str = "classic"
    test_steps: List[str]
    steps_data: str = ""
    expected_result: List[str]
    comments: str = ""
    severity: str = "Normal"
    priority: str = "Medium"
    suite: str = "default suite"
    suite_id: int
    suite_without_cases_id: str
    is_muted: str = "No"


class OutputSchema(BaseModel):
    test_cases: List[TestCase]


class State(TypedDict):
    user_story: str
    test_cases: List[TestCase]


llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0
)


def test_cases_generator(state: State):
    structured_llm = llm.with_structured_output(OutputSchema)

    prompt = f"""
You are a test case generator.

Generate test cases for this user story:

{state["user_story"]}

Rules:
- Return test cases using the required schema.
- Do not generate test_case_id. Leave it empty.
- behavior must be exactly one of: Positive, Negative, Destructive.
- layer should be one of: E2E, API, Unit.
- type should be one of: functional, smoke, performance, security, usability, compatibility, regression, acceptance, integration, exploratory, other.
- automation should be "is-not-automated".
- status should always be "actual".
- steps_type should always be "classic".
- is_flaky should always be "No".
- is_muted should always be "No".
- severity must always be "Normal".
- priority must always be "Medium".
- suite_without_cases should be empty.
- suite should be the name of the test suite.
- suite represents the functionality or module the test case belongs to. If the user story doesn't specify it, use "default suite".
- suite_id should be a unique integer for each suite. If the user story doesn't specify it, use 0 for "default suite".
- test_steps and expected_result must have the same number of items.
- Each test_steps item must have one matching expected_result item at the same index.
- Do not group multiple expected results into fewer lines.
"""

    try:
        result = structured_llm.invoke(prompt)

        return {
            "test_cases": result.test_cases
        }

    except BadRequestError as e:
        error_text = str(e)

        if "Failed to parse tool call arguments as JSON" in error_text:
            raise TestCaseGenerationError(
                "Too many test cases were generated and the AI response became too large. "
                "Try simplifying the user story."
            )

        raise TestCaseGenerationError(
            f"AI generation failed: {error_text}"
        )

    except Exception as e:
        raise TestCaseGenerationError(
            f"Unexpected error: {str(e)}"
        )


graph_builder = StateGraph(State)

graph_builder.add_node("generator", test_cases_generator)
graph_builder.set_entry_point("generator")
graph_builder.set_finish_point("generator")

graph = graph_builder.compile()


def generate_test_cases(user_input: str):
    result = graph.invoke({
        "user_story": user_input,
        "test_cases": []
    })

    return result["test_cases"]