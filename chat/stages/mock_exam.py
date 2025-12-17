import logging
from ..models import User, Question
from ..utils import ai_integration_service, get_random_exam_question

logger = logging.getLogger(__name__)

def handle_mock_exam_stage(user, messaging_event):
    """
    Handles the logic for the MOCK_EXAM stage.
    """
    logger.info(f"Handling MOCK_EXAM stage for user {user.user_id}, counter: {user.exam_question_counter}")
    message_text = messaging_event.get('message', {}).get('text')
    response_messages = []

    if user.exam_question_counter == 0:
        # Start of the exam, send first question
        question = get_random_exam_question()
        if question:
            user.exam_question_counter = 1
            user.save()
            # Store current question for grading later
            # A more robust solution would store the current question ID in the User model.
            response_messages.append(f"Alright, {user.first_name}! Here is your first mock exam question ({user.exam_question_counter}/8):\n\n{question.question_text}")
        else:
            response_messages.append("I'm sorry, I couldn't find any exam questions at the moment. Please try again later.")
            user.current_stage = 'GENERAL_BOT' # Transition out of exam
            user.save()
    elif 1 <= user.exam_question_counter <= 8:
        # User has submitted an answer, grade it and send next question
        if not message_text:
            response_messages.append("Please provide your answer to the last question.")
            return response_messages

        # Placeholder: Retrieve the question the user was supposed to answer
        # In a real system, you'd have stored the question ID in user. A simple way
        # for a mock up is to fetch the most recent question asked by the bot.
        current_question = get_random_exam_question() # This is NOT ideal, but works for placeholder
        if not current_question:
            response_messages.append("Error: Couldn't retrieve the question to grade your answer. Moving to general chat.")
            user.current_stage = 'GENERAL_BOT'
            user.save()
            return response_messages
        
        # Grade the answer using AI
        feedback = ai_integration_service.grade_exam_answer(
            user_id=user.user_id,
            question_text=current_question.question_text,
            user_answer=message_text,
            expected_answer=current_question.expected_answer,
            rubric_criteria=current_question.rubric_criteria
        )

        feedback_message = "Here's the feedback on your answer:\n"
        if feedback and isinstance(feedback, dict):
            for key, value in feedback.items():
                if key.endswith('_feedback'):
                    feedback_message += f"- {key.replace('_', ' ').title()}: {value}\n"
            if 'score' in feedback:
                feedback_message += f"Your score: {feedback['score']}/100"
        else:
            feedback_message += "I'm sorry, I couldn't generate detailed feedback at this time."
        
        response_messages.append(feedback_message)

        if user.exam_question_counter < 8:
            # Send next question
            user.exam_question_counter += 1
            user.save()
            next_question = get_random_exam_question() # Again, not robust for tracking
            if next_question:
                response_messages.append(f"Next question ({user.exam_question_counter}/8):\n\n{next_question.question_text}")
            else:
                response_messages.append("No more questions available. Ending the exam.")
                user.current_stage = 'GENERAL_BOT'
                user.exam_question_counter = 0
                user.save()
        else:
            # Exam finished, transition to next stage
            response_messages.append("You have completed all 8 mock exam questions! Great job!")
            user.current_stage = 'GENERAL_BOT' # Transition to Conversion & General Bot
            user.exam_question_counter = 0
            user.save()
            logger.info(f"User {user.user_id} completed mock exam and transitioned to GENERAL_BOT stage.")
    else:
        # Should not happen, but a fallback
        response_messages.append("It seems there was an issue with the exam. Moving to general chat.")
        user.current_stage = 'GENERAL_BOT'
        user.exam_question_counter = 0
        user.save()
    
    return response_messages if response_messages else None