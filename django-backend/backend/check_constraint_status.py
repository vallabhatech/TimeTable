#!/usr/bin/env python3
"""
Check the current status of the "No Duplicate Theory Classes Per Day" constraint
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from timetable.models import TimetableEntry
from collections import defaultdict

def check_duplicate_theory_constraint():
    """Check for violations of the No Duplicate Theory Classes Per Day constraint"""
    
    print('🔍 CHECKING CURRENT TIMETABLE FOR DUPLICATE THEORY CLASSES PER DAY')
    print('=' * 70)

    entries = TimetableEntry.objects.all()
    print(f'📊 Total timetable entries: {entries.count()}')

    if entries.count() == 0:
        print('❌ No timetable data found. Need to generate timetable first.')
        return False

    # Group by class_group, day, and subject
    violations = []
    class_day_subjects = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for entry in entries:
        if entry.subject and not entry.is_practical:  # Only theory subjects
            class_day_subjects[entry.class_group][entry.day][entry.subject.code].append(entry)

    print('\n🔍 Checking for violations...')
    for class_group, days in class_day_subjects.items():
        for day, subjects in days.items():
            for subject_code, subject_entries in subjects.items():
                if len(subject_entries) > 1:
                    violations.append({
                        'class_group': class_group,
                        'day': day,
                        'subject': subject_code,
                        'count': len(subject_entries),
                        'periods': [e.period for e in subject_entries]
                    })

    if violations:
        print(f'❌ Found {len(violations)} violations:')
        for v in violations:
            print(f'   • {v["class_group"]} has {v["count"]} {v["subject"]} classes on {v["day"]} (periods: {v["periods"]})')
        return False
    else:
        print('✅ No violations found! Constraint is working correctly.')
        return True

    print(f'\n📊 Summary:')
    print(f'   • Total sections: {len(class_day_subjects)}')
    print(f'   • Violations: {len(violations)}')

def wipe_timetable_data():
    """Wipe all existing timetable data"""
    print('\n🗑️ WIPING EXISTING TIMETABLE DATA')
    print('=' * 40)
    
    count = TimetableEntry.objects.count()
    if count == 0:
        print('✅ No timetable data to wipe.')
        return
    
    print(f'📊 Found {count} timetable entries to delete.')
    TimetableEntry.objects.all().delete()
    
    remaining = TimetableEntry.objects.count()
    print(f'✅ Deleted {count} entries. Remaining: {remaining}')

if __name__ == '__main__':
    # Check current status
    constraint_ok = check_duplicate_theory_constraint()
    
    if not constraint_ok:
        print('\n🔄 Constraint violations found. Wiping data for regeneration...')
        wipe_timetable_data()
        print('\n✅ Ready for timetable regeneration.')
    else:
        print('\n✅ Constraint is working correctly!')
