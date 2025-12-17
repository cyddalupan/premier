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
            user.last_question_id_asked = question  # Store the question
            user.save()
            response_messages.append(f"Alright, {user.first_name}! Here is your first mock exam question ({user.exam_question_counter}/8):\n\n{question.question_text}")
        else:
            response_messages.append("I'm sorry, I couldn't find any exam questions at the moment. Please try again later.")
            user.current_stage = 'GENERAL_BOT' # Transition out of exam
            user.last_question_id_asked = None # Clear the question
            user.save()
    elif 1 <= user.exam_question_counter <= 8:
        # User has submitted an answer, grade it and send next question
        if not message_text:
            response_messages.append("Please provide your answer to the last question.")
            return response_messages

        current_question = user.last_question_id_asked
        if not current_question:
            response_messages.append("Error: The question to grade your answer could not be found. Moving to general chat.")
            user.current_stage = 'GENERAL_BOT'
            user.exam_question_counter = 0
            user.last_question_id_asked = None
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
        exam_score = None
        grammar_feedback = None
        legal_basis_feedback = None
        application_feedback = None
        conclusion_feedback = None

        if feedback and isinstance(feedback, dict):
            if 'grammar_feedback' in feedback:
                grammar_feedback = feedback['grammar_feedback']
                feedback_message += f"- Grammar/Syntax: {grammar_feedback}\n"
            if 'legal_basis_feedback' in feedback:
                legal_basis_feedback = feedback['legal_basis_feedback']
                feedback_message += f"- Legal Basis: {legal_basis_feedback}\n"
            if 'application_feedback' in feedback:
                application_feedback = feedback['application_feedback']
                feedback_message += f"- Application: {application_feedback}\n"
            if 'conclusion_feedback' in feedback:
                conclusion_feedback = feedback['conclusion_feedback']
                feedback_message += f"- Conclusion: {conclusion_feedback}\n"
            if 'score' in feedback:
                exam_score = feedback['score']
                feedback_message += f"Your score: {exam_score}/100\n"
        else:
            feedback_message += "I'm sorry, I couldn't generate detailed feedback at this time.\n"
        
        response_messages.append(feedback_message)

        # Save the exam result
        if exam_score is not None:
            from ..models import ExamResult # Import locally to avoid circular dependency
            ExamResult.objects.create(
                user=user,
                question=current_question,
                score=exam_score,
                grammar_feedback=grammar_feedback,
                legal_basis_feedback=legal_basis_feedback,
                application_feedback=application_feedback,
                conclusion_feedback=conclusion_feedback,
            )

        if user.exam_question_counter < 8:
            # Send next question
            next_question = get_random_exam_question() 
            if next_question:
                user.exam_question_counter += 1
                user.last_question_id_asked = next_question # Store the new question
                user.save()
                response_messages.append(f"Next question ({user.exam_question_counter}/8):\n\n{next_question.question_text}")
            else:
                response_messages.append("No more questions available. Ending the exam.")
                user.current_stage = 'GENERAL_BOT'
                user.exam_question_counter = 0
                user.last_question_id_asked = None
                user.save()
        else:
            # Exam finished, transition to next stage
            response_messages.append("You have completed all 8 mock exam questions! Great job!")
            user.current_stage = 'GENERAL_BOT' # Transition to Conversion & General Bot
            user.exam_question_counter = 0
            user.last_question_id_asked = None
            user.save()
            logger.info(f"User {user.user_id} completed mock exam and transitioned to GENERAL_BOT stage.")
    else:
        # Should not happen, but a fallback
        response_messages.append("It seems there was an issue with the exam. Moving to general chat.")
        user.current_stage = 'GENERAL_BOT'
        user.exam_question_counter = 0
        user.last_question_id_asked = None
        user.save()
    
    return response_messages