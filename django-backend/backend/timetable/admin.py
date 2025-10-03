from django.contrib import admin
from .models import Subject, Teacher, Classroom, ScheduleConfig, TimetableEntry, TeacherSubjectAssignment

# Note: Group and Celery models are unregistered in apps.py ready() method

# Register models (removed Config and ClassGroup as requested)
admin.site.register(Subject)
admin.site.register(Teacher)
admin.site.register(Classroom)
admin.site.register(ScheduleConfig)
admin.site.register(TimetableEntry)

# Add TeacherSubjectAssignment that was missing from admin
admin.site.register(TeacherSubjectAssignment)
