from celery import shared_task
from django.db import transaction
from django.utils import timezone
import logging
from .models import TimetableEntry, ScheduleConfig, Subject, Teacher, Classroom
from .algorithms.advanced_scheduler import AdvancedTimetableScheduler
from .constraint_manager import ConstraintManager
import json

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def generate_timetable_async(self, config_id=None, constraints=None):
    """
    Asynchronous timetable generation task with progress tracking.
    
    Args:
        config_id: ID of the ScheduleConfig to use
        constraints: List of constraint definitions
    
    Returns:
        Dict containing generation results and statistics
    """
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': 100,
                'status': 'Initializing scheduler...'
            }
        )
        
        # Get configuration
        if config_id:
            config = ScheduleConfig.objects.filter(id=config_id, start_time__isnull=False).first()
        else:
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
        print("Loaded config:", config)
        print("Config start_time:", getattr(config, 'start_time', None))
        if not config or not config.start_time:
            return {
                'success': False,
                'error': 'No valid schedule configuration found.'
            }
        
        # Update constraints if provided
        if constraints:
            config.constraints = constraints
            config.save()
        
        # Initialize constraint manager
        constraint_manager = ConstraintManager(config)
        if not constraint_manager.validate_constraints():
            return {
                'success': False,
                'error': 'Constraint validation failed',
                'validation_errors': constraint_manager.validation_errors
            }
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 20,
                'total': 100,
                'status': 'Initializing genetic algorithm...'
            }
        )
        
        # Initialize advanced scheduler
        scheduler = AdvancedTimetableScheduler(config)
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 40,
                'total': 100,
                'status': 'Generating timetable with genetic algorithm...'
            }
        )
        
        # Generate timetable
        result = scheduler.generate_timetable()
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 80,
                'total': 100,
                'status': 'Saving timetable to database...'
            }
        )
        
        # Save to database
        with transaction.atomic():
            # Clear existing entries
            TimetableEntry.objects.all().delete()
            
            # Create new entries
            entries_to_create = []
            missing_data_warnings = []
            for entry_data in result['entries']:
                subject_name = entry_data['subject'].replace(' (PR)', '')
                subject = Subject.objects.filter(name=subject_name).first()
                teacher = Teacher.objects.filter(name=entry_data['teacher']).first()
                classroom = Classroom.objects.filter(name=entry_data['classroom']).first()
                
                if not subject or not teacher or not classroom:
                    warning = f"Missing: {'subject' if not subject else ''} {'teacher' if not teacher else ''} {'classroom' if not classroom else ''} for entry: {entry_data}"
                    missing_data_warnings.append(warning)
                
                entry = TimetableEntry(
                    day=entry_data['day'],
                    period=entry_data['period'],
                    subject=subject,
                    teacher=teacher,
                    classroom=classroom,
                    class_group=entry_data['class_group'],
                    start_time=entry_data['start_time'],
                    end_time=entry_data['end_time'],
                    is_practical=entry_data['is_practical']
                )
                entries_to_create.append(entry)
            # Bulk create entries (only those with at least a subject)
            if entries_to_create:
                TimetableEntry.objects.bulk_create(entries_to_create)
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 100,
                'total': 100,
                'status': 'Timetable generation completed successfully'
            }
        )
        
        # Return comprehensive result
        return {
            'success': True,
            'generation_time': result.get('generation_time', 0),
            'fitness_score': result.get('fitness_score', 0),
            'constraint_violations': result.get('constraint_violations', []),
            'generation': result.get('generation', 0),
            'entries_count': len(result.get('entries', [])),
            'constraint_summary': constraint_manager.get_constraint_summary(),
            'status': 'completed',
            'warnings': missing_data_warnings
        }
        
    except ScheduleConfig.DoesNotExist:
        return {
            'success': False,
            'error': 'No schedule configuration found'
        }
    except Exception as e:
        logger.error(f"Timetable generation failed: {str(e)}")
        return {
            'success': False,
            'error': f'Timetable generation failed: {str(e)}'
        }

@shared_task(bind=True)
def validate_constraints_async(self, config_id=None, constraints=None):
    """
    Asynchronous constraint validation task.
    
    Args:
        config_id: ID of the ScheduleConfig to use
        constraints: List of constraint definitions
    
    Returns:
        Dict containing validation results
    """
    try:
        # Get configuration
        if config_id:
            config = ScheduleConfig.objects.filter(id=config_id, start_time__isnull=False).first()
        else:
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
        print("Loaded config:", config)
        print("Config start_time:", getattr(config, 'start_time', None))
        if not config or not config.start_time:
            return {
                'success': False,
                'error': 'No valid schedule configuration found.'
            }
        
        # Update constraints if provided
        if constraints:
            config.constraints = constraints
            config.save()
        
        # Initialize constraint manager
        constraint_manager = ConstraintManager(config)
        
        # Validate constraints
        is_valid = constraint_manager.validate_constraints()
        
        return {
            'success': is_valid,
            'validation_errors': constraint_manager.validation_errors,
            'constraint_summary': constraint_manager.get_constraint_summary(),
            'constraints': constraint_manager.export_constraints()
        }
        
    except ScheduleConfig.DoesNotExist:
        return {
            'success': False,
            'error': 'No schedule configuration found'
        }
    except Exception as e:
        logger.error(f"Constraint validation failed: {str(e)}")
        return {
            'success': False,
            'error': f'Constraint validation failed: {str(e)}'
        }

