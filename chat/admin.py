from django.contrib import admin
from .models import User, Question, ChatLog

admin.site.register(User)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'category', 'course')
    list_filter = ('category', 'course')
    search_fields = ('question_text', 'expected_answer')

admin.site.register(ChatLog)