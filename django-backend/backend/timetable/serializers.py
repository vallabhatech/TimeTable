from rest_framework import serializers
from users.models import User
from .models import Subject, Teacher, Classroom, ScheduleConfig, TimetableEntry, Config, ClassGroup, Batch, TeacherSubjectAssignment, Department, UserDepartment
# from users.serializers import UserSerializer
from datetime import datetime
import traceback
from django.db import models



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

class NestedUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__'
    
    def validate_code(self, value):
        """Validate that subject code is not used more than twice"""
        if not value:
            raise serializers.ValidationError("Subject code is required")
        
        # Check if this code is already used more than once
        instance = getattr(self, 'instance', None)
        existing_count = Subject.objects.filter(code__iexact=value).exclude(pk=instance.pk if instance else None).count()
        
        if existing_count >= 2:
            raise serializers.ValidationError(
                f'Subject code "{value}" is already used twice. Maximum allowed is 2 (theory and practical versions).'
            )
        
        return value

class TeacherSerializer(serializers.ModelSerializer):
    # Add read-only fields to display assignments
    subject_names = serializers.SerializerMethodField(read_only=True)
    assignments = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Teacher
        fields = [
            'id',
            'name',
            'subject_names',
            'assignments',
            'max_classes_per_day',
            'unavailable_periods'
        ]

    def validate(self, attrs):
        """Custom validation to check for duplicate teachers"""
        name = attrs.get('name')
        instance = getattr(self, 'instance', None)
        
        # Check for existing teachers with same name
        if name:
            existing_teachers_by_name = Teacher.objects.filter(name=name)
            if instance:
                existing_teachers_by_name = existing_teachers_by_name.exclude(id=instance.id)
            
            if existing_teachers_by_name.exists():
                raise serializers.ValidationError({
                    'detail': 'A teacher with this name already exists.'
                })
        
        return attrs

    def get_subject_names(self, obj):
        """Get subject names from TeacherSubjectAssignment"""
        try:
            assignments = obj.teachersubjectassignment_set.all()
            subjects = set()
            for assignment in assignments:
                subjects.add(assignment.subject.name)
            return list(subjects)
        except:
            return []

    def get_assignments(self, obj):
        """Get detailed assignment information"""
        try:
            assignments = obj.teachersubjectassignment_set.all()
            assignment_list = []
            for assignment in assignments:
                assignment_list.append({
                    'subject': assignment.subject.name,
                    'subject_code': assignment.subject.code,
                    'batch': assignment.batch.name,
                    'sections': assignment.sections or []
                })
            return assignment_list
        except:
            return []
        

class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ['id', 'name', 'building', 'department', 'owner', 'is_lab', 'room_type', 'building_priority']

class ScheduleConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleConfig
        fields = '__all__'

class TimetableEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableEntry
        fields = '__all__'

class TimetableSerializer(serializers.ModelSerializer):
    subject = serializers.StringRelatedField()
    teacher = serializers.StringRelatedField()
    classroom = serializers.StringRelatedField()

    class Meta:
        model = TimetableEntry
        fields = ['day', 'period', 'subject', 'teacher', 'classroom', 'class_group', 'start_time', 'end_time', 'is_practical', 'is_extra_class']

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Handle Thesis entries (no teacher display)
        is_thesis = instance.subject and ('thesis' in instance.subject.name.lower() or
                                        'thesis' in instance.subject.code.lower())

        if is_thesis:
            # For Thesis entries, only show subject name (no teacher)
            data['display_text'] = str(data['subject'])
            data['teacher'] = None  # Don't display teacher for Thesis
            data['teacher_display'] = ""  # Empty teacher display
        else:
            # Format subject name with practical indicator and extra class suffix
            subject_name = str(data['subject'])
            
            # Add * suffix for extra classes
            if instance.is_extra_class:
                subject_name += "*"
            
            # Add practical indicator
            if data['is_practical']:
                data['display_text'] = f"{subject_name} (PR)"
            else:
                data['display_text'] = subject_name

            # Keep teacher display for non-Thesis subjects
            data['teacher_display'] = str(data['teacher']) if data['teacher'] else ""

        # Add room/lab info
        if data['classroom']:
            data['location'] = str(data['classroom'])

        # Format time slot
        start = datetime.strptime(data['start_time'], '%H:%M:%S').strftime('%I:%M')
        end = datetime.strptime(data['end_time'], '%H:%M:%S').strftime('%I:%M')
        data['time_slot'] = f"{start} to {end}"

        return data

class ConfigSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(
        format='%H:%M', 
        input_formats=['%H:%M', '%H:%M:%S'] 
    )
     
    class Meta:
        model = Config
        fields = '__all__'

class ClassGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassGroup
        fields = '__all__'

class BatchSerializer(serializers.ModelSerializer):
    sections = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = '__all__'

    def get_sections(self, obj):
        """Return list of section names for this batch"""
        return obj.get_sections()

class TeacherSubjectAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    sections_display = serializers.CharField(source='get_sections_display', read_only=True)

    class Meta:
        model = TeacherSubjectAssignment
        fields = [
            'id',
            'teacher',
            'teacher_name',
            'subject',
            'subject_name',
            'batch',
            'batch_name',
            'sections',
            'sections_display',
            'created_at'
        ]


class DepartmentSerializer(serializers.ModelSerializer):
    user_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Department
        fields = [
            'id',
            'name',
            'code',
            'description',
            'created_at',
            'is_active',
            'user_count'
        ]
    
    def get_user_count(self, obj):
        """Get the number of users in this department"""
        return obj.userdepartment_set.filter(is_active=True).count()


class UserDepartmentSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    
    class Meta:
        model = UserDepartment
        fields = [
            'id',
            'user',
            'user_username',
            'user_email',
            'user_full_name',
            'department',
            'department_name',
            'department_code',
            'role',
            'joined_at',
            'is_active'
        ]
    
    def get_user_full_name(self, obj):
        """Get the full name of the user"""
        if obj.user.first_name and obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}"
        return obj.user.username



class SubjectDetailsSerializer(serializers.ModelSerializer):
    teachers = serializers.SerializerMethodField()
    credit_hours = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['code', 'name', 'credit_hours', 'teachers']

    def get_teachers(self, obj):
        teachers = Teacher.objects.filter(subjects=obj)
        return [{'name': t.name, 'is_practical': False} for t in teachers]

    def get_credit_hours(self, obj):
        theory = 3 if obj.credits >= 3 else 2
        practical = 1 if obj.is_practical else 0
        return f"{theory}+{practical}"