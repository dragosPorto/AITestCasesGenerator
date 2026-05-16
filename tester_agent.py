from typing import TypedDict, List, Literal, Union
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from pydantic import BaseModel
from groq import BadRequestError, RateLimitError, AuthenticationError, APIConnectionError, APITimeoutError

load_dotenv()

GROQ_MODELS = [
    "llama-3.3-70b-versatile",   # primary
    "qwen/qwen3-32b",            # backup 1
    "llama-3.1-8b-instant",      # backup 2
]

class TestCaseGenerationError(Exception):
    pass

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
    test_cases: List[TestCase]
    model_used: str


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)


def test_cases_generator(state: State):
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
- test_title is required for every test case.
- test_title must be a short, clear title.
- Do not leave test_title empty.

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

    last_error = None

    for model_name in GROQ_MODELS:
        try:
            print(f"Trying model: {model_name}")

            llm = ChatGroq(
                model=model_name,
                temperature=0
            )

            structured_llm = llm.with_structured_output(
                OutputSchema
            )

            result = structured_llm.invoke(prompt)

            if not result.test_cases:
                raise TestCaseGenerationError(
                    "The AI did not generate any test cases. "
                    "Try adding more details to the user story."
                )

            for test_case in result.test_cases:
                if not test_case.test_title:
                    test_case.test_title = test_case.description or "Generated test case"
                    
            print(f"Success with model: {model_name}")

            return {
                "test_cases": result.test_cases,
                "model_used": model_name
            }

        except RateLimitError as e:
            print(f"Quota reached for {model_name}")

            last_error = e
            continue

        except BadRequestError as e:
            error_text = str(e)

            if (
                "Failed to parse tool call arguments as JSON"
                in error_text
            ):
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
            print(f"Model failed: {model_name}")
            print(f"Error: {str(e)}")
            continue

            # Catch hidden quota errors
        except Exception as e:
            error_text = str(e).lower()
            if (
                "rate limit" in error_text
                or "quota" in error_text
                or "429" in error_text
                or "tokens per day" in error_text
                or "tokens per minute" in error_text
            ):
                print(f"Fallback triggered for {model_name}")

                last_error = e
                continue

            raise TestCaseGenerationError(
                f"Unexpected error: {str(e)}"
            )

    raise TestCaseGenerationError(
        "All available Groq models reached their quota/rate limit. "
        "Please try again later."
    )


graph_builder = StateGraph(State)

graph_builder.add_node("generator", test_cases_generator)
graph_builder.set_entry_point("generator")
graph_builder.set_finish_point("generator")

graph = graph_builder.compile()


def generate_test_cases(user_input: str):
    result = graph.invoke({
        "user_story": user_input,
        "test_cases": [],
        "model_used": ""
    })

    return {
        "test_cases": result["test_cases"],
        "model_used": result.get("model_used", "unknown")
    }