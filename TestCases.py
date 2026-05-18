import streamlit as st

from tester_agent import (
    generate_test_cases,
    TestCaseGenerationError
)
from export_to_excel import export_to_excel
from qase_integration import add_csv_to_qase, QaseImportError

# Set up Streamlit page configuration and custom styles for the AI Test Case Generator app
st.set_page_config(
    page_title="AI Test Case Generator",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Custom CSS styles for headers, info cards, and other UI elements to enhance the appearance of the app
st.markdown(
    """
    <style>
        .main-header {
            padding: 1.5rem 0 0.75rem 0;
        }
        .app-title {
            font-size: 2.4rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
        }
        .app-subtitle {
            color: #6c757d;
            font-size: 1.05rem;
            margin-bottom: 1.5rem;
        }
        .info-card {
            padding: 1rem 1.1rem;
            border: 1px solid rgba(49, 51, 63, 0.15);
            border-radius: 0.9rem;
            background: rgba(250, 250, 250, 0.7);
            margin-bottom: 1rem;
        }
        .small-muted {
            color: #6c757d;
            font-size: 0.9rem;
        }
        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)


# -----------------------------
# Header
# -----------------------------
st.markdown(
    """
    <div class="main-header">
        <div class="app-title">🧪 AI Test Case Generator</div>
        <div class="app-subtitle">
            Generate structured QA test cases from user stories, export them to CSV,
            and optionally import them directly into your testing management tool.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# -----------------------------
# Sidebar configuration
# -----------------------------
with st.sidebar:
    st.header("⚙️ Configuration")

    test_management_tool = st.selectbox(
        "Test management tool",
        ["Qase", "TestRail"],
        help="Choose where the generated test cases should be prepared for."
    )
    
    test_type = st.selectbox(
        "Test type",
        options=["Positive", "Negative", "Destructive"],
        index=0,
        help="Select the type of test cases to generate.You can choose positive, negative, or destructive"
    )

    is_testrail = test_management_tool == "TestRail"

    st.divider()

    st.subheader("Import options")

    # When the user selects a test management tool, enable or disable the corresponding direct import options in the sidebar
    import_directly_to_qase = st.checkbox(
        "Import directly to Qase",
        disabled=is_testrail,
        help="When enabled, generated test cases are exported to CSV and then uploaded to Qase."
    )
    import_directly_to_testrail = st.checkbox(
        "Import directly to TestRail",
        disabled=not is_testrail,
        help="When enabled, generated test cases are exported to CSV and then uploaded to TestRail."
    )

    qase_project_code = ""

    # If the user has enabled direct import to Qase, show a text input for the Qase project code which is needed for the API integration
    if import_directly_to_qase:
        qase_project_code = st.text_input(
            "Qase Project Code",
            placeholder="Example: AT",
            help="Use the project code from your Qase project URL. Example: app.qase.io/project/AT → AT"
        )

    # If the user has enabled direct import to TestRail, 
    # show an error message that this feature is not implemented yet since the integration with TestRail is planned for a future update
    if is_testrail:
        st.warning("TestRail direct import is not implemented yet. CSV export can be added later.")

    st.divider()

    # In the sidebar, provide information about the output of the app,
    # specifically that generated test cases will be saved locally as a CSV file which can be downloaded or imported into a test management tool
    st.subheader("Output")
    st.caption("Generated test cases are saved locally as `test_cases.csv`.")


# -----------------------------
# Main content layout
# -----------------------------
left_col, right_col = st.columns([2, 1], gap="large")

with left_col:
    st.markdown('<div class="section-title">📝 Feature / User Story</div>', unsafe_allow_html=True)
    st.caption("Describe the feature, user story, acceptance criteria, or workflow you want to test.")

    user_story = st.text_area(
        "User story or functionality description",
        placeholder=(
            "Example: As a user, I want to create a table so that I can manage reservations.\n\n"
            "Include business rules, validations, edge cases, or acceptance criteria if available."
        ),
        height=260,
        label_visibility="collapsed"
    )

    # The button to trigger test case generation
    # Button is disabled if the user has selected TestRail since direct import is not implemented yet
    generate_clicked = st.button(
        "🚀 Generate Test Cases",
        disabled=is_testrail,
        use_container_width=True,
        type="primary"
    )

with right_col:
    st.markdown('<div class="section-title">📌 Current setup</div>', unsafe_allow_html=True)

    # Display the current configuration settings in the right column of the main content area, including the selected test management tool,
    # whether direct import is enabled, and the Qase project code if applicable
    st.markdown(
        f"""
        <div class="info-card">
            <strong>Tool:</strong> {test_management_tool}<br>
            <strong>Direct import:</strong> {'Enabled' if import_directly_to_qase or import_directly_to_testrail else 'Disabled'}<br>
            <strong>Qase project:</strong> {qase_project_code if qase_project_code else 'Not set'}<br>
            <strong>Test type:</strong> {test_type}
        </div>
        """,
        unsafe_allow_html=True
    )

    # Provide additional information about what happens when the user clicks the generate button,
    # explaining the steps of AI generation, CSV creation, and optional upload to Qase to set expectations for the user
    st.markdown(
        """
        <div class="info-card">
            <strong>What happens when you generate?</strong><br>
            <span class="small-muted">
                1. AI generates structured test cases<br>
                2. CSV is created locally<br>
                3. If enabled, cases are uploaded to Qase
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Provide a tip to the user that more detailed user stories usually produce better test coverage,
    # encouraging them to provide rich context for the AI to generate comprehensive test cases
    st.info("Tip: More detailed user stories usually produce better test coverage.")


# -----------------------------
# Generate flow
# Error handling
# -----------------------------
if generate_clicked:
    if user_story.strip():
        try:
            # When the generate button is clicked,
            # show a spinner while the AI is generating test cases from the provided user story
            # to indicate that processing is happening
            with st.spinner("Generating test cases with AI..."):
                generation_result = generate_test_cases(
                    user_input=user_story,
                    test_type=test_type.lower()
                )

            test_cases = generation_result[
                "test_cases"
            ]

            model_used = generation_result[
                "model_used"
            ]

            export_to_excel(test_cases)

            # If the user has enabled direct import to Qase,
            # attempt to upload the generated CSV file to Qase using the API integration
            if test_management_tool == "Qase":

                if import_directly_to_qase:
                    with st.spinner("Uploading generated test cases to Qase..."):
                        qase_result = add_csv_to_qase(
                            "test_cases.csv",
                            qase_project_code
                        )

                    st.success(
                        f"🎉 Test cases generated, "
                        f"exported to CSV, and uploaded "
                        f"to Qase.\n\n"
                    )

                else:
                    st.success(
                        f"🎉 Test cases generated and "
                        f"exported to CSV.\n\n"
                        f"Qase import was skipped.\n\n"
                    )

            st.divider()

            result_col_1, result_col_2, result_col_3 = st.columns(3)

            # Display metrics about the generation result,
            # including the number of test cases generated,
            # the model used for generation,
            # and confirmation that the CSV export is ready
            with result_col_1:
                st.metric("Generated cases", len(test_cases))

            with result_col_2:
                st.metric("Model used", model_used)

            with result_col_3:
                st.metric("Export", "CSV ready")

            # Provide a download button for the generated CSV file so the user can easily download it to their local machine
            try:
                with open("test_cases.csv", "rb") as csv_file:
                    st.download_button(
                        "⬇️ Download CSV",
                        data=csv_file,
                        file_name="test_cases.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            # Handle the case where the CSV file was generated but cannot be found for download, showing a warning message to the user
            except FileNotFoundError:
                st.warning("CSV file was generated but could not be found for download.")

            # Provide an expander section to preview the generated test cases directly in the app,
            # showing the title, description, and key attributes of each test case for quick review
            with st.expander("Preview generated test cases"):
                for index, test_case in enumerate(test_cases, start=1):
                    st.markdown(f"### {index}. {test_case.test_title}")
                    st.write(test_case.description)
                    st.caption(
                        f"Suite: {test_case.suite} | "
                        f"Priority: {test_case.priority} | "
                        f"Severity: {test_case.severity} | "
                        f"Behavior: {test_case.behavior}"
                    )

        except TestCaseGenerationError as e:
            st.error(f"⚠️ {str(e)}")

        except QaseImportError as e:
            st.error(
                f"Qase import failed: {str(e)}"
            )

        except Exception as e:
            st.error(
                f"Unexpected error: {str(e)}"
            )

    else:
        st.warning(
            "Please enter a user story "
            "to generate test cases."
        )
