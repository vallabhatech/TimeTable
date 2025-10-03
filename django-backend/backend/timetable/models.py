from django.db import models
from users.models import User
import json
from datetime import date

class Classroom(models.Model):
    name = models.CharField(max_length=50)
    building = models.CharField(max_length=50)
    # Add department and owner fields for data isolation
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    owner = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)

    # Room classification properties
    @property
    def is_lab(self):
        """Check if this classroom is a lab."""
        return 'lab' in self.name.lower() or 'laboratory' in self.name.lower()

    @property
    def room_type(self):
        """Get the room type for allocation purposes."""
        if self.is_lab:
            return 'lab'
        return 'regular'

    @property
    def building_priority(self):
        """Get building priority for allocation (lower = higher priority)."""
        priority_map = {
            'Lab Block': 1,      # Highest priority for labs
            'Main Block': 2,     # Main building rooms
            'Main Building': 2,  # Alternative main building name
            'Academic Building': 3,  # Academic building rooms
            'Admin Block': 4     # Lowest priority
        }
        return priority_map.get(self.building, 5)

    def is_suitable_for_practical(self):
        """Check if this room is suitable for practical classes."""
        return self.is_lab

    def is_suitable_for_theory(self):
        """Check if this room is suitable for theory classes."""
        return True  # All rooms can host theory classes

    # Capacity field removed - no longer needed

    class Meta:
        ordering = ['building', 'name']

class ScheduleConfig(models.Model):
    name = models.CharField(max_length=255)
    days = models.JSONField(default=list)
    periods = models.JSONField(default=list)
    start_time = models.TimeField()
    class_duration = models.PositiveIntegerField()
    constraints = models.JSONField(default=dict)
    class_groups = models.JSONField(default=list)
    semester = models.CharField(max_length=50, default="Fall 2024")
    academic_year = models.CharField(max_length=20, default="2024-2025")
    created_at = models.DateTimeField(auto_now_add=True)
    # Add department and owner fields for data isolation
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    owner = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Ensure periods is always stored as array of strings
        if isinstance(self.periods, str):
            try:
                self.periods = json.loads(self.periods)
            except json.JSONDecodeError:
                self.periods = []
        elif not isinstance(self.periods, list):
            self.periods = []
            
        # Ensure class_groups is always stored as array of strings
        if isinstance(self.class_groups, str):
            try:
                self.class_groups = json.loads(self.class_groups)
            except json.JSONDecodeError:
                self.class_groups = []
        elif not isinstance(self.class_groups, list):
            self.class_groups = []
            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Config(models.Model):
    name = models.CharField(max_length=255)
    days = models.JSONField(default=list)
    periods = models.PositiveIntegerField()
    start_time = models.TimeField()
    class_duration = models.PositiveIntegerField()
    generated_periods = models.JSONField(default=dict)

    def __str__(self):
        return self.name
    
class ClassGroup(models.Model):
    start_time = models.TimeField()
    end_time = models.TimeField()
    latest_start_time = models.TimeField()
    min_classes = models.PositiveIntegerField()
    max_classes = models.PositiveIntegerField()
    class_groups = models.JSONField()

    def __str__(self):
        return ".".join(self.class_groups) or "No class groups"
    
class Batch(models.Model):
    name = models.CharField(max_length=10, unique=True, help_text="e.g., 21SW, 22SW, 23SW, 24SW, 25SW, etc.")
    description = models.CharField(max_length=100, help_text="e.g., 8th Semester - Final Year")
    semester_number = models.PositiveIntegerField(default=8, help_text="e.g., 8 for 8th semester")
    academic_year = models.CharField(max_length=20, default="2024-2025")
    total_sections = models.PositiveIntegerField(default=1, help_text="Number of sections in this batch (e.g., 3 for I, II, III)")
    class_advisor = models.CharField(max_length=255, default="", blank=True, help_text="Name or details of the class advisor for this batch")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Add department and owner fields for data isolation
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    owner = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-semester_number']  # Final year first

    def __str__(self):
        return f"{self.name} - {self.description} ({self.total_sections} sections)"

    def get_sections(self):
        """Return list of section names for this batch"""
        sections = []
        for i in range(1, self.total_sections + 1):
            if i == 1:
                sections.append("I")
            elif i == 2:
                sections.append("II")
            elif i == 3:
                sections.append("III")
            elif i == 4:
                sections.append("IV")
            elif i == 5:
                sections.append("V")
            else:
                sections.append(str(i))
        return sections

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)  # Remove unique=True to allow duplicates
    subject_short_name = models.CharField(max_length=10, unique=True, null=True, blank=True, help_text="Short name for display (e.g., MATH, CS101)")
    credits = models.PositiveIntegerField()
    is_practical = models.BooleanField(default=False)
    batch = models.CharField(max_length=10, blank=True, null=True, help_text="e.g., 21SW, 22SW, 23SW, 24SW, 25SW, etc.")
    # Add department and owner fields for data isolation
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    owner = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        # Allow up to 2 subjects with the same code (theory + practical)
        pass

    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Check if this code is already used more than once
        if self.code:
            existing_count = Subject.objects.filter(code__iexact=self.code).exclude(pk=self.pk).count()
            if existing_count >= 2:
                raise ValidationError({
                    'code': f'Subject code "{self.code}" is already used twice. Maximum allowed is 2 (theory and practical versions).'
                })
        
        # Check if subject_short_name is unique (only if provided)
        if self.subject_short_name:
            existing_short_name = Subject.objects.filter(subject_short_name__iexact=self.subject_short_name).exclude(pk=self.pk).first()
            if existing_short_name:
                raise ValidationError({
                    'subject_short_name': f'Subject short name "{self.subject_short_name}" is already in use.'
                })

    def save(self, *args, **kwargs):
        # Auto-detect practical subjects based on name or code
        if '(PR)' in self.name or 'PR' in self.code:
            self.is_practical = True
        
        # Run validation before saving
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
class Teacher(models.Model):
    name = models.CharField(max_length=255, default="")
    # Note: subjects relationship now handled through TeacherSubjectAssignment
    max_classes_per_day = models.PositiveIntegerField(default=4)
    unavailable_periods = models.JSONField(default=dict, blank=True)
    # Add department and owner fields for data isolation
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    owner = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_subjects(self):
        """Get all subjects this teacher is assigned to"""
        return Subject.objects.filter(teachersubjectassignment__teacher=self).distinct()

    def get_assignments(self):
        """Get all teacher-subject assignments"""
        return TeacherSubjectAssignment.objects.filter(teacher=self)

