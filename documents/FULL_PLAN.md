### Updated Plan: Decommissioning Implicit Celery & Redis, Documenting Custom Task Queue

#### **1. Verify and Remove Celery-Related System Components (if any)**
*   **Goal:** Ensure no Celery services are mistakenly running or configured for this project on the server.
*   **Subtasks:**
    *   **1.1. Check Celery Systemd Services:**
        *   **Action:** Use `sudo systemctl status celery_worker_premier.service` and `sudo systemctl status celery_beat_premier.service` (or similar, project-specific names) to determine if any Celery-related services are active.
        *   **If found:** Stop and disable them: `sudo systemctl stop <service_name>` and `sudo systemctl disable <service_name>`.
    *   **1.2. Remove Celery Systemd Service Files:**
        *   **Action:** Search for and delete any systemd service files (e.g., in `/etc/systemd/system/`) that explicitly refer to Celery workers or beat for `premier.classapparelph.com`.

#### **2. Clean Up Project-Specific Celery and Redis Configuration**
*   **Goal:** Remove all unused Celery and Redis-specific entries from the Django project's codebase.
*   **Subtasks:**
    *   **2.1. Remove `celery` and `redis` from `requirements.txt`:**
        *   **Action:** Locate `/var/www/premier.classapparelph.com/requirements.txt` and remove any lines containing `celery` and `redis`.
        *   **Reason:** Redis is only configured as a Celery broker/backend for this project, and Celery is not used.
    *   **2.2. Remove Celery and Redis Settings from `settings.py`:**
        *   **Action:** Open `/var/www/premier.classapparelph.com/premier/settings.py` and delete the following lines:
            ```python
            CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
            CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
            ```
        *   **Action:** Additionally, delete any other variables or configurations explicitly related to Celery (e.g., `CELERY_ACCEPT_CONTENT`, `CELERY_TASK_SERIALIZER`, etc.) if they exist within the same file.
    *   **2.3. Delete `premier/celery.py` (if it exists):**
        *   **Action:** If a file named `/var/www/premier.classapparelph.com/premier/celery.py` exists, delete it, as it's not being used by the project's task queue.
    *   **2.4. Delete Redis Test Files:**
        *   **Action:** Delete `test_redis_connection_as_www_data.py` and `test_redis_connection.py` from the project root.

#### **3. Verify Existing Custom Task Queue (No Code Changes Expected)**
*   **Goal:** Confirm the existing `chat/task_queue.py` implementation is robust and efficient.
*   **Review:** The current threading-based task queue is a simple, effective, and native Python solution. It correctly uses `close_old_connections()` to prevent database connection issues in the worker thread. No code modifications are needed for `chat/task_queue.py` or the `enqueue_task` calls in `chat/views.py`.

#### **4. Enhanced Messenger User Experience: Initial Loading Message**
*   **Goal:** Provide immediate feedback to Messenger users that their message has been received and is being processed, improving perceived responsiveness.
*   **Implementation:**
    *   Upon receiving any incoming message from a Messenger user via the webhook, the system will first send a randomly selected loading message from a predefined list.
    *   Immediately after sending the loading message, a 'typing_on' sender action will be activated for the user.
    *   The core message processing (e.g., AI response generation) will then be offloaded to the custom task queue as before.
    *   The `typing_on` indicator will persist until the final response is sent.
*   **Files Modified:**
    *   `chat/prompts.py`: Added `LOADING_MESSAGES` constant.
    *   `chat/utils.py`: Added `get_random_loading_message` function.
    *   `chat/views.py`: Modified `webhook_callback` to send loading message and 'typing_on' before enqueuing the processing task.
*   **Tests Added:**
    *   `chat/tests/test_views.py`: New unit tests to verify the sequence of sending the loading message and activating the typing indicator.

#### **5. Update Project Documentation**
*   **Goal:** Ensure project documentation accurately reflects the asynchronous task handling strategy and the complete removal of Celery and Redis as project dependencies.
*   **Subtasks:**
    *   **5.1. Update `/var/www/premier.classapparelph.com/documents/FULL_PLAN.md`:** Populate this file with the current plan.
    *   **5.2. Update `GEMINI.md`:**
        *   **Action:** Revise the "Celery Usage" section under "8.2. Celery Usage" for `premier.classapparelph.com` to state explicitly that Celery is **not** used and has been fully decommissioned from this project.
        *   **Action:** Add a new subsection explaining that the project utilizes a custom threading-based task queue implemented in `chat/task_queue.py` for all asynchronous background processing.
        *   **Action:** Explicitly state that Redis is also no longer a dependency for this project.

