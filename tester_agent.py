from typing import TypedDict, List, Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from pydantic import BaseModel
from groq import (
    BadRequestError,
    RateLimitError,
    AuthenticationError,
    APIConnectionError,
    APITimeoutError,
)
from promptsUsedByAI import (
    POSITIVE_TEST_PROMPT,
    NEGATIVE_TEST_PROMPT,
    DESTRUCTIVE_TEST_PROMPT,
)

load_dotenv()


class TestCaseGenerationError(Exception):
    pass


PROMPT_MAP = {
    "positive": POSITIVE_TEST_PROMPT,
    "negative": NEGATIVE_TEST_PROMPT,
    "destructive": DESTRUCTIVE_TEST_PROMPT,
}


class TestCase(BaseModel):
    test_case_id: str = ""
    test_title: str = ""
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
    test_type: str
    test_cases: list
    model_used: str
    model: str


def test_cases_generator(state: State):
    test_type = state.get("test_type", "positive")
    model_name = state.get("model", "llama-3.3-70b-versatile")

    selected_prompt = PROMPT_MAP.get(
        test_type,
        POSITIVE_TEST_PROMPT
    )

    prompt = selected_prompt.format(
        user_story=state["user_story"]
    )

    try:
        print(f"Using selected model: {model_name}")

        llm = ChatGroq(
            model=model_name,
            temperature=0.2,
            max_tokens=4096,
            timeout=60,
            max_retries=1,
        )

        structured_llm = llm.with_structured_output(OutputSchema)

        result = structured_llm.invoke(prompt)

        if not result.test_cases:
            raise TestCaseGenerationError(
                "The AI did not generate any test cases. "
                "Try adding more details to the user story."
            )

        for test_case in result.test_cases:
            if not test_case.test_title:
                test_case.test_title = (
                    test_case.description or "Generated test case"
                )

        print(f"Success with model: {model_name}")

        return {
            "test_cases": result.test_cases,
            "model_used": model_name,
        }

    except RateLimitError:
        raise TestCaseGenerationError(
            f"The selected model reached its quota/rate limit: {model_name}. "
            "Please select another AI model from the dropdown."
        )

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

    except AuthenticationError:
        raise TestCaseGenerationError(
            "Authentication with Groq failed. "
            "Please check your API key and try again."
        )

    except APIConnectionError:
        raise TestCaseGenerationError(
            "Failed to connect to Groq API. "
            "Please check your network connection and try again."
        )

    except APITimeoutError:
        raise TestCaseGenerationError(
            "Request to Groq API timed out. "
            "Please try again later."
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


def generate_test_cases(
    user_input: str,
    test_type: str = "positive",
    model: str = "llama-3.3-70b-versatile",
):
    result = graph.invoke({
        "user_story": user_input,
        "test_type": test_type,
        "test_cases": [],
        "model_used": model,
        "model": model,
    })

    return {
        "test_cases": result["test_cases"],
        "model_used": result.get("model_used", model),
    }