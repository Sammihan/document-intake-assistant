# Document Intake Assistant

A conversational intake application that collects personal information and generates a structured, fictional **Personal Wishes Document** (`.docx`).

Built with **FastAPI**, **Streamlit**, **Google Gemini**, **SQLAlchemy / SQLite**, and **Pydantic v2**, the system uses an LLM for conversational dialogue and structured field extraction, while relying on deterministic state management and programmatic document compilation to prevent unvalidated state mutations.

---

> [!IMPORTANT]
> **Disclaimer**: This application is a technical intake demonstration. The generated output is a **FICTIONAL DOCUMENT â€” NOT LEGAL ADVICE**.

---

## 1. System Architecture & Request Flow

The application follows a decoupled client-server architecture. The Streamlit frontend communicates with the FastAPI backend strictly over HTTP JSON and binary endpoints.

```
+-------------------------------------------------------------------------------+
|                               Streamlit UI                                    |
|   (Chat Interface  |  Live State Inspector  |  Draft Preview & Download)      |
+---------------------------------------+---------------------------------------+
                                        | HTTP (REST / JSON / DOCX)
                                        v
+-------------------------------------------------------------------------------+
|                               FastAPI Backend                                 |
|                                                                               |
|  1. /sessions/{id}/messages (POST)                                            |
|     +--> Load Session & State from SQLite                                     |
|     +--> Query Gemini LLM (Structured JSON Extraction & Assistant Message)    |
|     +--> State Transition Engine (Deterministic Merge & Correction Detection) |
|     +--> Safety Guard (Detect Conflicting Unclarified Updates)                |
|     +--> Persist Messages & Versioned State in SQLite                         |
|     +--> Return JSON Response (Assistant Message + Updated State)             |
|                                                                               |
|  2. /sessions/{id}/document (GET)                                             |
|     +--> Fetch Confirmed State from SQLite                                    |
|     +--> Deterministic python-docx Compiler                                   |
|     +--> Return .docx Binary Stream                                           |
+-------------------------------------------------------------------------------+
```

### Request Lifecycle
1. **User Input**: The user sends a natural language message in the Streamlit chat.
2. **Context Assembly**: The backend retrieves conversation history (up to the last 10 messages) and the current confirmed state.
3. **Structured LLM Extraction**: Gemini analyzes the user's latest input within conversation context and returns structured JSON conforming strictly to `LLMExtractionResponse`.
4. **Deterministic State Transition**:
   - If updates represent explicit corrections or direct declarative statements (e.g., *"My name is Sam"*), confirmed state fields are safely updated.
   - If updates contradict confirmed information without explicit correction intent, the backend intercepts the conflict, preserves confirmed state without mutation, and asks the user for clarification.
5. **Persistence**: New messages and updated state (with incremented version number) are committed to SQLite.
6. **UI Synchronization**: Streamlit displays the assistant's message and re-renders the live state panel and draft preview.
7. **Document Generation**: When requested, `python-docx` compiles the validated state into a formatted `.docx` file.

---

## 2. Key Features

- **Conversational Intake**: Users can provide single fields, multiple fields at once, or conversational answers in any order.
- **Strict Structured State**: Validated Pydantic models act as a firewall between LLM outputs and persistent storage.
- **Natural Correction & Direct Declarative Replacement**: Recognizes explicit corrections (*"actually"*, *"correction"*, *"update"*, *"modify"*, *"revise"*, *"my address is now..."*) as well as direct field declarations (*"My name is Sam"* after confirming *"Sammian"*).
- **Safe Conflict Handling**: Conflicting unclarified statements are not silently applied or discarded with false acknowledgments. The state remains protected and the user is prompted to clarify.
- **Dynamic Follow-ups with Deterministic Fallback**: Preserves context-aware LLM messages while providing deterministic missing-field questions if LLM responses are empty.
- **Programmatic Document Compilation**: Document rendering is performed programmatically from validated state rather than generative LLM output.
- **Dual-Pane Interface**: Side-by-side view with chat on the left and live confirmed state / document preview on the right.

---

## 3. Project Structure

