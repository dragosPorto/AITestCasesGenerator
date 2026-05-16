import streamlit as st

from export_to_excel import export_to_excel
from tester_agent import generate_test_cases
from qase_integration import add_bulk_to_qase

st.title("AI Test Case Generator")
user_story = st.text_area("Enter the user story or functionality description:")
if st.button("Generate Test Cases"):
    if user_story.strip():
        test_cases = generate_test_cases(user_story)
        print(test_cases)
        print(len(test_cases))
        export_to_excel(test_cases)
        add_bulk_to_qase(test_cases)
        st.success("🎉 Test cases generated, exported to Excel, and uploaded to QASE!")
    else:
        st.warning("Please enter a user story to generate test cases.")