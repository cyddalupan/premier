import os
import openai
import logging
from django.conf import settings
from . import prompts
import json

logger = logging.getLogger(__name__)

class AIIntegration:
    def __init__(self):
        openai.api_key = settings.OPEN_AI_TOKEN
        if not openai.api_key:
            logger.error("OPEN_AI_TOKEN is not set in Django settings.")
            raise ValueError("OPEN_AI_TOKEN is not set.")

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
                    {"role": "system", "content": prompts.QUICK_REPLY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompts.QUICK_REPLY_USER_PROMPT_TEMPLATE.format(conversation_history=conversation_history)}
                ],
                max_tokens=50,
                temperature=0.7,
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
                {"role": "system", "content": prompts.SUMMARIZE_SYSTEM_PROMPT},
            ]
            if existing_summary:
                prompt_messages.append({"role": "user", "content": prompts.SUMMARIZE_USER_PROMPT_WITH_EXISTING_SUMMARY_TEMPLATE.format(existing_summary=existing_summary, conversation_chunk=conversation_chunk)})
            else:
                prompt_messages.append({"role": "user", "content": prompts.SUMMARIZE_USER_PROMPT_WITHOUT_EXISTING_SUMMARY_TEMPLATE.format(conversation_chunk=conversation_chunk)})

            response = openai.chat.completions.create(
                model="gpt-5-mini",
                messages=prompt_messages,
                max_tokens=200, # Adjust based on expected summary length and input
                temperature=0.7,
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

    def grade_exam_answer(self, user_id, question_text, user_answer, expected_answer, rubric_criteria):
        """
        Grades an exam answer based on expected answer and rubric.
        :param user_id: The ID of the user.
        :param question_text: The exam question.
        :param user_answer: The user's provided answer.
        :param expected_answer: The model's expected answer/key points.
        :param rubric_criteria: Specific points required for full credit.
        :return: A dict containing feedback (Grammar/Syntax, Legal Basis, Application, Conclusion, Score).
        """
        logger.info(f"Grading exam answer for user {user_id}. Question: {question_text[:50]}...")
        # Placeholder for actual AI call
        try:
            # Construct a detailed prompt for grading
            prompt = prompts.GRADE_EXAM_USER_PROMPT_TEMPLATE.format(question_text=question_text, user_answer=user_answer, expected_answer=expected_answer, rubric_criteria=rubric_criteria)
            response = openai.chat.completions.create(
                model="gpt-5.2", # Use a more capable model for grading
                messages=[
                    {"role": "system", "content": prompts.GRADE_EXAM_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            grading_result_str = response.choices[0].message.content.strip()
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

    def generate_re_engagement_message(self, user_id, current_stage, user_summary):
        """
        Generates a re-engagement message using a general AI model.
        :param user_id: The ID of the user.
        :param current_stage: The current stage of the user (e.g., ONBOARDING, MARKETING).
        :param user_summary: The AI-generated summary of the user's persona and history.
        :return: A generated re-engagement message.
        """
        logger.info(f"Generating re-engagement message for user {user_id} in stage {current_stage}")
        try:
            user_prompt = prompts.RE_ENGAGEMENT_USER_PROMPT_TEMPLATE.format(
                current_stage=current_stage,
                user_summary=user_summary if user_summary else "No summary available."
            )
            response = openai.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": prompts.RE_ENGAGEMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=100, # Keep re-engagement messages concise
                temperature=0.8, # More creative responses
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

