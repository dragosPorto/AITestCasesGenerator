from typing import TypedDict, List, Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from pydantic import BaseModel
from groq import BadRequestError, RateLimitError, AuthenticationError, APIConnectionError, APITimeoutError
from promptsUsedByAI import TEST_CASE_GENERATION_PROMPT

load_dotenv()

# Groq model names to try in order, with fallbacks in case of quota limits or errors
GROQ_MODELS = [
    "openai/gpt-oss-120b",       # primary
    "llama-3.3-70b-versatile",   # backup 1
    "qwen/qwen3-32b",            # backup 2
    "llama-3.1-8b-instant",      # backup 3
]

class TestCaseGenerationError(Exception):
    pass

# Testcase schema definition using Pydantic for structured output from the LLM
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

def test_cases_generator(state: State):
    prompt = TEST_CASE_GENERATION_PROMPT.format(
    user_story=state["user_story"]
)

    last_error = None

    for model_name in GROQ_MODELS:
        try:
            print(f"Trying model: {model_name}")

            # ChatGroq configuration
            # Adjust temperature and max_tokens as needed for your use case
            # Temperature is set low to encourage more focused and deterministic output. Increase if you want more creative test cases.
            llm = ChatGroq(
                model=model_name,
                temperature=0.2,
                max_tokens=4096,
                timeout=60,
                max_retries=1,
            )

            # Use structured output to get a list of test cases with defined fields
            structured_llm = llm.with_structured_output(
                OutputSchema
            )

            # Invoke the model with the prompt and get structured test cases
            result = structured_llm.invoke(prompt)

            # Validate that we got test cases back
            if not result.test_cases:
                raise TestCaseGenerationError(
                    "The AI did not generate any test cases. "
                    "Try adding more details to the user story."
                )

            # Ensure each test case has a title, if not use description as fallback
            for test_case in result.test_cases:
                if not test_case.test_title:
                    test_case.test_title = test_case.description or "Generated test case"
            
            # Print success message with the model that worked in console for debugging        
            print(f"Success with model: {model_name}")

            return {
                "test_cases": result.test_cases,
                "model_used": model_name
            }

        # Handle specific Groq exceptions to determine if we should fallback to the next model
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

# Build the state graph for test case generation using the defined state and generator function
graph_builder = StateGraph(State)

# Add the test case generator node to the graph and set it as the entry and finish point since it's a single-step process
graph_builder.add_node("generator", test_cases_generator)
graph_builder.set_entry_point("generator")
graph_builder.set_finish_point("generator")

# Compile the graph to create an executable workflow for generating test cases from a user story
graph = graph_builder.compile()

# Function to invoke the graph with a user story and get generated test cases and the model used
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