```
document-intake-assistant/
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ api/
â”‚   â”‚   â”œâ”€â”€ main.py                  # FastAPI application entrypoint & middleware
â”‚   â”‚   â””â”€â”€ routes/
â”‚   â”‚       â””â”€â”€ sessions.py          # Session, messaging, state, and document endpoints
â”‚   â”œâ”€â”€ config.py                    # Environment variable loader
â”‚   â”œâ”€â”€ database/
â”‚   â”‚   â”œâ”€â”€ base.py                  # SQLAlchemy declarative base
â”‚   â”‚   â”œâ”€â”€ init_db.py               # Table creation helper
â”‚   â”‚   â””â”€â”€ session.py               # Engine and sessionmaker setup (SQLite)
â”‚   â”œâ”€â”€ llm/
â”‚   â”‚   â”œâ”€â”€ gemini.py                # Gemini client, extraction prompt, error handling
â”‚   â”‚   â””â”€â”€ prompts.py               # System prompt and extraction schema definitions
â”‚   â”œâ”€â”€ models/
â”‚   â”‚   â””â”€â”€ database.py              # SQLAlchemy models (Session, Message, State)
â”‚   â”œâ”€â”€ schemas/
â”‚   â”‚   â”œâ”€â”€ api.py                   # FastAPI request/response schemas
â”‚   â”‚   â”œâ”€â”€ llm.py                   # Pydantic schemas for LLM structured output
â”‚   â”‚   â””â”€â”€ state.py                 # Core intake state schema (PersonalWishesState)
â”‚   â””â”€â”€ services/
â”‚       â”œâ”€â”€ document_generator.py    # Deterministic python-docx document builder
â”‚       â”œâ”€â”€ followups.py             # Missing-field logic & message composer
â”‚       â”œâ”€â”€ sessions.py              # Session orchestration & persistence
â”‚       â””â”€â”€ state_updates.py         # State update engine & correction detection
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ api_client.py                # Typed HTTP client for FastAPI backend
â”‚   â”œâ”€â”€ app.py                       # Streamlit multi-pane application
â”‚   â””â”€â”€ display.py                   # State formatting & preview renderers
â”œâ”€â”€ tests/
â”‚   â”œâ”€â”€ conftest.py                  # Pytest fixtures & mock LLM setup
â”‚   â”œâ”€â”€ helpers.py                   # Test session helpers
â”‚   â”œâ”€â”€ test_api.py                  # Backend HTTP endpoint tests (9 tests)
â”‚   â”œâ”€â”€ test_conversation_behavior.py# Intake flow, corrections, and conflict tests (20 tests)
â”‚   â”œâ”€â”€ test_database.py             # Database persistence and cascade tests (2 tests)
â”‚   â”œâ”€â”€ test_document_generation.py  # DOCX structure and formatting tests (10 tests)
â”‚   â”œâ”€â”€ test_frontend.py             # Streamlit client and rendering tests (13 tests)
â”‚   â”œâ”€â”€ test_llm_flow.py             # Gemini integration & mock extraction tests (11 tests)
â”‚   â””â”€â”€ test_state_schema.py         # Pydantic schema validation tests (4 tests)
â”œâ”€â”€ data/                            # SQLite database directory (document_intake.db)
â”œâ”€â”€ documents/                       # Generated .docx storage directory
â”œâ”€â”€ .env.example                     # Sample environment variables
â”œâ”€â”€ pytest.ini                       # Pytest configuration
â”œâ”€â”€ requirements.txt                 # Project dependencies
â””â”€â”€ README.md
```

---

## 4. Structured Data Model

The intake data model is defined in [`backend/schemas/state.py`](backend/schemas/state.py) as `PersonalWishesState`:

| Field | Type | Description |
| :--- | :--- | :--- |
| `full_name` | `str \| None` | Full legal/preferred name of the individual |
| `home_address` | `str \| None` | Primary residential address |
| `covers_worldwide_assets` | `bool \| None` | Whether fictional wishes apply to worldwide assets |
| `has_children` | `bool \| None` | Indicates if the individual has children |
| `children` | `list[str]` | List of child names (enforced empty when `has_children=False`) |
| `executor.name` | `str \| None` | Name of the designated executor |
| `executor.relationship` | `str \| None` | Executor's relationship to the individual |
| `specific_gifts` | `list[str]` | Specific items or bequests assigned to individuals |
| `additional_wishes` | `str \| None` | Special instructions or funeral/ceremony wishes |

### Cross-Field Validation Rules
- **Children Invariant**: If `has_children == False`, `children` must be empty (`[]`). Pydantic cross-field validators raise a `ValidationError` if names are provided.
- **Strict Typing**: All schemas enforce `extra="forbid"` and `strict=True` to prevent arbitrary field injection or type coercion bugs.

---

## 5. API Endpoints

All endpoints are hosted by FastAPI at default port `8000`:

| Method | Endpoint | Description | Status Codes |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Service health check | `200` |
| `POST` | `/sessions` | Create a new intake session with version 1 empty state | `201` |
| `GET` | `/sessions/{session_id}/state` | Get current confirmed `PersonalWishesState` | `200`, `404` |
| `GET` | `/sessions/{session_id}/messages` | Get complete conversation history | `200`, `404` |
| `POST` | `/sessions/{session_id}/messages` | Send user message, process intake, update state | `200`, `404`, `422`, `503` |
| `GET` | `/sessions/{session_id}/document` | Generate and download the `.docx` document | `200`, `404` |

---

## 6. Conversation & State Update Logic

The assistant handles complex real-world conversational turns with deterministic state-machine rules:

1. **Missing Information**:
   - The LLM asks conversational follow-up questions for uncollected fields based on `current_state`.
   - If the LLM generates an empty assistant message, [`compose_assistant_message`](backend/services/followups.py) falls back to deterministic priority questions (Children names $\rightarrow$ Executor details $\rightarrow$ Name $\rightarrow$ Address $\rightarrow$ Worldwide assets $\rightarrow$ Gifts $\rightarrow$ Additional wishes).

