# Database Structure

This document outlines the database schema for the Law Review Center AI Chatbot, detailing the purpose and fields of each model.

## 1. User Table (`User`)

**Purpose:** Stores user-specific information, including conversation state, personal details, and interaction timestamps.

| Field                        | Type          | Description                                         |
| :--------------------------- | :------------ | :-------------------------------------------------- |
| `user_id` (PK)               | `CharField`   | Unique Facebook PSID for the user.                  |
| `first_name`                 | `CharField`   | User's first name.                                  |
| `current_stage`              | `CharField`   | Current stage of the user in the conversation flow. |
| `exam_question_counter`      | `IntegerField`| Tracks progress during the mock exam (0-8).         |
| `summary`                    | `TextField`   | AI-generated summary of the user's persona/history. |
| `last_admin_reply_timestamp` | `DateTimeField`| Timestamp of the last admin reply for pause logic.  |
| `last_interaction_timestamp` | `DateTimeField`| Timestamp of the last user interaction for follow-up messages. |

**`current_stage` Choices:**
*   `ONBOARDING`
*   `MARKETING`
*   `MOCK_EXAM`
*   `GENERAL_BOT`

## 2. Question Bank Table (`Question`)

**Purpose:** Stores a pool of questions and their expected answers for the Mock Exam feature.

| Field             | Type          | Description                                         |
| :---------------- | :------------ | :-------------------------------------------------- |
| `id` (PK)         | `AutoField`   | Unique identifier for the question.                 |
| `category`        | `CharField`   | Category of the question (e.g., Criminal Law).      |
| `question_text`   | `TextField`   | The actual scenario or question.                    |
| `expected_answer` | `TextField`   | The model answer or key points.                     |
| `rubric_criteria` | `TextField`   | Specific points required for full credit (currently not populated from `questions.json`). |

**`category` Choices:**
*   `CRIMINAL_LAW`
*   `CIVIL_LAW`
*   `REMEDIAL_LAW`
*   `POLITICAL_LAW`
*   `LABOR_LAW`
*   `TAX_LAW`
*   `COMMERCIAL_LAW`
*   `ETHICS`

## 3. Chat Logs Table (`ChatLog`)

**Purpose:** Maintains a permanent record of all messages exchanged with users.

| Field             | Type          | Description                                         |
| :---------------- | :------------ | :-------------------------------------------------- |
| `id` (PK)         | `AutoField`   | Unique identifier for the chat log entry.           |
| `user` (FK)       | `ForeignKey`  | Foreign key to the `User` table.                    |
| `sender_type`     | `CharField`   | Type of sender (User, System AI, Admin Manual).     |
| `message_content` | `TextField`   | The text body of the message.                       |
| `timestamp`       | `DateTimeField`| Time when the message was sent (auto-generated).    |

**`sender_type` Choices:**
*   `USER`
*   `SYSTEM_AI`
*   `ADMIN_MANUAL`