class TeacherSubjectAssignment(models.Model):
    """Intermediate model to handle teacher-subject assignments with section specificity"""
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    sections = models.JSONField(default=list, help_text="List of sections this teacher handles for this subject, e.g., ['I', 'II']")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Remove unique_together constraint to allow multiple assignments for same teacher-subject-batch
        # This allows teachers to be assigned to different sections of the same subject
        verbose_name = "Teacher Subject Assignment"
        verbose_name_plural = "Teacher Subject Assignments"

    def clean(self):
        """Validate that sections don't conflict with existing assignments"""
        from django.core.exceptions import ValidationError

        if not self.sections:
            return  # No sections specified means all sections

        # Check for conflicts with other assignments for the same subject and batch
        existing_assignments = TeacherSubjectAssignment.objects.filter(
            subject=self.subject,
            batch=self.batch
        ).exclude(pk=self.pk if self.pk else None)

        for assignment in existing_assignments:
            if not assignment.sections:  # Other assignment covers all sections
                raise ValidationError(
                    f"Teacher {assignment.teacher.name} is already assigned to all sections of {self.subject.name} in {self.batch.name}"
                )

            # Check for section overlap
            overlapping_sections = set(self.sections) & set(assignment.sections)
            if overlapping_sections:
                raise ValidationError(
                    f"Sections {', '.join(overlapping_sections)} are already assigned to {assignment.teacher.name} for {self.subject.name} in {self.batch.name}"
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        sections_str = ", ".join(self.sections) if self.sections else "All"
        return f"{self.teacher.name} - {self.subject.name} ({self.batch.name} - Sections: {sections_str})"

    def get_sections_display(self):
        """Return formatted sections string"""
        if not self.sections:
            return "All Sections"
        return f"Section{'s' if len(self.sections) > 1 else ''}: {', '.join(self.sections)}"
    

class TimetableEntry(models.Model):
    day = models.CharField(max_length=20)
    period = models.IntegerField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, null=True, blank=True)
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, null=True, blank=True)
    class_group = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_practical = models.BooleanField(default=False)
    is_extra_class = models.BooleanField(default=False, help_text="Indicates if this is an extra class (with * suffix)")
    schedule_config = models.ForeignKey(ScheduleConfig, on_delete=models.CASCADE, null=True, blank=True)
    semester = models.CharField(max_length=50, default="Fall 2024")
    academic_year = models.CharField(max_length=20, default="2024-2025")
    created_at = models.DateTimeField(auto_now_add=True)
    # Add department and owner fields for data isolation
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    owner = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['day', 'period']

    def __str__(self):
        return f"{self.day} Period {self.period}: {self.subject} {'(PR)' if self.is_practical else ''} - {self.teacher} - {self.classroom}"


class Department(models.Model):
    """Model to represent different departments"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="Short department code (e.g., SWE, CS, EE)")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class UserDepartment(models.Model):
    """Model to link users with departments"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[
        ('ADMIN', 'Administrator'),
        ('TEACHER', 'Teacher'),
        ('VIEWER', 'Viewer'),
    ], default='TEACHER')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'department']
        ordering = ['department', 'role', 'user__username']

    def __str__(self):
        return f"{self.user.username} - {self.department.name} ({self.role})"


class SharedAccess(models.Model):
    """Model to manage shared access between users"""
    owner = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='shared_by_me')
    shared_with = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='shared_with_me')
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    access_level = models.CharField(max_length=20, choices=[
        ('VIEW', 'View Only'),
        ('COMMENT', 'Comment'),
        ('EDIT', 'Edit'),
    ], default='VIEW')
    shared_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, help_text="Optional notes about this shared access")
    
    # New fields for comprehensive data sharing
    share_subjects = models.BooleanField(default=True, help_text="Share subjects data")
    share_teachers = models.BooleanField(default=True, help_text="Share teachers data")
    share_classrooms = models.BooleanField(default=True, help_text="Share classrooms data")
    share_batches = models.BooleanField(default=True, help_text="Share batches data")
    share_constraints = models.BooleanField(default=True, help_text="Share constraints data")
    share_timetable = models.BooleanField(default=True, help_text="Share generated timetable")

    class Meta:
        unique_together = ['owner', 'shared_with', 'department']
        ordering = ['-shared_at']

    def __str__(self):
        return f"{self.owner.username} → {self.shared_with.username} ({self.department.name} - {self.access_level})"

    def is_expired(self):
        """Check if the shared access has expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def is_valid(self):
        """Check if the shared access is currently valid"""
        return self.is_active and not self.is_expired()