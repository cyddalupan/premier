"content" => <<<EOD
Compare the user_answer to expected_answer and output only a valid JSON object with:
- "score": integer (1-100, 100 for full match, 70-95 for close match, 0-30 for mismatch).
- "feedback": string (Bootstrap-styled HTML table that evaluates the following criteria: Answer, Legal Basis, Application, Conclusion, and Legal Writing. 
    - Each criterion should be graded individually (5/5 if perfect). 
    - Show subtotal per criterion (max 5 points each, total 25 = 100%).
    - Provide explanations for mistakes under each criterion.
    - After the table, include an "Additional Insights" section in plain text containing:
        a) The correct expected_answer (either provided or AI-generated if missing).
        b) A section titled: 
           🔎 Mistakes 
           ❌ List each mistake clearly and specifically.
        c) Suggestions for improvement.
        d) If the user scored perfectly, congratulate them in this section.
EOD
