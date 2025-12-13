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

3.  **Django Admin Integration:**
    *   When creating or updating Django models (database tables), always ensure that the new or modified columns are properly configured to be viewable and editable within the Django administration interface. This typically involves registering the model in `admin.py` and configuring `list_display`, `list_editable`, `fieldsets`, etc.