from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from .models import Subject, Teacher, Classroom, ScheduleConfig, TimetableEntry, Config, ClassGroup, Batch, TeacherSubjectAssignment, Department, UserDepartment
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import ScheduleConfig, TimetableEntry
from celery.result import AsyncResult
from datetime import datetime, timedelta
from rest_framework.permissions import IsAuthenticated
from .algorithms.advanced_scheduler import AdvancedTimetableScheduler
# from .algorithms.working_scheduler import WorkingTimetableScheduler  # Module not found
from .algorithms.final_scheduler import FinalUniversalScheduler
from .algorithms.constraint_enforced_scheduler import ConstraintEnforcedScheduler
from .constraint_manager import ConstraintManager
from .scheduling_orchestrator import get_scheduling_orchestrator
import logging
from typing import Dict, Any
from rest_framework.pagination import PageNumberPagination
from django.core.paginator import Paginator
from rest_framework import status
from django.db import transaction
from django.db.models import Q
from django.db import models
from django.db import IntegrityError

from .serializers import (
    SubjectSerializer,
    TeacherSerializer,
    ClassroomSerializer,
    ScheduleConfigSerializer,
    TimetableEntrySerializer,
    TimetableSerializer,
    ConfigSerializer,
    ClassGroupSerializer,
    BatchSerializer,
    TeacherSubjectAssignmentSerializer,
    DepartmentSerializer,
    UserDepartmentSerializer
)

from .tasks import (
    generate_timetable_async,
    validate_constraints_async,
    optimize_timetable_async,
    generate_timetable_report
)

from .services.cross_semester_conflict_detector import CrossSemesterConflictDetector
# from .constraint_validator import ConstraintValidator  # Using enhanced version

logger = logging.getLogger(__name__)

class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

class ClassroomViewSet(viewsets.ModelViewSet):
    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
    authentication_classes = []  # Temporarily disable authentication for testing

    def create(self, request, *args, **kwargs):
        logger.info(f"Classroom received data: {request.data}")
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Classroom save failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

class ScheduleConfigViewSet(viewsets.ModelViewSet):
    queryset = ScheduleConfig.objects.all()
    serializer_class = ScheduleConfigSerializer
    authentication_classes = []  # Temporarily disable authentication for testing

    def create(self, request, *args, **kwargs):
        logger.info(f"ScheduleConfig received data: {request.data}")
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"ScheduleConfig save failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    authentication_classes = []  # Temporarily disable authentication for testing

