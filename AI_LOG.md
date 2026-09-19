# AI-Assisted Development Log

This document records the engineering methodology, architectural decisions, critical code reviews, and iterative refinements involved in building the **Document Intake Assistant** with AI assistance.

---

## 1. Engineering Philosophy & Role of AI

AI tools were utilized as an implementation accelerator and pair programmer for tasks such as initial boilerplate scaffolding, schema drafting, and test generation.

Crucially, **all architectural boundaries, state machine invariants, security constraints, and code changes were guided by human engineering direction and subjected to critical review**. Code was never accepted blindly; every component underwent static analysis, automated testing, and manual end-to-end evaluation.

---

## 2. Core Architectural Decisions

### Decision 1: Structured State as the Single Source of Truth
* **Context**: LLMs can summarize conversations well but are prone to hallucination, omission, or inconsistency over multi-turn dialogues.
* **Engineering Decision**: The authoritative record of intake data is a strictly validated Pydantic model (`PersonalWishesState`) stored in SQLite with version tracking.
* **Outcome**: The LLM is used strictly as a semantic extractor and conversational agent. State transitions are governed by deterministic backend logic.

### Decision 2: Deterministic Document Generation
* **Context**: Relying on an LLM to generate the final `.docx` document introduces latency, token costs, formatting drift, and legal risk.
* **Engineering Decision**: Use `python-docx` to compile the `.docx` document directly from the confirmed `PersonalWishesState`.
* **Outcome**: Document output is deterministic, fast, and avoids generative formatting drift or hallucinations.

### Decision 3: Decoupled Client-Server Boundary
* **Context**: Monolithic UI/backend setups often blur state boundaries and make automated testing difficult.
* **Engineering Decision**: Implement a standalone FastAPI REST backend and a separate Streamlit frontend communicating exclusively over HTTP.
* **Outcome**: Clear separation of concerns, complete testability with `TestClient`, and reusable API endpoints.

---

## 3. Implementation Iterations & Critical Code Reviews

During the development and testing phases, rigorous review and manual exploratory testing identified three significant architectural and behavioral issues in the AI-scaffolded codebase. These were systematically investigated, diagnosed, and resolved.

### Issue 1: Unnecessary Replacement of LLM Follow-Up Messages
* **Discovery**: In [`backend/services/followups.py`](backend/services/followups.py), [`compose_assistant_message`](backend/services/followups.py) called [`get_next_missing_field`](backend/services/followups.py) whenever `needs_clarification` was `False`. As long as any intake field was uncollected, the function discarded the LLM's generated message and returned a hardcoded string (`f"Thanks, I've recorded that. {next_missing.question}"`).
* **Critical Review**: This undermined the purpose of using Gemini for empathetic, context-aware dialogue, turning the intake into a robotic script.
* **Fix**: Refactored [`compose_assistant_message`](backend/services/followups.py) to preserve valid, non-empty `llm_message` content directly. Deterministic missing-field questions are now used strictly as a resilient fallback when the LLM output is empty.

### Issue 2: Silent Rejection of Conflicting State Updates
* **Discovery**: In [`backend/services/sessions.py`](backend/services/sessions.py), `persist_message_exchange` caught `StateUpdateConflictError` and fell back to `updated_state = state`. It then proceeded to generate an assistant message acknowledging the turn as successful.
* **Critical Review**: If a user provided conflicting information that failed heuristic correction checks, the backend rejected the update silently while the UI told the user *"Thanks, I've recorded that."*
* **Fix**: Updated [`persist_message_exchange`](backend/services/sessions.py) to intercept `StateUpdateConflictError`. When a conflict occurs:
  1. The confirmed state remains unchanged (`updated_state = state`), and the state version is not incremented.
  2. The assistant returns a clear message explaining the conflict and requesting clarification or confirmation.

### Issue 3: Fragile Correction & Direct Declarative Replacement Detection
* **Discovery**: [`backend/services/state_updates.py`](backend/services/state_updates.py) initially relied on a fixed list of exact keyword substrings (`"actually"`, `"correction"`, etc.).
  - Natural correction verbs like `"update"`, `"modify"`, `"revise"`, `"fix"`, or phrases like `"my address is now..."` were missed.
  - Natural direct declarations (e.g., user says *"My name is Sammian"* on turn 1, then later says *"My name is Sam"*) were incorrectly flagged as unresolvable conflicts.
  - Child count statements beyond three (e.g. *"I have 4 children"*) failed substring detection.
* **Critical Review**: Users in real-world intake speak conversationally and directly declare replacements without always using formal correction keywords.
* **Fix**:
  1. Expanded keyword markers and added robust regex patterns (`EXPLICIT_CORRECTION_PATTERNS`, `CHILDREN_CORRECTION_PATTERN`, `NO_CHILDREN_CORRECTION_PATTERN`).
  2. Implemented `FIELD_DECLARATION_PATTERNS` and [`_is_field_declaration`](backend/services/state_updates.py) to detect field-specific declarative statements (`"My name is..."`, `"My address is..."`, `"My executor is..."`).
  3. Maintained strict conservative boundaries so ambiguous statements (e.g. *"Hello from Amit Patel"* when name is *"Rahul"*) remain treated as conflicts requiring clarification.

---

## 4. Verification & Quality Assurance

Quality was verified through a two-tier validation approach:

### 1. Automated Test Suite (69 Tests)
The test suite spans 7 test modules covering all layers of the application:
- **API Endpoints** (`tests/test_api.py` - 9 tests): Full session lifecycle, error codes (404, 422, 503), document streaming.
- **Conversation Behavior** (`tests/test_conversation_behavior.py` - 20 tests): Multi-turn extraction, explicit corrections, direct declarative updates, child count transitions, conflict prevention.
- **Database Layer** (`tests/test_database.py` - 2 tests): Relational schemas, cascades, version tracking.
- **Document Generator** (`tests/test_document_generation.py` - 10 tests): DOCX paragraph structure, disclaimer presence, empty/null field formatting.
- **Frontend Layer** (`tests/test_frontend.py` - 13 tests): HTTP client resilience, timeout handling, error display mapping, preview formatting.
- **LLM Flow & Integration** (`tests/test_llm_flow.py` - 11 tests): Schema validation, mock extraction pipelines, API failure resilience.
- **State Schema Invariants** (`tests/test_state_schema.py` - 4 tests): Strict typing, forbidden extra attributes, children cross-field validation.

### 2. Manual End-to-End Testing
Manual testing in the live Streamlit UI verified:
- Seamless multi-turn conversation flow with Gemini.
- Handling of multiple fields provided in a single message.
- Re-prompting when required details (e.g., executor relationship when only name was given) are missing.
- Live real-time state inspector and draft preview updates.
- End-to-end `.docx` download and formatting verification.

---

## 5. Key Takeaways

1. **AI as an Accelerator, Not an Architect**: AI tools significantly sped up initial scaffolding and boilerplate generation, but human engineering was required to design reliable state transitions, fault-tolerant error paths, and strict domain boundaries.
2. **Defensive Design Around Probabilistic Outputs**: LLMs should never be given direct write access to persistent state without strict validation schemas and deterministic business logic acting as a firewall.
3. **Adversarial Testing is Essential**: Thorough automated test suites with deliberate edge cases (contradictions, partial answers, natural corrections, network timeouts) are critical to uncovering silent failures in AI-assisted code.
