import logging
from django.db import transaction
from ..models import User, Question
from ..utils import get_random_exam_question, generate_persuasion_messages
from ..ai_integration import AIIntegration # Import AIIntegration directly

logger = logging.getLogger(__name__)

# Instantiate AIIntegration for use within this stage handler
ai_integration_service = AIIntegration()

def handle_mock_exam_stage(user, messaging_event):
    """
    Handles the logic for the MOCK_EXAM stage.
    """
    # The user object is already locked by the process_messenger_message transaction
    logger.info(f"Handling MOCK_EXAM stage for user {user.user_id}, counter: {user.exam_question_counter}")
    message_text = messaging_event.get('message', {}).get('text')
    response_messages = []

    # Simple opt-out detection for now (can be enhanced with AI intent later)
    if message_text and any(keyword in message_text.lower() for keyword in ["stop", "quit", "end exam", "i'm done", "i am done"]):
        persuasion = generate_persuasion_messages(user, 'exam_opt_out')
        response_messages.extend(persuasion)
        user.current_stage = 'GENERAL_BOT'
        user.exam_question_counter = 0
        user.last_question_id_asked = None
        user.save()
        logger.info(f"User {user.user_id} opted out of mock exam and transitioned to GENERAL_BOT stage.")
        return response_messages

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
            expected_answer=current_question.expected_answer
        )
        logger.info(f"Received feedback from AI integration service: {feedback}") # Added log

        feedback_message = "Here's the feedback on your answer:\n"
        exam_score = None
        legal_writing_feedback = None
        legal_basis_feedback = None
        application_feedback = None
        conclusion_feedback = None

        if feedback and isinstance(feedback, dict):
            if 'legal_writing_feedback' in feedback:
                legal_writing_feedback = feedback['legal_writing_feedback']
                feedback_message += f"- Legal Writing: {legal_writing_feedback}\n"
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
                legal_writing_feedback=legal_writing_feedback,
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
                # Persuasion messages for early exam end due to no more questions
                persuasion = generate_persuasion_messages(user, 'exam_opt_out') # Using opt_out context as it's an unexpected end
                response_messages.extend(persuasion)
        else:
            # Exam finished, generate strength assessment and then transition to next stage
            response_messages.append("You have completed all 8 mock exam questions! Great job!")
            
            # Generate and append strength assessment
            strength_assessment_message = ai_integration_service.generate_strength_assessment(user)
            response_messages.append(strength_assessment_message)

            # Log the strength assessment to ChatLog
            from chat.models import ChatLog # Import locally to avoid circular dependency
            ChatLog.objects.create(
                user=user,
                sender_type='SYSTEM_AI',
                message_content=strength_assessment_message
            )

            user.current_stage = 'GENERAL_BOT' # Transition to Conversion & General Bot
            user.exam_question_counter = 0
            user.last_question_id_asked = None
            user.save()
            logger.info(f"User {user.user_id} completed mock exam, received strength assessment, and transitioned to GENERAL_BOT stage.")
            # Add persuasion messages for exam completion
            persuasion = generate_persuasion_messages(user, 'exam_finished')
            response_messages.extend(persuasion)
    else:
        # Should not happen, but a fallback
        response_messages.append("It seems there was an issue with the exam. Moving to general chat.")
        user.current_stage = 'GENERAL_BOT'
        user.exam_question_counter = 0
        user.last_question_id_asked = None
        user.save()
        # Persuasion messages for unexpected exam end
        persuasion = generate_persuasion_messages(user, 'exam_opt_out') # Using opt_out context as it's an unexpected end
        response_messages.extend(persuasion)
    
    return response_messages