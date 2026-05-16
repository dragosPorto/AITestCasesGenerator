import streamlit as st

from tester_agent import (
    generate_test_cases,
    TestCaseGenerationError
)
from export_to_excel import export_to_excel
from qase_integration import add_csv_to_qase, QaseImportError

st.title("AI Test Case Generator")
test_management_tool = st.selectbox(
    "Select test management tool",
    ["Qase", "TestRail"]
)
st.caption(f"Selected: {test_management_tool}")

is_testrail = test_management_tool == "TestRail"

if is_testrail:
    st.error("⚠️ TestRail import is not implemented yet.")

import_directly_to_qase = st.checkbox(
    "Import directly to Qase",
    value=False
)

user_story = st.text_area("Enter the user story or functionality description:")

if st.button("Generate Test Cases",
             disabled=is_testrail
             ):
    if user_story.strip():
        try:
            test_cases = generate_test_cases(user_story)
            export_to_excel(test_cases)

            if test_management_tool == "Qase":
                if import_directly_to_qase:
                    result = add_csv_to_qase("test_cases.csv")
                    st.success(
                        f"🎉 Test cases generated, exported to CSV, and uploaded to Qase "
                        f"({result['imported_count']} cases)."
                    )
#                       show raw API response for debugging
#                       st.json(result["qase_response"])
                else:
                    st.success("🎉 Test cases generated and exported to CSV."
                               "Qase import was skipped."
                               )

        except TestCaseGenerationError as e:
            st.error(f"⚠️ {str(e)}")

        except QaseImportError as e:
            st.error(f"Qase import failed: {str(e)}")

        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")

    else:
        st.warning("Please enter a user story to generate test cases.")
