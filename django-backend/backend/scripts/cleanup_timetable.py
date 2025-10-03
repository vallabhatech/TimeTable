#!/usr/bin/env python3
"""
TIMETABLE CLEANUP SCRIPT
=======================
Wipes out ONLY timetable data from the database.
Preserves all other data including:
- Teachers
- Subjects
- Classrooms
- Batches
- Teacher Assignments
- Configurations

Only deletes:
- Timetable Entries

Usage: python cleanup_timetable.py
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

from timetable.models import TimetableEntry, Teacher, Subject, Classroom, Batch, TeacherSubjectAssignment, ScheduleConfig

def cleanup_timetable_data():
    """Delete only timetable entries from the database"""
    print('🗑️  TIMETABLE DATA CLEANUP')
    print('=' * 40)
    print('This will delete ONLY timetable entries.')
    print('All other data will be preserved:')
    print('  ✅ Teachers')
    print('  ✅ Subjects')
    print('  ✅ Classrooms')
    print('  ✅ Batches')
    print('  ✅ Teacher Assignments')
    print('  ✅ Configurations')
    print('  ❌ Timetable Entries (will be deleted)')
    
    # Count timetable entries
    timetable_count = TimetableEntry.objects.count()
    print(f'\n📊 Found {timetable_count} timetable entries to delete.')
    
    if timetable_count == 0:
        print('✅ No timetable entries found. Database is already clean.')
        return
    
    # Ask for confirmation
    confirm = input(f'\nAre you sure you want to delete {timetable_count} timetable entries? (y/N): ')
    
    if confirm.lower() not in ['y', 'yes']:
        print('❌ Operation cancelled.')
        return
    
    print('\n🗑️  Deleting timetable entries...')

    # Delete timetable entries
    deleted_count = TimetableEntry.objects.count()
    TimetableEntry.objects.all().delete()

    print(f'   ✅ Deleted {deleted_count} timetable entries')
    
    # Verify deletion
    remaining_count = TimetableEntry.objects.count()
    print(f'   📊 Remaining timetable entries: {remaining_count}')
    
    # Show preserved data counts
    print('\n📊 Preserved data:')
    print(f'   ✅ Teachers: {Teacher.objects.count()}')
    print(f'   ✅ Subjects: {Subject.objects.count()}')
    print(f'   ✅ Classrooms: {Classroom.objects.count()}')
    print(f'   ✅ Batches: {Batch.objects.count()}')
    print(f'   ✅ Teacher Assignments: {TeacherSubjectAssignment.objects.count()}')
    print(f'   ✅ Schedule Configurations: {ScheduleConfig.objects.count()}')
    
    print('\n' + '=' * 40)
    print('✅ TIMETABLE CLEANUP COMPLETE!')
    print('🎯 Ready for fresh timetable generation.')

def main():
    """Main function"""
    try:
        cleanup_timetable_data()
    except KeyboardInterrupt:
        print('\n❌ Operation cancelled by user.')
    except Exception as e:
        print(f'\n❌ Error during cleanup: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
