Project Blueprint: Law Review Center AI Chatbot

Review Center AI Chatbot

1. Core Logic & Mechanics

D. Message Processing Flow (Detailed Steps)
The following steps outline the sequential processing of incoming messages, orchestrated by a queuing system:
    1.  **Queue Entry:** An incoming message is first placed into a processing queue.
    2.  **Retrieve User FB ID:** Extract the Facebook PSID (user_id) from the message.
    3.  **Echo Check:** Determine if the message is an echo from Messenger. Echoes sent by the bot itself are ignored. Echoes originating from a human admin are logged (with sender_type: ADMIN_MANUAL), and the user's `last_admin_reply_timestamp` is updated, but AI processing continues without interruption.
    5.  **Get User Data:** Retrieve comprehensive user data based on the `fb_id`.
    6.  **Capture User Name (if new user):** If the user's `first_name` is not already set, capture it from the incoming message content.
    7.  **Save User Message:** Save the incoming user's message to the Chat Logs (with sender_type: USER).
    9.  **Determine User Stage:** Based on user data, identify the `current_stage` (e.g., ONBOARDING, MARKETING, MOCK_EXAM, GENERAL_BOT).
    10. **Quick Reply Logic:**
        *   **If the user is NOT in the Mock Exam stage:**
            *   Generate and send a quick reply using a nano model, incorporating the current prompt and the last 3 messages.
    11. **Select Function:** Choose the appropriate function/handler based on the user's `current_stage`. Each stage has distinct rules and processing logic.
    12. **Generate & Save Replies:** The selected function processes the message, potentially using a mini reasoning model, to generate one or more replies. Each generated reply is saved to the Chat Logs (with sender_type: SYSTEM_AI).
    13. **Context Summarization Check:** After all replies are generated and saved, check if the total number of uns summarized chat messages (USER, SYSTEM_AI, ADMIN_MANUAL) for this user exceeds 20.
        *   **If Yes:** Summarize the oldest 14 uns summarized messages, merge with the existing user summary, and update the user's summary field (ensuring it is less than 1,000 characters).


B. Context Management (Memory Optimization)
This mechanism handles token limits and maintains conversation continuity by dynamically summarizing chat history. The detailed "Sliding Window" algorithm, including its trigger conditions and summarization process, is described in the "Message Processing Flow" (Step 13).

C. Quick Reply Mechanism
This mechanism provides an immediate, concise response using a nano model. Its conditions for activation (user not in Mock Exam stage) and detailed process are described in the "Message Processing Flow" (Step 10).

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
B. Question Bank (exam_questions)
Pool for the Mock Exam.
    •   id (PK)
    •   category: (e.g., Criminal Law, Civil Law).
    •   question_text: The actual scenario.
    •   expected_answer: The lawyer's answer/key points.
        *   **Scoring Note:** The closer the user's answer is to this `expected_answer`, the higher the score.
C. Chat Logs (chat_history)
Permanent record of all messages.
    •   id (PK)
    •   user_id: FK to Users.
    •   sender_type: (Enum: USER, SYSTEM_AI, ADMIN_MANUAL).
    •   message_content: Text body.
    •   timestamp: Time sent.

D. Exam Results Table (exam_results)
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
    ◦   "You did great! To get full access to our materials, register here: [Link]."
    ◦   Switch role to General Legal Assistant/Mentor (answers general queries, gives motivation).

4. Re-engagement Strategy (Follow-up Messages)
Trigger: Scheduled cron job checking last_interaction_timestamp. Follow-up messages are sent at specific intervals of inactivity, ensuring a multi-stage re-engagement approach:
    •   **Stage 1:** 1 to 2 hours after the last interaction.
    •   **Stage 2:** 5 to 6 hours after the last interaction.
    •   **Stage 3:** 11 to 12 hours after the last interaction.
    •   **Stage 4:** 21 to 22 hours after the last interaction.

If inactive for any of these specific intervals, one of these (randomized) messages will be sent:
    1   Trivia/Fun Fact: "Did you know [Obscure Law] is still valid?"
    2   Giveaway/Promo: "We are giving away a free reviewer PDF..."
    3   Legal Maxim of the Day: "Explain 'Dura lex sed lex' in your own words."
    4   Success Story: "One of our students, [Name], just topped the bar..."
    5   Quick Case Digest: A 3-sentence summary of a recent Supreme Court ruling.
    6   Mental Health Check: "Law school is tough. Don't forget to hydrate and rest."

5. Technical Implementation Steps (Summary)
    1.  **AI Integration Module:** Design and implement shared functions for connecting to various AI models (e.g., for quick replies, summarization, exam grading, content generation). This module will abstract away model specifics, allowing for easy interchangeability and providing distinct functions for different model types or purposes, leveraging `OPEN_AI_TOKEN` from the `.env` file for authentication.
*   **Parameter Naming for Response Length:** Be aware that some advanced or newer AI models (e.g., `gpt-5.2`) may require `max_completion_tokens` instead of `max_tokens` to specify the maximum length of the generated response. Always consult the specific model's documentation to ensure correct parameter usage to avoid `invalid_request_error` issues.

    2.  Setup Webhook: Connect to Facebook Messenger API. Subscribe to messages, messaging_postbacks, and message_echoes.
    3.  Database Init: Created the necessary database tables and imported initial question data. (See `documents/DATABASE.md` for schema details).
    
    5.  Exam Logic: Build the function to fetch random questions and the Prompt Engineering for the "5-Point Feedback."
    6.  Context Logic: Implement the "Sliding Window" algorithm with the refined summarization rules (triggering at >20 messages, summarizing oldest 14, merging with existing summary, and ensuring the new summary is <1,000 characters).
    7.  Queuing System: Set up a task queuing system (e.g., Celery) for asynchronous message processing and handling the detailed message flow.
    8.  Quick Reply Implementation: Develop the nano-model quick reply mechanism, ensuring it respects the exam stage exclusion.
    9.  Testing: Specifically test that the AI continues to function correctly even when an admin is active, ensuring seamless interaction regardless of human intervention.
    10. **Cron Entry Point:** Implement a single URL endpoint (`/chat/cron/dispatch/`) that will serve as the hourly trigger for all scheduled cron tasks, including re-engagement messages and data collection. This endpoint will internally dispatch specific tasks to the queuing system.
    11. Modular Design: Implement each conversational stage (Onboarding, Marketing, Mock Exam, General Bot) as separate functions, ideally in their own files, to promote cleaner code, improve maintainability, and facilitate isolated unit testing.

### AI Models Used
-   **General AI Tasks (Quick Replies, Summarization):** `gpt-5-mini`
-   **Exam Grading:** `gpt-5.2`
-   **Note on AI Model Parameters:** Both `temperature` and parameter naming for response length (e.g., `max_tokens` vs. `max_completion_tokens`) require careful attention. Some models might not support `temperature` or may have specific naming conventions for output length parameters. Always verify parameter compatibility with the specific AI model's documentation to prevent `invalid_request_error` issues.