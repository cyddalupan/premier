# Law Review Center AI Chatbot - Re-engagement & Marketing TODO

This document outlines tasks for the re-engagement strategy and marketing data collection.

## 4. Re-engagement Strategy (Follow-up Messages)
- [ ] Trigger: Scheduled cron job checking `last_interaction_timestamp`.
- [ ] If inactive for X hours/days, send one of these (randomized):
    - [ ] Trivia/Fun Fact: "Did you know [Obscure Law] is still valid?"
    - [ ] Giveaway/Promo: "We are giving away a free reviewer PDF..."
    - [ ] Legal Maxim of the Day: "Explain 'Dura lex sed lex' in your own words."
    - [ ] Success Story: "One of our students, [Name], just topped the bar..."
    - [ ] Quick Case Digest: A 3-sentence summary of a recent Supreme Court ruling.
    - [ ] Mental Health Check: "Law school is tough. Don't forget to hydrate and rest."
- [ ] Complete plan for 1hr cron. This should have proper context per user and prompt including the marketing data.
- [ ] Get full marketing data (this will be used on follow ups and marketing phase).
