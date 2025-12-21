Project Blueprint: Law Review Center AI Chatbot

Review Center AI Chatbot

1. Core Logic & Mechanics

D. Message Processing Flow (Detailed Steps)
The following steps outline the sequential processing of incoming messages, orchestrated by a queuing system:
    1.  **Queue Entry:** An incoming message is first placed into a processing queue.
    1.1. **Initiate Typing Indicator:** Immediately send a `typing_on` sender action to the user via the Messenger API. This action, like all Messenger API calls, will first check `User.is_messenger_reachable`. If the user is marked as unreachable, the API call will be skipped.
    2.  **Retrieve User FB ID:** Extract the Facebook PSID (user_id) from the message.
    3.  **Echo Check:** Determine if the message is an echo from Messenger. Echoes sent by the bot itself are ignored. Echoes originating from a human admin are logged (with sender_type: ADMIN_MANUAL), but AI processing continues without interruption.
    5.  **Get User Data:** Retrieve comprehensive user data based on the `fb_id`.
    6.  **Capture User Name (if new user):** If the user's `first_name` is not already set, capture it from the incoming message content.
    7.  **Save User Message:** Save the incoming user's message to the Chat Logs (with sender_type: USER).
    9.  **Determine User Stage:** Based on user data, identify the `current_stage` (e.g., ONBOARDING, MARKETING, MOCK_EXAM, GENERAL_BOT).
    10. **Quick Reply Logic:**
        *   **If the user is NOT in the Mock Exam stage AND NOT in the General Bot stage:**
            *   Generate and send a quick reply using a nano model, incorporating the current prompt and the last 3 messages.
    11. **Select Function:** Choose the appropriate function/handler based on the user's `current_stage`. Each stage has distinct rules and processing logic.
    12. **Generate & Save Replies:** The selected function processes the message, potentially using a mini reasoning model, to generate one or more replies. Each generated reply is saved to the Chat Logs (with sender_type: SYSTEM_AI) and sent to the user via `send_messenger_message`. The `send_messenger_message` function includes internal logic to check `User.is_messenger_reachable` before sending and will update this flag to `False` if the Messenger API reports the user as unreachable (e.g., 'No matching user found' error). A `typing_off` sender action is also sent, subject to the same reachability checks.
    13. **Context Summarization Check:** After all replies are generated and saved, check if the total number of uns summarized chat messages (USER, SYSTEM_AI, ADMIN_MANUAL) for this user exceeds 20.
        *   **If Yes:** Summarize the oldest 14 uns summarized messages, merge with the existing user summary, and update the user's summary field (ensuring it is less than 1,000 characters).
    14. **Ensure Typing Indicator Off:** Regardless of success or failure of the message processing flow, a `typing_off` sender action is sent to the user via the Messenger API. This call will also honor the `User.is_messenger_reachable` flag and will be skipped if the user is found to be unreachable.

---

**Messenger API Interaction Guidelines**
To prevent errors with the Facebook Messenger API, particularly `(#100) No matching user found`, a `is_messenger_reachable` flag has been implemented in the `User` model (`chat/models.py`).

*   **Reachability Check:** Before any Messenger API call (messages or sender actions) is made via functions like `send_messenger_message` or `send_sender_action` in `chat/messenger_api.py`, the `User.is_messenger_reachable` flag is checked. If this flag is `False`, the API call is skipped, and a warning is logged.
*   **Flag Update:** If a Messenger API call results in an error indicating the user is unreachable (specifically, an API error with `code: 100` and `error_subcode: 2018001`, or a message containing "No matching user found"), the `User.is_messenger_reachable` flag for that user is automatically set to `False` in the database. This prevents future attempts to send messages or sender actions to an unreachable user.


B. Context Management (Memory Optimization)
This mechanism handles token limits and maintains conversation continuity by dynamically summarizing chat history. The detailed "Sliding Window" algorithm, including its trigger conditions and summarization process, is described in the "Message Processing Flow" (Step 13).

C. Quick Reply Mechanism
This mechanism provides an immediate, concise response using a nano model. Its conditions for activation (user not in Mock Exam stage, and excluding the General Bot stage for regular conversational interactions) and detailed process are described in the "Message Processing Flow" (Step 10). In the `GENERAL_BOT` stage, regular AI interactions are handled by the more comprehensive `generate_chat_response` function, with quick replies reserved for specific, proactive prompts if ever implemented.

