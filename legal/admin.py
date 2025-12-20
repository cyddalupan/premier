from django.contrib import admin
from .models import Course

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at', 'updated_at')
    # Automatically add created_at and updated_at to readonly_fields
    # This prevents them from being edited in the admin, as they are auto-populated
    readonly_fields = ('created_at', 'updated_at')
