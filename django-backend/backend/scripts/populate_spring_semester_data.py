#!/usr/bin/env python3
"""
SPRING SEMESTER DATA POPULATION SCRIPT
=====================================
Populates the database with the current spring semester data including:
- Teachers (38 total)
- Batches with sections (21SW-7th, 22SW-5th, 23SW-4th, 24SW-2nd)
- Subjects (assigned to batches)
- Classrooms
- Teacher-Subject-Section assignments
- All data except timetable entries

Usage: python populate_spring_semester_data.py
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

from timetable.models import Teacher, Subject, Classroom, Batch, TeacherSubjectAssignment

def populate_teachers():
    """Create all teachers"""
    print('=== CREATING TEACHERS ===')
    teachers_data = [
        {'name': 'Dr. Anoud Shaikh'},
        {'name': 'Dr. Areej Fatemah'},
        {'name': 'Dr. Asma Zubadi'},
        {'name': 'Dr. Mohsin Memon'},
        {'name': 'Dr. Naeem Ahmad'},
        {'name': 'Dr. Rabeea Jaffari'},
        {'name': 'Dr. S.M. Shehram Shah'},
        {'name': 'Dr. Saba Qureshi'},
        {'name': 'Dr. Sania Bhatti'},
        {'name': 'Mr Hafiz Imran Junejo'},
        {'name': 'Mr. Ali Asghar Sangha'},
        {'name': 'Mr. Aqib'},
        {'name': 'Mr. Arsalan Aftab'},
        {'name': 'Mr. Asadullah'},
        {'name': 'Mr. Irshad Ali Burfat'},
        {'name': 'Mr. Junaid Ahmad'},
        {'name': 'Mr. Mansoor Bhaagat'},
        {'name': 'Mr. Mansoor Samo'},
        {'name': 'Mr. Naveen Kumar'},
        {'name': 'Mr. Sajjad Ali'},
        {'name': 'Mr. Salahuddin Saddar'},
        {'name': 'Mr. Sarwar Ali'},
        {'name': 'Mr. Tabish'},
        {'name': 'Mr. Umar'},
        {'name': 'Mr. Zulfiqar'},
        {'name': 'Ms. Afifah'},
        {'name': 'Ms. Aleena'},
        {'name': 'Ms. Amirita'},
        {'name': 'Ms. Amna Baloch'},
        {'name': 'Ms. Aysha'},
        {'name': 'Ms. Dua Agha'},
        {'name': 'Ms. Fatima'},
        {'name': 'Ms. Hina Ali'},
        {'name': 'Ms. Mariam Memon'},
        {'name': 'Ms. Mehwish Shaikh'},
        {'name': 'Ms. Memoona Sami'},
        {'name': 'Ms. Shafiya Qadeer'},
        {'name': 'Prof. Dr. Qasim Ali'},
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
            'description': '7th Semester - Final Year',
            'semester_number': 7,
            'total_sections': 3,
            'academic_year': '2024-2025',
            'class_advisor': 'Prof. Dr. Qasim Ali (Email: qasim.arain@faculty.muet.edu.pk)'
        },
        {
            'name': '22SW',
            'description': '5th Semester - 3rd Year',
            'semester_number': 5,
            'total_sections': 3,
            'academic_year': '2024-2025',
            'class_advisor': 'Dr. S.M. Shehram Shah (Email: shehram.shah@faculty.muet.edu.pk)'
        },
        {
            'name': '23SW',
            'description': '4th Semester - 2nd Year',
            'semester_number': 4,
            'total_sections': 3,
            'academic_year': '2024-2025',
            'class_advisor': 'Ms. Mariam Memon (Email: mariam.memon@faculty.muet.edu.pk)'
        },
        {
            'name': '24SW',
            'description': '2nd Semester - 1st Year',
            'semester_number': 2,
            'total_sections': 3,
            'academic_year': '2024-2025',
            'class_advisor': 'Mr. Naeem Ahmed (Email: naeem.mahoto@faculty.muet.edu.pk)'
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
    
    # 21SW - 7th Semester (Final Year)
    subjects_21sw = [
        ('SW415', 'Software Reengineering', 3, False, 'SERE'),
        ('SW416', 'Multimedia Communication', 3, False, 'MC'),
        ('SW416_PR', 'Multimedia Communication (PR)', 1, True, 'MC2'),
        ('SW418', 'Formal Methods in Software Engineering', 3, False, 'FMSE'),
        ('SW417', 'Web Engineering', 3, False, 'WE'),
        ('SW417_PR', 'Web Engineering (PR)', 1, True, 'WE2'),
    ]
    
    # 22SW - 5th Semester (3rd Year)
    subjects_22sw = [
        ('SW316', 'Information Security', 3, False, 'IS'),
        ('SW318', 'Agent based Intelligent Systems', 3, False, 'ABIS'),
        ('SW317', 'Human Computer Interaction', 3, False, 'HCI'),
        ('SW315', 'Software Construction & Development', 2, False, 'SCD'),
        ('SW315_PR', 'Software Construction & Development (PR)', 1, True, 'SCD2'),
        ('MTH317', 'Statistics & Probability', 3, False, 'SP'),
        ('ENG311', 'Introduction to Entrepreneurship & Creativity', 3, False, 'IEC'),
    ]
    
    # 23SW - 4th Semester (2nd Year)
    subjects_23sw = [
        ('SW228', 'Data Warehousing', 3, False, 'DWH'),
        ('SW225', 'Operating Systems', 3, False, 'OS'),
        ('SW225_PR', 'Operating Systems (PR)', 1, True, 'OS2'),
        ('SW226', 'Computer Networks', 3, False, 'CN'),
        ('SW226_PR', 'Computer Networks (PR)', 1, True, 'CN2'),
        ('SW227', 'Software Design and Architecture', 2, False, 'SDA'),
        ('SW227_PR', 'Software Design and Architecture (PR)', 1, True, 'SDA2'),
        ('ENG301', 'Communication Skills', 2, False, 'CS'),
    ]
    
    # 24SW - 2nd Semester (1st Year)
    subjects_24sw = [
        ('SW121', 'Object Oriented Programming', 3, False, 'OOP'),
        ('SW121_PR', 'Object Oriented Programming (PR)', 1, True, 'OOP2'),
        ('SW1214', 'Introduction to Software Engineering', 3, False, 'ISE'),
        ('SW123', 'Professional Practices', 3, False, 'PP'),
        ('MTH112', 'Linear Algebra & Analytical Geometry', 3, False, 'LAAG'),
        ('PS106', 'Pakistan Studies', 3, False, 'PS'),
        ('SS104', 'Islamic Studies', 3, False, 'IST'),
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

def populate_teacher_assignments():
    """Create teacher-subject-section assignments"""
    print('\n=== CREATING TEACHER ASSIGNMENTS ===')
    
    # Teacher assignments with specific sections - EXACTLY as they exist in current database
    assignments_data = [
        # 21SW assignments
        ('Mr. Salahuddin Saddar', 'SW415', '21SW', ['I', 'II', 'III']),
        ('Dr. Sania Bhatti', 'SW416', '21SW', ['I']),
        ('Ms. Aleena', 'SW416', '21SW', ['II', 'III']),
        ('Mr. Aqib', 'SW416_PR', '21SW', ['I', 'II', 'III']),
        ('Ms. Mariam Memon', 'SW418', '21SW', ['I', 'II']),
        ('Mr. Arsalan Aftab', 'SW418', '21SW', ['III']),
        ('Ms. Dua Agha', 'SW417', '21SW', ['I', 'II']),
        ('Ms. Afifah', 'SW417', '21SW', ['III']),
        ('Mr. Tabish', 'SW417_PR', '21SW', ['I', 'II', 'III']),
        
        # 22SW assignments
        ('Prof. Dr. Qasim Ali', 'SW316', '22SW', ['I']),
        ('Ms. Fatima', 'SW316', '22SW', ['II', 'III']),
        ('Dr. Areej Fatemah', 'SW318', '22SW', ['I', 'II']),
        ('Ms. Amirita', 'SW318', '22SW', ['III']),
        ('Dr. S.M. Shehram Shah', 'SW317', '22SW', ['I', 'II']),
        ('Ms. Dua Agha', 'SW317', '22SW', ['III']),
        ('Dr. Rabeea Jaffari', 'SW315', '22SW', ['I', 'II', 'III']),
        ('Ms. Hina Ali', 'SW315_PR', '22SW', ['I', 'II', 'III']),
        ('Mr. Ali Asghar Sangha', 'MTH317', '22SW', ['I', 'II', 'III']),
        ('Dr. Asma Zubadi', 'ENG311', '22SW', ['I']),
        ('Dr. Saba Qureshi', 'ENG311', '22SW', ['II']),
        ('Mr. Mansoor Samo', 'ENG311', '22SW', ['III']),
        
        # 23SW assignments
        ('Dr. Naeem Ahmad', 'SW228', '23SW', ['I', 'II']),
        ('Ms. Amirita', 'SW228', '23SW', ['III']),
        ('Ms. Shafiya Qadeer', 'SW225', '23SW', ['I', 'II']),
        ('Mr. Sajjad Ali', 'SW225', '23SW', ['III']),
        ('Mr. Asadullah', 'SW225_PR', '23SW', ['I', 'II', 'III']),
        ('Ms. Memoona Sami', 'SW226', '23SW', ['I', 'II']),
        ('Mr. Umar', 'SW226', '23SW', ['III']),
        ('Ms. Aysha', 'SW226_PR', '23SW', ['I', 'II', 'III']),
        ('Ms. Mehwish Shaikh', 'SW227', '23SW', ['I', 'II', 'III']),
        ('Ms. Afifah', 'SW227_PR', '23SW', ['I', 'II', 'III']),
        ('Mr. Sarwar Ali', 'ENG301', '23SW', ['I', 'III']),
        ('Ms. Amna Baloch', 'ENG301', '23SW', ['II']),
        
        # 24SW assignments
        ('Dr. Mohsin Memon', 'SW121', '24SW', ['I', 'II']),
        ('Mr. Naveen Kumar', 'SW121', '24SW', ['III']),
        ('Mr. Naveen Kumar', 'SW121_PR', '24SW', ['I', 'II', 'III']),
        ('Dr. Anoud Shaikh', 'SW1214', '24SW', ['I', 'II']),
        ('Mr. Arsalan Aftab', 'SW1214', '24SW', ['III']),
        ('Mr. Junaid Ahmad', 'SW123', '24SW', ['I', 'II']),
        ('Mr. Zulfiqar', 'SW123', '24SW', ['III']),
        ('Mr. Mansoor Bhaagat', 'MTH112', '24SW', ['I', 'II', 'III']),
        ('Mr. Irshad Ali Burfat', 'PS106', '24SW', ['I', 'II', 'III']),
        ('Mr Hafiz Imran Junejo', 'SS104', '24SW', ['I', 'II', 'III']),
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
    print('🚀 STARTING SPRING SEMESTER DATA POPULATION')
    print('=' * 50)
    
    # Populate in order
    populate_teachers()
    populate_batches()
    populate_subjects()
    populate_classrooms()
    populate_teacher_assignments()
    
    print('\n' + '=' * 50)
    print('✅ SPRING SEMESTER DATA POPULATION COMPLETE!')
    print(f'📊 Final counts:')
    print(f'   Teachers: {Teacher.objects.count()}')
    print(f'   Batches: {Batch.objects.count()}')
    print(f'   Subjects: {Subject.objects.count()}')
    print(f'   Classrooms: {Classroom.objects.count()}')
    print(f'   Teacher Assignments: {TeacherSubjectAssignment.objects.count()}')
    print('\n🎯 Database is ready for spring semester timetable generation!')

if __name__ == '__main__':
    main()
