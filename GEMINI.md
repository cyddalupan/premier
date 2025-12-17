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
    *   To run tests: `python manage.py test`

2.  **Manual Testing:**
    *   After making code changes and running unit tests, it is often necessary to perform manual testing.
    *   To apply changes for manual testing in the deployed environment, restart the Apache web server:
        ```bash
        sudo systemctl restart apache2
        ```

### Django Admin Integration:
*   When creating or updating Django models (database tables), always ensure that the new or modified columns are properly configured to be viewable and editable within the Django administration interface. This typically involves registering the model in `admin.py` and configuring `list_display`, `list_editable`, `fieldsets`, etc.

# Coding Architecture and Rules

This section outlines the architectural principles and coding conventions to be followed, particularly in relation to the chat bot's functionality as detailed in `documents/FULL_PLAN.md`.

## Queueing Mechanism
For managing the chat flow and message processing, a robust queuing mechanism will be employed. This system is crucial for asynchronous processing and ensuring scalability and reliability of message handling as outlined in `documents/FULL_PLAN.md` under "Message Processing Flow (Detailed Steps)". Documentation for the specific queuing technology (e.g., Celery) and its usage will be provided alongside its implementation.

## Chat Message Ingestion
All incoming chat messages from Messenger will be received and processed through a single, designated entry point. This ensures consistency and simplifies maintenance. The receiving component should have minimal logic, primarily handling the initial receipt and immediate queuing of the message for further processing.

## AI Interaction Layer
A dedicated, shared module will handle all interactions with Artificial Intelligence models. This module will provide a standardized interface for various AI tasks (e.g., quick replies, summarization, exam grading, content generation). It will abstract away the specifics of different AI models, allowing for easy interchangeability and ensuring that distinct functions are available for different model types or purposes. All parts of the application requiring AI capabilities must utilize this centralized interaction layer, leveraging `OPEN_AI_TOKEN` from the `.env` file for authentication.

## Logic Separation
To maintain a clean and modular codebase, the complex business logic associated with processing chat messages will be externalized into separate functions and files. The initial chat message ingestion point will primarily delegate tasks to these external functions, keeping the ingestion layer lean and focused. This approach supports reusability, testability, and adherence to the Single Responsibility Principle.

## Testing Guidelines
Adhering to Test-Driven Development (TDD) principles is mandatory for this project.
*   **Unit Tests:** Comprehensive unit tests must be written for all new code, especially for the externalized logic functions. These tests should cover various scenarios and edge cases to ensure reliability and correctness.
*   **Regression Tests:** All significant unit tests will be retained as permanent regression tests to prevent future code changes from introducing new bugs or reintroducing old ones.

## Reply Mechanism
A single, standardized function will be responsible for sending replies back to the user. This function will encapsulate the necessary logic for interacting with the Messenger API for sending messages. All parts of the application, including different chat stages, external logic functions, and cron triggers, must utilize this centralized reply function to ensure uniform message delivery and simplify potential future changes to the sending mechanism.