# Law Review Center AI Chatbot - Mock Exam TODO

This document outlines tasks specifically for implementing the Mock Exam feature.

## 3. Conversation Lifecycle (The Flow)

### Stage 3: The Mock Exam (The Core Feature)
- [ ] Loop: Repeat 8 times.
    - [ ] AI selects a random question from `exam_questions`.
    - [ ] User answers.
    - [ ] AI Analysis (The 5-Point Feedback System):
        - [ ] Grammar/Syntax: Checks for professional legal tone.
        - [ ] Legal Basis: Cites relevant laws/jurisprudence.
        - [ ] Application: How the law was applied to facts.
        - [ ] Conclusion: Whether the final answer is correct.
        - [ ] Score: A numerical rating (1-100% or Bar scale).
- [ ] Prio: Get full grading system. How the score is being computed then plan implementation when gathered.
- [ ] Transition: After 8 questions, move to Stage 4.

## 5. Technical Implementation Steps (Summary)
- [ ] Exam Logic: Build the function to fetch random questions and the Prompt Engineering for the "5-Point Feedback."
