from django.db import models

class Course(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Name of the course")
    description = models.TextField(blank=True, null=True, help_text="Description of the course")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def __str__(self):
        return self.name
