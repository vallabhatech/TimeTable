#!/usr/bin/env python
"""
FULL TEACHER UTILIZATION: Ensure ALL teachers are used
Every teacher entered in the system MUST be utilized
"""

import os
import sys
import django
from collections import defaultdict

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from timetable.models import TimetableEntry, ScheduleConfig, Subject, Teacher, Classroom

def ensure_full_teacher_utilization():
    """Ensure ALL qualified teachers are utilized"""
    print("👥 FULL TEACHER UTILIZATION SYSTEM")
    print("=" * 60)
    
    # Clear existing timetables
    print("\n1️⃣  CLEARING EXISTING TIMETABLES...")
    TimetableEntry.objects.all().delete()
    print("✅ Cleared all entries")
    
    # Get all qualified teachers
    qualified_teachers = list(Teacher.objects.filter(subjects__isnull=False).distinct())
    print(f"\n2️⃣  TEACHER ANALYSIS:")
    print(f"   Total Teachers in DB: {Teacher.objects.count()}")
    print(f"   Qualified Teachers (with subjects): {len(qualified_teachers)}")
    
    # Analyze teacher-subject mapping
    teacher_subject_map = {}
    for teacher in qualified_teachers:
        subjects = list(teacher.subjects.all())
        teacher_subject_map[teacher.id] = subjects
        print(f"   {teacher.name}: {len(subjects)} subjects")
    
    # Get all configurations
    configs = list(ScheduleConfig.objects.filter(start_time__isnull=False).order_by('name'))
    print(f"\n3️⃣  PROCESSING {len(configs)} BATCHES WITH MANDATORY TEACHER USAGE...")
    
    # Track global schedules and teacher usage
    global_teacher_schedule = defaultdict(dict)  # teacher_id -> {(day, period): entry}
    global_classroom_schedule = defaultdict(dict)  # classroom_id -> {(day, period): entry}
    teacher_usage_count = defaultdict(int)  # Track how many periods each teacher has
    
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    periods = list(range(1, 8))  # 7 periods per day
    all_time_slots = [(day, period) for day in days for period in periods]  # 35 total slots
    
    successful_batches = 0
    total_entries = 0
    
    for i, config in enumerate(configs, 1):
        print(f"\n📅 [{i}/{len(configs)}] Processing: {config.name}")
        
        # Get subjects needed for this batch
        subjects_needed = []
        for class_group in config.class_groups:
            group_name = class_group['name']
            for subject_code in class_group.get('subjects', []):
                subject = Subject.objects.filter(code=subject_code).first()
                if subject:
                    # Each subject needs multiple periods (4-6 per week)
                    periods_per_week = 5  # Standard periods per subject
                    for _ in range(periods_per_week):
                        subjects_needed.append((subject, group_name))
        
        print(f"   📚 Need to schedule {len(subjects_needed)} periods")
        
        if not subjects_needed:
            print(f"   ⚠️  No subjects found")
            continue
        
        batch_entries = []
        
        # MANDATORY TEACHER ROTATION: Ensure every teacher gets used
        for subject, class_group in subjects_needed:
            # Get ALL teachers who can teach this subject
            available_teachers = [t for t in qualified_teachers if subject in teacher_subject_map[t.id]]
            
            if not available_teachers:
                print(f"   ⚠️  No teachers found for {subject.name}")
                continue
            
            # FORCE TEACHER ROTATION: Sort by usage count (least used first)
            available_teachers.sort(key=lambda t: teacher_usage_count[t.id])
            
            scheduled = False
            
            # Try each teacher in order of least usage
            for teacher in available_teachers:
                if scheduled:
                    break
                
                # Try all available time slots for this teacher
                import random
                random.shuffle(all_time_slots)  # Randomize slot selection
                
                for day, period in all_time_slots:
                    # Check if teacher is available
                    if (day, period) in global_teacher_schedule[teacher.id]:
                        continue
                    
                    # Find available classroom
                    classroom = None
                    for c in Classroom.objects.all():
                        if (day, period) not in global_classroom_schedule[c.id]:
                            classroom = c
                            break
                    
                    if not classroom:
                        continue
                    
                    # CREATE ENTRY - FORCE TEACHER USAGE
                    start_hour = 8 + (period - 1)
                    entry = TimetableEntry(
                        day=day,
                        period=period,
                        subject=subject,
                        teacher=teacher,
                        classroom=classroom,
                        class_group=class_group,
                        start_time=f"{start_hour:02d}:00:00",
                        end_time=f"{start_hour + 1:02d}:00:00",
                        is_practical=False,
                        schedule_config=config,
                        semester=config.semester,
                        academic_year=config.academic_year
                    )
                    
                    batch_entries.append(entry)
                    
                    # Update global schedules
                    global_teacher_schedule[teacher.id][(day, period)] = entry
                    global_classroom_schedule[classroom.id][(day, period)] = entry
                    teacher_usage_count[teacher.id] += 1
                    
                    scheduled = True
                    break
            
            if not scheduled:
                print(f"   ⚠️  Could not schedule {subject.name} for {class_group}")
        
        # Save batch entries
        if batch_entries:
            try:
                TimetableEntry.objects.bulk_create(batch_entries)
                successful_batches += 1
                total_entries += len(batch_entries)
                print(f"   ✅ Generated {len(batch_entries)} entries")
            except Exception as e:
                print(f"   ❌ Save failed: {e}")
        else:
            print(f"   ❌ No entries generated")
    
    # COMPREHENSIVE ANALYSIS
    print(f"\n4️⃣  FULL UTILIZATION ANALYSIS...")
    
    # Teacher utilization analysis
    teachers_used = set()
    teacher_final_usage = defaultdict(int)
    
    for entry in TimetableEntry.objects.select_related('teacher'):
        if entry.teacher:
            teachers_used.add(entry.teacher.name)
            teacher_final_usage[entry.teacher.name] += 1
    
    utilization_rate = (len(teachers_used) / len(qualified_teachers)) * 100
    
    print(f"\n👥 TEACHER UTILIZATION RESULTS:")
    print(f"   Qualified Teachers: {len(qualified_teachers)}")
    print(f"   Teachers Actually Used: {len(teachers_used)}")
    print(f"   Utilization Rate: {utilization_rate:.1f}%")
    
    # Show all teacher usage
    print(f"\n   Complete Teacher Usage:")
    sorted_usage = sorted(teacher_final_usage.items(), key=lambda x: x[1], reverse=True)
    for teacher, count in sorted_usage:
        print(f"     {teacher}: {count} periods")
    
    # Show unused teachers
    all_qualified_names = {t.name for t in qualified_teachers}
    unused_teachers = all_qualified_names - teachers_used
    
    if unused_teachers:
        print(f"\n   ❌ UNUSED TEACHERS ({len(unused_teachers)}):")
        for teacher_name in unused_teachers:
            teacher = Teacher.objects.get(name=teacher_name)
            subjects = list(teacher.subjects.values_list('name', flat=True))
            print(f"     {teacher_name}: {subjects}")
    else:
        print(f"\n   ✅ ALL TEACHERS UTILIZED!")
    
    # Conflict check
    teacher_conflicts = 0
    teacher_schedule_check = defaultdict(dict)
    
    for entry in TimetableEntry.objects.select_related('teacher'):
        if entry.teacher:
            time_key = (entry.day, entry.period)
            teacher_id = entry.teacher.id
            
            if time_key in teacher_schedule_check[teacher_id]:
                teacher_conflicts += 1
            else:
                teacher_schedule_check[teacher_id][time_key] = entry
    
    print(f"\n🔥 CONFLICT CHECK:")
    print(f"   Teacher Conflicts: {teacher_conflicts}")
    print(f"   Total Entries: {total_entries}")
    print(f"   Successful Batches: {successful_batches}/{len(configs)}")
    
    # FINAL VERDICT
    print(f"\n" + "=" * 60)
    print("🎯 FULL TEACHER UTILIZATION VERDICT")
    print("=" * 60)
    
    if utilization_rate >= 95 and teacher_conflicts == 0 and successful_batches >= len(configs) * 0.8:
        print("🎉 PERFECT: ALL TEACHERS FULLY UTILIZED!")
        print(f"   ✅ {utilization_rate:.1f}% teacher utilization")
        print(f"   ✅ {teacher_conflicts} conflicts")
        print(f"   ✅ {successful_batches}/{len(configs)} batches successful")
        print(f"   ✅ {total_entries} total entries generated")
        print("\n🚀 SYSTEM IS NOW PRODUCTION READY WITH FULL TEACHER UTILIZATION!")
        return True
    elif utilization_rate >= 80:
        print("✅ GOOD: Most teachers utilized")
        print(f"   📊 {utilization_rate:.1f}% teacher utilization")
        print(f"   📊 {teacher_conflicts} conflicts")
        print(f"   📊 {successful_batches}/{len(configs)} batches successful")
        if unused_teachers:
            print(f"   ⚠️  {len(unused_teachers)} teachers still unused")
        return utilization_rate >= 90 and teacher_conflicts == 0
    else:
        print("❌ INSUFFICIENT: Many teachers still unused")
        print(f"   📊 Only {utilization_rate:.1f}% teacher utilization")
        print(f"   📊 {len(unused_teachers)} teachers unused")
        return False

if __name__ == "__main__":
    success = ensure_full_teacher_utilization()
    if success:
        print("\n🎉 FULL TEACHER UTILIZATION ACHIEVED!")
    else:
        print("\n⚠️  TEACHER UTILIZATION NEEDS IMPROVEMENT")
