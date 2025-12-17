# Facebook Messenger Echo Bot Setup and Usage

This document outlines how to set up and use the Facebook Messenger Echo Bot functionality within your Django application. This bot is designed to receive messages sent to your Facebook Page and automatically echo them back to the sender, serving as a basic verification of your Messenger platform integration.

## 1. Prerequisites

Before you begin, ensure you have:
*   A Facebook Developer Account.
*   A Facebook Page.
*   A Facebook App linked to your Facebook Page, with the Messenger product added.
*   Your Django application running and accessible from the internet (e.g., via a public URL or a tunneling service like ngrok).

## 2. Configuration Steps

### 2.1. Environment Variables (`.env`)

You need to provide your Facebook Page Access Token to your Django application. This token should be stored securely in your `.env` file, located in the root directory of your project.

1.  **Obtain a Long-Lived Page Access Token:**
    *   Go to your Facebook Developer App dashboard (`https://developers.facebook.com/apps/YOUR_APP_ID/dashboard/`).
    *   Navigate to **Messenger -> Settings** in the left sidebar.
    *   Under the "Access Tokens" section, select your Facebook Page and click "Generate Token."
    *   **Crucially, ensure this is a *long-lived* Page Access Token** with `pages_messaging` and `pages_show_list` permissions.
2.  **Add to `.env`:**
    Open your `.env` file and add the following line, replacing `YOUR_FACEBOOK_PAGE_ACCESS_TOKEN` with the token you obtained:
    ```
    FACEBOOK_PAGE_ACCESS_TOKEN=YOUR_FACEBOOK_PAGE_ACCESS_TOKEN
    ```

### 2.2. Webhook Configuration in Facebook Developer App

Configure your webhook in the Facebook Developer App to point to your Django application.

1.  **Go to Webhooks:** In your Facebook Developer App dashboard, navigate to **Webhooks** under the "Products" section.
2.  **Configure a Webhook:**
    *   Click "Add Callback URL" or "Edit Callback URL".
    *   **Callback URL:** Set this to your public-facing URL where your Django app's webhook is accessible.
        *   Example: `https://your-domain.com/chat/webhook/`
        *   If using a local development server with ngrok: `https://your-ngrok-url.ngrok-free.app/chat/webhook/`
    *   **Verify Token:** Use `5a8ca116c293ae140ba1ff31489a9499087c5ed6b52cfda3`. This token is hardcoded in `chat/views.py` for verification.
    *   Click "Verify and Save".
3.  **Subscribe to Events:**
    *   After successful verification, click "Add Subscriptions" for the "Page" topic.
    *   Subscribe to the `messages` and `messaging_postbacks` events. These are essential for your bot to receive user messages.

## 3. Running Your Django Application

1.  **Install Dependencies:** Ensure you have `requests` and `python-dotenv` installed in your virtual environment:
    ```bash
    source venv/bin/activate
    pip install requests python-dotenv
    ```
2.  **Restart Your Web Server:**
    For changes to your `.env` file and code to take effect, you must restart your web server.
    *   If running with Apache/WSGI:
        ```bash
        sudo systemctl daemon-reload
        sudo systemctl restart apache2
        ```
    *   If running Django's development server:
        ```bash
        python3 manage.py runserver
        ```

## 4. Testing the Echo Bot

Once your Django application is running and your Facebook webhook is configured:

1.  **Send a message** to your Facebook Page via Messenger (as a user).
2.  The bot should **automatically reply** with the same message you sent.

## 5. Code Structure Overview

*   **`chat/views.py`**: Contains the `webhook_callback` function, which handles both verification (`GET`) and incoming messages (`POST`). It uses `chat.messenger_api.send_messenger_message` to send replies.
*   **`chat/messenger_api.py`**: Contains the reusable `send_messenger_message` function, responsible for constructing and sending messages to the Facebook Graph API.
*   **`premier/settings.py`**: Configures Django's logging and loads the `FACEBOOK_PAGE_ACCESS_TOKEN` from environment variables.
*   **`premier/wsgi.py`**: Ensures the `.env` file is loaded for the WSGI process before the Django application starts.
*   **Facebook Graph API Version:** The bot uses Facebook Graph API `v24.0`.

This setup provides a robust and maintainable way to integrate your Django application with Facebook Messenger.