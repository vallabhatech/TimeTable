from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    ROLES = (
        ('ADMIN', 'Admin'),
        ('TEACHER', 'Teacher'),
        ('STUDENT', 'Student'),
    )
    # role = models.CharField(max_length=10, choices=ROLES, default='TEACHER')
    firebase_uid = models.CharField(max_length=128, unique=True, null=True, blank=True)
    
    # Override email field to make it unique
    email = models.EmailField(_('email address'), unique=True, blank=True)
    
    def clean(self):
        super().clean()
        # Additional validation to ensure email uniqueness
        if self.email:
            # Check if another user has the same email (excluding self)
            if User.objects.filter(email=self.email).exclude(pk=self.pk).exists():
                raise ValidationError({
                    'email': _('A user with this email address already exists.')
                })
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)