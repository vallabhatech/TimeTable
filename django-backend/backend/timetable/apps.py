from django.apps import AppConfig


class TimetableConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'timetable'
    
    def ready(self):
        from django.contrib import admin
        from django.contrib.auth.models import Group
        
        # Unregister Django's default Group model
        try:
            admin.site.unregister(Group)
        except admin.sites.NotRegistered:
            pass
            
        # Unregister Celery result models
        try:
            from django_celery_results.models import TaskResult, GroupResult
            admin.site.unregister(TaskResult)
            admin.site.unregister(GroupResult)
        except (ImportError, admin.sites.NotRegistered):
            pass
