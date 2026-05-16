from typing import TypedDict, List, Literal, Union
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from pydantic import BaseModel
from groq import BadRequestError, RateLimitError, AuthenticationError, APIConnectionError, APITimeoutError

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
    model="llama-3.3-70b-versatile",
    temperature=0
)


def test_cases_generator(state: State):
    structured_llm = llm.with_structured_output(OutputSchema)

    prompt = f"""
You are a test case generator.

Generate test cases for this user story:

{state["user_story"]}

Rules:
# ==========================================
# GENERAL OUTPUT RULES
# ==========================================
- Return test cases using the required schema.
- Do not generate test_case_id. Leave it empty.
- Keep descriptions concise and clear.

# ==========================================
# ENUM / ALLOWED VALUES
# ==========================================
- behavior must be exactly one of:
  - Positive
  - Negative
  - Destructive

- layer must be exactly one of:
  - E2E
  - API
  - Unit

- type must be exactly one of:
  - functional
  - smoke
  - performance
  - security
  - usability
  - compatibility
  - regression
  - acceptance
  - integration
  - exploratory
  - other

# ==========================================
# FIXED DEFAULT VALUES
# ==========================================
- automation must always be:
  "is-not-automated"

- status must always be:
  "actual"

- steps_type must always be:
  "classic"

- is_flaky must always be:
  "No"

- is_muted must always be:
  "No"

- tags must always be:
  "test-case-generator"

- severity must always be:
  "Normal"

- priority must always be:
  "Medium"

# ==========================================
# SUITE RULES
# ==========================================
- suite represents the functionality or module
  the test case belongs to.

- suite must contain the test suite name.

- If the functionality/module is unclear,
  use:
  "Default Suite"

- suite_without_cases must always be empty.

- suite_id must be:
  - a unique integer for each suite
  - 0 for "Default Suite"

# ==========================================
# TEST STEP RULES
# ==========================================
- test_steps must be a list of strings.
- expected_result must be a list of strings.

- test_steps and expected_result must
  contain the same number of items.

- Each test_steps item must have exactly
  one matching expected_result item
  at the same index.

- Do not group multiple expected results
  into a single item.

# ==========================================
# QUALITY RULES
# ==========================================
- Generate realistic QA test cases.
- Include positive, negative, and destructive
  scenarios when applicable.
- Test cases should be implementation-agnostic
  and business-focused.
"""

    try:
        result = structured_llm.invoke(prompt)

        if not result.test_cases:
            raise TestCaseGenerationError(
                "The AI did not generate any test cases. Try adding more details to the user story."
            )

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

    except RateLimitError:
        raise TestCaseGenerationError(
            "Groq quota or rate limit reached for the selected model. "
            "Please switch to another model or try again later."
    )
    except AuthenticationError:
        raise TestCaseGenerationError(
            "Authentication with Groq failed. Please check your API key and try again."
    )
    except APIConnectionError:
        raise TestCaseGenerationError(
            "Failed to connect to Groq API. Please check your network connection and try again."
    )
    except APITimeoutError:
        raise TestCaseGenerationError(
            "Request to Groq API timed out. Please try again later."
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