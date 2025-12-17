import os
import openai
import logging
from django.conf import settings

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
                model="gpt-3.5-turbo", # Or a more "nano" model if available and suitable
                messages=[
                    {"role": "system", "content": "You are a helpful assistant providing very brief replies."},
                    {"role": "user", "content": f"Based on this conversation: {conversation_history}, provide a quick, one-sentence reply."}
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
                {"role": "system", "content": "You are an AI assistant that summarizes conversations concisely."},
            ]
            if existing_summary:
                prompt_messages.append({"role": "user", "content": f"Here is a previous summary: {existing_summary}. Summarize the following new conversation chunk and merge it with the previous summary, keeping it under 1000 characters: {conversation_chunk}"})
            else:
                prompt_messages.append({"role": "user", "content": f"Summarize the following conversation chunk under 1000 characters: {conversation_chunk}"})

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
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
            prompt = f"""
            Grade the following exam answer provided by a student based on the given question, expected answer, and rubric criteria.
            Provide feedback for Grammar/Syntax, Legal Basis, Application, and Conclusion. Assign a score out of 100.

            Question: {question_text}
            Student Answer: {user_answer}
            Expected Answer/Key Points: {expected_answer}
            Rubric Criteria: {rubric_criteria}

            Please format your response as a JSON object with the following keys:
            {{
                "grammar_syntax_feedback": "...",
                "legal_basis_feedback": "...",
                "application_feedback": "...",
                "conclusion_feedback": "...",
                "score": int (1-100)
            }}
            """
            response = openai.chat.completions.create(
                model="gpt-4", # Use a more capable model for grading
                messages=[
                    {"role": "system", "content": "You are a legal expert AI assistant tasked with grading law exam answers objectively and providing constructive feedback."},
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
