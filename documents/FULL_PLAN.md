Project Blueprint: Law Review Center AI Chatbot

Review Center AI Chatbot

1. Core Logic & Mechanics

D. Message Processing Flow (Detailed Steps)
The following steps outline the sequential processing of incoming messages, orchestrated by a queuing system:
    1.  **Queue Entry:** An incoming message is first placed into a processing queue.
    2.  **Retrieve User FB ID:** Extract the Facebook PSID (user_id) from the message.
    3.  **Echo Check:** Determine if the message is an echo from Messenger (indicating an admin's reply).
        *   **If Yes (Admin Echo):**
            *   Save the admin's message to the Chat Logs (with sender_type: ADMIN_MANUAL).
            *   Update the user's data, noting that the admin has replied.
            *   Update the user's `last_admin_reply_timestamp`.
            *   **STOP Processing** for this message.
    4.  **Get User Data:** Retrieve comprehensive user data based on the `fb_id`.
    5.  **Save User Message:** Save the incoming user's message to the Chat Logs (with sender_type: USER).
    6.  **Admin Active Check:** Check if an admin has replied to this user within the last 10 minutes (using `last_admin_reply_timestamp`).
        *   **If Yes:** **STOP Processing** for this message.
    7.  **Determine User Stage:** Based on user data, identify the `current_stage` (e.g., ONBOARDING, MARKETING, MOCK_EXAM, GENERAL_BOT).
    8.  **Quick Reply Logic:**
        *   **If the user is NOT in the Mock Exam stage:**
            *   Generate and send a quick reply using a nano model, incorporating the current prompt and the last 3 messages.
    9.  **Select Function:** Choose the appropriate function/handler based on the user's `current_stage`. Each stage has distinct rules and processing logic.
    10. **Generate & Save Replies:** The selected function processes the message, potentially using a mini reasoning model, to generate one or more replies. Each generated reply is saved to the Chat Logs (with sender_type: SYSTEM_AI).
    11. **Context Summarization Check:** After all replies are generated and saved, check if the total number of uns summarized chat messages (USER, SYSTEM_AI, ADMIN_MANUAL) for this user exceeds 20.
        *   **If Yes:** Summarize the oldest 14 uns summarized messages, merge with the existing user summary, and update the user's summary field (ensuring it is less than 1,000 characters).

A. The "Manual Override" (Admin Pause)
This mechanism prevents the AI from interrupting a human admin during a live chat. Its detailed operation, including the handling of admin echoes and the 10-minute pause logic, is described in the "Message Processing Flow" (Steps 3 & 6).
B. Context Management (Memory Optimization)
This mechanism handles token limits and maintains conversation continuity by dynamically summarizing chat history. The detailed "Sliding Window" algorithm, including its trigger conditions and summarization process, is described in the "Message Processing Flow" (Step 11).

C. Quick Reply Mechanism
This mechanism provides an immediate, concise response using a nano model. Its conditions for activation (user not in Mock Exam stage) and detailed process are described in the "Message Processing Flow" (Step 8).

2. Database Schema Structure
A. Users Table (users)
Stores state and memory.
    •   user_id (PK): Facebook PSID.
    •   first_name: User's name.
    •   current_stage: (Enum: ONBOARDING, MARKETING, MOCK_EXAM, GENERAL_BOT).
    •   exam_question_counter: (Int: 0-8) To track progress during the exam.
    •   summary: (Text) The AI-generated summary of the user's persona and history.
    •   last_admin_reply_timestamp: (DateTime) For the 10-minute pause logic.
    •   last_interaction_timestamp: (DateTime) To trigger follow-up messages.
B. Question Bank (exam_questions)
Pool for the Mock Exam.
    •   id (PK)
    •   category: (e.g., Criminal Law, Civil Law).
    •   question_text: The actual scenario.
    •   expected_answer: The model answer/key points.
    •   rubric_criteria: Specific points required for full credit.
C. Chat Logs (chat_history)
Permanent record of all messages.
    •   id (PK)
    •   user_id: FK to Users.
    •   sender_type: (Enum: USER, SYSTEM_AI, ADMIN_MANUAL).
    •   message_content: Text body.
    •   timestamp: Time sent.

3. Conversation Lifecycle (The Flow)
Stage 1: Onboarding & Introduction
    •   Goal: Capture user interest and basic info.
    •   Action: AI introduces itself, asks for the student's year level/focus, and establishes a friendly rapport.
Stage 2: Pre-Exam Marketing
    •   Goal: Soft-sell the Review Center.
    •   Action:
    ◦   Highlight unique selling points (USPs) based on documentation.
    ◦   Transition: "Would you like to test your skills with a quick Mock Bar Exam?"
Stage 3: The Mock Exam (The Core Feature)
    •   Loop: Repeat 8 times.
    •   Process:
    1   AI selects a random question from exam_questions.
    2   User answers.
    3   AI Analysis (The 5-Point Feedback System):
    ▪   Grammar/Syntax: Checks for professional legal tone.
    ▪   Legal Basis: Cites relevant laws/jurisprudence.
    ▪   Application: How the law was applied to facts.
    ▪   Conclusion: Whether the final answer is correct.
    ▪   Score: A numerical rating (1-100% or Bar scale).
    •   Transition: After 8 questions, move to Stage 4.
Stage 4: Conversion & General Bot
    •   Goal: Convert to website registration.
    •   Action:
    ◦   "You did great! To get full access to our materials, register here: [Link]."
    ◦   Switch role to General Legal Assistant/Mentor (answers general queries, gives motivation).

4. Re-engagement Strategy (Follow-up Messages)
Trigger: Scheduled cron job checking last_interaction_timestamp. If inactive for X hours/days, send one of these (randomized):
    1   Trivia/Fun Fact: "Did you know [Obscure Law] is still valid?"
    2   Giveaway/Promo: "We are giving away a free reviewer PDF..."
    3   Legal Maxim of the Day: "Explain 'Dura lex sed lex' in your own words."
    4   Success Story: "One of our students, [Name], just topped the bar..."
    5   Quick Case Digest: A 3-sentence summary of a recent Supreme Court ruling.
    6   Mental Health Check: "Law school is tough. Don't forget to hydrate and rest."

5. Technical Implementation Steps (Summary)
    1   Setup Webhook: Connect to Facebook Messenger API. Subscribe to messages, messaging_postbacks, and message_echoes.
    2   Database Init: Create the tables listed above.
    3   Admin Logic: Implement the middleware to check the 10-minute timer.
    4   Exam Logic: Build the function to fetch random questions and the Prompt Engineering for the "5-Point Feedback."
    5   Context Logic: Implement the "Sliding Window" algorithm with the refined summarization rules (triggering at >20 messages, summarizing oldest 14, merging with existing summary, and ensuring the new summary is <1,000 characters).
    6   Queuing System: Set up a task queuing system (e.g., Celery) for asynchronous message processing and handling the detailed message flow.
    7   Quick Reply Implementation: Develop the nano-model quick reply mechanism, ensuring it respects the exam stage exclusion.
    8   Testing: Specifically test the Admin interruption to ensure the AI stays silent.
    9   Modular Design: Implement each conversational stage (Onboarding, Marketing, Mock Exam, General Bot) as separate functions, ideally in their own files, to promote cleaner code, improve maintainability, and facilitate isolated unit testing.

