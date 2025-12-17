import json
from django.core.management.base import BaseCommand
from chat.models import Question
import os

class Command(BaseCommand):
    help = 'Imports questions from questions.json into the database and removes them from the JSON file.'

    def handle(self, *args, **options):
        json_file_path = 'questions.json'

        if not os.path.exists(json_file_path):
            self.stdout.write(self.style.ERROR(f"Error: {json_file_path} not found."))
            return

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f"Error: Could not decode JSON from {json_file_path}. Is it a valid JSON file?"))
            return

        questions_to_import = []
        metadata_parts = []
        original_data_container = None
        
        # Define the category mapping based on existing choices in models.py
        category_mapping = {
            "Political Law": "POLITICAL_LAW",
            "Criminal Law": "CRIMINAL_LAW",
            "Commercial Law": "COMMERCIAL_LAW",
            "Taxation": "TAX_LAW",
            "Remedial Law": "REMEDIAL_LAW",
            "Legal & Judicial Ethics": "ETHICS",
            "Civil Law": "CIVIL_LAW",
            # Add other mappings if necessary, or a default.
        }
        valid_categories = dict(Question.CATEGORY_CHOICES).keys()


        # Try to find the 'data' array containing the questions
        # This handles the specific structure observed: a list where the last element is a dict with a 'data' key
        if isinstance(data, list) and len(data) > 0 and 'data' in data[-1] and isinstance(data[-1]['data'], list):
            questions_to_import = data[-1]['data']
            metadata_parts = data[:-1]
            original_data_container = data[-1] # Reference to the dict containing the 'data' list
        elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            # If the entire file is just one dict with a 'data' key
            questions_to_import = data['data']
            original_data_container = data
        else:
            self.stdout.write(self.style.ERROR(f"Error: Unexpected JSON structure in {json_file_path}. Expected a 'data' key containing a list of questions within a dictionary or as the last element of a list."))
            return

        imported_count = 0
        failed_count = 0
        remaining_questions_in_json = []
        
        for q_entry in questions_to_import:
            q_question = q_entry.get("q_question")
            q_answer = q_entry.get("q_answer")
            course_name = q_entry.get("course_name")

            if not q_question or not q_answer or not course_name:
                self.stdout.write(self.style.WARNING(f"Skipping malformed entry: {q_entry}"))
                failed_count += 1
                remaining_questions_in_json.append(q_entry)
                continue

            formatted_category = category_mapping.get(course_name)
            
            if not formatted_category:
                self.stdout.write(self.style.WARNING(f"Skipping question due to unmapped category '{course_name}': {q_question[:50]}..."))
                failed_count += 1
                remaining_questions_in_json.append(q_entry)
                continue
            
            if formatted_category not in valid_categories:
                self.stdout.write(self.style.WARNING(f"Skipping question due to invalid mapped category '{formatted_category}' for original '{course_name}': {q_question[:50]}..."))
                failed_count += 1
                remaining_questions_in_json.append(q_entry)
                continue


            try:
                question = Question(
                    category=formatted_category,
                    question_text=q_question,
                    expected_answer=q_answer,
                    rubric_criteria="" # Default empty string as it's not in the JSON and optional
                )
                question.save()
                imported_count += 1
                self.stdout.write(self.style.SUCCESS(f"Successfully imported: {q_question[:50]}..."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to import question '{q_question[:50]}...': {e}"))
                failed_count += 1
                remaining_questions_in_json.append(q_entry)

        self.stdout.write(self.style.MIGRATE_HEADING(f"Import complete. Imported: {imported_count}, Failed: {failed_count}"))

        # Write back remaining questions to the JSON file
        if original_data_container:
            original_data_container['data'] = remaining_questions_in_json
            # If original data was a list, reassemble it
            if isinstance(data, list):
                new_json_content = metadata_parts + [original_data_container]
            else: # it was a dict
                new_json_content = original_data_container
        else:
            # If questions_to_import was empty initially or unexpected structure,
            # just write an empty data list in the expected format.
            new_json_content = {'data': remaining_questions_in_json}
            if metadata_parts:
                new_json_content = metadata_parts + [new_json_content]


        try:
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(new_json_content, f, indent=4, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(f"Updated {json_file_path} with {len(remaining_questions_in_json)} remaining questions."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error writing back to {json_file_path}: {e}"))
