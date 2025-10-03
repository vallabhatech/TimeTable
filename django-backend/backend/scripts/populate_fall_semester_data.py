#!/usr/bin/env python3
"""
DATA POPULATION SCRIPT
=====================
Populates the database with all necessary data including:
- Teachers
- Batches with sections (21SW-8th, 22SW-6th, 23SW-5th, 24SW-3rd)
- Subjects (assigned to batches)
- Classrooms
- Teacher-Subject-Section assignments
- Configuration data
- All data except timetable entries

Usage: python populate_data.py
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

from timetable.models import Teacher, Subject, Classroom, Batch, TeacherSubjectAssignment, ScheduleConfig
from datetime import time

def populate_teachers():
    """Create all teachers"""
    print('=== CREATING TEACHERS ===')
    teachers_data = [
        {'name': 'Dr. Olivia Smith'},
        {'name': 'Dr. Liam Johnson'},
        {'name': 'Dr. Ethan Brown'},
        {'name': 'Dr. Ava Davis'},
        {'name': 'Mr. Noah Wilson'},
        {'name': 'Mr. Mason Taylor'},
        {'name': 'Mr. Lucas Anderson'},
        {'name': 'Mr. Henry Thomas'},
        {'name': 'Mr. Jack Moore'},
        {'name': 'Mr. Leo Martin'},
        {'name': 'Mr. Isaac Lee'},
        {'name': 'Ms. Emily Clark'},
        {'name': 'Ms. Sophia Lewis'},
        {'name': 'Ms. Mia Walker'},
        {'name': 'Ms. Amelia Hall'},
        {'name': 'Ms. Harper Young'},
        {'name': 'Ms. Ella King'},
        {'name': 'Ms. Zoe Wright'},
        {'name': 'Prof. Dr. William Scott'},
        {'name': 'Dr. James Green'},
        {'name': 'Mr. Benjamin Adams'},
        {'name': 'Ms. Aria Baker'},
        {'name': 'Mr. Joseph Perez'},
        {'name': 'Ms. Layla Turner'},
        {'name': 'Ms. Hannah Phillips'},
        {'name': 'Ms. Chloe Campbell'},
    ]

    for teacher_data in teachers_data:
        teacher, created = Teacher.objects.get_or_create(
            name=teacher_data['name'],
            defaults=teacher_data
        )
        if created:
            print(f'   ✅ Created: {teacher.name}')
        else:
            print(f'   ⚪ Exists: {teacher.name}')

    print(f'Total teachers: {Teacher.objects.count()}')

def populate_batches():
    """Create all batches with their sections"""
    print('\n=== CREATING BATCHES ===')
    
    batches_data = [
        {
            'name': '21SW',
            'description': '8th Semester - Final Year',
            'semester_number': 8,
            'total_sections': 3,
            'academic_year': '2024-2025',
            'class_advisor': 'Prof. Dr. William Scott (Email: qasim.arain@faculty.muet.edu.pk)'
        },
        {
            'name': '22SW',
            'description': '6th Semester - 3rd Year',
            'semester_number': 6,
            'total_sections': 3,
            'academic_year': '2024-2025',
            'class_advisor': 'Dr. Ethan Brown (Email: shehram.shah@faculty.muet.edu.pk)'
        },
        {
            'name': '23SW',
            'description': '5th Semester - 2nd Year',
            'semester_number': 5,
            'total_sections': 3,
            'academic_year': '2024-2025',
            'class_advisor': 'Ms. Mia Walker (Email: mariam.memon@faculty.muet.edu.pk)'
        },
        {
            'name': '24SW',
            'description': '3rd Semester - 1st Year',
            'semester_number': 3,
            'total_sections': 3,
            'academic_year': '2024-2025',
            'class_advisor': 'Mr. Daniel Rivera (Email: naeem.mahoto@faculty.muet.edu.pk)'
        }
    ]
    
    for batch_data in batches_data:
        batch, created = Batch.objects.get_or_create(
            name=batch_data['name'],
            defaults=batch_data
        )
        if created:
            print(f'   ✅ Created: {batch.name} - {batch.description} ({batch.total_sections} sections)')
        else:
            # Update batch data if it exists but has different values
            updated = False
            for field, value in batch_data.items():
                if field != 'name' and getattr(batch, field) != value:
                    setattr(batch, field, value)
                    updated = True
            
            if updated:
                batch.save()
                print(f'   🔄 Updated: {batch.name} - {batch.description} ({batch.total_sections} sections)')
            else:
                print(f'   ⚪ Exists: {batch.name} - {batch.description} ({batch.total_sections} sections)')
    
    print(f'Total batches: {Batch.objects.count()}')
    
    # Show all batches with their sections
    print('\n📋 Batch Details:')
    for batch in Batch.objects.all().order_by('-semester_number'):
        sections = batch.get_sections()
        print(f'   {batch.name}: {batch.description} - Sections: {", ".join(sections)}')

def populate_subjects():
    """Create all subjects and assign them to batches"""
    print('\n=== CREATING SUBJECTS ===')
    
    # 21SW - 8th Semester (Final Year)
    subjects_21sw = [
        ('SW224', 'Simulation and Modeling', 3, False, 'SM'),
        ('SW426', 'Software Quality Engineering', 3, False, 'SQE'),
        ('SW426_PR', 'Software Quality Engineering (PR)', 1, True, 'SQE (PR)'),
        ('SW425', 'Cloud Computing', 3, False, 'CC'),
        ('SW425_PR', 'Cloud Computing (PR)', 1, True, 'CC (PR)'),
        ('SW499', 'Thesis', 3, False, 'THESIS'), 
    ]
    
    # 22SW - 6th Semester (3rd Year)
    subjects_22sw = [
        ('SW322', 'Software Project Management', 3, False, 'SPM'),
        ('ENG301', 'Technical & Scientific Writing', 2, False, 'TSW'),
        ('SW325', 'Discrete Structures', 3, False, 'DS'),
        ('SW326', 'Data Science & Analytics', 3, False, 'DS&A'),
        ('SW326_PR', 'Data Science & Analytics (PR)', 1, True, 'DS&A (PR)'),
        ('SW327', 'Mobile Application Development', 3, False, 'MAD'),
        ('SW327_PR', 'Mobile Application Development (PR)', 1, True, 'MAD (PR)'),
    ]
    
    # 23SW - 4th Semester (2nd Year)
    subjects_23sw = [
        ('SW318', 'Agent based Intelligent Systems', 3, False, 'ABIS'),
        ('SW316', 'Information Security', 3, False, 'ISEC'),
        ('SW317', 'Human Computer Interaction', 3, False, 'HCI'),
        ('MTH317', 'Statistics & Probability', 3, False, 'SP'),
        ('SW315', 'Software Construction & Development', 2, False, 'SCD'),
        ('SW315_PR', 'Software Construction & Development (PR)', 1, True, 'SCD (PR)'),
    ]
    
    # 24SW - 2nd Semester (1st Year)
    subjects_24sw = [
        ('SW215', 'Database Systems', 3, False, 'DBS'),
        ('SW215_PR', 'Database Systems (PR)', 1, True, 'DBS (PR)'),
        ('SW212', 'Data Structures & Algorithm', 3, False, 'DSA'),
        ('SW212_PR', 'Data Structures & Algorithm (PR)', 1, True, 'DSA (PR)'),
        ('SW216', 'Software Requirement Engineering', 3, False, 'SRE'),
        ('SW217', 'Operations Research', 3, False, 'OR'),
        ('SW211', 'Software Economics & Management', 3, False, 'SEM'),
    ]
    
    all_subjects = [
        ('21SW', subjects_21sw),
        ('22SW', subjects_22sw),
        ('23SW', subjects_23sw),
        ('24SW', subjects_24sw),
    ]
    
    for batch_name, subjects in all_subjects:
        print(f'\n--- {batch_name} Subjects ---')
        for code, name, credits, is_practical, short_name in subjects:
            subject, created = Subject.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'credits': credits,
                    'is_practical': is_practical,
                    'batch': batch_name,
                    'subject_short_name': short_name
                }
            )
            if created:
                print(f'   ✅ Created: {code} - {name}')
            else:
                # Update batch if it was missing
                if not subject.batch:
                    subject.batch = batch_name
                    subject.save()
                    print(f'   🔄 Updated batch for: {code} - {name}')
                else:
                    print(f'   ⚪ Exists: {code} - {name}')

    print(f'\nTotal subjects: {Subject.objects.count()}')

def populate_classrooms():
    """Create all classrooms"""
    print('\n=== CREATING CLASSROOMS ===')
    classrooms_data = [
        {'name': 'Room 01', 'building': 'Main Building'},
        {'name': 'Room 02', 'building': 'Main Building'},
        {'name': 'Room 03', 'building': 'Main Building'},
        {'name': 'Room 04', 'building': 'Main Building'},
        {'name': 'A.C. Room 01', 'building': 'Academic Building'},
        {'name': 'A.C. Room 02', 'building': 'Academic Building'},
        {'name': 'A.C. Room 03', 'building': 'Academic Building'},
        {'name': 'Lab 1', 'building': 'Main Building'},
        {'name': 'Lab 2', 'building': 'Main Building'},
        {'name': 'Lab 3', 'building': 'Main Building'},
        {'name': 'Lab 4', 'building': 'Main Building'},
        {'name': 'Lab 5', 'building': 'Main Building'},
        {'name': 'Lab 6', 'building': 'Main Building'},
    ]

    for classroom_data in classrooms_data:
        classroom, created = Classroom.objects.get_or_create(
            name=classroom_data['name'],
            defaults=classroom_data
        )
        if created:
            print(f'   ✅ Created: {classroom.name}')
        else:
            print(f'   ⚪ Exists: {classroom.name}')

    print(f'Total classrooms: {Classroom.objects.count()}')

def populate_configuration():
    """Create configuration data"""
    print('\n=== CREATING CONFIGURATION ===')
    
    config_data = {
        'name': 'Software Engineering Department',
        'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        'periods': ['1', '2', '3', '4', '5', '6', '7'],
        'start_time': time(8, 0),  # 08:00 AM
        'class_duration': 60,  # 60 minutes
        'constraints': {},
        'class_groups': ['21SW', '22SW', '23SW', '24SW'],
        'semester': 'Fall 2024',
        'academic_year': '2024-2025'
    }
    
    config, created = ScheduleConfig.objects.get_or_create(
        name=config_data['name'],
        defaults=config_data
    )
    
    if created:
        print(f'   ✅ Created: {config.name}')
        print(f'      • Department: Software Engineering')
        print(f'      • Number of Periods: {len(config.periods)}')
        print(f'      • Starting Time: {config.start_time.strftime("%I:%M %p")}')
        print(f'      • Class Duration: {config.class_duration} minutes')
        print(f'      • Days: {", ".join(config.days)}')
        print(f'      • Batches: {", ".join(config.class_groups)}')
    else:
        print(f'   ⚪ Exists: {config.name}')
    
    print(f'Total configurations: {ScheduleConfig.objects.count()}')

def populate_teacher_assignments():
    """Create teacher-subject-section assignments"""
    print('\n=== CREATING TEACHER ASSIGNMENTS ===')
    
    # Teacher assignments with specific sections
    assignments_data = [
        # 21SW assignments
        ('Dr. Ava Davis', 'SW224', '21SW', ['I', 'II']),
        ('Mr. Isaac Lee', 'SW224', '21SW', ['III']),
        ('Mr. Noah Wilson', 'SW426', '21SW', ['I', 'II', 'III']),
        ('Mr. Noah Wilson', 'SW426_PR', '21SW', ['I', 'II', 'III']),
        ('Dr. Liam Johnson', 'SW425', '21SW', ['I', 'II', 'III']),
        ('Ms. Amelia Hall', 'SW425_PR', '21SW', ['I', 'II', 'III']),
        
        # 22SW assignments
        ('Mr. Jack Moore', 'SW322', '22SW', ['I', 'II', 'III']),
        ('Ms. Zoe Wright', 'ENG301', '22SW', ['I', 'II']),
        ('Mr. Leo Martin', 'ENG301', '22SW', ['III']),
        ('Ms. Harper Young', 'SW325', '22SW', ['I', 'II', 'III']),
        ('Dr. Olivia Smith', 'SW326', '22SW', ['I', 'II', 'III']),
        ('Ms. Emily Clark', 'SW326_PR', '22SW', ['I', 'II', 'III']),
        ('Ms. Mia Walker', 'SW327', '22SW', ['I', 'II', 'III']),
        ('Mr. Isaac Lee', 'SW327_PR', '22SW', ['I', 'II', 'III']),
        
        # 23SW assignments
        ('Mr. Henry Thomas', 'SW318', '23SW', ['I', 'II', 'III']),
        ('Prof. Dr. William Scott', 'SW316', '23SW', ['I']),
        ('Ms. Ella King', 'SW316', '23SW', ['II', 'III']),
        ('Dr. Ethan Brown', 'SW317', '23SW', ['I', 'II']),
        ('Mr. Mason Taylor', 'SW317', '23SW', ['III']),
        ('Mr. Lucas Anderson', 'MTH317', '23SW', ['I', 'II', 'III']),
        ('Ms. Sophia Lewis', 'SW315', '23SW', ['I', 'II', 'III']),
        ('Ms. Sophia Lewis', 'SW315_PR', '23SW', ['I', 'II', 'III']),
        
        # 24SW assignments
        ('Ms. Layla Turner', 'SW215', '24SW', ['I', 'II', 'III']),
        ('Ms. Hannah Phillips', 'SW215_PR', '24SW', ['I', 'II', 'III']),
        ('Dr. James Green', 'SW212', '24SW', ['I', 'II']),
        ('Mr. Benjamin Adams', 'SW212', '24SW', ['III']),
        ('Mr. Henry Thomas', 'SW212_PR', '24SW', ['I', 'II', 'III']),
        ('Ms. Chloe Campbell', 'SW216', '24SW', ['I', 'II', 'III']),
        ('Ms. Aria Baker', 'SW217', '24SW', ['I', 'II', 'III']),
        ('Mr. Joseph Perez', 'SW211', '24SW', ['I', 'II', 'III']),
    ]
    
    for teacher_name, subject_code, batch_name, sections in assignments_data:
        try:
            # Resolve teacher by name safely in case of duplicates
            teacher_qs = Teacher.objects.filter(name=teacher_name)
            if not teacher_qs.exists():
                print(f'   ❌ Teacher not found: {teacher_name}')
                continue
            if teacher_qs.count() > 1:
                print(f'   ⚠️ Multiple teachers named "{teacher_name}" found. Using the earliest created.')
            teacher = teacher_qs.order_by('id').first()

            subject = Subject.objects.get(code=subject_code)
            batch = Batch.objects.get(name=batch_name)

            assignment, created = TeacherSubjectAssignment.objects.get_or_create(
                teacher=teacher,
                subject=subject,
                batch=batch,
                defaults={'sections': sections}
            )

            if created:
                print(f'   ✅ Created: {teacher_name} -> {subject_code} ({batch_name} - {", ".join(sections)})')
            else:
                # Update sections if different
                if set(assignment.sections) != set(sections):
                    assignment.sections = sections
                    assignment.save()
                    print(f'   🔄 Updated: {teacher_name} -> {subject_code} ({batch_name} - {", ".join(sections)})')
                else:
                    print(f'   ⚪ Exists: {teacher_name} -> {subject_code} ({batch_name} - {", ".join(sections)})')

        except Subject.DoesNotExist:
            print(f'   ❌ Subject not found: {subject_code}')
        except Batch.DoesNotExist:
            print(f'   ❌ Batch not found: {batch_name}')
    
    print(f'Total teacher assignments: {TeacherSubjectAssignment.objects.count()}')

def main():
    """Main function to populate all data"""
    print('🚀 STARTING DATA POPULATION')
    print('=' * 50)
    
    # Populate in order
    populate_teachers()
    populate_batches()
    populate_subjects()
    populate_classrooms()
    populate_configuration()
    populate_teacher_assignments()
    
    print('\n' + '=' * 50)
    print('✅ DATA POPULATION COMPLETE!')
    print(f'📊 Final counts:')
    print(f'   Teachers: {Teacher.objects.count()}')
    print(f'   Batches: {Batch.objects.count()}')
    print(f'   Subjects: {Subject.objects.count()}')
    print(f'   Classrooms: {Classroom.objects.count()}')
    print(f'   Configurations: {ScheduleConfig.objects.count()}')
    print(f'   Teacher Assignments: {TeacherSubjectAssignment.objects.count()}')
    print('\n🎯 Database is ready for timetable generation!')

if __name__ == '__main__':
    main()
