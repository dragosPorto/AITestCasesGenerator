# AI Test Cases Generator

AI-powered QA test case generator built with **Streamlit + Groq LLMs** that generates structured test cases from feature descriptions or user stories.

The tool can:

* Generate QA test cases using AI
* Export test cases to CSV
* Automatically import test cases into Qase
* Use fallback AI models when Groq rate limits are reached
* Generate implementation-agnostic, business-focused test cases

> **TestRail direct import is not implemented yet** (CSV export only).

---

## Features

* AI-generated QA test cases
* Positive, Negative, and Destructive scenarios
* Structured outputs
* CSV export
* Optional direct import into Qase
* Automatic Qase suite creation
* Groq model fallback support
* Error handling for API failures and quota limits

---

## Tech Stack

* Python
* Streamlit
* Groq API
* LangChain
* LangGraph
* Qase API
* Pandas

---

## Project Structure

```txt
.
├── TestCases.py              # Streamlit app entry point
├── tester_agent.py           # AI agent logic
├── export_to_excel.py        # CSV export logic
├── qase_integration.py       # Qase API integration
├── helpers.py                # Utility/helper functions
├── .env                      # API keys (not committed)
├── requirements.txt
└── test_cases.csv            # Generated output
```

---

## Requirements

* Python 3.11+ recommended
* Groq API key
* (Optional) Qase API key for direct import

---

## Installation

### 1. Clone repository

```bash
git clone https://github.com/dragosPorto/AITestCasesGenerator.git
cd AITestCasesGenerator
```

### 2. Create virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Mac/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If you don't have a `requirements.txt` yet:

```bash
pip install streamlit langchain langgraph langchain-groq python-dotenv pandas requests groq
```

---

### 4. Create `.env`

Create a file named:

```txt
.env
```

Add:

```env
GROQ_API_KEY=your_groq_api_key_here
QASE_API_KEY=your_qase_api_key_here
```

> `QASE_API_KEY` is only required if you want direct Qase import.

---

## Running the App

Start Streamlit:

```bash
streamlit run TestCases.py
```

or:

```bash
python -m streamlit run TestCases.py
```

The app opens in your browser:

```txt
http://localhost:8501
```

---

## How to Use

### 1. Select Test Management Tool

Choose:

* **Qase**
* **TestRail** *(CSV export only for now)*

---

### 2. Optional: Enable Direct Qase Import

Check:

```txt
Import directly to Qase
```

Then enter your:

```txt
Qase Project Code
```

Example:

```txt
AT
```

You can find the project code inside Qase.

Example:

```txt
https://app.qase.io/project/AT
```

Project code:

```txt
AT
```

---

### 3. Enter Feature / User Story

Example:

```txt
As a user, I want to create a table so I can manage reservations.
```

---

### 4. Generate Test Cases

Click:

```txt
Generate Test Cases
```

The app will:

1. Generate structured QA test cases
2. Export them to:

```txt
test_cases.csv
```

3. Optionally import them into Qase

---

## AI Model Architecture

The application uses **Groq-hosted LLMs** with automatic fallback support.

### Model Fallback Strategy

Primary model:

```txt
llama-3.3-70b-versatile
```

Fallback models:

```txt
qwen/qwen3-32b
llama-3.1-8b-instant
```

If the selected model reaches:

* daily quota
* token limits
* rate limits
* API throttling

The app automatically switches to the next available model.

This prevents interruptions during test case generation.

---

## Architecture

```txt
User Story
     ↓
Groq AI Model
     ↓
Structured Test Cases
     ↓
CSV Export
     ↓
Optional Qase Import
```

### Generation Flow

1. User enters a feature/user story
2. AI generates structured QA test cases
3. Validation ensures required schema
4. CSV file is created
5. Optional Qase import is triggered
6. Missing Qase suites are automatically created

---

## CSV Output

Generated file:

```txt
test_cases.csv
```

Includes:

* title
* description
* preconditions
* postconditions
* priority
* severity
* test type
* behavior
* automation status
* test steps
* expected results
* suite mapping

---

## Error Handling

The app includes handling for:

### Groq quota/rate limit reached

Automatic model fallback.

If all models fail:

```txt
All available Groq models reached their quota/rate limit.
```

---

### Invalid Qase Project Code

Example:

```txt
AT123
```

Error:

```txt
Qase import failed:
Qase project 'AT123' not found.
Please check the project code and try again.
```

---

### Invalid Qase API Key

Error:

```txt
Qase authentication failed.
Please check your API key.
```

---

### AI Response Schema Failure

Sometimes the AI may return invalid structure.

Example:

```txt
missing properties: 'test_title'
```

The app retries using fallback logic and validation.

---

### Missing Dependencies

Example:

```txt
ModuleNotFoundError
```

Install missing package:

```bash
pip install package-name
```

Example:

```bash
pip install python-dotenv
```

---

## Known Limitations

* TestRail direct import not implemented
* Large stories may hit token limits
* AI output quality depends on prompt clarity
* Groq free-tier quotas apply

---

## Future Improvements

* TestRail API integration
* Download button for generated CSV
* Better prompt customization
* Model selector in UI
* Advanced test categorization

---

## License

MIT License
