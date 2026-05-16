import streamlit as st

from tester_agent import (
    generate_test_cases,
    TestCaseGenerationError
)
from export_to_excel import export_to_excel
from qase_integration import add_bulk_to_qase

st.title("AI Test Case Generator")
user_story = st.text_area("Enter the user story or functionality description:")
if st.button("Generate Test Cases"):
    if user_story.strip():
        try:
            test_cases = generate_test_cases(user_story)

            export_to_excel(test_cases)
            add_bulk_to_qase(test_cases)

            st.success(
                "🎉 Test cases generated, exported to CSV, and uploaded to QASE!"
            )

        except TestCaseGenerationError as e:
            st.error(f"⚠️ {str(e)}")

        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")

    else:
        st.warning(
            "Please enter a user story to generate test cases."
        )