@shared_task(bind=True)
def optimize_timetable_async(self, config_id=None, optimization_params=None):
    """
    Asynchronous timetable optimization task.
    
    Args:
        config_id: ID of the ScheduleConfig to use
        optimization_params: Dictionary of optimization parameters
    
    Returns:
        Dict containing optimization results
    """
    try:
        # Get configuration
        if config_id:
            config = ScheduleConfig.objects.filter(id=config_id, start_time__isnull=False).first()
        else:
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
        print("Loaded config:", config)
        print("Config start_time:", getattr(config, 'start_time', None))
        if not config or not config.start_time:
            return {
                'success': False,
                'error': 'No valid schedule configuration found.'
            }
        
        # Set optimization parameters
        if optimization_params:
            # Update scheduler parameters based on optimization_params
            pass
        
        # Initialize scheduler
        scheduler = AdvancedTimetableScheduler(config)
        
        # Run optimization with different parameters
        optimization_results = []
        
        # Try different genetic algorithm parameters
        parameter_sets = [
            {'population_size': 30, 'generations': 50, 'mutation_rate': 0.15},
            {'population_size': 50, 'generations': 100, 'mutation_rate': 0.1},
            {'population_size': 100, 'generations': 150, 'mutation_rate': 0.05}
        ]
        
        for i, params in enumerate(parameter_sets):
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': (i * 100) // len(parameter_sets),
                    'total': 100,
                    'status': f'Running optimization with parameters {i+1}/{len(parameter_sets)}...'
                }
            )
            
            # Update scheduler parameters
            scheduler.population_size = params['population_size']
            scheduler.generations = params['generations']
            scheduler.mutation_rate = params['mutation_rate']
            
            # Generate timetable
            result = scheduler.generate_timetable()
            
            optimization_results.append({
                'parameters': params,
                'fitness_score': result.get('fitness_score', 0),
                'generation_time': result.get('generation_time', 0),
                'constraint_violations': result.get('constraint_violations', []),
                'generation': result.get('generation', 0)
            })
        
        # Find best result
        best_result = max(optimization_results, key=lambda x: x['fitness_score'])
        
        return {
            'success': True,
            'best_result': best_result,
            'all_results': optimization_results,
            'status': 'completed'
        }
        
    except ScheduleConfig.DoesNotExist:
        return {
            'success': False,
            'error': 'No schedule configuration found'
        }
    except Exception as e:
        logger.error(f"Timetable optimization failed: {str(e)}")
        return {
            'success': False,
            'error': f'Timetable optimization failed: {str(e)}'
        }

@shared_task
def cleanup_old_timetables():
    """
    Cleanup task to remove old timetable entries.
    """
    try:
        # Remove entries older than 30 days
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Note: TimetableEntry doesn't have a created_at field, so we'll just clean all
        # In a real implementation, you'd add a created_at field to track entry age
        old_entries = TimetableEntry.objects.all()
        count = old_entries.count()
        old_entries.delete()
        
        logger.info(f"Cleaned up {count} old timetable entries")
        
        return {
            'success': True,
            'cleaned_entries': count
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        return {
            'success': False,
            'error': f'Cleanup failed: {str(e)}'
        }

@shared_task
def generate_timetable_report():
    """
    Generate a comprehensive report of the current timetable.
    """
    try:
        from django.db.models import Count, Q
        
        # Get current timetable statistics
        total_entries = TimetableEntry.objects.count()
        subjects_count = TimetableEntry.objects.values('subject').distinct().count()
        teachers_count = TimetableEntry.objects.values('teacher').distinct().count()
        classrooms_count = TimetableEntry.objects.values('classroom').distinct().count()
        class_groups_count = TimetableEntry.objects.values('class_group').distinct().count()
        
        # Get practical vs theory distribution
        practical_count = TimetableEntry.objects.filter(is_practical=True).count()
        theory_count = TimetableEntry.objects.filter(is_practical=False).count()
        
        # Get teacher workload distribution
        teacher_workload = TimetableEntry.objects.values('teacher__name').annotate(
            class_count=Count('id')
        ).order_by('-class_count')
        
        # Get classroom usage distribution
        classroom_usage = TimetableEntry.objects.values('classroom__name').annotate(
            usage_count=Count('id')
        ).order_by('-usage_count')
        
        # Get subject distribution
        subject_distribution = TimetableEntry.objects.values('subject__name').annotate(
            class_count=Count('id')
        ).order_by('-class_count')
        
        report = {
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'statistics': {
                'total_entries': total_entries,
                'subjects_count': subjects_count,
                'teachers_count': teachers_count,
                'classrooms_count': classrooms_count,
                'class_groups_count': class_groups_count,
                'practical_classes': practical_count,
                'theory_classes': theory_count
            },
            'teacher_workload': list(teacher_workload),
            'classroom_usage': list(classroom_usage),
            'subject_distribution': list(subject_distribution)
        }
        
        return report
        
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        return {
            'success': False,
            'error': f'Report generation failed: {str(e)}'
        }