2. Database Schema Structure
A. Users Table (users)
Stores state and memory.
    •   user_id (PK): Facebook PSID.
    •   first_name: User's name, captured from their first message if not already known.
    •   current_stage: (Enum: ONBOARDING, MARKETING, MOCK_EXAM, GENERAL_BOT).
    •   exam_question_counter: (Int: 0-8) To track progress during the exam.
    •   last_question_id_asked: (FK to exam_questions) Stores the ID of the last question presented to the user during the mock exam.
    •   summary: (Text) The AI-generated summary of the user's persona and history.

    •   last_interaction_timestamp: (DateTime) To trigger follow-up messages.

B. Course Catalog (courses)
New table to categorize exam questions.
    •   id (PK)
    •   name: (String) Unique name of the course (e.g., "Criminal Law", "Civil Law").
    •   description: (Text) Optional detailed description of the course.
    •   created_at: (DateTime) Timestamp when the course was created.
    •   updated_at: (DateTime) Timestamp when the course was last updated.

C. Question Bank (exam_questions)
Pool for the Mock Exam.
    •   id (PK)
    •   course: (FK to courses) The course this question belongs to. (Nullable)
    •   category: (e.g., Criminal Law, Civil Law) - *Note: This can now be refined or become a sub-category under 'course'*.
    •   question_text: The actual scenario.
    •   expected_answer: The lawyer's answer/key points.
        *   **Scoring Note:** The closer the user's answer is to this `expected_answer`, the higher the score.
D. Chat Logs (chat_history)
Permanent record of all messages.
    •   id (PK)
    •   user_id: FK to Users.
    •   sender_type: (Enum: USER, SYSTEM_AI, ADMIN_MANUAL).
    •   message_content: Text body.
    •   timestamp: Time sent.

E. Exam Results Table (exam_results)
Stores the results of each mock exam question.
    •   id (PK)
    •   user_id: FK to Users.
    •   question_id: FK to Question Bank (exam_questions).
    •   score: (Int) Numerical score for the answer (e.g., 1-100).
    •   legal_writing_feedback: (Text) Feedback on legal writing/syntax.
    •   legal_basis_feedback: (Text) Feedback on legal basis.
    •   application_feedback: (Text) Feedback on application of law.
    •   conclusion_feedback: (Text) Feedback on correctness of conclusion.
    •   timestamp: Time the result was recorded.

F. Prompts Table (prompts)
Stores AI prompt templates, allowing for dynamic updates via the Django admin.
    •   id (PK)
    •   name: (String) Unique identifier for the prompt (e.g., "QUICK_REPLY_SYSTEM_PROMPT"). This directly maps to original Python constant names for fallback purposes.
    •   category: (Enum) Categorizes the prompt (e.g., "QUICK_REPLY", "EXAM_GRADING", "RE_ENGAGEMENT").
    •   text_content: (Text) The actual content of the prompt, including any placeholders.
    •   description: (Text, nullable) An optional description of the prompt's purpose.
    •   created_at: (DateTime) Timestamp when the prompt was created.
    •   updated_at: (DateTime) Timestamp when the prompt was last updated.


3. Conversation Lifecycle (The Flow)
Stage 1: Onboarding & Introduction
    •   Goal: Capture user interest and basic info.
    •   Action: AI introduces itself, captures the user's name, and establishes a friendly rapport.
Stage 2: Pre-Exam Marketing
    •   Goal: Soft-sell the Review Center.
    •   Action:
    ◦   Highlight unique selling points (USPs) based on documentation.
    ◦   Transition: "Would you like to test your skills with a quick Mock Bar Exam?"
Stage 3: The Mock Exam (The Core Feature)
    •   Loop: Repeat 8 times.
    •   Process:
    1   AI selects a random question from exam_questions and stores its ID in the user's `last_question_id_asked` field.
    2   User answers.
    3   AI Analysis (The 5-Point Feedback System):
    ▪   Legal Writing: Checks for professional legal tone.
    ▪   Legal Basis: Cites relevant laws/jurisprudence.
    ▪   Application: How the law was applied to facts.
    ▪   Conclusion: Whether the final answer is correct.
    ▪   Score: A numerical rating (1-100% or Bar scale).
    4   Save the question ID, score, and all 5 feedback points to the `Exam Results Table`.
    •   **User Strength Assessment:**
        1   Analyze the user's `exam_results` to determine their performance across different legal `category` types.
        2   Identify categories where the user demonstrated significant strength (e.g., consistently high scores).
        3   Formulate a prompt for `gpt-5.2` that includes the identified strengths and requests a personalized assessment message.
        4   Generate the assessment message using `gpt-5.2` (model `gpt-5.2`).
        5   Send this detailed assessment message to the user via the standardized reply function.
        6   Save the AI-generated assessment message to the `Chat Logs` (sender_type: SYSTEM_AI).
    •   Transition: After 8 questions and the strength assessment, move to Stage 4.
