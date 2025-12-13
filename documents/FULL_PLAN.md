Project Blueprint: Law Review Center AI Chatbot

Review Center AI Chatbot

1. Core Logic & Mechanics
A. The "Manual Override" (Admin Pause)
This logic prevents the AI from interrupting a human admin during a live chat.
    •   Trigger: The system listens for the Facebook message_echo event (indicates a message was sent by the Page Admin).
    •   Action: When an echo is detected, update the user's last_admin_reply_timestamp.
    •   Condition: Before the AI processes any incoming user message, it checks:  $$CurrentTime - LastAdminReplyTimestamp > 10\ minutes$$ 
    •   Result:
    ◦   If True: AI processes the message and replies.
    ◦   If False: AI ignores the message (silence).
B. Context Management (Memory Optimization)
To handle token limits while maintaining conversation continuity.
    •   Storage: A summary field in the User Table (Target: ~1,500 - 2,000 characters).
    •   The "Sliding Window" Algorithm:
    ◦   Trigger: When the active chat history hits 10 messages.
    ◦   Process:
    1   Take the oldest 7 messages + the current summary.
    2   Feed them to the LLM with instructions to "Condense this into the existing summary."
    3   Update the summary field.
    4   Delete those 7 raw messages from the "Active Context" array (but keep them in the ChatLogs database for records).
    5   Keep the newest 3 messages as raw text for immediate context.

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
    5   Context Logic: Implement the "Summarize 7, Keep 3" algorithm.
    6   Testing: Specifically test the Admin interruption to ensure the AI stays silent.