## AI Interaction Layer
A dedicated, shared module will handle all interactions with Artificial Intelligence models. This module will provide a standardized interface for various AI tasks (e.g., quick replies, summarization, exam grading, content generation). It will abstract away the specifics of different AI models, allowing for easy interchangeability and ensuring that distinct functions are available for different model types or purposes. All parts of the application requiring AI capabilities must utilize this centralized AI interaction layer, leveraging `OPEN_AI_TOKEN` from the `.env` file for authentication.

### AI Model Usage Policy for General Chatbot

To optimize resource utilization and provide a differentiated user experience, a specific policy governs the use of AI models for 'GENERAL_BOT' interactions:

*   **Premium Model (gpt-5.2):** For users in the 'GENERAL_BOT' stage, the more capable `gpt-5.2` model is used for the first 10 messages within a single UTC day.
*   **Fallback Model (gpt-5-mini):** After a user has sent 10 messages in the 'GENERAL_BOT' stage within a UTC day, subsequent messages for that user on the same day will automatically fall back to using the `gpt-5-mini` model.
*   **Daily Reset:** The message count for `gpt-5.2` usage is reset to zero for all users at 00:00 UTC each day.
*   **Scope:** This policy exclusively applies to messages processed by the 'GENERAL_BOT' stage. Interactions in other stages (e.g., 'ONBOARDING', 'MOCK_EXAM', 'MARKETING') are not subject to this daily limit and will use their pre-configured models (e.g., `gpt-5-mini` for quick replies, `gpt-5.2` for exam grading) as defined by their respective AI integration points.
*   **User Experience:** The transition between models (from `gpt-5.2` to `gpt-5-mini`) is seamless and transparent to the user; no explicit notification is provided.

### AI Models Used
-   **General AI Tasks (Quick Replies, Summarization):** `gpt-5-mini`
-   **Exam Grading:** `gpt-5.2`
-   **Note on AI Model Parameters:** The `temperature` parameter has been removed from all AI model configurations (e.g., in `chat/ai_integration.py`). This is because not all models consistently support the `temperature` parameter, and some may only allow a default value of 1. Removing it ensures broader compatibility and prevents `invalid_request_error` issues.

## Time Calculation Best Practices
For any time-dependent logic, especially within background tasks or re-engagement flows, it is critical to use precise time units. For example, when converting seconds to hours, always use `3600` (seconds in an hour) as the divisor. Arbitrarily altering such constants (e.g., to `3800`) will lead to subtle bugs, incorrect timing, and features failing to trigger as expected. Prefer using Python's `datetime` and `timedelta` objects for robust time arithmetic.

## Logic Separation
To maintain a clean and modular codebase, the complex business logic associated with processing chat messages will be externalized into separate functions and files. The initial chat message ingestion point will primarily delegate tasks to these external functions, keeping the ingestion layer lean and focused. This approach supports reusability, testability, and adherence to the Single Responsibility Principle.

## Testing Guidelines
Adhering to Test-Driven Development (TDD) principles is mandatory for this project.
*   **Unit Tests:** Comprehensive unit tests must be written for all new code, especially for the externalized logic functions. These tests should cover various scenarios and edge cases to ensure reliability and correctness.
*   **Regression Tests:** All significant unit tests will be retained as permanent regression tests to prevent future code changes from introducing new bugs or reintroducing old ones.

### Modifying Existing Tests
When changes to the application's logic necessitate updates to existing tests, prioritize making granular modifications over wholesale deletions of large test blocks or classes. This approach helps maintain a clear history of changes and reduces the risk of inadvertently removing valid test coverage. If an existing test or a portion of it becomes completely irrelevant due to a fundamental change in the underlying feature or logic, then it should be removed. However, the default strategy should always be to modify existing tests to reflect the new expected behavior, ensuring continued and robust regression coverage.

## Reply Mechanism
A single, standardized function will be responsible for sending replies back to the user. This function will encapsulate the necessary logic for interacting with the Messenger API for sending messages. All parts of the application, including different chat stages, external logic functions, and cron triggers, must utilize this centralized reply function to ensure uniform message delivery and simplify potential future changes to the sending mechanism.

## Echo Message Handling
Incoming messages from the Facebook Messenger Platform with the `is_echo` flag set to `true` are now explicitly ignored by the system. This includes both echo messages generated by the bot's own activity and those originating from human administrators replying through the page. This change prevents unintended processing, user lookups, and sender actions for messages that are merely confirmations of outbound communication.