class TeacherSubjectAssignmentViewSet(viewsets.ModelViewSet):
    queryset = TeacherSubjectAssignment.objects.all()
    serializer_class = TeacherSubjectAssignmentSerializer
    authentication_classes = []  # Temporarily disable authentication for testing

    def get_queryset(self):
        queryset = TeacherSubjectAssignment.objects.all()
        teacher_id = self.request.query_params.get('teacher', None)
        subject_id = self.request.query_params.get('subject', None)
        batch_id = self.request.query_params.get('batch', None)

        if teacher_id is not None:
            queryset = queryset.filter(teacher_id=teacher_id)
        if subject_id is not None:
            queryset = queryset.filter(subject_id=subject_id)
        if batch_id is not None:
            queryset = queryset.filter(batch_id=batch_id)

        return queryset

    def create(self, request, *args, **kwargs):
        try:
            # Check if this teacher is already assigned to this subject and batch
            teacher_id = request.data.get('teacher')
            subject_id = request.data.get('subject')
            batch_id = request.data.get('batch')
            new_sections = request.data.get('sections', [])
            
            if teacher_id and subject_id and batch_id:
                # Find existing assignments for this teacher-subject-batch combination
                existing_assignments = TeacherSubjectAssignment.objects.filter(
                    teacher_id=teacher_id,
                    subject_id=subject_id,
                    batch_id=batch_id
                )
                
                # Check for section conflicts with existing assignments
                for existing_assignment in existing_assignments:
                    if existing_assignment.sections and new_sections:
                        overlapping_sections = set(existing_assignment.sections) & set(new_sections)
                        if overlapping_sections:
                            return Response(
                                {'error': f'Sections {", ".join(overlapping_sections)} are already assigned to this teacher for {existing_assignment.subject.name} in {existing_assignment.batch.name}'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                
                # Check for conflicts with other teachers' assignments
                other_assignments = TeacherSubjectAssignment.objects.filter(
                    subject_id=subject_id,
                    batch_id=batch_id
                ).exclude(teacher_id=teacher_id)
                
                for other_assignment in other_assignments:
                    if other_assignment.sections and new_sections:
                        overlapping_sections = set(other_assignment.sections) & set(new_sections)
                        if overlapping_sections:
                            return Response(
                                {'error': f'Sections {", ".join(overlapping_sections)} are already assigned to {other_assignment.teacher.name} for {other_assignment.subject.name} in {other_assignment.batch.name}'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
            
            return super().create(request, *args, **kwargs)
        except Exception as e:
            # Handle validation errors and provide user-friendly messages
            error_message = str(e)
            if "already assigned" in error_message.lower():
                return Response(
                    {'error': error_message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif "sections" in error_message.lower() and "assigned" in error_message.lower():
                return Response(
                    {'error': error_message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {'error': f'Failed to create assignment: {error_message}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            error_message = str(e)
            if "already assigned" in error_message.lower():
                return Response(
                    {'error': error_message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif "sections" in error_message.lower() and "assigned" in error_message.lower():
                return Response(
                    {'error': error_message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {'error': f'Failed to update assignment: {error_message}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

class TimetableViewSet(viewsets.ModelViewSet):
    queryset = TimetableEntry.objects.all()
    serializer_class = TimetableEntrySerializer

class FastTimetableView(APIView):
    """
    Very fast timetable generation for immediate results.
    """
    
    def post(self, request):
        try:
            # Get the latest config
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config or not config.start_time:
                return Response(
                    {'error': 'No valid schedule configuration found.'},
                    status=400
                )
            
            # Get subjects, teachers, and classrooms
            subjects = Subject.objects.all()
            teachers = Teacher.objects.all()
            classrooms = Classroom.objects.all()
            
            print(f"Debug: Found {subjects.count()} subjects, {teachers.count()} teachers, {classrooms.count()} classrooms")
            print(f"Debug: Class groups: {config.class_groups}")
            
            if not subjects.exists() or not teachers.exists() or not classrooms.exists():
                return Response(
                    {'error': 'Please populate data first using the data population script.'},
                    status=400
                )
            
            # Clear existing timetable entries
            TimetableEntry.objects.all().delete()
            
            # Create a simple timetable
            entries = []
            class_groups = config.class_groups[:3] if isinstance(config.class_groups, list) else config.class_groups  # Use first 3 class groups for speed
            
            for class_group in class_groups:
                # Get theory and practical subjects
                theory_subjects = subjects.filter(is_practical=False)[:5]  # First 5 theory subjects
                practical_subjects = subjects.filter(is_practical=True)[:3]  # First 3 practical subjects
                
                print(f"Debug: For {class_group}, found {theory_subjects.count()} theory subjects, {practical_subjects.count()} practical subjects")
                
                # Schedule theory subjects
                theory_classrooms = [c for c in classrooms if 'Lab' not in c.name]
                if not theory_classrooms:
                    theory_classrooms = list(classrooms)  # Fallback to all classrooms
                
                for i, subject in enumerate(theory_subjects):
                    teacher = teachers[i % len(teachers)]
                    classroom = theory_classrooms[i % len(theory_classrooms)]
                    
                    entry = TimetableEntry.objects.create(
                        day=config.days[i % len(config.days)],
                        period=(i % 7) + 1,
                        subject=subject,
                        teacher=teacher,
                        classroom=classroom,
                        class_group=class_group,
                        start_time=config.start_time,
                        end_time=config.start_time,
                        is_practical=False
                    )
                    entries.append(entry)
                
                # Schedule practical subjects in 3 consecutive periods
                lab_classrooms = [c for c in classrooms if 'Lab' in c.name]
                if not lab_classrooms:
                    lab_classrooms = list(classrooms)  # Fallback to all classrooms
                
                for i, subject in enumerate(practical_subjects):
                    teacher = teachers[(i + 5) % len(teachers)]
                    lab_classroom = lab_classrooms[i % len(lab_classrooms)]
                    
                    # Create 3 consecutive periods for practical
                    for j in range(3):
                        entry = TimetableEntry.objects.create(
                            day=config.days[(i + 2) % len(config.days)],  # Different day
                            period=j + 1,
                            subject=subject,
                            teacher=teacher,
                            classroom=lab_classroom,
                            class_group=class_group,
                            start_time=config.start_time,
                            end_time=config.start_time,
                            is_practical=True
                        )
                        entries.append(entry)
            
            # Format response
            result = {
                'success': True,
                'message': 'Fast timetable generated successfully',
                'generation_time': 0.5,
                'fitness_score': 85.0,
                'constraint_violations': [],
                'generation': 1,
                'days': config.days,
                'timeSlots': [f"Period {i+1}" for i in range(7)],
                'entries': [{
                    'day': entry.day,
                    'period': entry.period,
                    'subject': f"{entry.subject.name}{' (PR)' if entry.is_practical else ''}",
                    'subject_code': entry.subject.code if entry.subject else '',  # Add subject code
                    'teacher': entry.teacher.name if entry.teacher else '',
                    'classroom': entry.classroom.name if entry.classroom else '',
                    'class_group': entry.class_group,
                    'start_time': entry.start_time.strftime("%H:%M:%S"),
                    'end_time': entry.end_time.strftime("%H:%M:%S"),
                    'is_practical': entry.is_practical,
                    'credits': entry.subject.credits if entry.subject else 0
                } for entry in entries]
            }
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Fast timetable generation error: {str(e)}")
            return Response(
                {'error': f'Failed to generate timetable: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SimpleTimetableView(APIView):
    """
    Simple synchronous timetable generation for faster response.
    """
    
    def post(self, request):
        try:
            # Get the latest config
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config or not config.start_time:
                return Response(
                    {'error': 'No valid schedule configuration found.'},
                    status=400
                )
            
            # Use the FINAL UNIVERSAL scheduler - works with ANY data
            # Create scheduler instance - use CONSTRAINT ENFORCED scheduler
            scheduler = ConstraintEnforcedScheduler(config)

            # Generate timetable synchronously (faster)
            result = scheduler.generate_timetable()
            
            return Response({
                'success': True,
                'message': 'Timetable generated successfully',
                'data': result
            })
            
        except Exception as e:
            logger.error(f"Simple timetable generation error: {str(e)}")
            return Response(
                {'error': f'Failed to generate timetable: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AdvancedTimetableView(APIView):
    """
    Advanced timetable generation with genetic algorithm and constraint satisfaction.
    """
    
    def post(self, request):
        try:
            # Get the latest config
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            print("Loaded config:", config)
            print("Config start_time:", getattr(config, 'start_time', None))
            if not config or not config.start_time:
                return Response(
                    {'error': 'No valid schedule configuration found.'},
                    status=400
                )
            
            # Get constraints from request
            constraints = request.data.get('constraints', [])
            
            # Start async generation
            task = generate_timetable_async.delay(
                config_id=config.id,
                constraints=constraints
            )
            
            return Response({
                'success': True,
                'task_id': task.id,
                'message': 'Timetable generation started. Use task status endpoint to track progress.',
                'status_endpoint': f'/api/timetable/task-status/{task.id}/'
            })
            
        except ScheduleConfig.DoesNotExist:
            return Response(
                {'error': 'No schedule configuration found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Advanced timetable generation error: {str(e)}")
            return Response(
                {'error': f'Failed to start timetable generation: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ConstraintManagementView(APIView):
    """
    Manage scheduling constraints.
    """
    
    def get(self, request):
        try:
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            print("Loaded config:", config)
            print("Config start_time:", getattr(config, 'start_time', None))
            if not config or not config.start_time:
                return Response(
                    {'error': 'No valid schedule configuration found.'},
                    status=400
                )
            constraint_manager = ConstraintManager(config)
            
            return Response(constraint_manager.export_constraints())
            
        except ScheduleConfig.DoesNotExist:
            return Response(
                {'error': 'No schedule configuration found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Constraint management error: {str(e)}")
            return Response(
                {'error': f'Failed to get constraints: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        try:
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            print("Loaded config:", config)
            print("Config start_time:", getattr(config, 'start_time', None))
            if not config or not config.start_time:
                return Response(
                    {'error': 'No valid schedule configuration found.'},
                    status=400
                )
            constraint_manager = ConstraintManager(config)
            
            # Validate constraints
            is_valid = constraint_manager.validate_constraints()
            
            if not is_valid:
                return Response({
                    'success': False,
                    'validation_errors': constraint_manager.validation_errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update config with new constraints
            config.constraints = request.data.get('constraints', [])
            config.save()
            
            return Response({
                'success': True,
                'message': 'Constraints updated successfully',
                'constraint_summary': constraint_manager.get_constraint_summary()
            })
            
        except ScheduleConfig.DoesNotExist:
            return Response(
                {'error': 'No schedule configuration found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Constraint update error: {str(e)}")
            return Response(
                {'error': f'Failed to update constraints: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class OptimizationView(APIView):
    """
    Timetable optimization with multiple parameter sets.
    """
    
    def post(self, request):
        try:
            # Get optimization parameters
            optimization_params = request.data.get('optimization_params', {})
            
            # Start async optimization
            task = optimize_timetable_async.delay(
                optimization_params=optimization_params
            )
            
            return Response({
                'success': True,
                'task_id': task.id,
                'message': 'Timetable optimization started. Use task status endpoint to track progress.',
                'status_endpoint': f'/api/timetable/task-status/{task.id}/'
            })
            
        except Exception as e:
            logger.error(f"Optimization error: {str(e)}")
            return Response(
                {'error': f'Failed to start optimization: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TimetableReportView(APIView):
    """
    Generate comprehensive timetable reports.
    """
    
    def get(self, request):
        try:
            # Start async report generation
            task = generate_timetable_report.delay()
            
            return Response({
                'success': True,
                'task_id': task.id,
                'message': 'Report generation started. Use task status endpoint to get results.',
                'status_endpoint': f'/api/timetable/task-status/{task.id}/'
            })
            
        except Exception as e:
            logger.error(f"Report generation error: {str(e)}")
            return Response(
                {'error': f'Failed to generate report: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TaskStatusView(APIView):
    """
    Get status of async tasks.
    """
    
    def get(self, request, task_id):
        try:
            task = AsyncResult(task_id)
            
            if task.ready():
                result = task.result
                return Response({
                    'status': 'completed',
                    'result': result
                })
            else:
                # Get progress information
                if hasattr(task, 'info'):
                    progress = task.info
                else:
                    progress = {
                        'current': 0,
                        'total': 100,
                        'status': 'Processing...'
                    }
                
                return Response({
                    'status': 'processing',
                    'progress': progress
                })
                
        except Exception as e:
            logger.error(f"Task status error: {str(e)}")
            return Response(
                {'error': f'Failed to get task status: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TimetableView(APIView):
    authentication_classes = []  # Temporarily disable authentication for testing
    
    def get(self, request):
        try:
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            print("Loaded config:", config)
            print("Config start_time:", getattr(config, 'start_time', None))
            if not config or not config.start_time:
                return Response(
                    {'error': 'No valid schedule configuration found.'},
                    status=400
                )
            entries = TimetableEntry.objects.all().order_by('day', 'period')
            
            # Get unique class groups
            class_groups = entries.values_list('class_group', flat=True).distinct()
            
            # Get pagination parameters
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 1))  # Default to 1 timetable per page
            
            timetables = []
            for class_group in class_groups:
                class_entries = entries.filter(class_group=class_group)
                
                # Get all subjects for this class group
                subjects = Subject.objects.filter(
                    id__in=class_entries.values_list('subject', flat=True).distinct()
                )
                
                # Format time slots
                time_slots = []
                current_time = config.start_time
                for i in range(len(config.periods)):
                    end_time = (datetime.combine(datetime.today(), current_time) + 
                              timedelta(minutes=config.class_duration)).time()
                    slot = {
                        'period': i + 1,
                        'display': f"{i+1}{'st' if i==0 else 'nd' if i==1 else 'rd' if i==2 else 'th'} [{current_time.strftime('%I:%M')} to {end_time.strftime('%I:%M')}]"
                    }
                    time_slots.append(slot)
                    current_time = end_time
                
                # Create day-wise entries
                days_data = {}
                for day in config.days:
                    day_entries = class_entries.filter(day=day)
                    rooms = day_entries.values_list('classroom__name', flat=True).distinct()
                    days_data[day] = {
                        'room': next(iter(rooms), ''),
                        'entries': {}
                    }
                    for entry in day_entries:
                        days_data[day]['entries'][entry.period] = {
                            'subject': f"{entry.subject.name}{'(PR)' if entry.is_practical else ''}",
                            'room': entry.classroom.name if entry.classroom else '',
                            'teacher': entry.teacher.name if entry.teacher else ''
                        }
                
                # Get subject details
                subject_details = []
                for subject in subjects:
                    teachers = Teacher.objects.filter(subjects=subject)
                    theory_credits = 3 if subject.credits >= 3 else 2
                    practical_credits = 1 if subject.is_practical else 0
                    
                    subject_details.append({
                        'code': subject.code,
                        'name': subject.name,
                        'credit_hours': f"{theory_credits}+{practical_credits}",
                        'teachers': [t.name for t in teachers]
                    })
                
                timetable_data = {
                    'class_group': class_group,
                    'header': f"TIMETABLE OF {class_group}",
                    'time_slots': time_slots,
                    'days': days_data,
                    'subject_details': subject_details
                }
                
                timetables.append(timetable_data)
            
            # Implement pagination
            paginator = Paginator(timetables, page_size)
            total_pages = paginator.num_pages
            
            try:
                current_page = paginator.page(page)
            except Exception:
                current_page = paginator.page(1)
            
            return Response({
                'days': config.days,
                'timeSlots': time_slots,
                'entries': current_page.object_list,
                'semester': config.semester,
                'academic_year': config.academic_year,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'page_size': page_size,
                    'total_class_groups': len(class_groups),
                    'has_next': paginator.page(page).has_next(),
                    'has_previous': paginator.page(page).has_previous(),
                    'class_groups': class_groups,
                    'current_class_groups': list(class_groups) if not request.query_params.get('class_group') else [request.query_params.get('class_group')]
                }
            })
            
        except ScheduleConfig.DoesNotExist:
            return Response(
                {'error': 'No schedule configuration found'}, 
                status=404
            )
        except Exception as e:
            logger.error(f"Error retrieving timetable: {str(e)}")
            return Response(
                {'error': f'Failed to retrieve timetable: {str(e)}'}, 
                status=500
            )

    def post(self, request):
        try:
            # Get the latest config
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config:
                return Response(
                    {'error': 'No schedule configuration found. Please create a schedule configuration first.'},
                    status=400
                )
            if not config.start_time:
                return Response(
                    {'error': 'Schedule configuration is missing start time. Please update the configuration.'},
                    status=400
                )
            
            # Check if this is a regenerate request
            is_regenerate = request.path.endswith('/regenerate/')
            
            if is_regenerate:
                # For regeneration: Clear ALL existing timetable data first
                print("🔄 REGENERATING TIMETABLE - Clearing all existing data...")
                deleted_count = TimetableEntry.objects.all().delete()[0]
                print(f"🗑️ Deleted {deleted_count} existing timetable entries")
                
                # Get active constraints from the latest config (not from request)
                constraints = getattr(config, 'constraints', [])
                print(f"📋 Using {len(constraints)} constraints from config for regeneration")
            else:
                # For normal generation: Get active constraints from request
                constraints = request.data.get('constraints', [])
                print(f"📋 Using {len(constraints)} constraints from request for generation")
            
            # Update config with the constraints
            config.constraints = constraints
            # Create scheduler instance - use FINAL UNIVERSAL scheduler
            scheduler = FinalUniversalScheduler(config)
            # Generate timetable
            print("🎲 Generating timetable with enhanced randomization...")
            timetable = scheduler.generate_timetable()
            
            # Save entries to database
            entries_to_create = []
            for entry in timetable['entries']:
                # Remove (PR) from subject name if present
                subject_name = entry['subject'].replace(' (PR)', '')

                # Handle teacher assignment (may be None for THESISDAY entries)
                teacher = None
                if entry['teacher'] and entry['teacher'] != 'No Teacher Assigned':
                    try:
                        teacher = Teacher.objects.get(name=entry['teacher'])
                    except Teacher.DoesNotExist:
                        logger.warning(f"Teacher '{entry['teacher']}' not found, setting to None")
                        teacher = None

                # Handle classroom assignment (may be None)
                classroom = None
                if entry['classroom'] and entry['classroom'] != 'No Classroom Assigned':
                    try:
                        classroom = Classroom.objects.get(name=entry['classroom'])
                    except Classroom.DoesNotExist:
                        logger.warning(f"Classroom '{entry['classroom']}' not found, setting to None")
                        classroom = None

                # Handle subject assignment with error handling
                subject = None
                try:
                    # Try to find subject by code first (since _entry_to_dict uses subject.code)
                    subject = Subject.objects.get(code=subject_name)
                except Subject.DoesNotExist:
                    try:
                        # Fallback: try to find by name
                        subject = Subject.objects.get(name=subject_name)
                    except Subject.DoesNotExist:
                        logger.warning(f"Subject '{subject_name}' not found by code or name, skipping entry")
                        continue  # Skip this entry if subject doesn't exist

                entries_to_create.append(TimetableEntry(
                    day=entry['day'],
                    period=entry['period'],
                    subject=subject,
                    teacher=teacher,
                    classroom=classroom,
                    class_group=entry['class_group'],
                    start_time=entry['start_time'],
                    end_time=entry['end_time'],
                    is_practical='(PR)' in entry['subject'],
                    is_extra_class=entry.get('is_extra_class', False),
                    schedule_config=config,
                    semester=config.semester,
                    academic_year=config.academic_year
                ))
            
            # Bulk create entries for better performance
            TimetableEntry.objects.bulk_create(entries_to_create)
            
            # Return success message with appropriate text
            if is_regenerate:
                message = 'Timetable regenerated successfully'
                print(f"✅ Timetable regenerated with {len(entries_to_create)} entries")
            else:
                message = 'Timetable generated successfully'
                print(f"✅ Timetable generated with {len(entries_to_create)} entries")
            
            return Response({
                'message': message,
                'entries_count': len(entries_to_create),
                'regenerated': is_regenerate
            })
            
        except ScheduleConfig.DoesNotExist:
            return Response(
                {'error': 'No schedule configuration found'}, 
                status=404
            )
        except Subject.DoesNotExist as e:
            logger.error(f"Subject not found during timetable generation: {str(e)}")
            return Response(
                {'error': 'Failed to generate timetable: One or more subjects referenced in the schedule do not exist in the database. Please check your subject data.'}, 
                status=400
            )
        except Exception as e:
            logger.error(f"Timetable generation error: {str(e)}")
            return Response(
                {'error': f'Failed to generate timetable: {str(e)}'}, 
                status=500
            )
    

class ConfigViewSet(viewsets.ModelViewSet):
    # permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = Config.objects.all()
    serializer_class = ConfigSerializer

    def create(self, request, *args, **kwargs):
        logger.info(f"Received data: {request.data}")
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Save failed: {str(e)}")
            raise

class ClassRoomViewSet(viewsets.ModelViewSet):
    queryset = ClassGroup.objects.all()
    serializer_class = ClassGroupSerializer


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    # permission_classes = [IsAuthenticated]
    filterset_fields = ['code', 'name']

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search)
            )
        return queryset
    
class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    # permission_classes = [IsAuthenticated]
    filterset_fields = ['name', 'email']

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError as e:
            # Handle unique constraint violations specifically
            error_message = str(e)
            
            # Check which field caused the violation
            if "email" in error_message.lower():
                return Response(
                    {'detail': 'A teacher with this email already exists.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif "name" in error_message.lower():
                return Response(
                    {'detail': 'A teacher with this name already exists.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {'detail': 'Teacher already exists with this information.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            # Handle other types of errors
            error_message = str(e)
            return Response(
                {'detail': f'Failed to create teacher: {error_message}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except IntegrityError as e:
            # Handle unique constraint violations specifically
            error_message = str(e)
            
            # Check which field caused the violation
            if "email" in error_message.lower():
                return Response(
                    {'detail': 'A teacher with this email already exists.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif "name" in error_message.lower():
                return Response(
                    {'detail': 'A teacher with this name already exists.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {'detail': 'Teacher already exists with this information.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            # Handle other types of errors
            error_message = str(e)
            return Response(
                {'detail': f'Failed to update teacher: {error_message}'},
                status=status.HTTP_400_BAD_REQUEST
            )

class LatestTimetableView(APIView):
    authentication_classes = []  # Temporarily disable authentication for testing
    
    def get(self, request):
        try:
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config or not config.start_time:
                return Response(
                    {'error': 'No valid schedule configuration found.'},
                    status=400
                )

            # Get pagination parameters
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))
            class_group_filter = request.query_params.get('class_group', None)

            # Get all entries
            entries_query = TimetableEntry.objects.all().order_by('day', 'period')

            # Filter by class group if specified
            if class_group_filter:
                entries_query = entries_query.filter(class_group=class_group_filter)

            # Get unique class groups for pagination info
            all_class_groups = list(TimetableEntry.objects.values_list('class_group', flat=True).distinct())
            total_class_groups = len(all_class_groups)
            
            # Get batch information for better descriptions
            batch_info = {}
            try:
                from .models import Batch
                for class_group in all_class_groups:
                    if '-' in class_group:
                        batch_name = class_group.split('-')[0]
                        batch_obj = Batch.objects.filter(name=batch_name).first()
                        if batch_obj:
                            batch_info[batch_name] = {
                                'description': batch_obj.description,
                                'semester_number': batch_obj.semester_number,
                                'academic_year': batch_obj.academic_year,
                                'class_advisor': getattr(batch_obj, 'class_advisor', '')
                            }
            except Exception as e:
                print(f"Warning: Could not fetch batch info: {e}")
                batch_info = {}

            # If no specific class group requested, paginate by class groups
            if not class_group_filter:
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                paginated_class_groups = all_class_groups[start_idx:end_idx]
                entries_query = entries_query.filter(class_group__in=paginated_class_groups)

            entries = list(entries_query)

            # Format time slots
            time_slots = []
            current_time = config.start_time
            for i in range(len(config.periods)):
                end_time = (datetime.combine(datetime.today(), current_time) +
                          timedelta(minutes=config.class_duration)).time()
                time_slots.append(f"{current_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}")
                current_time = end_time

            # Format entries
            formatted_entries = []
            for entry in entries:
                # Format subject name with practical indicator and extra class suffix
                subject_name = entry.subject.name if entry.subject else ''
                if entry.is_extra_class:
                    subject_name += "*"
                if entry.is_practical:
                    subject_name += " (PR)"
                
                formatted_entries.append({
                    'id': entry.id,
                    'day': entry.day,
                    'period': entry.period,
                    'subject': subject_name,
                    'subject_code': entry.subject.code if entry.subject else '',  # Use actual subject code
                    'subject_short_name': entry.subject.subject_short_name if entry.subject and entry.subject.subject_short_name else '',
                    'teacher': entry.teacher.name if entry.teacher else '',
                    'classroom': entry.classroom.name if entry.classroom else '',
                    'class_group': entry.class_group,
                    'start_time': entry.start_time.strftime("%H:%M:%S"),
                    'end_time': entry.end_time.strftime("%H:%M:%S"),
                    'is_practical': entry.is_practical,
                    'is_extra_class': entry.is_extra_class,
                    'credits': entry.subject.credits if entry.subject else 0
                })

            # Calculate pagination info
            total_pages = (total_class_groups + page_size - 1) // page_size if not class_group_filter else 1
            has_next = page < total_pages
            has_previous = page > 1

            return Response({
                'days': config.days,
                'timeSlots': time_slots,
                'entries': formatted_entries,
                'semester': config.semester,
                'academic_year': config.academic_year,
                'batch_info': batch_info,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'page_size': page_size,
                    'total_class_groups': total_class_groups,
                    'has_next': has_next,
                    'has_previous': has_previous,
                    'class_groups': all_class_groups,
                    'current_class_groups': paginated_class_groups if not class_group_filter else [class_group_filter]
                }
            })
            
        except ScheduleConfig.DoesNotExist:
            return Response(
                {'error': 'No schedule configuration found'}, 
                status=404
            )
        except Exception as e:
            logger.error(f"Error retrieving latest timetable: {str(e)}")
            return Response(
                {'error': f'Failed to retrieve latest timetable: {str(e)}'},
                status=500
            )


class CrossSemesterConflictView(APIView):
    """
    API endpoint for checking cross-semester conflicts
    """

    def get(self, request):
        """Get cross-semester conflict summary"""
        try:
            # Get the latest config
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config:
                return Response(
                    {'error': 'No schedule configuration found.'},
                    status=400
                )

            # Initialize conflict detector
            conflict_detector = CrossSemesterConflictDetector(config)

            # Get conflict summary
            summary = conflict_detector.get_conflict_summary()

            return Response({
                'success': True,
                'current_semester': config.semester,
                'current_academic_year': config.academic_year,
                'conflict_summary': summary
            })

        except Exception as e:
            logger.error(f"Cross-semester conflict check error: {str(e)}")
            return Response(
                {'error': f'Failed to check cross-semester conflicts: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Check conflicts for specific teacher and time slot"""
        try:
            teacher_id = request.data.get('teacher_id')
            day = request.data.get('day')
            period = request.data.get('period')

            if not all([teacher_id, day, period]):
                return Response(
                    {'error': 'teacher_id, day, and period are required'},
                    status=400
                )

            # Get the latest config
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config:
                return Response(
                    {'error': 'No schedule configuration found.'},
                    status=400
                )

            # Initialize conflict detector
            conflict_detector = CrossSemesterConflictDetector(config)

            # Check specific conflict
            has_conflict, conflict_descriptions = conflict_detector.check_teacher_conflict(
                teacher_id, day, period
            )

            # Get alternative suggestions if there's a conflict
            suggestions = []
            if has_conflict:
                suggestions = conflict_detector.suggest_alternative_slots(teacher_id, day)

            return Response({
                'success': True,
                'has_conflict': has_conflict,
                'conflicts': conflict_descriptions,
                'alternative_suggestions': suggestions
            })

        except Exception as e:
            logger.error(f"Specific conflict check error: {str(e)}")
            return Response(
                {'error': f'Failed to check specific conflict: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConstraintTestingView(APIView):
    """
    Comprehensive constraint testing interface for validating timetable constraints.
    Provides detailed analysis for each constraint type.
    """

    def get(self, request):
        """Get detailed constraint analysis for all constraints"""
        try:
            # Get all timetable entries
            entries = TimetableEntry.objects.all()

            if not entries.exists():
                return Response({
                    'success': False,
                    'error': 'No timetable entries found. Please generate a timetable first.'
                })

            # Initialize constraint validator
            from .enhanced_constraint_validator import EnhancedConstraintValidator
            validator = EnhancedConstraintValidator()

            # Run comprehensive validation
            validation_results = validator.validate_all_constraints(list(entries))

            # Get detailed constraint analysis
            constraint_analysis = self._get_detailed_constraint_analysis(entries)

            return Response({
                'success': True,
                'validation_results': validation_results,
                'constraint_analysis': constraint_analysis,
                'total_entries': entries.count(),
                'total_violations': validation_results['total_violations'],
                'overall_compliance': validation_results['overall_compliance']
            })

        except Exception as e:
            logger.error(f"Constraint testing failed: {str(e)}")
            return Response(
                {'error': f'Constraint testing failed: {str(e)}'},
                status=500
            )

    def post(self, request):
        """Get detailed analysis for a specific constraint type"""
        try:
            constraint_type = request.data.get('constraint_type')

            if not constraint_type:
                return Response(
                    {'error': 'constraint_type is required'},
                    status=400
                )

            # For cross-semester analysis, get ALL entries across all semesters
            if constraint_type == 'cross_semester_conflicts':
                entries = TimetableEntry.objects.all()  # All semesters
            else:
                # For other constraints, get current semester entries
                entries = TimetableEntry.objects.all()

            if not entries.exists():
                return Response({
                    'success': False,
                    'error': 'No timetable entries found. Please generate a timetable first.'
                })

            # Get specific constraint analysis
            analysis = self._get_specific_constraint_analysis(entries, constraint_type)

            return Response({
                'success': True,
                'constraint_type': constraint_type,
                'analysis': analysis,
                'total_entries_analyzed': entries.count()
            })

        except Exception as e:
            logger.error(f"Specific constraint testing failed: {str(e)}")
            return Response(
                {'error': f'Specific constraint testing failed: {str(e)}'},
                status=500
            )

    def _get_detailed_constraint_analysis(self, entries):
        """Get detailed analysis for all constraints"""
        analysis = {}

        # Cross-semester conflicts
        analysis['cross_semester_conflicts'] = self._analyze_cross_semester_conflicts(entries)

        # Subject frequency
        analysis['subject_frequency'] = self._analyze_subject_frequency(entries)

        # Teacher conflicts
        analysis['teacher_conflicts'] = self._analyze_teacher_conflicts(entries)

        # Room conflicts
        analysis['room_conflicts'] = self._analyze_room_conflicts(entries)

        # Practical blocks
        analysis['practical_blocks'] = self._analyze_practical_blocks(entries)

        # Friday time limits
        analysis['friday_time_limits'] = self._analyze_friday_time_limits(entries)

        # Thesis day constraint
        analysis['thesis_day_constraint'] = self._analyze_thesis_day_constraint(entries)

        # Teacher assignments
        analysis['teacher_assignments'] = self._analyze_teacher_assignments(entries)

        # Minimum daily classes
        analysis['minimum_daily_classes'] = self._analyze_minimum_daily_classes(entries)

        # Compact scheduling
        analysis['compact_scheduling'] = self._analyze_compact_scheduling(entries)

        # Friday-aware scheduling
        analysis['friday_aware_scheduling'] = self._analyze_friday_aware_scheduling(entries)

        # Room allocation constraints
        analysis['room_double_booking'] = self._analyze_room_double_booking(entries)
        analysis['practical_same_lab'] = self._analyze_practical_same_lab(entries)
        analysis['practical_in_labs_only'] = self._analyze_practical_in_labs_only(entries)
        analysis['theory_room_consistency'] = self._analyze_theory_room_consistency(entries)
        analysis['section_simultaneous_classes'] = self._analyze_section_simultaneous_classes(entries)
        analysis['working_hours_compliance'] = self._analyze_working_hours_compliance(entries)
        analysis['max_theory_per_day'] = self._analyze_max_theory_per_day(entries)

        return analysis

    def _get_specific_constraint_analysis(self, entries, constraint_type):
        """Get detailed analysis for a specific constraint"""
        analysis_methods = {
            'cross_semester_conflicts': self._analyze_cross_semester_conflicts,
            'subject_frequency': self._analyze_subject_frequency,
            'teacher_conflicts': self._analyze_teacher_conflicts,
            'room_conflicts': self._analyze_room_conflicts,
            'practical_blocks': self._analyze_practical_blocks,
            'friday_time_limits': self._analyze_friday_time_limits,
            'thesis_day_constraint': self._analyze_thesis_day_constraint,
            'teacher_assignments': self._analyze_teacher_assignments,
            'minimum_daily_classes': self._analyze_minimum_daily_classes,
            'compact_scheduling': self._analyze_compact_scheduling,
            'friday_aware_scheduling': self._analyze_friday_aware_scheduling,
            # Room allocation constraints
            'room_double_booking': self._analyze_room_double_booking,
            'practical_same_lab': self._analyze_practical_same_lab,
            'practical_in_labs_only': self._analyze_practical_in_labs_only,
            'theory_room_consistency': self._analyze_theory_room_consistency,
            'section_simultaneous_classes': self._analyze_section_simultaneous_classes,
            'working_hours_compliance': self._analyze_working_hours_compliance,
            'max_theory_per_day': self._analyze_max_theory_per_day,
        }

        if constraint_type in analysis_methods:
            return analysis_methods[constraint_type](entries)
        else:
            return {'error': f'Unknown constraint type: {constraint_type}'}

    def _analyze_cross_semester_conflicts(self, entries):
        """Analyze cross-semester conflicts in detail with teacher-based grouping"""
        try:
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config:
                return {'error': 'No schedule configuration found'}

            conflict_detector = CrossSemesterConflictDetector(config)
            conflicts = []
            teacher_schedules = {}

            # Group all entries by teacher to get complete picture
            for entry in entries:
                if entry.teacher:
                    teacher_name = entry.teacher.name
                    if teacher_name not in teacher_schedules:
                        teacher_schedules[teacher_name] = {
                            'teacher_id': entry.teacher.id,
                            'teacher_name': teacher_name,
                            'subjects': set(),
                            'sections': set(),
                            'schedule': [],
                            'rooms': set(),
                            'semesters': set(),
                            'conflicts': []
                        }

                    teacher_data = teacher_schedules[teacher_name]
                    teacher_data['subjects'].add(entry.subject.name if entry.subject else 'N/A')
                    teacher_data['sections'].add(entry.class_group)
                    teacher_data['rooms'].add(entry.classroom.name if entry.classroom else 'N/A')
                    teacher_data['semesters'].add(entry.semester)

                    # Add schedule entry
                    schedule_entry = {
                        'day': entry.day,
                        'period': entry.period,
                        'time': f"{entry.start_time} - {entry.end_time}",
                        'subject': entry.subject.name if entry.subject else 'N/A',
                        'section': entry.class_group,
                        'room': entry.classroom.name if entry.classroom else 'N/A',
                        'semester': entry.semester,
                        'academic_year': entry.academic_year
                    }
                    teacher_data['schedule'].append(schedule_entry)

                    # Check for conflicts
                    has_conflict, conflict_descriptions = conflict_detector.check_teacher_conflict(
                        entry.teacher.id, entry.day, entry.period
                    )

                    if has_conflict:
                        conflict_info = {
                            'entry_id': entry.id,
                            'teacher': teacher_name,
                            'subject': entry.subject.name if entry.subject else 'N/A',
                            'class_group': entry.class_group,
                            'day': entry.day,
                            'period': entry.period,
                            'time': f"{entry.start_time} - {entry.end_time}",
                            'room': entry.classroom.name if entry.classroom else 'N/A',
                            'conflicts': conflict_descriptions
                        }
                        conflicts.append(conflict_info)
                        teacher_data['conflicts'].append(conflict_info)

            # Convert sets to lists for JSON serialization
            for teacher_name, data in teacher_schedules.items():
                data['subjects'] = list(data['subjects'])
                data['sections'] = list(data['sections'])
                data['rooms'] = list(data['rooms'])
                data['semesters'] = list(data['semesters'])

                # Sort schedule by day and period
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                data['schedule'].sort(key=lambda x: (day_order.index(x['day']) if x['day'] in day_order else 999, x['period']))

            return {
                'total_conflicts': len(conflicts),
                'conflicts': conflicts,
                'teacher_schedules': teacher_schedules,
                'total_teachers': len(teacher_schedules),
                'status': 'PASS' if len(conflicts) == 0 else 'FAIL'
            }

        except Exception as e:
            return {'error': f'Cross-semester analysis failed: {str(e)}'}

    def _analyze_subject_frequency(self, entries):
        """Analyze subject frequency constraints - checks entire timetable data"""
        from collections import defaultdict
        from timetable.models import TeacherSubjectAssignment

        # Group by class_group and subject
        class_subject_counts = defaultdict(lambda: defaultdict(int))
        class_practical_sessions = defaultdict(lambda: defaultdict(int))
        subject_details = defaultdict(list)

        # Get all class groups from entries
        all_class_groups = set(entry.class_group for entry in entries)

        for entry in entries:
            if entry.subject:
                class_group = entry.class_group
                subject_code = entry.subject.code

                # For practical subjects, count sessions (not individual blocks)
                if entry.subject.is_practical:
                    # Group practical entries by day to count sessions
                    class_practical_sessions[class_group][subject_code] += 1
                else:
                    # For theory subjects, count individual classes
                    class_subject_counts[class_group][subject_code] += 1

                subject_details[f"{class_group}-{subject_code}"].append({
                    'day': entry.day,
                    'period': entry.period,
                    'time': f"{entry.start_time} - {entry.end_time}",
                    'teacher': entry.teacher.name if entry.teacher else 'N/A',
                    'classroom': entry.classroom.name if entry.classroom else 'N/A'
                })

        # Get all subjects that should be scheduled for each class group
        expected_subjects = defaultdict(set)
        for assignment in TeacherSubjectAssignment.objects.all():
            for section in assignment.sections:
                for class_group in all_class_groups:
                    if section in class_group:
                        expected_subjects[class_group].add(assignment.subject.code)

        violations = []
        compliant_subjects = []

        # Check all expected subjects for each class group
        for class_group in all_class_groups:
            # Check theory subjects that are scheduled
            if class_group in class_subject_counts:
                for subject_code, actual_count in class_subject_counts[class_group].items():
                    try:
                        subject = Subject.objects.get(code=subject_code)
                        expected_count = subject.credits

                        subject_info = {
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'subject_name': subject.name,
                            'expected_count': expected_count,
                            'actual_count': actual_count,
                            'is_practical': subject.is_practical,
                            'schedule_details': subject_details[f"{class_group}-{subject_code}"]
                        }

                        if actual_count != expected_count:
                            subject_info['violation_type'] = 'frequency_mismatch'
                            violations.append(subject_info)
                        else:
                            compliant_subjects.append(subject_info)

                    except Subject.DoesNotExist:
                        violations.append({
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'violation_type': 'subject_not_found',
                            'schedule_details': subject_details[f"{class_group}-{subject_code}"]
                        })

            # Check for missing theory subjects
            for subject_code in expected_subjects[class_group]:
                try:
                    subject = Subject.objects.get(code=subject_code)
                    if not subject.is_practical:  # Only check theory subjects here
                        if subject_code not in class_subject_counts[class_group]:
                            violations.append({
                                'class_group': class_group,
                                'subject_code': subject_code,
                                'subject_name': subject.name,
                                'expected_count': subject.credits,
                                'actual_count': 0,
                                'is_practical': subject.is_practical,
                                'violation_type': 'missing_subject',
                                'schedule_details': []
                            })
                except Subject.DoesNotExist:
                    pass

        # Check practical subjects (count sessions, not blocks)
        for class_group in all_class_groups:
            # Check practical subjects that are scheduled
            if class_group in class_practical_sessions:
                for subject_code, actual_sessions in class_practical_sessions[class_group].items():
                    try:
                        subject = Subject.objects.get(code=subject_code)
                        expected_sessions = 1  # Practical subjects: 1 session per week (3 consecutive blocks)

                        # Count actual sessions by grouping blocks by day
                        practical_details = subject_details[f"{class_group}-{subject_code}"]
                        days_with_practical = set(detail['day'] for detail in practical_details)
                        actual_sessions = len(days_with_practical)

                        subject_info = {
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'subject_name': subject.name,
                            'expected_count': expected_sessions,
                            'actual_count': actual_sessions,
                            'is_practical': subject.is_practical,
                            'schedule_details': practical_details
                        }

                        if actual_sessions != expected_sessions:
                            subject_info['violation_type'] = 'practical_session_mismatch'
                            violations.append(subject_info)
                        else:
                            compliant_subjects.append(subject_info)

                    except Subject.DoesNotExist:
                        violations.append({
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'violation_type': 'subject_not_found',
                            'schedule_details': subject_details[f"{class_group}-{subject_code}"]
                        })

            # Check for missing practical subjects
            for subject_code in expected_subjects[class_group]:
                try:
                    subject = Subject.objects.get(code=subject_code)
                    if subject.is_practical:  # Only check practical subjects here
                        if subject_code not in class_practical_sessions[class_group]:
                            violations.append({
                                'class_group': class_group,
                                'subject_code': subject_code,
                                'subject_name': subject.name,
                                'expected_count': 1,
                                'actual_count': 0,
                                'is_practical': subject.is_practical,
                                'violation_type': 'missing_practical_subject',
                                'schedule_details': []
                            })
                except Subject.DoesNotExist:
                    pass

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_subjects': compliant_subjects,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_teacher_conflicts(self, entries):
        """Analyze teacher conflicts (same teacher in multiple places at same time)"""
        from collections import defaultdict

        # Group by day and period
        time_slot_teachers = defaultdict(list)

        for entry in entries:
            if entry.teacher:
                key = f"{entry.day}-{entry.period}"
                time_slot_teachers[key].append({
                    'teacher_id': entry.teacher.id,
                    'teacher_name': entry.teacher.name,
                    'subject': entry.subject.name if entry.subject else 'N/A',
                    'class_group': entry.class_group,
                    'classroom': entry.classroom.name if entry.classroom else 'N/A',
                    'time': f"{entry.start_time} - {entry.end_time}"
                })

        conflicts = []

        for time_slot, teacher_entries in time_slot_teachers.items():
            # Group by teacher
            teacher_groups = defaultdict(list)
            for entry in teacher_entries:
                teacher_groups[entry['teacher_id']].append(entry)

            # Check for conflicts (same teacher in multiple places)
            for teacher_id, teacher_entries_list in teacher_groups.items():
                if len(teacher_entries_list) > 1:
                    day, period = time_slot.split('-')
                    conflicts.append({
                        'day': day,
                        'period': int(period),
                        'teacher_id': teacher_id,
                        'teacher_name': teacher_entries_list[0]['teacher_name'],
                        'conflicting_assignments': teacher_entries_list,
                        'conflict_count': len(teacher_entries_list)
                    })

        return {
            'total_conflicts': len(conflicts),
            'conflicts': conflicts,
            'status': 'PASS' if len(conflicts) == 0 else 'FAIL'
        }

    def _analyze_room_conflicts(self, entries):
        """Analyze room conflicts (same room assigned to multiple classes at same time)"""
        from collections import defaultdict

        conflicts = []

        # Group by day-period to find room conflicts
        day_period_rooms = defaultdict(lambda: defaultdict(list))

        for entry in entries:
            if entry.classroom:
                day_period_key = f"{entry.day}-{entry.period}"
                room_id = entry.classroom.id
                day_period_rooms[day_period_key][room_id].append({
                    'entry_id': entry.id,
                    'classroom_name': entry.classroom.name,
                    'subject': entry.subject.name if entry.subject else 'N/A',
                    'teacher': entry.teacher.name if entry.teacher else 'N/A',
                    'class_group': entry.class_group,
                    'time': f"{entry.start_time} - {entry.end_time}"
                })

        print(f"Analyzing room conflicts for {len(entries)} entries")

        for day_period, rooms in day_period_rooms.items():
            for room_id, room_entries in rooms.items():
                if len(room_entries) > 1:
                    day, period = day_period.split('-')
                    conflict_info = {
                        'day': day,
                        'period': int(period),
                        'classroom_id': room_id,
                        'classroom_name': room_entries[0]['classroom_name'],
                        'conflicting_assignments': room_entries,
                        'conflict_count': len(room_entries)
                    }
                    conflicts.append(conflict_info)
                    print(f"Found room conflict: {room_entries[0]['classroom_name']} on {day} P{period} - {len(room_entries)} assignments")

        print(f"Total room conflicts found: {len(conflicts)}")

        return {
            'total_conflicts': len(conflicts),
            'conflicts': conflicts,
            'status': 'PASS' if len(conflicts) == 0 else 'FAIL'
        }

    def _analyze_practical_in_labs_only(self, entries):
        """Analyze if practical subjects are only in labs"""
        violations = []

        for entry in entries:
            if (entry.subject and entry.subject.is_practical and
                entry.classroom and not entry.classroom.is_lab):
                violations.append({
                    'class_group': entry.class_group,
                    'subject': entry.subject.code,
                    'classroom': entry.classroom.name,
                    'day': entry.day,
                    'period': entry.period,
                    'description': f'Practical {entry.subject.code} in non-lab room {entry.classroom.name}'
                })

        return {
            'status': 'PASS' if len(violations) == 0 else 'FAIL',
            'total_violations': len(violations),
            'violations': violations,
            'message': f'Found {len(violations)} practical subjects not in labs'
        }

    def _analyze_theory_room_consistency(self, entries):
        """Analyze theory room consistency violations"""
        from collections import defaultdict

        violations = []
        section_daily_rooms = defaultdict(lambda: defaultdict(set))

        # Track rooms used by each section on each day for theory classes
        for entry in entries:
            if entry.subject and not entry.subject.is_practical and entry.classroom:
                section_daily_rooms[entry.class_group][entry.day].add(entry.classroom.name)

        # Check for inconsistencies
        for class_group, daily_rooms in section_daily_rooms.items():
            for day, rooms in daily_rooms.items():
                if len(rooms) > 1:
                    violations.append({
                        'class_group': class_group,
                        'day': day,
                        'rooms_used': list(rooms),
                        'description': f'{class_group} uses multiple rooms on {day}: {", ".join(rooms)}'
                    })

        return {
            'status': 'PASS' if len(violations) == 0 else 'FAIL',
            'total_violations': len(violations),
            'violations': violations,
            'message': f'Found {len(violations)} room consistency violations'
        }

    def _analyze_section_simultaneous_classes(self, entries):
        """Analyze sections with simultaneous classes"""
        from collections import defaultdict

        violations = []
        time_slot_sections = defaultdict(list)

        # Group entries by time slot
        for entry in entries:
            key = (entry.day, entry.period)
            time_slot_sections[key].append(entry)

        # Check for sections with multiple classes at same time
        for (day, period), slot_entries in time_slot_sections.items():
            section_counts = defaultdict(int)
            for entry in slot_entries:
                section_counts[entry.class_group] += 1

            for class_group, count in section_counts.items():
                if count > 1:
                    violations.append({
                        'class_group': class_group,
                        'day': day,
                        'period': period,
                        'simultaneous_classes': count,
                        'description': f'{class_group} has {count} simultaneous classes on {day} P{period}'
                    })

        return {
            'status': 'PASS' if len(violations) == 0 else 'FAIL',
            'total_violations': len(violations),
            'violations': violations,
            'message': f'Found {len(violations)} simultaneous class violations'
        }

    def _analyze_working_hours_compliance(self, entries):
        """Analyze working hours compliance (8AM-3PM)"""
        violations = []

        for entry in entries:
            if entry.start_time and entry.end_time:
                # Handle both string and time object formats
                if isinstance(entry.start_time, str):
                    start_hour = int(entry.start_time.split(':')[0])
                else:
                    start_hour = entry.start_time.hour

                if isinstance(entry.end_time, str):
                    end_hour = int(entry.end_time.split(':')[0])
                else:
                    end_hour = entry.end_time.hour

                if start_hour < 8 or end_hour > 15:
                    violations.append({
                        'class_group': entry.class_group,
                        'subject': entry.subject.code if entry.subject else 'Unknown',
                        'day': entry.day,
                        'period': entry.period,
                        'start_time': str(entry.start_time),
                        'end_time': str(entry.end_time),
                        'description': f'Class {entry.start_time}-{entry.end_time} outside 8AM-3PM'
                    })

        return {
            'status': 'PASS' if len(violations) == 0 else 'FAIL',
            'total_violations': len(violations),
            'violations': violations,
            'message': f'Found {len(violations)} working hours violations'
        }

    def _analyze_max_theory_per_day(self, entries):
        """Analyze maximum one theory class per day constraint"""
        from collections import defaultdict

        violations = []
        section_daily_theory = defaultdict(lambda: defaultdict(list))

        # Count theory classes per section per day
        for entry in entries:
            if entry.subject and not entry.subject.is_practical:
                section_daily_theory[entry.class_group][entry.day].append(entry)

        # Check for violations (more than 1 theory class per day)
        for class_group, daily_classes in section_daily_theory.items():
            for day, theory_classes in daily_classes.items():
                if len(theory_classes) > 1:
                    violations.append({
                        'class_group': class_group,
                        'day': day,
                        'theory_count': len(theory_classes),
                        'subjects': [e.subject.code for e in theory_classes],
                        'description': f'{class_group} has {len(theory_classes)} theory classes on {day}'
                    })

        return {
            'status': 'PASS' if len(violations) == 0 else 'FAIL',
            'total_violations': len(violations),
            'violations': violations,
            'message': f'Found {len(violations)} multiple theory per day violations'
        }

    def _analyze_practical_blocks(self, entries):
        """Analyze practical block constraints (3-hour consecutive blocks)"""
        from collections import defaultdict

        # Group practical entries by class_group and subject
        practical_groups = defaultdict(lambda: defaultdict(list))

        for entry in entries:
            if entry.is_practical and entry.subject:
                practical_groups[entry.class_group][entry.subject.code].append({
                    'day': entry.day,
                    'period': entry.period,
                    'subject': entry.subject.name,
                    'teacher': entry.teacher.name if entry.teacher else 'N/A',
                    'classroom': entry.classroom.name if entry.classroom else 'N/A',
                    'time': f"{entry.start_time} - {entry.end_time}"
                })

        violations = []
        compliant_blocks = []

        for class_group, subjects in practical_groups.items():
            for subject_code, practical_entries in subjects.items():
                # Group by day to check for consecutive blocks
                day_groups = defaultdict(list)
                for entry in practical_entries:
                    day_groups[entry['day']].append(entry)

                for day, day_entries in day_groups.items():
                    # Sort by period
                    day_entries.sort(key=lambda x: x['period'])

                    # Check if periods are consecutive and total 3 hours
                    if len(day_entries) >= 3:
                        periods = [entry['period'] for entry in day_entries]
                        is_consecutive = all(periods[i] + 1 == periods[i + 1] for i in range(len(periods) - 1))

                        block_info = {
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'subject_name': day_entries[0]['subject'],
                            'day': day,
                            'periods': periods,
                            'entries': day_entries,
                            'is_consecutive': is_consecutive,
                            'block_length': len(day_entries)
                        }

                        if is_consecutive and len(day_entries) == 3:
                            compliant_blocks.append(block_info)
                        else:
                            block_info['violation_type'] = 'invalid_block_structure'
                            violations.append(block_info)
                    else:
                        violations.append({
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'subject_name': day_entries[0]['subject'],
                            'day': day,
                            'periods': [entry['period'] for entry in day_entries],
                            'entries': day_entries,
                            'violation_type': 'insufficient_block_length',
                            'block_length': len(day_entries)
                        })

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_blocks': compliant_blocks,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_friday_time_limits(self, entries):
        """Analyze Friday time limit constraints"""
        friday_entries = [entry for entry in entries if entry.day.upper() == 'FRIDAY']
        violations = []
        compliant_entries = []

        for entry in friday_entries:
            has_practical = any(e.is_practical for e in friday_entries if e.class_group == entry.class_group)

            # Friday limits: 12:00/1:00 PM with practical, 11:00 AM without practical
            if has_practical:
                # Allow until period 4 (1:00 PM) if there are practicals
                max_period = 4
                limit_description = "1:00 PM (with practicals)"
            else:
                # Allow until period 3 (11:00 AM) if no practicals
                max_period = 3
                limit_description = "11:00 AM (no practicals)"

            entry_info = {
                'class_group': entry.class_group,
                'subject': entry.subject.name if entry.subject else 'N/A',
                'teacher': entry.teacher.name if entry.teacher else 'N/A',
                'period': entry.period,
                'time': f"{entry.start_time} - {entry.end_time}",
                'is_practical': entry.is_practical,
                'has_practical_in_class': has_practical,
                'limit_description': limit_description,
                'max_allowed_period': max_period
            }

            if entry.period > max_period:
                entry_info['violation_type'] = 'exceeds_friday_limit'
                violations.append(entry_info)
            else:
                compliant_entries.append(entry_info)

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_entries': compliant_entries,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_thesis_day_constraint(self, entries):
        """Analyze thesis day constraint (Wednesday exclusive for thesis)"""
        wednesday_entries = [entry for entry in entries if entry.day.upper() == 'WEDNESDAY']
        violations = []
        compliant_entries = []

        # Group by class_group
        from collections import defaultdict
        class_groups = defaultdict(list)

        for entry in wednesday_entries:
            class_groups[entry.class_group].append(entry)

        for class_group, group_entries in class_groups.items():
            has_thesis = any(
                entry.subject and ('thesis' in entry.subject.name.lower() or 'thesis' in entry.subject.code.lower())
                for entry in group_entries
            )

            if has_thesis:
                # If class has thesis, Wednesday should be exclusive for thesis
                for entry in group_entries:
                    is_thesis_subject = (
                        entry.subject and
                        ('thesis' in entry.subject.name.lower() or 'thesis' in entry.subject.code.lower())
                    )

                    entry_info = {
                        'class_group': class_group,
                        'subject': entry.subject.name if entry.subject else 'N/A',
                        'teacher': entry.teacher.name if entry.teacher else 'N/A',
                        'period': entry.period,
                        'time': f"{entry.start_time} - {entry.end_time}",
                        'is_thesis_subject': is_thesis_subject,
                        'class_has_thesis': has_thesis
                    }

                    if not is_thesis_subject:
                        entry_info['violation_type'] = 'non_thesis_on_thesis_day'
                        violations.append(entry_info)
                    else:
                        compliant_entries.append(entry_info)
            else:
                # If no thesis, any subject is allowed on Wednesday
                for entry in group_entries:
                    compliant_entries.append({
                        'class_group': class_group,
                        'subject': entry.subject.name if entry.subject else 'N/A',
                        'teacher': entry.teacher.name if entry.teacher else 'N/A',
                        'period': entry.period,
                        'time': f"{entry.start_time} - {entry.end_time}",
                        'is_thesis_subject': False,
                        'class_has_thesis': False
                    })

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_entries': compliant_entries,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_teacher_assignments(self, entries):
        """Analyze teacher assignment constraints"""
        violations = []
        compliant_assignments = []

        for entry in entries:
            if entry.subject and entry.teacher:
                # Check if teacher is assigned to teach this subject for this class group
                try:
                    # Check if teacher is assigned to this subject for this section
                    section = entry.class_group.split('-')[1] if '-' in entry.class_group else entry.class_group
                    assignments = TeacherSubjectAssignment.objects.filter(
                        teacher=entry.teacher,
                        subject=entry.subject
                    )

                    # Check if any assignment includes this section
                    assignment = None
                    for assign in assignments:
                        if section in assign.sections:
                            assignment = assign
                            break

                    if not assignment:
                        raise TeacherSubjectAssignment.DoesNotExist()

                    compliant_assignments.append({
                        'teacher': entry.teacher.name,
                        'subject': entry.subject.name,
                        'class_group': entry.class_group,
                        'day': entry.day,
                        'period': entry.period,
                        'time': f"{entry.start_time} - {entry.end_time}",
                        'assignment_id': assignment.id
                    })

                except TeacherSubjectAssignment.DoesNotExist:
                    violations.append({
                        'teacher': entry.teacher.name,
                        'subject': entry.subject.name,
                        'class_group': entry.class_group,
                        'day': entry.day,
                        'period': entry.period,
                        'time': f"{entry.start_time} - {entry.end_time}",
                        'violation_type': 'teacher_not_assigned_to_subject'
                    })

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_assignments': compliant_assignments,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_minimum_daily_classes(self, entries):
        """Analyze minimum daily classes constraint"""
        from collections import defaultdict

        # Group by class_group and day
        daily_classes = defaultdict(lambda: defaultdict(list))

        for entry in entries:
            daily_classes[entry.class_group][entry.day].append({
                'subject': entry.subject.name if entry.subject else 'N/A',
                'teacher': entry.teacher.name if entry.teacher else 'N/A',
                'period': entry.period,
                'time': f"{entry.start_time} - {entry.end_time}",
                'is_practical': entry.is_practical
            })

        violations = []
        compliant_days = []

        for class_group, days in daily_classes.items():
            for day, day_entries in days.items():
                practical_count = sum(1 for entry in day_entries if entry['is_practical'])
                theory_count = len(day_entries) - practical_count

                day_info = {
                    'class_group': class_group,
                    'day': day,
                    'total_classes': len(day_entries),
                    'practical_count': practical_count,
                    'theory_count': theory_count,
                    'entries': day_entries
                }

                # Check violations: only practical or only one class
                if len(day_entries) == 1 or (practical_count > 0 and theory_count == 0):
                    if len(day_entries) == 1:
                        day_info['violation_type'] = 'only_one_class'
                    else:
                        day_info['violation_type'] = 'only_practical_classes'
                    violations.append(day_info)
                else:
                    compliant_days.append(day_info)

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_days': compliant_days,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_compact_scheduling(self, entries):
        """Analyze compact scheduling constraint"""
        from collections import defaultdict

        # Group by class_group and day
        daily_schedules = defaultdict(lambda: defaultdict(list))

        for entry in entries:
            daily_schedules[entry.class_group][entry.day].append(entry.period)

        violations = []
        compliant_schedules = []

        for class_group, days in daily_schedules.items():
            for day, periods in days.items():
                periods.sort()

                # Check for gaps in schedule
                gaps = []
                if len(periods) > 1:
                    for i in range(len(periods) - 1):
                        gap_size = periods[i + 1] - periods[i] - 1
                        if gap_size > 0:
                            gaps.append({
                                'start_period': periods[i],
                                'end_period': periods[i + 1],
                                'gap_size': gap_size
                            })

                schedule_info = {
                    'class_group': class_group,
                    'day': day,
                    'periods': periods,
                    'start_period': min(periods) if periods else None,
                    'end_period': max(periods) if periods else None,
                    'total_periods': len(periods),
                    'gaps': gaps,
                    'has_gaps': len(gaps) > 0
                }

                # Check if schedule is compact (no gaps and reasonable end time)
                if len(gaps) > 0 or (periods and max(periods) > 5):
                    if len(gaps) > 0:
                        schedule_info['violation_type'] = 'schedule_gaps'
                    else:
                        schedule_info['violation_type'] = 'late_end_time'
                    violations.append(schedule_info)
                else:
                    compliant_schedules.append(schedule_info)

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_schedules': compliant_schedules,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_friday_aware_scheduling(self, entries):
        """Analyze Friday-aware scheduling constraint"""
        from collections import defaultdict

        # Group by class_group
        class_schedules = defaultdict(lambda: defaultdict(list))

        for entry in entries:
            class_schedules[entry.class_group][entry.day].append(entry.period)

        violations = []
        compliant_schedules = []

        for class_group, days in class_schedules.items():
            friday_periods = days.get('FRIDAY', [])
            has_friday_practical = any(
                entry.is_practical for entry in entries
                if entry.class_group == class_group and entry.day.upper() == 'FRIDAY'
            )

            # Check Monday-Thursday scheduling considering Friday limits
            for day in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY']:
                day_periods = days.get(day, [])

                if day_periods:
                    max_period = max(day_periods)

                    # If Friday has constraints, Monday-Thursday should be more compact
                    if friday_periods:
                        friday_max = max(friday_periods)
                        expected_friday_limit = 4 if has_friday_practical else 3

                        schedule_info = {
                            'class_group': class_group,
                            'day': day,
                            'periods': day_periods,
                            'max_period': max_period,
                            'friday_max_period': friday_max,
                            'friday_limit': expected_friday_limit,
                            'has_friday_practical': has_friday_practical
                        }

                        # Check if weekday scheduling is Friday-aware
                        if max_period > 5:  # Too late on weekdays when Friday is constrained
                            schedule_info['violation_type'] = 'not_friday_aware'
                            violations.append(schedule_info)
                        else:
                            compliant_schedules.append(schedule_info)

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_schedules': compliant_schedules,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_senior_batch_lab_assignment(self, entries):
        """Analyze senior batch lab assignment constraint"""
        from collections import defaultdict

        violations = []
        compliant_assignments = []

        # Group entries by batch (extract batch from class_group)
        batch_assignments = defaultdict(list)

        for entry in entries:
            if entry.classroom and entry.class_group:
                # Extract batch from class_group (e.g., "21SW-A" -> "21SW")
                batch_name = entry.class_group.split('-')[0] if '-' in entry.class_group else entry.class_group
                batch_assignments[batch_name].append(entry)

        # Determine seniority based on batch year (lower number = senior)
        # e.g., 21SW is senior to 22SW, 23SW, 24SW
        for batch_name, batch_entries in batch_assignments.items():
            try:
                # Extract year from batch name (e.g., "21SW" -> 21)
                batch_year = int(batch_name[:2])

                # Determine if this is a senior batch (lower year numbers are senior)
                # 21SW, 22SW = Senior batches (ALL classes in labs)
                # 23SW, 24SW = Junior batches (only practicals in labs)
                is_senior_batch = batch_year <= 22

                for entry in batch_entries:
                    classroom_name = entry.classroom.name.lower()
                    is_lab_room = 'lab' in classroom_name or 'laboratory' in classroom_name

                    assignment_info = {
                        'batch': batch_name,
                        'class_group': entry.class_group,
                        'subject': entry.subject.name if entry.subject else 'N/A',
                        'classroom': entry.classroom.name,
                        'day': entry.day,
                        'period': entry.period,
                        'time': f"{entry.start_time} - {entry.end_time}",
                        'is_senior_batch': is_senior_batch,
                        'is_lab_room': is_lab_room,
                        'is_practical': entry.is_practical
                    }

                    # Check constraint: Senior batches MUST be in labs (ALL classes)
                    if is_senior_batch:
                        if not is_lab_room:
                            # VIOLATION: Senior batch not in lab
                            assignment_info['violation_type'] = 'senior_batch_not_in_lab'
                            assignment_info['expected'] = 'Lab room (senior batch privilege)'
                            assignment_info['actual'] = f'Regular classroom ({entry.classroom.name})'
                            violations.append(assignment_info)
                        else:
                            # COMPLIANT: Senior batch in lab
                            compliant_assignments.append(assignment_info)
                    else:
                        # Junior batches: practicals in labs, theory in regular rooms
                        if entry.is_practical:
                            if is_lab_room:
                                # COMPLIANT: Junior practical in lab
                                compliant_assignments.append(assignment_info)
                            else:
                                # VIOLATION: Junior practical not in lab
                                assignment_info['violation_type'] = 'junior_practical_not_in_lab'
                                assignment_info['expected'] = 'Lab room for practical'
                                assignment_info['actual'] = f'Regular classroom ({entry.classroom.name})'
                                violations.append(assignment_info)
                        else:
                            # Junior theory can be in regular rooms (preferred) or labs if needed
                            compliant_assignments.append(assignment_info)

            except (ValueError, IndexError):
                # Skip batches with invalid naming format
                continue

        return {
            'total_violations': len(violations),
            'violations': violations,
            'compliant_assignments': compliant_assignments,
            'status': 'PASS' if len(violations) == 0 else 'FAIL'
        }

    def _analyze_room_double_booking(self, entries):
        """
        ENHANCED: Analyze room double-booking conflicts.
        Detects when multiple classes are assigned to the same room at the same time.
        """
        try:
            from collections import defaultdict

            room_schedule = defaultdict(list)
            conflicts = []

            # Group entries by room, day, and period
            for entry in entries:
                if entry.classroom:
                    key = (entry.classroom.id, entry.day, entry.period)
                    room_schedule[key].append(entry)

            # Find conflicts (more than one entry per time slot)
            for (room_id, day, period), room_entries in room_schedule.items():
                if len(room_entries) > 1:
                    room_name = room_entries[0].classroom.name
                    conflict_details = []

                    for entry in room_entries:
                        subject_code = entry.subject.code if entry.subject else 'Unknown'
                        conflict_details.append({
                            'class_group': entry.class_group,
                            'subject': subject_code,
                            'teacher': entry.teacher.name if entry.teacher else 'Unknown'
                        })

                    conflicts.append({
                        'room_name': room_name,
                        'day': day,
                        'period': period,
                        'conflict_count': len(room_entries),
                        'conflicting_classes': conflict_details
                    })

            return {
                'status': 'FAIL' if conflicts else 'PASS',
                'total_conflicts': len(conflicts),
                'conflicts': conflicts,
                'message': f'Found {len(conflicts)} room double-booking conflicts' if conflicts else 'No room conflicts detected'
            }

        except Exception as e:
            return {
                'status': 'ERROR',
                'error': f'Failed to analyze room conflicts: {str(e)}'
            }

    def _analyze_practical_same_lab(self, entries):
        """
        ENHANCED: Analyze practical same-lab rule compliance.
        Ensures all 3 blocks of each practical subject use the same lab.
        """
        try:
            from collections import defaultdict

            practical_groups = defaultdict(list)
            violations = []
            compliant_practicals = []

            # Group practical entries by class group and subject
            for entry in entries:
                if entry.subject and entry.subject.is_practical and entry.classroom:
                    key = (entry.class_group, entry.subject.code)
                    practical_groups[key].append(entry)

            # Check each practical group for same-lab compliance
            for (class_group, subject_code), group_entries in practical_groups.items():
                if len(group_entries) >= 2:  # Need at least 2 entries to check consistency
                    # Get all unique labs used by this practical
                    labs_used = set(entry.classroom.id for entry in group_entries)

                    if len(labs_used) > 1:
                        # VIOLATION: Multiple labs used for same practical
                        lab_details = []
                        for entry in group_entries:
                            lab_details.append({
                                'day': entry.day,
                                'period': entry.period,
                                'lab_name': entry.classroom.name,
                                'is_lab': entry.classroom.is_lab
                            })

                        violations.append({
                            'class_group': class_group,
                            'subject': subject_code,
                            'labs_used': len(labs_used),
                            'total_blocks': len(group_entries),
                            'lab_details': lab_details
                        })
                    else:
                        # COMPLIANT: All blocks in same lab
                        lab_name = group_entries[0].classroom.name
                        compliant_practicals.append({
                            'class_group': class_group,
                            'subject': subject_code,
                            'lab_name': lab_name,
                            'total_blocks': len(group_entries),
                            'is_lab': group_entries[0].classroom.is_lab
                        })

            return {
                'status': 'FAIL' if violations else 'PASS',
                'total_violations': len(violations),
                'violations': violations,
                'compliant_practicals': compliant_practicals,
                'total_practical_groups': len(practical_groups),
                'message': f'Found {len(violations)} same-lab violations' if violations else 'All practicals follow same-lab rule'
            }

        except Exception as e:
            return {
                'status': 'ERROR',
                'error': f'Failed to analyze practical same-lab rule: {str(e)}'
            }


class ConstraintResolverView(APIView):
    """
    Intelligent constraint resolution for specific constraint types.
    Attempts to fix violations without creating new ones.
    """

    def post(self, request):
        """Attempt to resolve a specific constraint type"""
        try:
            constraint_type = request.data.get('constraint_type')
            max_attempts = request.data.get('max_attempts', 5)

            if not constraint_type:
                return Response(
                    {'error': 'constraint_type is required'},
                    status=400
                )

            # Get current timetable entries
            entries = TimetableEntry.objects.all()

            if not entries.exists():
                return Response({
                    'success': False,
                    'error': 'No timetable entries found. Please generate a timetable first.'
                })

            # Initialize constraint validator for side effect tracking
            from .enhanced_constraint_validator import EnhancedConstraintValidator
            validator = EnhancedConstraintValidator()

            # Get initial state using the same analysis methods as constraint testing
            initial_analysis = self._get_specific_constraint_analysis(entries, constraint_type)
            initial_violations = initial_analysis.get('total_violations', 0)

            print(f"Constraint resolution for {constraint_type}: {initial_violations} initial violations")

            if initial_violations == 0:
                return Response({
                    'success': True,
                    'message': f'{constraint_type} constraint is already satisfied',
                    'attempts_made': 0,
                    'violations_before': 0,
                    'violations_after': 0,
                    'other_constraints_affected': 0
                })

            # Attempt to resolve the specific constraint
            resolution_result = self._resolve_specific_constraint(
                constraint_type, entries, validator, max_attempts
            )

            return Response({
                'success': resolution_result['success'],
                'message': resolution_result['message'],
                'attempts_made': resolution_result['attempts_made'],
                'violations_before': initial_violations,
                'violations_after': resolution_result['violations_after'],
                'other_constraints_affected': resolution_result['other_constraints_affected'],
                'resolution_details': resolution_result['details']
            })

        except Exception as e:
            logger.error(f"Constraint resolution failed: {str(e)}")
            return Response(
                {'error': f'Constraint resolution failed: {str(e)}'},
                status=500
            )

    def _get_specific_constraint_analysis(self, entries, constraint_type):
        """Get detailed analysis for a specific constraint - delegates to ConstraintTestingView"""
        # Create an instance of ConstraintTestingView to use its analysis methods
        testing_view = ConstraintTestingView()
        return testing_view._get_specific_constraint_analysis(entries, constraint_type)

    def _resolve_specific_constraint(self, constraint_type, entries, validator, max_attempts):
        """Resolve a specific constraint type intelligently"""
        attempts_made = 0
        violations_after = 0
        other_constraints_affected = 0
        details = []

        try:
            # Get initial state using the same analysis methods as constraint testing
            initial_analysis = self._get_specific_constraint_analysis(entries, constraint_type)
            initial_target_violations = initial_analysis.get('total_violations', 0)

            # Get initial state of all other constraints for side effect tracking
            initial_state = validator.validate_all_constraints(list(entries))
            initial_other_violations = initial_state['total_violations'] - initial_target_violations

            for attempt in range(max_attempts):
                attempts_made += 1

                # Apply constraint-specific resolution strategy
                resolution_applied = self._apply_constraint_resolution(constraint_type, entries)

                if not resolution_applied:
                    details.append(f"Attempt {attempt + 1}: No resolution strategy available")
                    break

                # Validate after resolution attempt using the same analysis methods
                current_analysis = self._get_specific_constraint_analysis(entries, constraint_type)
                current_violations = current_analysis.get('total_violations', 0)

                # Check other constraints for side effects
                current_state = validator.validate_all_constraints(list(entries))
                current_other_violations = current_state['total_violations'] - current_violations

                violations_after = current_violations
                other_constraints_affected = current_other_violations - initial_other_violations

                details.append(f"Attempt {attempt + 1}: {resolution_applied['action']} - "
                             f"Violations: {current_violations}, Other affected: {other_constraints_affected}")

                # Check if constraint is resolved without breaking others
                if current_violations == 0:
                    if other_constraints_affected <= 0:  # No new violations in other constraints
                        return {
                            'success': True,
                            'message': f'{constraint_type} constraint resolved successfully',
                            'attempts_made': attempts_made,
                            'violations_before': initial_target_violations,
                            'violations_after': violations_after,
                            'other_constraints_affected': other_constraints_affected,
                            'details': details
                        }
                    else:
                        details.append(f"Constraint resolved but created {other_constraints_affected} new violations")

                # If we created too many new violations, revert and try different approach
                if other_constraints_affected > 2:
                    details.append(f"Too many new violations created, trying different approach")
                    continue

            return {
                'success': violations_after < initial_target_violations,
                'message': f'Partial resolution achieved after {attempts_made} attempts',
                'attempts_made': attempts_made,
                'violations_before': initial_target_violations,
                'violations_after': violations_after,
                'other_constraints_affected': other_constraints_affected,
                'details': details
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Resolution failed: {str(e)}',
                'attempts_made': attempts_made,
                'violations_before': initial_target_violations,
                'violations_after': violations_after,
                'other_constraints_affected': other_constraints_affected,
                'details': details + [f"Error: {str(e)}"]
            }

    def _apply_constraint_resolution(self, constraint_type, entries):
        """Apply specific resolution strategy based on constraint type"""
        try:
            if constraint_type == 'teacher_conflicts':
                return self._resolve_teacher_conflicts(entries)
            elif constraint_type == 'room_conflicts':
                return self._resolve_room_conflicts(entries)
            elif constraint_type == 'subject_frequency':
                return {'action': 'Subject frequency constraint resolution disabled', 'success': False, 'message': 'Constraint resolution has been removed'}
            elif constraint_type == 'practical_blocks':
                return self._resolve_practical_blocks(entries)
            elif constraint_type == 'friday_time_limits':
                return self._resolve_friday_time_limits(entries)
            elif constraint_type == 'compact_scheduling':
                return self._resolve_compact_scheduling(entries)
            elif constraint_type == 'thesis_day_constraint':
                return self._resolve_thesis_day_constraint(entries)
            elif constraint_type == 'room_double_booking':
                return self._resolve_room_double_booking(entries)
            elif constraint_type == 'practical_same_lab':
                return self._resolve_practical_same_lab(entries)
            elif constraint_type == 'practical_in_labs_only':
                return self._resolve_practical_in_labs_only(entries)
            elif constraint_type == 'theory_room_consistency':
                return self._resolve_theory_room_consistency(entries)
            elif constraint_type == 'section_simultaneous_classes':
                return self._resolve_section_simultaneous_classes(entries)
            elif constraint_type == 'working_hours_compliance':
                return self._resolve_working_hours_compliance(entries)
            elif constraint_type == 'max_theory_per_day':
                return self._resolve_max_theory_per_day(entries)
            elif constraint_type == 'minimum_daily_classes':
                return self._resolve_minimum_daily_classes(entries)
            elif constraint_type == 'teacher_assignments':
                return self._resolve_teacher_assignments(entries)
            elif constraint_type == 'friday_aware_scheduling':
                return self._resolve_friday_aware_scheduling(entries)
            else:
                return None

        except Exception as e:
            logger.error(f"Resolution strategy failed for {constraint_type}: {str(e)}")
            return None

    def _resolve_teacher_conflicts(self, entries):
        """Universal teacher conflict resolution - works with any timetable structure"""
        from collections import defaultdict

        changes_made = 0
        resolution_details = []

        try:
            # STEP 1: Analyze teacher conflicts universally
            conflicts = self._analyze_universal_teacher_conflicts(entries)

            # STEP 2: Resolve conflicts by intelligent rescheduling
            for conflict in conflicts:
                resolution = self._resolve_single_teacher_conflict(conflict, entries)
                if resolution['success']:
                    changes_made += resolution['changes']
                    resolution_details.extend(resolution['details'])

            return {
                'action': f'Universal teacher conflict resolution: {changes_made} conflicts resolved',
                'success': changes_made > 0,
                'changes_made': changes_made,
                'details': resolution_details
            } if changes_made > 0 else None

        except Exception as e:
            return {
                'action': f'Teacher conflict resolution failed: {str(e)}',
                'success': False,
                'changes_made': 0,
                'error': str(e)
            }

    def _analyze_universal_teacher_conflicts(self, entries):
        """Universal analysis of teacher conflicts - works with any data structure"""
        from collections import defaultdict

        conflicts = []
        time_slot_teachers = defaultdict(lambda: defaultdict(list))

        # Group entries by time slot and teacher
        for entry in entries:
            if entry.teacher and entry.day and entry.period:
                time_key = (entry.day, entry.period)
                time_slot_teachers[time_key][entry.teacher.id].append(entry)

        # Identify conflicts (same teacher, multiple classes at same time)
        for time_slot, teachers in time_slot_teachers.items():
            for teacher_id, teacher_entries in teachers.items():
                if len(teacher_entries) > 1:
                    conflicts.append({
                        'time_slot': time_slot,
                        'teacher_id': teacher_id,
                        'teacher': teacher_entries[0].teacher,
                        'conflicting_entries': teacher_entries,
                        'conflict_count': len(teacher_entries)
                    })

        return conflicts

    def _resolve_single_teacher_conflict(self, conflict, entries):
        """Resolve a single teacher conflict by intelligent rescheduling"""
        changes_made = 0
        details = []

        conflicting_entries = conflict['conflicting_entries']
        teacher = conflict['teacher']

        # Strategy: Keep the first entry, move others
        entries_to_move = conflicting_entries[1:]

        for entry_to_move in entries_to_move:
            # Find alternative time slots for this entry
            alternative_slots = self._find_alternative_slots_for_entry(entry_to_move, entries)

            for day, period in alternative_slots:
                # Check if teacher is available at this time
                if self._is_teacher_available(teacher, day, period, entries):
                    # Check if classroom is available
                    if self._is_classroom_available(entry_to_move.classroom, day, period, entries):
                        # Check if class group is available
                        if self._is_class_group_available(entry_to_move.class_group, day, period, entries):
                            try:
                                # Move the entry
                                old_day, old_period = entry_to_move.day, entry_to_move.period
                                entry_to_move.day = day
                                entry_to_move.period = period
                                entry_to_move.start_time = self._get_period_start_time(period)
                                entry_to_move.end_time = self._get_period_end_time(period)
                                entry_to_move.save()

                                changes_made += 1
                                details.append(f"Moved {entry_to_move.subject.code} for {entry_to_move.class_group} from {old_day} P{old_period} to {day} P{period}")
                                break

                            except Exception as e:
                                continue

                if changes_made > 0:
                    break

        return {
            'success': changes_made > 0,
            'changes': changes_made,
            'details': details
        }

    def _find_alternative_slots_for_entry(self, entry, entries):
        """Find alternative time slots for a specific entry"""
        # Get all possible time slots
        all_slots = []
        for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
            for period in range(1, 9):
                all_slots.append((day, period))

        # Filter out current slot
        current_slot = (entry.day, entry.period)
        alternative_slots = [slot for slot in all_slots if slot != current_slot]

        return alternative_slots

    def _is_teacher_available(self, teacher, day, period, entries):
        """Check if teacher is available at specific time"""
        for entry in entries:
            if (entry.teacher and entry.teacher.id == teacher.id and
                entry.day == day and entry.period == period):
                return False
        return True

    def _is_classroom_available(self, classroom, day, period, entries):
        """Check if classroom is available at specific time"""
        if not classroom:
            return True

        for entry in entries:
            if (entry.classroom and entry.classroom.id == classroom.id and
                entry.day == day and entry.period == period):
                return False
        return True

    def _is_class_group_available(self, class_group, day, period, entries):
        """Check if class group is available at specific time"""
        for entry in entries:
            if (entry.class_group == class_group and
                entry.day == day and entry.period == period):
                return False
        return True

    def _resolve_room_conflicts(self, entries):
        """Universal room conflict resolution - works with any timetable structure"""
        from collections import defaultdict

        changes_made = 0
        resolution_details = []

        try:
            # STEP 1: Analyze room conflicts universally
            conflicts = self._analyze_universal_room_conflicts(entries)

            # STEP 2: Resolve conflicts by intelligent room reassignment
            for conflict in conflicts:
                resolution = self._resolve_single_room_conflict(conflict, entries)
                if resolution['success']:
                    changes_made += resolution['changes']
                    resolution_details.extend(resolution['details'])

            return {
                'action': f'Universal room conflict resolution: {changes_made} conflicts resolved',
                'success': changes_made > 0,
                'changes_made': changes_made,
                'details': resolution_details
            } if changes_made > 0 else None

        except Exception as e:
            return {
                'action': f'Room conflict resolution failed: {str(e)}',
                'success': False,
                'changes_made': 0,
                'error': str(e)
            }

    def _analyze_universal_room_conflicts(self, entries):
        """Universal analysis of room conflicts - works with any data structure"""
        from collections import defaultdict

        conflicts = []
        time_slot_rooms = defaultdict(lambda: defaultdict(list))

        # Group entries by time slot and room
        for entry in entries:
            if entry.classroom and entry.day and entry.period:
                time_key = (entry.day, entry.period)
                time_slot_rooms[time_key][entry.classroom.id].append(entry)

        # Identify conflicts (same room, multiple classes at same time)
        for time_slot, rooms in time_slot_rooms.items():
            for room_id, room_entries in rooms.items():
                if len(room_entries) > 1:
                    conflicts.append({
                        'time_slot': time_slot,
                        'room_id': room_id,
                        'room': room_entries[0].classroom,
                        'conflicting_entries': room_entries,
                        'conflict_count': len(room_entries)
                    })

        return conflicts

    def _resolve_single_room_conflict(self, conflict, entries):
        """Resolve a single room conflict by intelligent room reassignment"""
        from timetable.models import Classroom

        changes_made = 0
        details = []

        conflicting_entries = conflict['conflicting_entries']
        room = conflict['room']
        day, period = conflict['time_slot']

        # Strategy: Keep the first entry, reassign others
        entries_to_reassign = conflicting_entries[1:]

        for entry_to_reassign in entries_to_reassign:
            # Find alternative rooms for this entry
            alternative_rooms = self._find_alternative_rooms_for_entry(entry_to_reassign, day, period, entries)

            for alternative_room in alternative_rooms:
                try:
                    # Reassign the room
                    old_room = entry_to_reassign.classroom
                    entry_to_reassign.classroom = alternative_room
                    entry_to_reassign.save()

                    changes_made += 1
                    details.append(f"Reassigned {entry_to_reassign.subject.code} for {entry_to_reassign.class_group} from {old_room.name} to {alternative_room.name} at {day} P{period}")
                    break

                except Exception as e:
                    continue

        return {
            'success': changes_made > 0,
            'changes': changes_made,
            'details': details
        }

    def _find_alternative_rooms_for_entry(self, entry, day, period, entries):
        """Find alternative rooms for a specific entry at specific time"""
        from timetable.models import Classroom

        # Get all occupied rooms at this time slot
        occupied_rooms = set()
        for e in entries:
            if e.classroom and e.day == day and e.period == period:
                occupied_rooms.add(e.classroom.id)

        # Find available rooms based on entry type
        if entry.subject and entry.subject.is_practical:
            # For practical subjects, find available labs (rooms with 'lab' in name)
            available_rooms = Classroom.objects.filter(
                name__icontains='lab'
            ).exclude(id__in=occupied_rooms)
        else:
            # For theory subjects, find available theory rooms (rooms without 'lab' in name)
            available_rooms = Classroom.objects.exclude(
                name__icontains='lab'
            ).exclude(id__in=occupied_rooms)

        return list(available_rooms)

    def _resolve_subject_frequency(self, entries):
        """Intelligent Subject Frequency resolution that respects all other constraints"""
        from timetable.models import TeacherSubjectAssignment, Subject, TimetableEntry
        # from timetable.constraint_validator import ConstraintValidator  # Using enhanced version
        from collections import defaultdict

        changes_made = 0
        resolution_details = []

        try:
            # Initialize constraint validator to check all constraints
            from timetable.enhanced_constraint_validator import EnhancedConstraintValidator
            validator = EnhancedConstraintValidator()

            # STEP 1: Analyze current subject frequency violations
            print("🔍 Analyzing Subject Frequency violations...")
            analysis = self._analyze_subject_frequency(entries)

            if analysis['total_violations'] == 0:
                return {
                    'action': 'Subject frequency already compliant - no changes needed',
                    'success': True,
                    'changes_made': 0,
                    'details': ['All subjects already have correct frequency distribution']
                }

            resolution_details.append(f"Found {analysis['total_violations']} Subject Frequency violations")

            # STEP 2: Process violations while respecting all constraints
            for violation in analysis['violations']:
                if violation.get('violation_type') in ['frequency_mismatch', 'missing_subject']:
                    class_group = violation['class_group']
                    subject_code = violation['subject_code']
                    expected = violation['expected_count']
                    actual = violation['actual_count']

                    if actual < expected:
                        # Need to add classes
                        added = self._safely_add_subject_classes(
                            entries, class_group, subject_code, expected - actual, validator
                        )
                        changes_made += added
                        if added > 0:
                            resolution_details.append(f"Added {added} {subject_code} classes for {class_group}")
                        else:
                            resolution_details.append(f"Could not add {subject_code} classes for {class_group} - would violate other constraints")

                    elif actual > expected:
                        # Need to remove classes
                        removed = self._safely_remove_subject_classes(
                            entries, class_group, subject_code, actual - expected, validator
                        )
                        changes_made += removed
                        if removed > 0:
                            resolution_details.append(f"Removed {removed} excess {subject_code} classes for {class_group}")

            # STEP 3: Final validation to ensure no other constraints were violated
            final_validation = validator.validate_all_constraints(list(TimetableEntry.objects.all()))

            return {
                'action': f'Subject frequency resolution completed: {changes_made} changes made',
                'success': changes_made > 0,
                'changes_made': changes_made,
                'details': resolution_details,
                'final_constraint_status': f"Total violations across all constraints: {final_validation['total_violations']}"
            }

        except Exception as e:
            print(f"❌ Subject frequency resolution failed: {str(e)}")
            return {
                'action': f'Subject frequency resolution failed: {str(e)}',
                'success': False,
                'changes_made': 0,
                'error': str(e),
                'details': [f"Error occurred: {str(e)}"]
            }

    def _safely_add_subject_classes(self, entries, class_group, subject_code, classes_to_add, validator):
        """Safely add subject classes while respecting all constraints"""
        from timetable.models import Subject, TeacherSubjectAssignment, TimetableEntry

        try:
            subject = Subject.objects.get(code=subject_code)
        except Subject.DoesNotExist:
            return 0

        # Get assigned teacher for this subject
        assignments = TeacherSubjectAssignment.objects.filter(subject=subject)
        if not assignments.exists():
            return 0

        teacher = assignments.first().teacher
        classes_added = 0

        # Try to find safe slots for the required classes
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            if classes_added >= classes_to_add:
                break

            for period in range(1, 8):  # Periods 1-7
                if classes_added >= classes_to_add:
                    break

                # Check if this slot would violate any constraints
                if self._would_violate_any_constraint(entries, class_group, day, period, subject, teacher, validator):
                    continue

                # Find available room
                available_room = self._find_safe_available_room(entries, day, period, subject.is_practical)
                if not available_room:
                    continue

                # Create the new entry
                try:
                    new_entry = TimetableEntry.objects.create(
                        class_group=class_group,
                        subject=subject,
                        teacher=teacher,
                        classroom=available_room,
                        day=day,
                        period=period,
                        start_time=self._get_period_start_time(period),
                        end_time=self._get_period_end_time(period),
                        is_practical=subject.is_practical
                    )
                    classes_added += 1
                    print(f"✅ Added {subject_code} class: {day} P{period} in {available_room.name}")

                except Exception as e:
                    print(f"❌ Failed to create entry: {str(e)}")
                    continue

        return classes_added

    def _safely_remove_subject_classes(self, entries, class_group, subject_code, classes_to_remove, validator):
        """Safely remove excess subject classes"""
        from timetable.models import TimetableEntry

        # Find entries to remove (prefer removing from less optimal slots)
        excess_entries = TimetableEntry.objects.filter(
            class_group=class_group,
            subject__code=subject_code
        ).order_by('-period', 'day')  # Remove later periods first

        classes_removed = 0
        for entry in excess_entries[:classes_to_remove]:
            try:
                day = entry.day
                period = entry.period
                room = entry.classroom.name if entry.classroom else 'N/A'

                entry.delete()
                classes_removed += 1
                print(f"✅ Removed {subject_code} class: {day} P{period} in {room}")

            except Exception as e:
                print(f"❌ Failed to remove entry: {str(e)}")
                continue

        return classes_removed

    def _would_violate_any_constraint(self, entries, class_group, day, period, subject, teacher, validator):
        """Check if adding a class would violate any constraint"""
        from timetable.models import TimetableEntry

        # Create a temporary entry to test constraints
        temp_entry = TimetableEntry(
            class_group=class_group,
            subject=subject,
            teacher=teacher,
            day=day,
            period=period,
            is_practical=subject.is_practical
        )

        # Check basic conflicts first
        existing_entries = TimetableEntry.objects.filter(
            class_group=class_group,
            day=day,
            period=period
        )
        if existing_entries.exists():
            return True  # Class group already has a class at this time

        # Check teacher conflicts
        teacher_conflicts = TimetableEntry.objects.filter(
            teacher=teacher,
            day=day,
            period=period
        )
        if teacher_conflicts.exists():
            return True  # Teacher already teaching at this time

        # Check Friday time limits
        if day.lower() == 'friday':
            friday_entries = TimetableEntry.objects.filter(
                class_group=class_group,
                day__icontains='friday'
            )
            practical_count = friday_entries.filter(subject__is_practical=True).count()

            if subject.is_practical:
                if period > 6:  # Practical subjects can go up to P6 on Friday
                    return True
            else:
                if practical_count > 0 and period > 4:  # Has practical, theory limit P4
                    return True
                elif practical_count == 0 and period > 3:  # No practical, limit P3
                    return True

        # Check max theory per day constraint
        if not subject.is_practical:
            theory_classes_today = TimetableEntry.objects.filter(
                class_group=class_group,
                day=day,
                subject__is_practical=False
            ).count()
            if theory_classes_today >= 1:
                return True  # Already has one theory class today

        # Check if this would exceed credit hours
        current_count = TimetableEntry.objects.filter(
            class_group=class_group,
            subject=subject
        ).count()
        if current_count >= subject.credits:
            return True  # Already has enough classes for this subject

        return False

    def _find_safe_available_room(self, entries, day, period, is_practical):
        """Find an available room that doesn't conflict"""
        from timetable.models import Classroom, TimetableEntry

        # Get occupied rooms at this time
        occupied_rooms = TimetableEntry.objects.filter(
            day=day,
            period=period
        ).values_list('classroom_id', flat=True)

        # Find appropriate room type
        if is_practical:
            # For practical subjects, find labs
            available_rooms = Classroom.objects.filter(
                name__icontains='lab'
            ).exclude(id__in=occupied_rooms)
        else:
            # For theory subjects, find regular rooms
            available_rooms = Classroom.objects.exclude(
                name__icontains='lab'
            ).exclude(id__in=occupied_rooms)

        return available_rooms.first()

    def _resolve_practical_blocks(self, entries):
        """Universal practical block resolution - ensures 3 consecutive blocks in same lab"""
        from timetable.models import Classroom
        from collections import defaultdict

        changes_made = 0
        resolution_details = []

        try:
            # STEP 1: Analyze practical block violations
            violations = self._analyze_practical_block_violations(entries)

            # STEP 2: Resolve each violation
            for violation in violations:
                resolution = self._resolve_single_practical_block_violation(violation, entries)
                if resolution['success']:
                    changes_made += resolution['changes']
                    resolution_details.extend(resolution['details'])

            return {
                'action': f'Universal practical block resolution: {changes_made} violations resolved',
                'success': changes_made > 0,
                'changes_made': changes_made,
                'details': resolution_details
            } if changes_made > 0 else None

        except Exception as e:
            return {
                'action': f'Practical block resolution failed: {str(e)}',
                'success': False,
                'changes_made': 0,
                'error': str(e)
            }

    def _analyze_practical_block_violations(self, entries):
        """Analyze practical subjects that don't have 3 consecutive blocks in same lab"""
        from collections import defaultdict

        violations = []
        practical_sessions = defaultdict(dict)

        # Group practical entries by class group and subject
        for entry in entries:
            if entry.subject and entry.subject.is_practical:
                key = (entry.class_group, entry.subject.code)
                if 'entries' not in practical_sessions[key]:
                    practical_sessions[key]['entries'] = []
                practical_sessions[key]['entries'].append(entry)

        # Check each practical subject
        for (class_group, subject_code), session_data in practical_sessions.items():
            entries_list = session_data['entries']

            # Group by day to check consecutive blocks
            days_sessions = defaultdict(list)
            for entry in entries_list:
                days_sessions[entry.day].append(entry)

            # Check each day's session
            for day, day_entries in days_sessions.items():
                if len(day_entries) != 3:
                    violations.append({
                        'type': 'incorrect_block_count',
                        'class_group': class_group,
                        'subject_code': subject_code,
                        'day': day,
                        'current_blocks': len(day_entries),
                        'entries': day_entries
                    })
                    continue

                # Check if blocks are consecutive
                periods = sorted([entry.period for entry in day_entries])
                if periods != [periods[0], periods[0]+1, periods[0]+2]:
                    violations.append({
                        'type': 'non_consecutive_blocks',
                        'class_group': class_group,
                        'subject_code': subject_code,
                        'day': day,
                        'periods': periods,
                        'entries': day_entries
                    })
                    continue

                # Check if all blocks are in same lab
                labs = set(entry.classroom.id for entry in day_entries if entry.classroom)
                if len(labs) > 1:
                    violations.append({
                        'type': 'different_labs',
                        'class_group': class_group,
                        'subject_code': subject_code,
                        'day': day,
                        'labs': labs,
                        'entries': day_entries
                    })

        return violations

    def _resolve_single_practical_block_violation(self, violation, entries):
        """Resolve a single practical block violation"""
        changes_made = 0
        details = []

        violation_type = violation['type']
        class_group = violation['class_group']
        subject_code = violation['subject_code']

        if violation_type in ['incorrect_block_count', 'non_consecutive_blocks']:
            # Find consecutive slots and recreate the practical session
            consecutive_slots = self._find_consecutive_lab_slots(entries, class_group, 3)
            if consecutive_slots:
                # Remove existing blocks
                for entry in violation['entries']:
                    entry.delete()
                    changes_made += 1

                # Create new 3-block session
                day, start_period, lab = consecutive_slots
                subject = violation['entries'][0].subject if violation['entries'] else None
                teacher = violation['entries'][0].teacher if violation['entries'] else None

                if subject and teacher:
                    for period_offset in range(3):
                        period = start_period + period_offset
                        try:
                            from timetable.models import TimetableEntry
                            new_entry = TimetableEntry.objects.create(
                                class_group=class_group,
                                subject=subject,
                                teacher=teacher,
                                classroom=lab,
                                day=day,
                                period=period,
                                start_time=self._get_period_start_time(period),
                                end_time=self._get_period_end_time(period),
                                is_practical=True
                            )
                            changes_made += 1
                        except Exception as e:
                            continue

                    details.append(f"Fixed {subject_code} practical blocks for {class_group} - created 3 consecutive blocks in {lab.name}")

        elif violation_type == 'different_labs':
            # Move all blocks to same lab
            target_lab = violation['entries'][0].classroom  # Use first entry's lab as target

            for entry in violation['entries'][1:]:  # Skip first entry
                if entry.classroom.id != target_lab.id:
                    entry.classroom = target_lab
                    entry.save()
                    changes_made += 1

            details.append(f"Moved all {subject_code} blocks for {class_group} to same lab: {target_lab.name}")

        return {
            'success': changes_made > 0,
            'changes': changes_made,
            'details': details
        }

    def _analyze_universal_subject_frequency(self, entries):
        """Universal analysis of subject frequency state - works with any data structure"""
        from timetable.models import TeacherSubjectAssignment, Subject
        from collections import defaultdict

        state = {
            'class_groups': set(),
            'expected_subjects': defaultdict(dict),  # {class_group: {subject_code: {teacher, subject, expected_count}}}
            'current_theory_counts': defaultdict(lambda: defaultdict(int)),
            'current_practical_sessions': defaultdict(lambda: defaultdict(set)),  # Track days for practical sessions
            'violations': {
                'missing_theory': [],
                'excess_theory': [],
                'missing_practical': [],
                'excess_practical': []
            }
        }

        # Get all class groups from entries
        state['class_groups'] = set(entry.class_group for entry in entries if entry.class_group)

        # Get expected subjects for each class group (universal approach)
        for assignment in TeacherSubjectAssignment.objects.all():
            for section in assignment.sections:
                for class_group in state['class_groups']:
                    # Universal matching - works with any naming convention
                    if self._class_group_matches_section(class_group, section):
                        state['expected_subjects'][class_group][assignment.subject.code] = {
                            'teacher': assignment.teacher,
                            'subject': assignment.subject,
                            'expected_count': 1 if assignment.subject.is_practical else assignment.subject.credits
                        }

        # Count current frequencies
        for entry in entries:
            if entry.subject and entry.class_group:
                class_group = entry.class_group
                subject_code = entry.subject.code

                if entry.subject.is_practical:
                    # For practical subjects, track days (sessions)
                    state['current_practical_sessions'][class_group][subject_code].add(entry.day)
                else:
                    # For theory subjects, count individual classes
                    state['current_theory_counts'][class_group][subject_code] += 1

        # Identify violations
        for class_group in state['class_groups']:
            for subject_code, subject_info in state['expected_subjects'][class_group].items():
                expected_count = subject_info['expected_count']
                subject = subject_info['subject']

                if subject.is_practical:
                    actual_sessions = len(state['current_practical_sessions'][class_group][subject_code])
                    if actual_sessions < expected_count:
                        state['violations']['missing_practical'].append({
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'subject_info': subject_info,
                            'missing_sessions': expected_count - actual_sessions
                        })
                    elif actual_sessions > expected_count:
                        state['violations']['excess_practical'].append({
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'subject_info': subject_info,
                            'excess_sessions': actual_sessions - expected_count
                        })
                else:
                    actual_count = state['current_theory_counts'][class_group][subject_code]
                    if actual_count < expected_count:
                        state['violations']['missing_theory'].append({
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'subject_info': subject_info,
                            'missing_classes': expected_count - actual_count
                        })
                    elif actual_count > expected_count:
                        state['violations']['excess_theory'].append({
                            'class_group': class_group,
                            'subject_code': subject_code,
                            'subject_info': subject_info,
                            'excess_classes': actual_count - expected_count
                        })

        return state

    def _class_group_matches_section(self, class_group, section):
        """Universal class group to section matching - works with any naming convention"""
        class_group_clean = class_group.replace('-', '').replace('_', '').upper()
        section_clean = section.replace('-', '').replace('_', '').upper()
        return section_clean in class_group_clean or class_group_clean in section_clean

    def _resolve_theory_frequency_violations(self, entries, state):
        """Enhanced theory subject frequency resolution with detailed tracking"""
        from timetable.models import TimetableEntry

        changes_made = 0
        details = []

        if not state['violations']['missing_theory']:
            details.append("No missing theory classes to add")
            return {'count': 0, 'details': details}

        for violation in state['violations']['missing_theory']:
            class_group = violation['class_group']
            subject_code = violation['subject_code']
            subject_info = violation['subject_info']
            missing_classes = violation['missing_classes']

            details.append(f"Processing {subject_code} for {class_group}: need {missing_classes} more classes")

            # Find available slots for this class group
            available_slots = self._find_universal_available_slots(entries, class_group, missing_classes)

            if not available_slots:
                details.append(f"⚠️ No available slots found for {subject_code} in {class_group}")
                continue

            classes_added = 0
            for i in range(min(missing_classes, len(available_slots))):
                day, period = available_slots[i]

                # Find available room
                available_room = self._find_universal_available_room(entries, day, period)

                if available_room:
                    try:
                        # Skip this slot for now - using safer constraint checking in new implementation

                        # Create new timetable entry
                        new_entry = TimetableEntry.objects.create(
                            class_group=class_group,
                            subject=subject_info['subject'],
                            teacher=subject_info['teacher'],
                            classroom=available_room,
                            day=day,
                            period=period,
                            start_time=self._get_period_start_time(period),
                            end_time=self._get_period_end_time(period),
                            is_practical=False
                        )
                        classes_added += 1
                        changes_made += 1
                        details.append(f"✅ Added {subject_code} class: {day} P{period} in {available_room.name}")

                    except Exception as e:
                        details.append(f"❌ Failed to add {subject_code} class at {day} P{period}: {str(e)}")
                        continue
                else:
                    details.append(f"⚠️ No available room for {subject_code} at {day} P{period}")

            if classes_added > 0:
                details.append(f"✅ Successfully added {classes_added}/{missing_classes} {subject_code} classes for {class_group}")
            else:
                details.append(f"❌ Could not add any {subject_code} classes for {class_group}")

        return {'count': changes_made, 'details': details}

    def _would_violate_other_constraints(self, entries, class_group, day, period, subject):
        """Check if adding a class would violate other constraints"""

        # Check for class group conflicts (no simultaneous classes for same section)
        for entry in entries:
            if (entry.class_group == class_group and
                entry.day == day and entry.period == period):
                return True

        # Check Friday time limits
        if day.lower().startswith('fri'):
            # Count existing practical classes on Friday for this class group
            friday_practicals = sum(1 for e in entries
                                  if e.class_group == class_group and
                                     e.day.lower().startswith('fri') and
                                     e.subject and e.subject.is_practical)

            if subject.is_practical:
                # Practical subjects can go up to P6 on Friday
                if period > 6:
                    return True
            else:
                # Theory subjects limited by practical presence
                if friday_practicals > 0 and period > 4:  # Has practical, theory limit P4
                    return True
                elif friday_practicals == 0 and period > 3:  # No practical, limit P3
                    return True

        # Check max theory per day constraint (only one theory class per day per section)
        if not subject.is_practical:
            theory_classes_today = sum(1 for e in entries
                                     if e.class_group == class_group and
                                        e.day == day and
                                        e.subject and not e.subject.is_practical)
            if theory_classes_today >= 1:
                return True

        # Check teacher conflicts
        for entry in entries:
            if (entry.teacher and entry.teacher.id == subject.id and  # Same teacher
                entry.day == day and entry.period == period):
                return True

        return False

    def _resolve_practical_frequency_violations(self, entries, state):
        """Resolve practical subject frequency violations by adding missing sessions"""
        from timetable.models import TimetableEntry

        changes_made = 0
        details = []

        for violation in state['violations']['missing_practical']:
            class_group = violation['class_group']
            subject_code = violation['subject_code']
            subject_info = violation['subject_info']
            missing_sessions = violation['missing_sessions']

            # For each missing session, find 3 consecutive slots in the same lab
            for session in range(missing_sessions):
                consecutive_slots = self._find_consecutive_lab_slots(entries, class_group, 3)

                if consecutive_slots:
                    day, start_period, lab = consecutive_slots

                    session_added = 0
                    for period_offset in range(3):  # 3 consecutive periods
                        period = start_period + period_offset

                        try:
                            new_entry = TimetableEntry.objects.create(
                                class_group=class_group,
                                subject=subject_info['subject'],
                                teacher=subject_info['teacher'],
                                classroom=lab,
                                day=day,
                                period=period,
                                start_time=self._get_period_start_time(period),
                                end_time=self._get_period_end_time(period),
                                is_practical=True
                            )
                            session_added += 1
                            changes_made += 1

                        except Exception as e:
                            continue

                    if session_added == 3:
                        details.append(f"Added {subject_code} practical session for {class_group} on {day}")

        return {'count': changes_made, 'details': details}

    def _remove_excess_subject_instances(self, entries, state):
        """Enhanced removal of excess subject instances with detailed tracking"""
        changes_made = 0
        details = []

        if not state['violations']['excess_theory'] and not state['violations']['excess_practical']:
            details.append("No excess classes to remove")
            return {'count': 0, 'details': details}

        # Remove excess theory classes
        for violation in state['violations']['excess_theory']:
            class_group = violation['class_group']
            subject_code = violation['subject_code']
            excess_classes = violation['excess_classes']

            details.append(f"Processing excess {subject_code} for {class_group}: removing {excess_classes} classes")

            # Find entries to remove (prefer removing from less optimal slots)
            excess_entries = [e for e in entries
                            if e.class_group == class_group
                            and e.subject
                            and e.subject.code == subject_code
                            and not e.subject.is_practical]

            # Sort by preference (remove Friday late periods first, then other suboptimal slots)
            excess_entries.sort(key=lambda e: (
                e.day.lower().startswith('fri') and e.period > 3,  # Friday late periods first
                e.period > 5,  # Late periods
                e.period  # Higher periods
            ), reverse=True)

            removed_count = 0
            for i in range(min(excess_classes, len(excess_entries))):
                try:
                    entry_to_remove = excess_entries[i]
                    day = entry_to_remove.day
                    period = entry_to_remove.period
                    room = entry_to_remove.classroom.name if entry_to_remove.classroom else 'N/A'

                    entry_to_remove.delete()
                    changes_made += 1
                    removed_count += 1
                    details.append(f"✅ Removed {subject_code} class: {day} P{period} in {room}")

                except Exception as e:
                    details.append(f"❌ Failed to remove {subject_code} class: {str(e)}")
                    continue

            if removed_count > 0:
                details.append(f"✅ Successfully removed {removed_count}/{excess_classes} excess {subject_code} classes for {class_group}")
            else:
                details.append(f"❌ Could not remove any excess {subject_code} classes for {class_group}")

        # Remove excess practical sessions
        for violation in state['violations']['excess_practical']:
            class_group = violation['class_group']
            subject_code = violation['subject_code']
            excess_sessions = violation['excess_sessions']

            # Find practical entries grouped by day
            practical_entries = [e for e in entries
                               if e.class_group == class_group
                               and e.subject
                               and e.subject.code == subject_code
                               and e.subject.is_practical]

            # Group by day and remove excess days
            from collections import defaultdict
            entries_by_day = defaultdict(list)
            for entry in practical_entries:
                entries_by_day[entry.day].append(entry)

            days_to_remove = list(entries_by_day.keys())[-excess_sessions:]

            for day in days_to_remove:
                for entry in entries_by_day[day]:
                    try:
                        entry.delete()
                        changes_made += 1
                    except Exception as e:
                        continue

                details.append(f"Removed excess {subject_code} practical session for {class_group} on {day}")

        return {'count': changes_made, 'details': details}

    def _class_group_matches_section(self, class_group, section):
        """Universal class group to section matching - works with any naming convention"""
        # Handle various naming patterns: 21SW-III, 21SW3, SW-21-III, etc.
        class_group_clean = class_group.replace('-', '').replace('_', '').upper()
        section_clean = section.replace('-', '').replace('_', '').upper()

        # Check if section is contained in class_group or vice versa
        return section_clean in class_group_clean or class_group_clean in section_clean

    def _find_available_slots(self, entries, class_group, needed_slots):
        """Find available time slots for a class group"""
        # Get all occupied slots for this class group
        occupied_slots = set()
        for entry in entries:
            if entry.class_group == class_group:
                occupied_slots.add((entry.day, entry.period))

        # Define all possible slots (Monday-Friday, periods 1-8)
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        periods = list(range(1, 9))

        available_slots = []
        for day in days:
            for period in periods:
                if (day, period) not in occupied_slots:
                    available_slots.append((day, period))
                    if len(available_slots) >= needed_slots:
                        break
            if len(available_slots) >= needed_slots:
                break

        return available_slots[:needed_slots]

    def _find_available_room(self, entries, day, period):
        """Find an available room for a specific day and period"""
        from timetable.models import Classroom

        # Get all occupied rooms for this time slot
        occupied_rooms = set()
        for entry in entries:
            if entry.day == day and entry.period == period and entry.classroom:
                occupied_rooms.add(entry.classroom.id)

        # Find an available room
        available_rooms = Classroom.objects.exclude(id__in=occupied_rooms)
        return available_rooms.first() if available_rooms.exists() else None

    def _get_period_start_time(self, period):
        """Get start time for a period"""
        start_times = {
            1: "08:00", 2: "09:00", 3: "10:00", 4: "11:00",
            5: "12:00", 6: "13:00", 7: "14:00", 8: "15:00"
        }
        return start_times.get(period, "08:00")

    def _get_period_end_time(self, period):
        """Get end time for a period"""
        end_times = {
            1: "09:00", 2: "10:00", 3: "11:00", 4: "12:00",
            5: "13:00", 6: "14:00", 7: "15:00", 8: "16:00"
        }
        return end_times.get(period, "09:00")

    def _find_universal_available_slots(self, entries, class_group, needed_slots):
        """Universal method to find available time slots - works with any timetable structure"""
        # Get all occupied slots for this class group
        occupied_slots = set()
        for entry in entries:
            if entry.class_group == class_group:
                occupied_slots.add((entry.day, entry.period))

        # Define all possible slots (universal approach)
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        periods = list(range(1, 9))  # Periods 1-8 (universal)

        # Normalize day names to handle different formats
        day_mapping = {
            'Monday': 'Mon', 'Tuesday': 'Tue', 'Wednesday': 'Wed',
            'Thursday': 'Thu', 'Friday': 'Fri'
        }

        available_slots = []
        for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
            for period in periods:
                # Check all possible day name formats
                slot_occupied = False
                for day_variant in [day, day_mapping.get(day, day)]:
                    if (day_variant, period) in occupied_slots:
                        slot_occupied = True
                        break

                if not slot_occupied:
                    available_slots.append((day, period))
                    if len(available_slots) >= needed_slots:
                        break
            if len(available_slots) >= needed_slots:
                break

        return available_slots[:needed_slots]

    def _find_universal_available_room(self, entries, day, period):
        """Universal method to find available room - works with any room structure"""
        from timetable.models import Classroom

        # Get all occupied rooms for this time slot
        occupied_rooms = set()
        for entry in entries:
            if entry.day == day and entry.period == period and entry.classroom:
                occupied_rooms.add(entry.classroom.id)

        # Find available room (prefer theory rooms for theory subjects)
        available_rooms = Classroom.objects.exclude(id__in=occupied_rooms).exclude(name__icontains='lab')
        return available_rooms.first() if available_rooms.exists() else None

    def _find_consecutive_lab_slots(self, entries, class_group, consecutive_periods):
        """Find consecutive periods in the same lab for practical subjects"""
        from timetable.models import Classroom

        # Get all occupied slots for this class group
        occupied_slots = set()
        for entry in entries:
            if entry.class_group == class_group:
                occupied_slots.add((entry.day, entry.period))

        # Get all lab rooms
        labs = Classroom.objects.filter(name__icontains='lab')

        for lab in labs:
            for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
                for start_period in range(1, 9 - consecutive_periods + 1):
                    # Check if consecutive periods are available
                    consecutive_available = True
                    lab_occupied = False

                    for period_offset in range(consecutive_periods):
                        period = start_period + period_offset

                        # Check if class group has conflict
                        if (day, period) in occupied_slots:
                            consecutive_available = False
                            break

                        # Check if lab is occupied
                        for entry in entries:
                            if (entry.day == day and entry.period == period and
                                entry.classroom and entry.classroom.id == lab.id):
                                lab_occupied = True
                                break

                        if lab_occupied:
                            consecutive_available = False
                            break

                    if consecutive_available:
                        return (day, start_period, lab)

        return None

    def _resolve_compact_scheduling(self, entries):
        """Resolve compact scheduling by moving classes to reduce gaps"""
        from collections import defaultdict

        # Group by class_group and day
        daily_schedules = defaultdict(lambda: defaultdict(list))

        for entry in entries:
            daily_schedules[entry.class_group][entry.day].append(entry)

        gaps_resolved = 0

        for class_group, days in daily_schedules.items():
            for day, day_entries in days.items():
                if len(day_entries) > 1:
                    # Sort by period
                    day_entries.sort(key=lambda x: x.period)

                    # Find gaps
                    for i in range(len(day_entries) - 1):
                        gap_size = day_entries[i + 1].period - day_entries[i].period - 1
                        if gap_size > 0:
                            # Try to move the later entry to fill the gap
                            moved = self._move_entry_to_fill_gap(day_entries[i + 1], day_entries[i].period + 1)
                            if moved:
                                gaps_resolved += 1

        if gaps_resolved > 0:
            return {'action': f'Filled {gaps_resolved} schedule gaps'}
        return None

    def _find_available_slot_and_move(self, entry, all_entries):
        """Find an available time slot and move the entry"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        periods = range(1, 8)  # Assuming 7 periods max

        # Get occupied slots for this teacher
        teacher_slots = set()
        for e in all_entries:
            if e.teacher and e.teacher.id == entry.teacher.id and e.id != entry.id:
                teacher_slots.add(f"{e.day}-{e.period}")

        # Find available slot
        for day in days:
            for period in periods:
                slot_key = f"{day}-{period}"
                if slot_key not in teacher_slots:
                    # Check if room is available too
                    room_available = not any(
                        e.classroom and e.classroom.id == entry.classroom.id and
                        e.day == day and e.period == period and e.id != entry.id
                        for e in all_entries
                    )

                    if room_available:
                        # Move the entry
                        entry.day = day
                        entry.period = period
                        entry.save()
                        return True

        return False

    def _find_available_room_and_reassign(self, entry, day, period):
        """Find an available room and reassign the entry"""
        from .models import Classroom

        # Get all available classrooms
        all_rooms = Classroom.objects.all()

        print(f"Looking for available room for {entry.subject} on {day} period {period}")
        print(f"Current room: {entry.classroom.name if entry.classroom else 'None'}")

        # Find rooms not occupied at this time
        for room in all_rooms:
            room_occupied = TimetableEntry.objects.filter(
                classroom=room,
                day=day,
                period=period
            ).exclude(id=entry.id).exists()

            print(f"Checking room {room.name}: {'occupied' if room_occupied else 'available'}")

            if not room_occupied:
                old_room = entry.classroom.name if entry.classroom else 'None'
                entry.classroom = room
                entry.save()
                print(f"Successfully moved {entry.subject} from {old_room} to {room.name}")
                return True

        print(f"No available rooms found for {entry.subject}")
        return False

    def _resolve_senior_batch_lab_assignment(self, entries):
        """Resolve senior batch lab assignment by moving senior batches to labs"""
        from .models import Classroom

        violations_resolved = 0

        # Get all lab rooms (using name matching for labs)
        lab_rooms = Classroom.objects.filter(name__icontains='lab')

        if not lab_rooms.exists():
            print("No lab rooms found in the system")
            return None

        print(f"Found {lab_rooms.count()} lab rooms: {[lab.name for lab in lab_rooms]}")

        # Find senior batch entries not in labs
        senior_violations = []

        for entry in entries:
            if entry.classroom and entry.class_group:
                # Extract batch from class_group
                batch_name = entry.class_group.split('-')[0] if '-' in entry.class_group else entry.class_group

                try:
                    batch_year = int(batch_name[:2])
                    is_senior_batch = batch_year <= 22  # 21SW, 22SW are senior

                    if is_senior_batch:
                        classroom_name = entry.classroom.name.lower()
                        is_lab_room = 'lab' in classroom_name or 'laboratory' in classroom_name

                        if not is_lab_room:
                            senior_violations.append(entry)
                            print(f"Found senior violation: {batch_name} {entry.subject} in {entry.classroom.name} on {entry.day} P{entry.period}")

                except (ValueError, IndexError):
                    continue

        print(f"Found {len(senior_violations)} senior batch violations to resolve")

        # Try to resolve violations by moving to labs
        for entry in senior_violations:
            moved_to_lab = self._move_to_available_lab(entry, lab_rooms)
            if moved_to_lab:
                violations_resolved += 1
                batch_name = entry.class_group.split('-')[0]
                print(f"Successfully moved {batch_name} ({entry.subject}) to lab room")
            else:
                print(f"Failed to move {entry.class_group} ({entry.subject}) - no available labs")

        if violations_resolved > 0:
            return {'action': f'Moved {violations_resolved} senior batch classes to lab rooms'}
        else:
            return {'action': f'Attempted to resolve {len(senior_violations)} violations but no labs were available'}

    def _move_to_available_lab(self, entry, lab_rooms):
        """Move an entry to an available lab room, with smart swapping if needed"""

        # First, try to find a completely free lab
        for lab_room in lab_rooms:
            lab_occupied = TimetableEntry.objects.filter(
                classroom=lab_room,
                day=entry.day,
                period=entry.period
            ).exclude(id=entry.id).exists()

            if not lab_occupied:
                old_room = entry.classroom.name if entry.classroom else 'None'
                entry.classroom = lab_room
                entry.save()
                print(f"Moved {entry.class_group} from {old_room} to {lab_room.name} (free lab)")
                return True

        # If no free labs, try to swap with junior batches in labs
        for lab_room in lab_rooms:
            lab_occupant = TimetableEntry.objects.filter(
                classroom=lab_room,
                day=entry.day,
                period=entry.period
            ).exclude(id=entry.id).first()

            if lab_occupant and lab_occupant.class_group:
                # Check if occupant is a junior batch
                occupant_batch = lab_occupant.class_group.split('-')[0]
                try:
                    occupant_year = int(occupant_batch[:2])
                    is_occupant_junior = occupant_year > 22  # 23SW, 24SW are junior

                    # Only swap if occupant is junior and their subject is theory (not practical)
                    if is_occupant_junior and not lab_occupant.is_practical:
                        # Swap rooms: senior gets lab, junior gets regular room
                        old_senior_room = entry.classroom
                        old_junior_room = lab_occupant.classroom

                        entry.classroom = old_junior_room  # Senior gets lab
                        lab_occupant.classroom = old_senior_room  # Junior gets regular room

                        entry.save()
                        lab_occupant.save()

                        print(f"Swapped rooms: {entry.class_group} (senior) gets {old_junior_room.name}, {lab_occupant.class_group} (junior) gets {old_senior_room.name}")
                        return True

                except (ValueError, IndexError):
                    continue

        return False

    def _move_entry_to_fill_gap(self, entry, target_period):
        """Move an entry to a specific period to fill a gap"""
        # Check if target period is available for this teacher and room
        conflicts = TimetableEntry.objects.filter(
            day=entry.day,
            period=target_period
        ).filter(
            models.Q(teacher=entry.teacher) | models.Q(classroom=entry.classroom)
        ).exclude(id=entry.id)

        if not conflicts.exists():
            entry.period = target_period
            entry.save()
            return True

        return False

    def _resolve_room_double_booking(self, entries):
        """
        ENHANCED: Resolve room double-booking conflicts.
        Moves conflicting classes to available rooms while maintaining constraints.
        """
        try:
            from collections import defaultdict
            from .room_allocator import RoomAllocator

            room_allocator = RoomAllocator()
            room_schedule = defaultdict(list)
            conflicts_resolved = 0

            # Group entries by room, day, and period to find conflicts
            for entry in entries:
                if entry.classroom:
                    key = (entry.classroom.id, entry.day, entry.period)
                    room_schedule[key].append(entry)

            # Resolve conflicts
            for (room_id, day, period), room_entries in room_schedule.items():
                if len(room_entries) > 1:
                    # Keep the first entry, move others
                    entries_to_move = room_entries[1:]

                    for entry in entries_to_move:
                        # Find alternative room
                        if entry.subject and entry.subject.is_practical:
                            # Practical subjects need labs
                            alternative_room = room_allocator.allocate_room_for_practical(
                                day, period, entry.class_group, entry.subject, entries
                            )
                        else:
                            # Theory subjects can use regular rooms or labs
                            alternative_room = room_allocator.allocate_room_for_theory(
                                day, period, entry.class_group, entry.subject, entries
                            )

                        if alternative_room:
                            entry.classroom = alternative_room
                            entry.save()
                            conflicts_resolved += 1

            return {
                'action': f'Resolved {conflicts_resolved} room conflicts by moving classes to available rooms',
                'success': conflicts_resolved > 0,
                'changes_made': conflicts_resolved
            }

        except Exception as e:
            return {
                'action': f'Failed to resolve room conflicts: {str(e)}',
                'success': False,
                'changes_made': 0
            }

    def _resolve_practical_same_lab(self, entries):
        """
        ENHANCED: Resolve practical same-lab violations.
        Ensures all blocks of each practical use the same lab.
        """
        try:
            from collections import defaultdict
            from .room_allocator import RoomAllocator

            room_allocator = RoomAllocator()
            practical_groups = defaultdict(list)
            violations_resolved = 0

            # Group practical entries by class group and subject
            for entry in entries:
                if entry.subject and entry.subject.is_practical and entry.classroom:
                    key = (entry.class_group, entry.subject.code)
                    practical_groups[key].append(entry)

            # Fix violations using the enhanced consistency enforcement
            fixed_entries = room_allocator.ensure_practical_block_consistency(entries)

            # Count how many violations were fixed
            for (class_group, subject_code), group_entries in practical_groups.items():
                if len(group_entries) >= 2:
                    labs_used_before = set(entry.classroom.id for entry in group_entries)
                    if len(labs_used_before) > 1:
                        # Check if it's fixed now
                        current_entries = [e for e in fixed_entries
                                         if e.class_group == class_group and
                                         e.subject and e.subject.code == subject_code]
                        labs_used_after = set(entry.classroom.id for entry in current_entries
                                            if entry.classroom)
                        if len(labs_used_after) == 1:
                            violations_resolved += 1

            return {
                'action': f'Applied same-lab consistency enforcement, resolved {violations_resolved} violations',
                'success': violations_resolved > 0,
                'changes_made': violations_resolved
            }

        except Exception as e:
            return {
                'action': f'Failed to resolve same-lab violations: {str(e)}',
                'success': False,
                'changes_made': 0
            }





    def _analyze_theory_room_consistency(self, entries):
        """Analyze theory room consistency violations"""
        from collections import defaultdict

        violations = []
        section_daily_rooms = defaultdict(lambda: defaultdict(set))

        # Track rooms used by each section on each day for theory classes
        for entry in entries:
            if entry.subject and not entry.subject.is_practical and entry.classroom:
                section_daily_rooms[entry.class_group][entry.day].add(entry.classroom.name)

        # Check for inconsistencies
        for class_group, daily_rooms in section_daily_rooms.items():
            for day, rooms in daily_rooms.items():
                if len(rooms) > 1:
                    violations.append({
                        'class_group': class_group,
                        'day': day,
                        'rooms_used': list(rooms),
                        'description': f'{class_group} uses multiple rooms on {day}: {", ".join(rooms)}'
                    })

        return {
            'status': 'PASS' if len(violations) == 0 else 'FAIL',
            'total_violations': len(violations),
            'violations': violations,
            'message': f'Found {len(violations)} room consistency violations'
        }

    def _analyze_section_simultaneous_classes(self, entries):
        """Analyze sections with simultaneous classes"""
        from collections import defaultdict

        violations = []
        time_slot_sections = defaultdict(list)

        # Group entries by time slot
        for entry in entries:
            key = (entry.day, entry.period)
            time_slot_sections[key].append(entry)

        # Check for sections with multiple classes at same time
        for (day, period), slot_entries in time_slot_sections.items():
            section_counts = defaultdict(int)
            for entry in slot_entries:
                section_counts[entry.class_group] += 1

            for class_group, count in section_counts.items():
                if count > 1:
                    violations.append({
                        'class_group': class_group,
                        'day': day,
                        'period': period,
                        'simultaneous_classes': count,
                        'description': f'{class_group} has {count} simultaneous classes on {day} P{period}'
                    })

        return {
            'status': 'PASS' if len(violations) == 0 else 'FAIL',
            'total_violations': len(violations),
            'violations': violations,
            'message': f'Found {len(violations)} simultaneous class violations'
        }

    def _analyze_working_hours_compliance(self, entries):
        """Analyze working hours compliance (8AM-3PM)"""
        violations = []

        for entry in entries:
            if entry.start_time and entry.end_time:
                start_hour = int(entry.start_time.split(':')[0])
                end_hour = int(entry.end_time.split(':')[0])

                if start_hour < 8 or end_hour > 15:
                    violations.append({
                        'class_group': entry.class_group,
                        'subject': entry.subject.code if entry.subject else 'Unknown',
                        'day': entry.day,
                        'period': entry.period,
                        'start_time': entry.start_time,
                        'end_time': entry.end_time,
                        'description': f'Class {entry.start_time}-{entry.end_time} outside 8AM-3PM'
                    })

        return {
            'status': 'PASS' if len(violations) == 0 else 'FAIL',
            'total_violations': len(violations),
            'violations': violations,
            'message': f'Found {len(violations)} working hours violations'
        }

    # Additional constraint resolution methods for new constraint types
    def _resolve_practical_in_labs_only(self, entries):
        """Resolve practical subjects not in labs by moving them to available labs"""
        from .room_allocator import RoomAllocator

        room_allocator = RoomAllocator()
        resolved_count = 0

        for entry in entries:
            if (entry.subject and entry.subject.is_practical and
                entry.classroom and not entry.classroom.is_lab):

                # Find an available lab for this practical
                available_lab = room_allocator.allocate_room_for_practical(
                    entry.day, entry.period, entry.class_group, entry.subject, entries
                )

                if available_lab:
                    entry.classroom = available_lab
                    entry.save()
                    resolved_count += 1

        return {
            'action': f'Moved {resolved_count} practical subjects to labs',
            'success': resolved_count > 0,
            'changes_made': resolved_count
        } if resolved_count > 0 else None



    def _resolve_theory_room_consistency(self, entries):
        """Resolve theory room consistency by assigning consistent rooms per section per day"""
        from collections import defaultdict

        resolved_count = 0
        section_daily_rooms = defaultdict(lambda: defaultdict(list))

        # Group theory entries by section and day
        for entry in entries:
            if entry.subject and not entry.subject.is_practical:
                section_daily_rooms[entry.class_group][entry.day].append(entry)

        # Fix inconsistencies
        for class_group, daily_entries in section_daily_rooms.items():
            for day, day_entries in daily_entries.items():
                if len(day_entries) > 1:
                    # Use the first entry's room as the standard
                    standard_room = day_entries[0].classroom

                    for entry in day_entries[1:]:
                        if entry.classroom != standard_room:
                            # Check if standard room is available for this period
                            conflicts = TimetableEntry.objects.filter(
                                day=entry.day,
                                period=entry.period,
                                classroom=standard_room
                            ).exclude(id=entry.id)

                            if not conflicts.exists():
                                entry.classroom = standard_room
                                entry.save()
                                resolved_count += 1

        return {
            'action': f'Standardized {resolved_count} room assignments for consistency',
            'success': resolved_count > 0,
            'changes_made': resolved_count
        } if resolved_count > 0 else None

    def _resolve_section_simultaneous_classes(self, entries):
        """Resolve sections with simultaneous classes by moving one of the conflicting classes"""
        from collections import defaultdict

        resolved_count = 0
        time_slot_sections = defaultdict(list)

        # Group entries by time slot
        for entry in entries:
            key = (entry.day, entry.period)
            time_slot_sections[key].append(entry)

        # Find and resolve conflicts
        for (day, period), slot_entries in time_slot_sections.items():
            section_entries = defaultdict(list)
            for entry in slot_entries:
                section_entries[entry.class_group].append(entry)

            for class_group, group_entries in section_entries.items():
                if len(group_entries) > 1:
                    # Move all but the first entry
                    for entry in group_entries[1:]:
                        moved = self._find_available_slot_and_move(entry, entries)
                        if moved:
                            resolved_count += 1

        return {
            'action': f'Moved {resolved_count} simultaneous classes to different time slots',
            'success': resolved_count > 0,
            'changes_made': resolved_count
        } if resolved_count > 0 else None

    def _resolve_working_hours_compliance(self, entries):
        """Resolve working hours violations by moving classes to valid time slots"""
        resolved_count = 0

        for entry in entries:
            if entry.start_time and entry.end_time:
                start_hour = int(entry.start_time.split(':')[0])
                end_hour = int(entry.end_time.split(':')[0])

                if start_hour < 8 or end_hour > 15:
                    # Try to move to a valid time slot (periods 1-7, 8AM-3PM)
                    for period in range(1, 8):
                        # Check if this period is within working hours
                        if 8 <= (7 + period) <= 15:  # Assuming period 1 starts at 8AM
                            # Check if slot is available
                            conflicts = TimetableEntry.objects.filter(
                                day=entry.day,
                                period=period,
                                teacher=entry.teacher,
                                classroom=entry.classroom
                            ).exclude(id=entry.id)

                            if not conflicts.exists():
                                entry.period = period
                                entry.save()
                                resolved_count += 1
                                break

        return {
            'action': f'Moved {resolved_count} classes to valid working hours',
            'success': resolved_count > 0,
            'changes_made': resolved_count
        } if resolved_count > 0 else None

    def _resolve_max_theory_per_day(self, entries):
        """Resolve multiple theory classes per day by moving excess classes to other days"""
        from collections import defaultdict

        resolved_count = 0
        section_daily_theory = defaultdict(lambda: defaultdict(list))

        # Group theory classes by section and day
        for entry in entries:
            if entry.subject and not entry.subject.is_practical:
                section_daily_theory[entry.class_group][entry.day].append(entry)

        # Resolve violations
        for class_group, daily_classes in section_daily_theory.items():
            for day, theory_classes in daily_classes.items():
                if len(theory_classes) > 1:
                    # Keep the first class, move others to different days
                    for entry in theory_classes[1:]:
                        moved = self._move_to_different_day(entry, entries)
                        if moved:
                            resolved_count += 1

        return {
            'action': f'Moved {resolved_count} excess theory classes to different days',
            'success': resolved_count > 0,
            'changes_made': resolved_count
        } if resolved_count > 0 else None

    def _resolve_minimum_daily_classes(self, entries):
        """Resolve minimum daily classes violations by redistributing classes"""
        # This is complex and may require adding classes, which is beyond simple resolution
        return {
            'action': 'Minimum daily classes constraint requires schedule regeneration',
            'success': False,
            'changes_made': 0
        }

    def _resolve_teacher_assignments(self, entries):
        """Resolve teacher assignment violations by reassigning teachers"""
        from timetable.models import TeacherSubjectAssignment

        resolved_count = 0

        for entry in entries:
            if entry.teacher and entry.subject:
                # Check if teacher is assigned to this subject
                assignments = TeacherSubjectAssignment.objects.filter(
                    teacher=entry.teacher,
                    subject=entry.subject
                )

                if not assignments.exists():
                    # Find a teacher who is assigned to this subject
                    valid_assignments = TeacherSubjectAssignment.objects.filter(
                        subject=entry.subject
                    )

                    for assignment in valid_assignments:
                        # Check if this teacher is available at this time
                        conflicts = TimetableEntry.objects.filter(
                            day=entry.day,
                            period=entry.period,
                            teacher=assignment.teacher
                        ).exclude(id=entry.id)

                        if not conflicts.exists():
                            entry.teacher = assignment.teacher
                            entry.save()
                            resolved_count += 1
                            break

        return {
            'action': f'Reassigned {resolved_count} teachers to their designated subjects',
            'success': resolved_count > 0,
            'changes_made': resolved_count
        } if resolved_count > 0 else None

    def _resolve_friday_aware_scheduling(self, entries):
        """Resolve Friday-aware scheduling violations"""
        # This is a quality constraint that's hard to resolve automatically
        return {
            'action': 'Friday-aware scheduling requires comprehensive schedule review',
            'success': False,
            'changes_made': 0
        }

    def _move_to_different_day(self, entry, entries):
        """Move an entry to a different day"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        current_day = entry.day

        for day in days:
            if day != current_day:
                # Check if teacher and room are available on this day at same period
                conflicts = TimetableEntry.objects.filter(
                    day=day,
                    period=entry.period
                ).filter(
                    models.Q(teacher=entry.teacher) | models.Q(classroom=entry.classroom)
                ).exclude(id=entry.id)

                if not conflicts.exists():
                    entry.day = day
                    entry.save()
                    return True

        return False


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing departments"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter departments based on user's access"""
        user = self.request.user
        if user.is_superuser:
            return Department.objects.all()
        
        # Get user's department
        try:
            user_dept = UserDepartment.objects.get(user=user, is_active=True)
            return Department.objects.filter(id=user_dept.department.id)
        except UserDepartment.DoesNotExist:
            return Department.objects.none()


class UserDepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user-department relationships"""
    queryset = UserDepartment.objects.all()
    serializer_class = UserDepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter based on user's access"""
        user = self.request.user
        if user.is_superuser:
            return UserDepartment.objects.all()
        
        # Get user's department
        try:
            user_dept = UserDepartment.objects.get(user=user, is_active=True)
            return UserDepartment.objects.filter(department=user_dept.department)
        except UserDepartment.DoesNotExist:
            return UserDepartment.objects.none()


"""SharedAccess endpoints are disabled intentionally."""


# Mixin for data isolation
class DepartmentDataMixin:
    """Mixin to filter data based on user's department and shared access"""
    
    def get_user_department(self, user):
        """Get the department for a user"""
        try:
            return UserDepartment.objects.get(user=user, is_active=True).department
        except UserDepartment.DoesNotExist:
            return None
    
    def get_accessible_departments(self, user):
        """Get all departments a user can access (own + shared)"""
        departments = set()
        
        # User's own department
        own_dept = self.get_user_department(user)
        if own_dept:
            departments.add(own_dept.id)
        # SharedAccess disabled: do not filter by shared access
        
        return list(departments)
    
    def filter_by_department_access(self, queryset, user):
        """Filter queryset based on user's department access and shared access permissions"""
        if user.is_superuser:
            return queryset
        
        accessible_depts = self.get_accessible_departments(user)
        if not accessible_depts:
            # No department mapping: do not restrict data visibility
            return queryset
        
        # Start with user's own department data
        queryset = queryset.filter(department_id__in=accessible_depts)
        
        # Include user's own unassigned data too (in case some rows have no department)
        queryset = queryset | self.model.objects.filter(owner=user, department__isnull=True)
        
        return queryset


# Update existing ViewSets to use the mixin
class SubjectViewSet(DepartmentDataMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter subjects based on user's department access"""
        queryset = super().get_queryset()
        return self.filter_by_department_access(queryset, self.request.user)

    def perform_create(self, serializer):
        """Set department and owner when creating"""
        user = self.request.user
        user_dept = self.get_user_department(user)
        if user_dept:
            serializer.save(department=user_dept, owner=user)
        else:
            serializer.save(owner=user)


class TeacherViewSet(DepartmentDataMixin, viewsets.ModelViewSet):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter teachers based on user's department access"""
        queryset = super().get_queryset()
        return self.filter_by_department_access(queryset, self.request.user)

    def perform_create(self, serializer):
        """Set department and owner when creating"""
        user = self.request.user
        user_dept = self.get_user_department(user)
        if user_dept:
            serializer.save(department=user_dept, owner=user)
        else:
            serializer.save(owner=user)


class ClassroomViewSet(DepartmentDataMixin, viewsets.ModelViewSet):
    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter classrooms based on user's department access"""
        queryset = super().get_queryset()
        return self.filter_by_department_access(queryset, self.request.user)

    def perform_create(self, serializer):
        """Set department and owner when creating"""
        user = self.request.user
        user_dept = self.get_user_department(user)
        if user_dept:
            serializer.save(department=user_dept, owner=user)
        else:
            serializer.save(owner=user)


class ScheduleConfigViewSet(DepartmentDataMixin, viewsets.ModelViewSet):
    queryset = ScheduleConfig.objects.all()
    serializer_class = ScheduleConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter configs based on user's department access"""
        queryset = super().get_queryset()
        return self.filter_by_department_access(queryset, self.request.user)

    def perform_create(self, serializer):
        """Set department and owner when creating"""
        user = self.request.user
        user_dept = self.get_user_department(user)
        if user_dept:
            serializer.save(department=user_dept, owner=user)
        else:
            serializer.save(owner=user)


class BatchViewSet(DepartmentDataMixin, viewsets.ModelViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter batches based on user's department access"""
        queryset = super().get_queryset()
        return self.filter_by_department_access(queryset, self.request.user)

    def perform_create(self, serializer):
        """Set department and owner when creating"""
        user = self.request.user
        user_dept = self.get_user_department(user)
        if user_dept:
            serializer.save(department=user_dept, owner=user)
        else:
            serializer.save(owner=user)


class TimetableEntryViewSet(DepartmentDataMixin, viewsets.ModelViewSet):
    queryset = TimetableEntry.objects.all()
    serializer_class = TimetableEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter entries based on user's department access"""
        queryset = super().get_queryset()
        return self.filter_by_department_access(queryset, self.request.user)

    def perform_create(self, serializer):
        """Set department and owner when creating"""
        user = self.request.user
        user_dept = self.get_user_department(user)
        if user_dept:
            serializer.save(department=user_dept, owner=user)
        else:
            serializer.save(owner=user)

    @action(detail=True, methods=['get'], url_path='safe-moves', permission_classes=[AllowAny])
    def safe_moves(self, request, pk=None):
        """Return a list of safe (day, period) slots for this entry.
        Per request: consider ALL blank slots for this section, then include those
        where THIS entry's teacher has no class anywhere (any section/batch) at that time.
        """
        try:
            entry = self.get_object()
            teacher = entry.teacher
            subject = entry.subject

            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config:
                return Response({'safe_slots': []})

            # Determine max periods
            try:
                max_periods = len(config.periods)
            except Exception:
                max_periods = TimetableEntry.objects.aggregate(models.Max('period')).get('period__max') or 8

            days = list(config.days)

            # Helper checks using DB queries to always reflect current state
            def is_slot_blank_for_section(day: str, period: int) -> bool:
                return not TimetableEntry.objects.filter(
                    class_group=entry.class_group, day=day, period=period
                ).exclude(id=entry.id).exists()

            def teacher_is_free(day: str, period: int) -> bool:
                if not teacher:
                    return True
                return not TimetableEntry.objects.filter(
                    teacher=teacher, day=day, period=period
                ).exclude(id=entry.id).exists()

            def duplicate_theory_same_day_with_same_teacher(day: str) -> bool:
                # Disallow scheduling the same theory subject more than once per day
                # for the same section with the same teacher
                if not subject or getattr(subject, 'is_practical', False) or not teacher:
                    return False
                return TimetableEntry.objects.filter(
                    class_group=entry.class_group,
                    day=day,
                    subject=subject,
                    teacher=teacher
                ).exclude(id=entry.id).exists()

            safe = []
            for day in days:
                for period in range(1, max_periods + 1):
                    if not is_slot_blank_for_section(day, period):
                        continue
                    if not teacher_is_free(day, period):
                        continue
                    if duplicate_theory_same_day_with_same_teacher(day):
                        continue
                    safe.append({'day': day, 'period': period})

            return Response({'safe_slots': safe})
        except Exception as e:
            logger.exception("Failed to compute safe moves: %s", e)
            return Response({'detail': 'Failed to compute safe slots'}, status=500)

    @action(detail=True, methods=['post'], url_path='move', permission_classes=[AllowAny])
    def move(self, request, pk=None):
        """Move an entry to a new day/period. If the requested slot is free for the
        same class_group, and the entry's teacher is free at that time across all
        sections/batches, perform the move.
        """
        try:
            entry = self.get_object()
            day = request.data.get('day')
            period = request.data.get('period')
            if not day or not period:
                return Response({'detail': 'day and period are required'}, status=400)

            try:
                period = int(period)
            except Exception:
                return Response({'detail': 'period must be an integer'}, status=400)

            # Enforce same checks as safe-moves to guarantee no issues
            conflict_for_section = TimetableEntry.objects.filter(
                class_group=entry.class_group, day=day, period=period
            ).exclude(id=entry.id).exists()
            if conflict_for_section:
                return Response({'detail': 'Target slot already occupied for this section'}, status=400)

            if entry.teacher and TimetableEntry.objects.filter(
                teacher=entry.teacher, day=day, period=period
            ).exclude(id=entry.id).exists():
                return Response({'detail': 'Teacher is not available at the target time'}, status=400)

            if entry.classroom and TimetableEntry.objects.filter(
                classroom=entry.classroom, day=day, period=period
            ).exclude(id=entry.id).exists():
                return Response({'detail': 'Room is not available at the target time'}, status=400)

            # Enforce duplicate theory same day with same teacher as well
            if entry.subject and not entry.is_practical and entry.teacher:
                dup_same_day = TimetableEntry.objects.filter(
                    class_group=entry.class_group,
                    day=day,
                    subject=entry.subject,
                    teacher=entry.teacher
                ).exclude(id=entry.id).exists()
                if dup_same_day:
                    return Response({'detail': 'Duplicate theory class with same teacher on same day is not allowed'}, status=400)

            entry.day = day
            entry.period = period
            entry.save(update_fields=['day', 'period'])
            return Response({'success': True})
        except Exception as e:
            logger.exception("Failed to move slot: %s", e)
            return Response({'detail': 'Move failed'}, status=500)


class TeacherSubjectAssignmentViewSet(DepartmentDataMixin, viewsets.ModelViewSet):
    queryset = TeacherSubjectAssignment.objects.all()
    serializer_class = TeacherSubjectAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter assignments based on user's department access"""
        queryset = super().get_queryset()
        # Filter by department through related models
        accessible_depts = self.get_accessible_departments(self.request.user)
        # If the user has no department mapping, do not hide data
        # Keep consistent with other viewsets behavior
        if not accessible_depts:
            return queryset
        
        return queryset.filter(
            models.Q(teacher__department_id__in=accessible_depts) |
            models.Q(subject__department_id__in=accessible_depts) |
            models.Q(batch__department_id__in=accessible_depts)
        )

    def perform_create(self, serializer):
        """Validate department consistency when creating"""
        user = self.request.user
        user_dept = self.get_user_department(user)
        
        # Check if all related objects belong to the same department
        teacher = serializer.validated_data.get('teacher')
        subject = serializer.validated_data.get('subject')
        batch = serializer.validated_data.get('batch')
        
        if user_dept:
            # Ensure all objects belong to user's department
            if teacher and hasattr(teacher, 'department') and teacher.department != user_dept:
                raise serializers.ValidationError("Teacher must belong to your department")
            if subject and hasattr(subject, 'department') and subject.department != user_dept:
                raise serializers.ValidationError("Subject must belong to your department")
            if batch and hasattr(batch, 'department') and batch.department != user_dept:
                raise serializers.ValidationError("Batch must belong to your department")
        
        serializer.save()


class DataManagementView(APIView):
    """API endpoints for data management operations"""
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, action=None):
        """Handle DELETE requests for different deletion operations"""
        if action == 'timetable':
            return self.delete_timetable(request)
        elif action == 'all_data':
            return self.delete_all_data(request)
        elif action == 'batches':
            return self.delete_batches(request)
        elif action == 'subjects':
            return self.delete_subjects(request)
        elif action == 'teachers':
            return self.delete_teachers(request)
        elif action == 'classrooms':
            return self.delete_classrooms(request)
        elif action == 'teacher_assignments':
            return self.delete_teacher_assignments(request)
        else:
            return Response({
                'success': False,
                'error': 'Invalid action specified'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        """Handle GET requests for data counts"""
        return self.get_data_counts(request)
    
    def delete_timetable(self, request):
        """Delete all timetable entries"""
        try:
            count = TimetableEntry.objects.count()
            TimetableEntry.objects.all().delete()
            
            return Response({
                'success': True,
                'message': f'Successfully deleted {count} timetable entries',
                'deleted_count': count
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete_all_data(self, request):
        """Delete all data from the database"""
        try:
            # Count before deletion
            counts_before = {
                'timetable_entries': TimetableEntry.objects.count(),
                'teacher_assignments': TeacherSubjectAssignment.objects.count(),
                'teachers': Teacher.objects.count(),
                'subjects': Subject.objects.count(),
                'classrooms': Classroom.objects.count(),
                'schedule_configs': ScheduleConfig.objects.count(),
                'configs': Config.objects.count(),
                'class_groups': ClassGroup.objects.count(),
                'batches': Batch.objects.count(),
            }
            
            # Delete in reverse dependency order
            TimetableEntry.objects.all().delete()
            TeacherSubjectAssignment.objects.all().delete()
            Teacher.objects.all().delete()
            Subject.objects.all().delete()
            Classroom.objects.all().delete()
            ScheduleConfig.objects.all().delete()
            Config.objects.all().delete()
            ClassGroup.objects.all().delete()
            Batch.objects.all().delete()
            
            return Response({
                'success': True,
                'message': 'Successfully deleted all data',
                'deleted_counts': counts_before
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete_batches(self, request):
        """Delete all batches and related data"""
        try:
            batch_count = Batch.objects.count()
            assignment_count = TeacherSubjectAssignment.objects.count()
            timetable_count = TimetableEntry.objects.count()
            
            # Delete in order to handle foreign key relationships
            TimetableEntry.objects.all().delete()
            TeacherSubjectAssignment.objects.all().delete()
            Batch.objects.all().delete()
            
            return Response({
                'success': True,
                'message': f'Successfully deleted {batch_count} batches and related data',
                'deleted_counts': {
                    'batches': batch_count,
                    'teacher_assignments': assignment_count,
                    'timetable_entries': timetable_count
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete_subjects(self, request):
        """Delete all subjects and related data"""
        try:
            subject_count = Subject.objects.count()
            assignment_count = TeacherSubjectAssignment.objects.count()
            timetable_count = TimetableEntry.objects.count()
            
            # Delete in order to handle foreign key relationships
            TimetableEntry.objects.all().delete()
            TeacherSubjectAssignment.objects.all().delete()
            Subject.objects.all().delete()
            
            return Response({
                'success': True,
                'message': f'Successfully deleted {subject_count} subjects and related data',
                'deleted_counts': {
                    'subjects': subject_count,
                    'teacher_assignments': assignment_count,
                    'timetable_entries': timetable_count
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete_teachers(self, request):
        """Delete all teachers and related data"""
        try:
            teacher_count = Teacher.objects.count()
            assignment_count = TeacherSubjectAssignment.objects.count()
            timetable_count = TimetableEntry.objects.count()
            
            # Delete in order to handle foreign key relationships
            TimetableEntry.objects.all().delete()
            TeacherSubjectAssignment.objects.all().delete()
            Teacher.objects.all().delete()
            
            return Response({
                'success': True,
                'message': f'Successfully deleted {teacher_count} teachers and related data',
                'deleted_counts': {
                    'teachers': teacher_count,
                    'teacher_assignments': assignment_count,
                    'timetable_entries': timetable_count
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete_classrooms(self, request):
        """Delete all classrooms and related data"""
        try:
            classroom_count = Classroom.objects.count()
            timetable_count = TimetableEntry.objects.count()
            
            # Delete in order to handle foreign key relationships
            TimetableEntry.objects.all().delete()
            Classroom.objects.all().delete()
            
            return Response({
                'success': True,
                'message': f'Successfully deleted {classroom_count} classrooms and related data',
                'deleted_counts': {
                    'classrooms': classroom_count,
                    'timetable_entries': timetable_count
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete_teacher_assignments(self, request):
        """Delete all teacher assignments and related data"""
        try:
            assignment_count = TeacherSubjectAssignment.objects.count()
            timetable_count = TimetableEntry.objects.count()
            
            # Delete in order to handle foreign key relationships
            TimetableEntry.objects.all().delete()
            TeacherSubjectAssignment.objects.all().delete()
            
            return Response({
                'success': True,
                'message': f'Successfully deleted {assignment_count} teacher assignments and related data',
                'deleted_counts': {
                    'teacher_assignments': assignment_count,
                    'timetable_entries': timetable_count
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_data_counts(self, request):
        """Get current data counts for all models"""
        try:
            counts = {
                'timetable_entries': TimetableEntry.objects.count(),
                'teacher_assignments': TeacherSubjectAssignment.objects.count(),
                'teachers': Teacher.objects.count(),
                'subjects': Subject.objects.count(),
                'classrooms': Classroom.objects.count(),
                'schedule_configs': ScheduleConfig.objects.count(),
                'configs': Config.objects.count(),
                'class_groups': ClassGroup.objects.count(),
                'batches': Batch.objects.count(),
                'departments': Department.objects.count(),
                'user_departments': UserDepartment.objects.count(),
            }
            
            return Response({
                'success': True,
                'counts': counts
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConsolidatedSchedulingView(APIView):
    """
    CONSOLIDATED SCHEDULING API
    ===========================
    Uses the new scheduling orchestrator for zero-violation timetable generation.
    This is the NEW MASTER ENDPOINT that consolidates all scheduling logic.
    """
    
    permission_classes = [AllowAny]  # Adjust as needed
    
    def post(self, request):
        """
        Generate timetable using the consolidated scheduling orchestrator.
        Ensures ZERO constraint violations, especially same-lab rule for practicals.
        """
        try:
            batch_ids = request.data.get('batch_ids', None)  # Optional: specific batches
            verbose = request.data.get('verbose', True)  # Control logging output
            
            # Get the consolidated orchestrator
            orchestrator = get_scheduling_orchestrator(verbose=verbose)
            
            # Generate complete timetable with zero violations
            result = orchestrator.generate_complete_timetable(batch_ids=batch_ids)
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': 'CONSOLIDATED SCHEDULING COMPLETED SUCCESSFULLY',
                    'data': {
                        'entries_generated': result['entries_count'],
                        'same_lab_violations_fixed': result['scheduling_stats']['same_lab_violations_fixed'],
                        'room_conflicts_resolved': result['scheduling_stats']['room_conflicts_resolved'],
                        'constraint_compliance': result['final_report']['constraint_compliance'],
                        'same_lab_compliance_percentage': result['final_report']['same_lab_compliance'],
                        'total_violations': result['final_report']['total_violations'],
                        'scheduling_stats': result['scheduling_stats'],
                        'validation_summary': result['validation_result'],
                        'final_report': result['final_report']
                    },
                    'orchestrator_used': True,
                    'consolidated_approach': True
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'CONSOLIDATED SCHEDULING FAILED',
                    'error': result['message'],
                    'error_details': result.get('error_details', 'No additional details'),
                    'orchestrator_used': True
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Consolidated scheduling API error: {str(e)}")
            return Response({
                'success': False,
                'message': 'CONSOLIDATED SCHEDULING API ERROR',
                'error': str(e),
                'orchestrator_used': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """
        Validate current schedule using consolidated constraint enforcement.
        """
        try:
            verbose = request.query_params.get('verbose', 'true').lower() == 'true'
            
            # Get the orchestrator
            orchestrator = get_scheduling_orchestrator(verbose=verbose)
            
            # Validate current schedule
            validation_result = orchestrator.validate_current_schedule()
            
            return Response({
                'success': True,
                'message': 'SCHEDULE VALIDATION COMPLETED',
                'data': {
                    'overall_compliance': validation_result['overall_compliance'],
                    'total_violations': validation_result['total_violations'],
                    'constraint_details': validation_result.get('enhanced', {}),
                    'same_lab_violations': self._count_same_lab_violations(validation_result),
                },
                'validation_timestamp': datetime.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Schedule validation error: {str(e)}")
            return Response({
                'success': False,
                'message': 'SCHEDULE VALIDATION FAILED',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request):
        """
        Fix constraint violations in current schedule.
        """
        try:
            verbose = request.data.get('verbose', True)
            
            # Get the orchestrator
            orchestrator = get_scheduling_orchestrator(verbose=verbose)
            
            # Fix constraint violations
            fix_result = orchestrator.fix_constraint_violations()
            
            return Response({
                'success': fix_result['success'],
                'message': 'CONSTRAINT VIOLATION FIXES APPLIED',
                'data': {
                    'fixes_applied': fix_result.get('actions', []),
                    'total_fixes': len(fix_result.get('actions', [])),
                },
                'fix_timestamp': datetime.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Constraint fix error: {str(e)}")
            return Response({
                'success': False,
                'message': 'CONSTRAINT FIX FAILED',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _count_same_lab_violations(self, validation_result: Dict[str, Any]) -> int:
        """Count same-lab rule violations from validation result."""
        try:
            enhanced_results = validation_result.get('enhanced', {})
            violations_by_constraint = enhanced_results.get('violations_by_constraint', {})
            same_lab_violations = violations_by_constraint.get('Same Lab Rule', [])
            return len(same_lab_violations)
        except:
            return 0

