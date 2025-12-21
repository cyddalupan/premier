# Project Overview

This project is a Django application (`premier`) serving as a backend for a "Law Review Center AI Chatbot." It currently handles static legal content and will support chatbot functionalities as detailed in `documents/FULL_PLAN.md`.

# Setup & Running

## Prerequisites
*   Python 3.x
*   pip
*   MySQL server

## Setup
1.  **Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
2.  **Dependencies:**
    Install Python dependencies. It is recommended to create a `requirements.txt` (`pip freeze > requirements.txt`) then install:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Environment Variables:**
    Create a `.env` file for database credentials (e.g., `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`).
    **AI API Keys:** Include `OPEN_AI_TOKEN` for AI model authentication.
    **Note on WSGI/Apache:** For proper loading of `.env` variables in a WSGI environment (e.g., when running with Apache/mod_wsgi), ensure `load_dotenv()` is explicitly called in your `premier/wsgi.py` file *before* Django settings are configured. This prevents issues where critical variables like `OPEN_AI_TOKEN` are not found.
4.  **Database Migrations:**
    ```bash
    python manage.py migrate
    ```

## Running
*   **Development Server:**
    ```bash
    python manage.py runserver
    ```
*   **Collect Static Files:**
    ```bash
    python manage.py collectstatic
    ```

# Key Information & Conventions

*   **Framework:** Django (version 6.0).
*   **Database:** MySQL.
*   **Environment Variables:** Managed via `python-dotenv`.
*   **Key Document:** `documents/FULL_PLAN.md`.
*   **Apps:** Includes the `legal` app.
*   **Admin:** Django admin accessible at `/admin/`.

## Development Workflow

1.  **Test-Driven Development (TDD):**
    *   For every code change, unit tests should be written and executed. This project adheres to a TDD approach.
    *   While temporary test code may be used during development, it is crucial to retain all important and useful unit tests as permanent regression tests.

## Testing Workflow

### Running Tests
*   **Run all tests for a specific app (e.g., `chat`):**
    ```bash
    python manage.py test chat.tests
    ```
    *Note: If you encounter an `ImportError` related to `chat/tests`, try clearing the `__pycache__` directories within the `chat/` and `chat/tests/` folders before running tests again: `find chat/ -name "__pycache__" -exec rm -rf {} +`*
*   **Run a specific test file (e.g., `test_models.py` in the `chat` app):**
    ```bash
    python manage.py test chat.tests.test_models
    ```
*   **Run all tests in the project:**
    ```bash
    python manage.py test
    ```

### Writing Tests
*   **Location:** New test files for an app (e.g., `chat`) should be placed in the `app_name/tests/` directory (e.g., `chat/tests/`).
*   **Naming Convention:** Test files should start with `test_` (e.g., `test_my_feature.py`).
*   **Test Cases:** Each test file should contain one or more `unittest.TestCase` classes or simple test functions if using `pytest` (though `unittest` is the primary framework here).
*   **Best Practices:**
    *   Adhere to TDD principles: write tests before writing the code they test.
    *   Ensure comprehensive coverage for new features and bug fixes.
    *   Keep tests focused, testing one piece of functionality per test method.
    *   Use Django's `TestCase` or `TransactionTestCase` as appropriate for database interactions.
    *   Mock external dependencies (like API calls) to ensure tests are fast and reliable.
    *   **`unittest.mock` Best Practices:** When using `@patch` decorators, ensure the order of mock arguments in the test function matches the reverse order of the decorators. Always update `assert_called_once_with` or `assert_any_call` arguments when the underlying mocked function's signature changes, providing all expected arguments (or `mock.ANY` for less critical ones). This prevents `TypeError`s and `AssertionError`s due to argument mismatches during testing.

2.  **Manual Testing:**
    *   After making code changes and running unit tests, it is often necessary to perform manual testing.
    *   To apply changes for manual testing in the deployed environment, restart the Apache web server:
        ```bash
        sudo systemctl restart apache2
        ```
    *   **Debugging Visibility (Development):** For quick visibility of values during development and testing, especially when standard logging configuration is complex, `print()` statements can be temporarily used. Remember to remove them before committing production code.

### Django Admin Integration:
*   When creating or updating Django models (database tables), always ensure that the new or modified columns are properly configured to be viewable and editable within the Django administration interface. This typically involves registering the model in `admin.py` and configuring `list_display`, `list_editable`, `fieldsets`, etc.

# Coding Architecture and Rules

This section outlines the architectural principles and coding conventions to be followed, particularly in relation to the chat bot's functionality as detailed in `documents/FULL_PLAN.md`.

## Queueing Mechanism
For managing the chat flow and message processing, a robust queuing mechanism will be employed. This system is crucial for asynchronous processing and ensuring scalability and reliability of message handling as outlined in `documents/FULL_PLAN.md` under "Message Processing Flow (Detailed Steps)". Documentation for the specific queuing technology (e.g., Celery) and its usage will be provided alongside its implementation.

## Chat Message Ingestion
All incoming chat messages from Messenger will be received and processed through a single, designated entry point. This ensures consistency and simplifies maintenance. The receiving component should have minimal logic, primarily handling the initial receipt and immediate queuing of the message for further processing.

## AI Interaction Layer
A dedicated, shared module will handle all interactions with Artificial Intelligence models. This module will provide a standardized interface for various AI tasks (e.g., quick replies, summarization, exam grading, content generation). It will abstract away the specifics of different AI models, allowing for easy interchangeability and ensuring that distinct functions are available for different model types or purposes. All parts of the application requiring AI capabilities must utilize this centralized AI interaction layer, leveraging `OPEN_AI_TOKEN` from the `.env` file for authentication.

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