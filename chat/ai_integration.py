import os
import openai
import logging
from django.conf import settings
from chat.utils import get_prompt
import json

logger = logging.getLogger(__name__)

class AIIntegration:
    def __init__(self):
        pass


    def generate_chat_response(self, user_id, system_prompt_name, user_prompt_name, prompt_category, prompt_context, model="gpt-5-mini"):
        """
        Generates a general chat response using a specified AI model and prompts.
        :param user_id: The ID of the user.
        :param system_prompt_name: The name of the system prompt to retrieve.
        :param user_prompt_name: The name of the user prompt template to retrieve.
        :param prompt_category: The category for prompt retrieval.
        :param prompt_context: A dictionary with values to format the user prompt.
        :param model: The AI model to use (defaults to gpt-5-mini).
        :return: A string containing the AI's response, or None if an error occurs.
        """
        logger.info(f"Generating chat response for user {user_id} using prompts {system_prompt_name}, {user_prompt_name} in category {prompt_category}")
        try:
            system_prompt = get_prompt(name=system_prompt_name, category=prompt_category)
            user_prompt_template = get_prompt(name=user_prompt_name, category=prompt_category)
            
            # Format the user prompt with the provided context
            formatted_user_prompt = user_prompt_template.format(**prompt_context)

            print("DEBUG: Reached openai.chat.completions.create call in generate_chat_response.")
            response = openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": formatted_user_prompt}
                ],
            )
            reply = response.choices[0].message.content.strip()
            logger.info(f"Generated chat response: {reply}")
            return reply
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error during chat response generation: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error during chat response generation: {e}", exc_info=True)
            return None

    def get_quick_reply(self, user_id, conversation_history):
        """
        Generates a quick reply using a nano AI model.
        :param user_id: The ID of the user.
        :param conversation_history: A list of recent messages for context.
        :return: A short, concise reply.
        """
        logger.info(f"Generating quick reply for user {user_id} with history: {conversation_history}")
        # Placeholder for actual AI call
        try:
            # Example: Use OpenAI's chat completion for a quick reply
            response = openai.chat.completions.create(
                model="gpt-5-mini", # Or a more "nano" model if available and suitable
                messages=[
                    {"role": "system", "content": get_prompt(name='QUICK_REPLY_SYSTEM_PROMPT', category='QUICK_REPLY')},
                    {"role": "user", "content": get_prompt(name='QUICK_REPLY_USER_PROMPT_TEMPLATE', category='QUICK_REPLY').format(conversation_history=conversation_history)}
                ],
            )
            reply = response.choices[0].message.content.strip()
            logger.info(f"Generated quick reply: {reply}")
            return reply
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error during quick reply generation: {e}")
            return "I'm sorry, I couldn't generate a quick reply at the moment."
        except Exception as e:
            logger.error(f"Unexpected error during quick reply generation: {e}")
            return "An unexpected error occurred."

    def summarize_conversation(self, user_id, conversation_chunk, existing_summary=None):
        """
        Summarizes a chunk of conversation, optionally merging with an existing summary.
        :param user_id: The ID of the user.
        :param conversation_chunk: A list of messages to summarize.
        :param existing_summary: An optional existing summary to merge with.
        :return: A concise summary of the conversation.
        """
        logger.info(f"Summarizing conversation for user {user_id}. Chunk: {conversation_chunk}")
        # Placeholder for actual AI call
        try:
            prompt_messages = [
                {"role": "system", "content": get_prompt(name='SUMMARIZE_SYSTEM_PROMPT', category='SUMMARIZATION')},
            ]
            if existing_summary:
                prompt_messages.append({"role": "user", "content": get_prompt(name='SUMMARIZE_USER_PROMPT_WITH_EXISTING_SUMMARY_TEMPLATE', category='SUMMARIZATION').format(existing_summary=existing_summary, conversation_chunk=conversation_chunk)})
            else:
                prompt_messages.append({"role": "user", "content": get_prompt(name='SUMMARIZE_USER_PROMPT_WITHOUT_EXISTING_SUMMARY_TEMPLATE', category='SUMMARIZATION').format(conversation_chunk=conversation_chunk)})

            response = openai.chat.completions.create(
                model="gpt-5-mini",
                messages=prompt_messages,
            )
            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated summary: {summary}")
            return summary
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error during conversation summarization: {e}")
            return "I'm sorry, I couldn't summarize the conversation at the moment."
        except Exception as e:
            logger.error(f"Unexpected error during conversation summarization: {e}")
            return "An unexpected error occurred."

    def grade_exam_answer(self, user_id, question_text, user_answer, expected_answer):
        """
        Grades an exam answer based on expected answer.
        :param user_id: The ID of the user.
        :param question_text: The exam question.
        :param user_answer: The user's provided answer.
        :param expected_answer: The model's expected answer/key points.
        :return: A dict containing feedback (Grammar/Syntax, Legal Basis, Application, Conclusion, Score).
        """
        logger.info(f"Grading exam answer for user {user_id}. Question: {question_text[:50]}...")
        # Placeholder for actual AI call
        try:
            # Construct a detailed prompt for grading
            prompt = get_prompt(name='GRADE_EXAM_USER_PROMPT_TEMPLATE', category='EXAM_GRADING').format(question_text=question_text, user_answer=user_answer, expected_answer=expected_answer)
            response = openai.chat.completions.create(
                model="gpt-5.2", # Use a more capable model for grading
                messages=[
                    {"role": "system", "content": get_prompt(name='GRADE_EXAM_SYSTEM_PROMPT', category='EXAM_GRADING')},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=500,
                response_format={"type": "json_object"}
            )
            grading_result_str = response.choices[0].message.content.strip()
            logger.info(f"Raw AI grading response: {grading_result_str}") # Added log
            grading_result = json.loads(grading_result_str)
            logger.info(f"Grading result: {grading_result}")
            return grading_result
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error during exam grading: {e}")
            return {"error": "I'm sorry, I couldn't grade the answer at the moment."}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from AI for exam grading: {e}. Raw response: {grading_result_str}")
            return {"error": "I received an unreadable response from the grading system."}
        except Exception as e:
            logger.error(f"Unexpected error during exam grading: {e}")
            return {"error": "An unexpected error occurred."}

    def generate_re_engagement_message(self, user_id, first_name, current_stage, user_summary, conversation_history):
        """
        Generates a re-engagement message using a general AI model.
        :param user_id: The ID of the user.
        :param first_name: The first name of the user.
        :param current_stage: The current stage of the user (e.g., ONBOARDING, MARKETING).
        :param user_summary: The AI-generated summary of the user's persona and history.
        :param conversation_history: A formatted string of recent conversation history.
        :return: A generated re-engagement message.
        """
        logger.info(f"Generating re-engagement message for user {user_id} in stage {current_stage}")
        try:
            user_prompt = get_prompt(name='RE_ENGAGEMENT_USER_PROMPT_TEMPLATE', category='RE_ENGAGEMENT').format(
                first_name=first_name if first_name else "there",
                current_stage=current_stage,
                user_summary=user_summary if user_summary else "No summary available.",
                conversation_history=conversation_history if conversation_history else "No recent conversation history."
            )
            response = openai.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": get_prompt(name='RE_ENGAGEMENT_SYSTEM_PROMPT', category='RE_ENGAGEMENT')},
                    {"role": "user", "content": user_prompt}
                ],
            )
            message = response.choices[0].message.content.strip()
            logger.info(f"Generated re-engagement message for {user_id}: {message}")
            return message
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error during re-engagement message generation: {e}")
            return "Hello! We missed you. How can I help you today?" # Fallback message
        except Exception as e:
            logger.error(f"Unexpected error during re-engagement message generation: {e}")
            return "Hi there! Just checking in. Let me know if you have any questions." # Fallback message

    def generate_strength_assessment(self, user):
        """
        Generates a personalized assessment of the user's strengths based on their mock exam results.
        :param user: The User object for whom to generate the assessment.
        :return: A string containing the AI-generated strength assessment.
        """
        from chat.models import ExamResult, Question # Import locally to avoid circular dependency
        logger.info(f"Generating strength assessment for user {user.user_id}")

        exam_results = ExamResult.objects.filter(user=user).select_related('question')
        if not exam_results.exists():
            return "You haven't completed any mock exam questions yet. Complete an exam to get a personalized strength assessment!"

        # Aggregate scores by category
        category_scores = {}
        for result in exam_results:
            category = result.question.category
            if category not in category_scores:
                category_scores[category] = {'total_score': 0, 'count': 0}
            category_scores[category]['total_score'] += result.score
            category_scores[category]['count'] += 1

        categorized_scores_list = []
        for category, data in category_scores.items():
            avg_score = data['total_score'] / data['count']
            categorized_scores_list.append(f"- {category} (Avg Score: {avg_score:.1f})")
        
        categorized_scores_str = "\n".join(categorized_scores_list)
        logger.info(f"Categorized scores for user {user.user_id}:\n{categorized_scores_str}")

        try:
            user_prompt = get_prompt(name='ASSESSMENT_USER_PROMPT_TEMPLATE', category='ASSESSMENT').format(categorized_scores=categorized_scores_str)
            messages_to_send = [
                {"role": "system", "content": get_prompt(name='ASSESSMENT_SYSTEM_PROMPT', category='ASSESSMENT')},
                {"role": "user", "content": user_prompt}
            ]
            logger.info("Sending prompt to OpenAI for strength assessment")

            response = openai.chat.completions.create(
                model="gpt-5.2", # Use a more capable model for detailed assessment
                messages=messages_to_send,
                max_completion_tokens=500, # Allow for a comprehensive assessment
            )
            assessment = response.choices[0].message.content.strip()
            logger.info(f"Generated strength assessment for {user.user_id}: {assessment}")
            return assessment
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error during strength assessment generation: {e}")
            return "I'm sorry, I couldn't generate your strength assessment at the moment. Please try again later."
        except Exception as e:
            logger.error(f"Unexpected error during strength assessment generation: {e}")
            return "An unexpected error occurred while trying to assess your strengths."

    def extract_name_from_message(self, message_text):
        """
        Extracts a person's name from the given message text using an AI model.
        :param message_text: The full text from which to extract the name.
        :return: The extracted name as a string, or None if no name is found.
        """
        logger.info(f"Attempting to extract name from message: {message_text}")
        try:
            response = openai.chat.completions.create(
                model="gpt-5.2", # Upgraded model for improved name extraction
                messages=[
                    {"role": "system", "content": get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION')},
                    {"role": "user", "content": get_prompt(name='NAME_EXTRACTION_USER_PROMPT_TEMPLATE', category='NAME_EXTRACTION').format(message_text=message_text)}
                ],
                max_completion_tokens=20 # A name should not be very long
            )
            extracted_name = response.choices[0].message.content
            logger.info(f"Raw AI extracted name response: '{extracted_name}'") # Added for debugging
            print(f"DEBUG: Raw AI extracted name response: '{extracted_name}'") # Explicit print for visibility
            extracted_name = extracted_name.strip()
            if extracted_name and extracted_name != '[NO_NAME]':
                logger.info(f"Extracted name: {extracted_name}")
                return extracted_name
            else:
                logger.info("No name extracted by AI or AI returned '[NO_NAME]'. Falling back to 'User'.")
                return "User"
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error during name extraction: {e}. Falling back to 'User'.")
            return "User"
        except Exception as e:
            logger.error(f"Unexpected error during name extraction: {e}. Falling back to 'User'.")
            return "User"


