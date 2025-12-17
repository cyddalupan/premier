# Law Review Center AI Chatbot - Main TODO

This main TODO list contains foundational tasks that need to be completed first to set up the core infrastructure. Once these are done, individual teams can pick up tasks from the batch TODO files.

## 0. High-Level Adjustments & Prioritization
- [x] Prio: Get full list of stages then adjust checklist. Each stage should have clear checklist steps. (This is a meta-task for refinement, but a prerequisite for accurate stage-based development)

## 2. Database Schema Structure
- [x] Implement Users Table (`users`)
    - [x] `user_id` (PK): Facebook PSID.
    - [x] `first_name`: User's name.
    - [x] `current_stage`: (Enum: ONBOARDING, MARKETING, MOCK_EXAM, GENERAL_BOT).
    - [x] `exam_question_counter`: (Int: 0-8) To track progress during the exam.
    - [x] `summary`: (Text) AI-generated summary of user's persona and history.
    - [x] `last_admin_reply_timestamp`: (DateTime) For 10-minute pause logic.
    - [x] `last_interaction_timestamp`: (DateTime) To trigger follow-up messages.
- [x] Implement Question Bank (`exam_questions`)
    - [x] `id` (PK)
    - [x] `category`: (e.g., Criminal Law, Civil Law).
    - [x] `question_text`: The actual scenario.
    - [x] `expected_answer`: The model answer/key points.
    - [x] `rubric_criteria`: Specific points required for full credit.
- [x] Implement Chat Logs (`chat_history`)
    - [x] `id` (PK)
    - [x] `user_id`: FK to Users.
    - [x] `sender_type`: (Enum: USER, SYSTEM_AI, ADMIN_MANUAL).
    - [x] `message_content`: Text body.
    - [x] `timestamp`: Time sent.

## 5. Technical Implementation Steps (Summary)
- [x] Setup Webhook: Connect to Facebook Messenger API. Subscribe to messages, messaging_postbacks, and message_echoes.
- [x] Database Init: Create the tables listed above.
    - [x] Make sure database table creation and adjustment has its own clear steps.
- [x] Queuing System: Set up a task queuing system (e.g., Celery) for asynchronous message processing and handling the detailed message flow.
- [x] AI Integration Module:
    - [x] Design and implement shared functions for connecting to various AI models (e.g., for quick replies, summarization, exam grading).
    - [x] Ensure different functions are available for different model types/purposes.
    - [x] Establish a clear API for AI calls to be used across the application.