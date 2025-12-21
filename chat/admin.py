from django.contrib import admin
from .models import User, Question, ChatLog, Prompt

admin.site.register(User)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'category', 'course')
    list_filter = ('category', 'course')
    search_fields = ('question_text', 'expected_answer')

admin.site.register(ChatLog)

@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'description', 'updated_at')
    list_filter = ('category',)
    search_fields = ('name', 'text_content', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'category', 'text_content', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )