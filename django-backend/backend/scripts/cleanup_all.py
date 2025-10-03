#!/usr/bin/env python3
"""
COMPLETE DATABASE CLEANUP SCRIPT
===============================
Wipes out ALL data from the database including:
- Teachers
- Subjects
- Classrooms
- ALL Batches
- Teacher Assignments
- Timetable Entries
- All other data

⚠️  WARNING: This will delete ALL data! Use with caution!

Usage: python cleanup_all.py
"""

import os
import sys
import django

# Add the parent directory to Python path so we can import backend module
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from timetable.models import (
    Teacher, Subject, Classroom, Batch, 
    TeacherSubjectAssignment, TimetableEntry,
    ScheduleConfig, Config, ClassGroup
)

def cleanup_all_data():
    """Delete all data from the database"""
    print('⚠️  WARNING: This will delete ALL data from the database!')
    print('This includes:')
    print('  - All Teachers')
    print('  - All Subjects')
    print('  - All Classrooms')
    print('  - ALL Batches')
    print('  - All Teacher Assignments')
    print('  - All Timetable Entries')
    print('  - All Configurations')
    print('  - All Class Groups')
    
    # Ask for confirmation
    confirm = input('\nAre you sure you want to proceed? Type "DELETE ALL" to confirm: ')
    
    if confirm != "DELETE ALL":
        print('❌ Operation cancelled.')
        return
    
    print('\n🗑️  STARTING COMPLETE DATABASE CLEANUP')
    print('=' * 50)
    
    # Count before deletion
    counts_before = {
        'Teachers': Teacher.objects.count(),
        'Subjects': Subject.objects.count(),
        'Classrooms': Classroom.objects.count(),
        'Teacher Assignments': TeacherSubjectAssignment.objects.count(),
        'Timetable Entries': TimetableEntry.objects.count(),
        'Schedule Configs': ScheduleConfig.objects.count(),
        'Configs': Config.objects.count(),
        'Class Groups': ClassGroup.objects.count(),
        'Batches': Batch.objects.count(),
    }
    
    print('📊 Data before cleanup:')
    for model, count in counts_before.items():
        print(f'   {model}: {count}')
    
    print('\n🗑️  Deleting data...')
    
    # Delete in reverse dependency order to handle foreign key relationships
    print('   🗑️  Deleting Timetable Entries...')
    TimetableEntry.objects.all().delete()
    
    print('   🗑️  Deleting Teacher Assignments...')
    TeacherSubjectAssignment.objects.all().delete()
    
    print('   🗑️  Deleting Teachers...')
    Teacher.objects.all().delete()
    
    print('   🗑️  Deleting Subjects...')
    Subject.objects.all().delete()
    
    print('   🗑️  Deleting Classrooms...')
    Classroom.objects.all().delete()
    
    print('   🗑️  Deleting Schedule Configurations...')
    ScheduleConfig.objects.all().delete()
    
    print('   🗑️  Deleting Configs...')
    Config.objects.all().delete()
    
    print('   🗑️  Deleting Class Groups...')
    ClassGroup.objects.all().delete()
    
    print('   🗑️  Deleting ALL Batches...')
    Batch.objects.all().delete()
    
    # Count after deletion
    counts_after = {
        'Teachers': Teacher.objects.count(),
        'Subjects': Subject.objects.count(),
        'Classrooms': Classroom.objects.count(),
        'Teacher Assignments': TeacherSubjectAssignment.objects.count(),
        'Timetable Entries': TimetableEntry.objects.count(),
        'Schedule Configs': ScheduleConfig.objects.count(),
        'Configs': Config.objects.count(),
        'Class Groups': ClassGroup.objects.count(),
        'Batches': Batch.objects.count(),
    }
    
    print('\n📊 Data after cleanup:')
    for model, count in counts_after.items():
        print(f'   {model}: {count}')
    
    print('\n' + '=' * 50)
    print('✅ COMPLETE DATABASE CLEANUP FINISHED!')
    print('🎯 Database is now completely empty and ready for fresh data population.')

def main():
    """Main function"""
    try:
        cleanup_all_data()
    except KeyboardInterrupt:
        print('\n❌ Operation cancelled by user.')
    except Exception as e:
        print(f'\n❌ Error during cleanup: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
