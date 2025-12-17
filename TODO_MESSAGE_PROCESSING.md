# Law Review Center AI Chatbot - Message Processing TODO

This document outlines tasks related to the core message processing flow and related mechanisms.

## 1. Core Logic & Mechanics

### Message Processing Flow
- [ ] Queue Entry: Incoming message placed into processing queue.
- [ ] Retrieve User FB ID: Extract Facebook PSID (user_id).
- [ ] Echo Check: Determine if message is an echo from Messenger.
    - [ ] If Yes (Admin Echo):
        - [ ] Save admin message to Chat Logs (sender_type: ADMIN_MANUAL).
        - [ ] Update user data: admin has replied.
        - [ ] Update user's `last_admin_reply_timestamp`.
        - [ ] STOP Processing.
- [ ] Get User Data: Retrieve comprehensive user data based on `fb_id`.
- [ ] Save User Message: Save incoming user message to Chat Logs (sender_type: USER).
- [ ] Admin Active Check: Check if admin replied within last 10 minutes (using `last_admin_reply_timestamp`).
    - [ ] If Yes: STOP Processing.
- [ ] Determine User Stage: Identify `current_stage` (ONBOARDING, MARKETING, MOCK_EXAM, GENERAL_BOT).
- [ ] Quick Reply Logic:
    - [ ] If user NOT in Mock Exam stage:
        - [ ] Generate and send quick reply (nano model, current prompt, last 3 messages).
- [ ] Select Function: Choose appropriate function/handler based on `current_stage`.
- [ ] Generate & Save Replies: Selected function processes message, generates replies, saves to Chat Logs (sender_type: SYSTEM_AI).
- [ ] Context Summarization Check: Check if total unsynced chat messages (USER, SYSTEM_AI, ADMIN_MANUAL) for user exceeds 20.
    - [ ] If Yes:
        - [ ] Summarize oldest 14 unsynced messages.
        - [ ] Merge with existing user summary.
        - [ ] Update user's summary field (<1,000 characters).

### Manual Override (Admin Pause)
- [ ] Implement manual override based on Message Processing Flow Steps 3 & 6.

### Context Management (Memory Optimization)
- [ ] Implement sliding window algorithm based on Message Processing Flow Step 11.

### Quick Reply Mechanism
- [ ] Implement quick reply mechanism based on Message Processing Flow Step 8.

### Prompt Management
- [ ] Put prompts in the same file for easier update.

## 5. Technical Implementation Steps (Summary)
- [ ] Context Logic: Implement the "Sliding Window" algorithm with the refined summarization rules.
- [ ] Quick Reply Implementation: Develop the nano-model quick reply mechanism, ensuring it respects the exam stage exclusion.
