from typing import TypedDict, List, Literal, Union
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from pydantic import BaseModel

load_dotenv()


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
    layer: str = "unknown"
    steps_type: str = "classic"
    test_steps: List[str]
    steps_data: str = ""
    expected_result: List[str]
    comments: str = ""
    severity: int = 3
    priority: int = 3
    suite_id: str = ""
    suite_without_cases_id: str = "1"
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
- type should be "other".
- automation should be "is-not-automated".
- status should be "actual".
- steps_type should be "classic".
- is_flaky should be "No".
- is_muted should be "No".
- severity must be an integer from 1 to 5.
- priority must be an integer from 1 to 5.
"""

    result = structured_llm.invoke(prompt)

    return {"test_cases": result.test_cases}


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