2. **Explicit Corrections**:
   - Recognizes intent indicators (e.g., *"actually"*, *"correction"*, *"update"*, *"modify"*, *"revise"*, *"fix"*, *"replace"*, *"is now"*, *"no my address is"*).
   - Supports natural direct replacements: if a user says *"My name is Sam"* after previously confirming *"Sammian"*, the field-specific declaration pattern allows the state update.
   - Supports child count adjustments (e.g., transitioning from no children to *"I have 4 children: A, B, C, D"* or *"I have a daughter"*).

3. **Ambiguity & Contradiction Protection**:
   - If an extracted field conflicts with a confirmed value without an explicit correction or field declaration (e.g. user says *"Hello from Amit Patel"* when name is *"Rahul Sharma"*), the update is intercepted.
   - Confirmed state remains completely unchanged.
   - The assistant asks the user for clarification rather than falsely reporting that the conflicting data was recorded.

---

## 7. Deterministic Document Generation

Document generation is performed by [`backend/services/document_generator.py`](backend/services/document_generator.py) using `python-docx`:
- **Header**: `PERSONAL WISHES DOCUMENT` with mandatory notice `FICTIONAL DOCUMENT â€” NOT LEGAL ADVICE`.
- **Structured Sections**: Personal Information, Asset Coverage, Children, Executor, Specific Gifts, and Additional Wishes.
- **Standardized Placeholders**: Unconfirmed fields are cleanly rendered as `"Not confirmed"`, `"None specified"`, or `"Not provided"`.
- **Deterministic Rendering**: By compiling directly from validated `PersonalWishesState` records, document generation avoids generative formatting drift and hallucinations.

---

## 8. Testing Suite

The repository contains **69 automated tests** covering end-to-end integration, API endpoints, state transition mechanics, and UI logic.

```powershell
pytest
```

### Test Suite Breakdown
- [`tests/test_api.py`](tests/test_api.py) (9 tests): Session lifecycle, message roundtrips, 404/422 handling, DOCX download headers.
- [`tests/test_conversation_behavior.py`](tests/test_conversation_behavior.py) (20 tests): Multi-turn extraction, explicit corrections, direct declarative updates, child count transitions, contradiction guards, state versioning.
- [`tests/test_database.py`](tests/test_database.py) (2 tests): Database schema initialization, relational foreign keys, orphan cleanup.
- [`tests/test_document_generation.py`](tests/test_document_generation.py) (10 tests): DOCX paragraph formatting, disclaimer presence, list bullet rendering, empty state handling.
- [`tests/test_frontend.py`](tests/test_frontend.py) (13 tests): Streamlit `BackendClient` error mapping (404/500/503/timeouts), session state helpers, preview renderers.
- [`tests/test_llm_flow.py`](tests/test_llm_flow.py) (11 tests): Gemini client integration, schema validation errors, API failure recovery (503 status), context propagation, conflict safety.
- [`tests/test_state_schema.py`](tests/test_state_schema.py) (4 tests): Schema validation, forbidden extra keys, strict type checking, children invariant enforcement.

---

## 9. Setup & Run Instructions

### Prerequisites
- Python 3.11+ (Python 3.12 recommended)
- A Google Gemini API key ([Google AI Studio](https://aistudio.google.com/))

### 1. Clone & Setup Virtual Environment
```bash
# Clone the repository
git clone <repository-url>
cd document-intake-assistant

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and provide your Gemini API key:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3-flash-preview
BACKEND_URL=http://127.0.0.1:8000
```

### 3. Run the Backend (FastAPI)
```bash
uvicorn backend.api.main:app --reload --port 8000
```
Backend Swagger API documentation will be available at: `http://127.0.0.1:8000/docs`

### 4. Run the Frontend (Streamlit)
In a separate terminal (with the virtual environment activated):
```bash
streamlit run frontend/app.py
```
The application UI will open in your browser at: `http://localhost:8501`

### 5. Run Automated Tests
```bash
pytest
```

---

## 10. Design Decisions & Trade-Offs

1. **State as Single Source of Truth vs. Freeform LLM Summary**:
   - *Decision*: Maintain a validated Pydantic model stored as JSON in SQLite.
   - *Rationale*: Prevents ungrounded information from being persisted and enables reliable document generation.
2. **Decoupled API Architecture vs. Monolithic App**:
   - *Decision*: Build a standalone FastAPI backend and a separate Streamlit UI consuming the backend via HTTP.
   - *Rationale*: Enables clean separation of concerns, independent testing of business logic, and API reuse for alternate clients.
3. **Structured Extraction with Deterministic State Guards**:
   - *Decision*: Combine Gemini JSON schema output with backend state machine verification.
   - *Rationale*: LLMs are effective for semantic parsing but cannot be trusted with authoritative state consistency. The backend acts as the authoritative arbitrator for conflicts and corrections.