Stage 4: Conversion & General Bot
    •   Goal: Convert to website registration.
    •   Action:
    ◦   Upon transitioning to this stage, the bot sends congratulatory and persuasion messages to encourage website registration.
    ◦   Subsequently, the bot switches its role to a General Legal Assistant/Mentor (answers general queries, gives motivation). Persuasion messages are not sent for general queries or as AI fallbacks in this stage.

4. Re-engagement Strategy (Follow-up Messages)
Trigger: Scheduled cron job checking last_interaction_timestamp. Follow-up messages are sent at specific intervals of inactivity, ensuring a multi-stage re-engagement approach:
    •   **Stage 1:** 1 to 2 hours after the last interaction.
    •   **Stage 2:** 5 to 6 hours after the last interaction.
    •   **Stage 3:** 11 to 12 hours after the last interaction.
    •   **Stage 4:** 21 to 22 hours after the last interaction.

**Implementation Details:**
The re-engagement process is orchestrated by a Celery beat task `check_inactive_users` (defined in [`chat/tasks.py`](chat/tasks.py)), which is scheduled to run daily via `CELERY_BEAT_SCHEDULE` in [`premier/settings.py`](premier/settings.py). This task identifies inactive users and determines their re-engagement stage.

Instead of static messages, the system leverages AI to generate personalized re-engagement messages. The function `generate_re_engagement_message` (located in [`chat/ai_integration.py`](chat/ai_integration.py)) is responsible for calling the `gpt-5-mini` model. AI prompts for this process are dynamically retrieved from the `Prompt` database table (managed via [`chat/models.py`](chat/models.py)) using the `get_prompt` utility function ([`chat/utils.py`](chat/utils.py)). Hardcoded fallback prompts are available in [`chat/prompts.py`](chat/prompts.py) if database prompts are not found.

The current generic message "Hello! We missed you. How can I help you today?" serves as a fallback only if the AI API call fails. All outgoing messages, including re-engagement messages, are sent via the standardized function `send_messenger_message` in [`chat/messenger_api.py`](chat/messenger_api.py).

The `User` model ([`chat/models.py`](chat/models.py)) stores `last_interaction_timestamp` to track inactivity and `re_engagement_stage_index` to manage the user's progress through the follow-up stages.

**Enhancement Goal:** To make these re-engagement messages more creative and varied (e.g., marketing, motivational, tips, guides, trivia), the AI prompts (`RE_ENGAGEMENT_SYSTEM_PROMPT` and `RE_ENGAGEMENT_USER_PROMPT_TEMPLATE`) need to be refined. These prompts should instruct the AI to generate diverse content and incorporate relevant user context such as `first_name`, `summary`, `current_stage`, and recent conversation history. The AI itself will handle the "randomization" of message types based on these enhanced prompts.

5. Technical Implementation Steps (Summary)
    1.  **AI Integration Module & Dynamic Prompt Management:** Design and implement shared functions for connecting to various AI models (e.g., for quick replies, summarization, exam grading, content generation). This module abstracts away model specifics, allowing for easy interchangeability. Crucially, AI prompt templates are now managed dynamically:
        *   **Retrieval Hierarchy:** Prompts are first retrieved from the `Prompts` database table.
        *   **Caching:** Retrieved prompts are aggressively cached (e.g., for 1 hour) to minimize database hits and improve performance.
        *   **Code Fallback:** If a prompt is not found in the database or cache, the system falls back to using the hardcoded prompt constants defined in `chat/prompts.py`. This ensures system stability and provides default behavior.
        *   **Django Admin Integration:** All prompts are editable via the Django administration interface.
        This system leverages `OPEN_AI_TOKEN` from the `.env` file for authentication.
*   **Parameter Naming for Response Length (Standardization):** It is a project standard to use `max_completion_tokens` when specifying the maximum length of generated responses from AI models (e.g., `gpt-5.2`, `gpt-5-mini`). The parameter `max_tokens` should be avoided as it is not consistently supported across all models and can lead to `invalid_request_error` issues. Always consult the specific model's documentation for any exceptions, but `max_completion_tokens` is the preferred and default parameter for this project.
...
-   **Note on AI Model Parameters:** The project standard is to use `max_completion_tokens` for controlling the output length of AI model responses. The `temperature` parameter has been removed from all AI model configurations (e.g., in `chat/ai_integration.py`). This is because not all models consistently support the `temperature` parameter, and some may only allow a default value of 1. Removing it ensures broader compatibility and prevents `invalid_request_error` issues. Always verify parameter compatibility with the specific AI model's documentation.