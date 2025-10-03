#!/usr/bin/env python3
"""
ENFORCE ROOM CONSTRAINTS
========================
This script actively enforces the enhanced room consistency constraint by:
1. Identifying current violations
2. Fixing them by reallocating rooms
3. Ensuring all future scheduling follows the constraint rules

The constraint ensures:
- If only theory classes are scheduled for the entire day, all classes for a section should be assigned in same room
- If both theory and practical classes are scheduled for a day, all practical classes must be in same lab (all 3 consecutive blocks) 
  and then if theory classes are scheduled in a room, all must be in same room
"""

import os
import sys
import django
from django.conf import settings

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from timetable.models import TimetableEntry, Subject, Teacher, Classroom, Batch
from timetable.enhanced_room_allocator import EnhancedRoomAllocator
from collections import defaultdict


def enforce_room_constraints():
    """Enforce the enhanced room consistency constraint by fixing violations."""
    print("🔒 ENFORCING ROOM CONSTRAINTS")
    print("=" * 60)
    
    # Initialize the room allocator
    room_allocator = EnhancedRoomAllocator()
    
    # Get all timetable entries
    entries = list(TimetableEntry.objects.all())
    
    if not entries:
        print("❌ No timetable entries found. Please populate the database first.")
        return
    
    print(f"📊 Found {len(entries)} timetable entries")
    
    # Step 1: Identify all violations
    print("\n🔍 STEP 1: IDENTIFYING VIOLATIONS")
    print("-" * 40)
    
    violations = identify_constraint_violations(entries)
    
    if not violations:
        print("✅ No violations found! All constraints are already enforced.")
        return
    
    print(f"❌ Found {len(violations)} violations to fix:")
    for violation in violations:
        print(f"   🚫 {violation['description']}")
    
    # Step 2: Fix violations
    print(f"\n🔧 STEP 2: FIXING VIOLATIONS")
    print("-" * 40)
    
    fixed_count = 0
    for violation in violations:
        if fix_violation(violation, entries, room_allocator):
            fixed_count += 1
            print(f"   ✅ Fixed: {violation['description']}")
        else:
            print(f"   ❌ Failed to fix: {violation['description']}")
    
    print(f"\n📊 Fixed {fixed_count} out of {len(violations)} violations")
    
    # Step 3: Verify fixes
    print(f"\n🔍 STEP 3: VERIFYING FIXES")
    print("-" * 40)
    
    remaining_violations = identify_constraint_violations(entries)
    
    if not remaining_violations:
        print("🎉 SUCCESS: All constraints are now enforced!")
    else:
        print(f"⚠️  {len(remaining_violations)} violations remain:")
        for violation in remaining_violations:
            print(f"   🚫 {violation['description']}")
    
    # Step 4: Show final status
    print(f"\n📊 FINAL STATUS")
    print("-" * 40)
    
    total_sections = len(set(entry.class_group for entry in entries))
    enforced_sections = total_sections - len(remaining_violations)
    enforcement_rate = (enforced_sections / total_sections) * 100 if total_sections > 0 else 0
    
    print(f"   Total sections: {total_sections}")
    print(f"   Enforced sections: {enforced_sections}")
    print(f"   Remaining violations: {len(remaining_violations)}")
    print(f"   Enforcement rate: {enforcement_rate:.1f}%")


def identify_constraint_violations(entries):
    """Identify all constraint violations in the current timetable."""
    violations = []
    
    # Group entries by class group and day
    class_day_entries = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        class_day_entries[entry.class_group][entry.day].append(entry)
    
    for class_group, days in class_day_entries.items():
        for day, day_entries in days.items():
            if len(day_entries) > 1:
                # Separate theory and practical classes
                theory_entries = [e for e in day_entries if not e.is_practical]
                practical_entries = [e for e in day_entries if e.is_practical]
                
                # Check theory class room consistency
                if len(theory_entries) > 1:
                    theory_rooms = set(e.classroom.name for e in theory_entries if e.classroom)
                    if len(theory_rooms) > 1:
                        violations.append({
                            'type': 'theory_room_inconsistency',
                            'class_group': class_group,
                            'day': day,
                            'theory_entries': theory_entries,
                            'theory_rooms': list(theory_rooms),
                            'description': f"{class_group} uses {len(theory_rooms)} rooms for theory classes on {day}: {theory_rooms}"
                        })
                
                # Check practical class lab consistency
                if len(practical_entries) > 1:
                    practical_labs = set(e.classroom.name for e in practical_entries if e.classroom)
                    if len(practical_labs) > 1:
                        violations.append({
                            'type': 'practical_lab_inconsistency',
                            'class_group': class_group,
                            'day': day,
                            'practical_entries': practical_entries,
                            'practical_labs': list(practical_labs),
                            'description': f"{class_group} uses {len(practical_labs)} labs for practical classes on {day}: {practical_labs}"
                        })
    
    return violations


def fix_violation(violation, entries, room_allocator):
    """Fix a specific constraint violation."""
    try:
        if violation['type'] == 'theory_room_inconsistency':
            return fix_theory_room_inconsistency(violation, entries, room_allocator)
        elif violation['type'] == 'practical_lab_inconsistency':
            return fix_practical_lab_inconsistency(violation, entries, room_allocator)
        else:
            return False
    except Exception as e:
        print(f"      Error fixing violation: {e}")
        return False


def fix_theory_room_inconsistency(violation, entries, room_allocator):
    """Fix theory room inconsistency by using the same room for all theory classes."""
    class_group = violation['class_group']
    day = violation['day']
    theory_entries = violation['theory_entries']
    
    # Choose the first room as the target room
    target_room = theory_entries[0].classroom
    if not target_room:
        return False
    
    print(f"      Enforcing: All theory classes for {class_group} on {day} must use {target_room.name}")
    
    # Check if target room is available for all periods
    all_available = True
    for entry in theory_entries:
        if not room_allocator._is_room_available(target_room, day, entry.period, entries):
            all_available = False
            break
    
    if all_available:
        # Assign all theory classes to the target room
        for entry in theory_entries:
            entry.classroom = target_room
            entry.save()
        
        # Update room allocator's tracking
        if class_group not in room_allocator.section_room_assignments:
            room_allocator.section_room_assignments[class_group] = {}
        room_allocator.section_room_assignments[class_group][day] = target_room
        
        return True
    else:
        # Try to free up the target room by moving conflicting classes
        print(f"      Trying to free up {target_room.name} for {class_group} on {day}")
        
        # Find alternative rooms for conflicting classes
        for entry in theory_entries:
            if entry.classroom != target_room:
                # Find an alternative room
                alternative_rooms = room_allocator.get_available_rooms_for_time(
                    day, entry.period, 1, entries, class_group
                )
                
                if alternative_rooms:
                    # Move to alternative room
                    old_room = entry.classroom
                    entry.classroom = alternative_rooms[0]
                    entry.save()
                    print(f"        Moved {entry.subject.code} P{entry.period} from {old_room.name} to {alternative_rooms[0].name}")
                else:
                    print(f"        No alternative room available for {entry.subject.code} P{entry.period}")
                    return False
        
        # Now assign all theory classes to the target room
        for entry in theory_entries:
            entry.classroom = target_room
            entry.save()
        
        # Update room allocator's tracking
        if class_group not in room_allocator.section_room_assignments:
            room_allocator.section_room_assignments[class_group] = {}
        room_allocator.section_room_assignments[class_group][day] = target_room
        
        return True


def fix_practical_lab_inconsistency(violation, entries, room_allocator):
    """Fix practical lab inconsistency by using the same lab for all practical classes."""
    class_group = violation['class_group']
    day = violation['day']
    practical_entries = violation['practical_entries']
    
    # Choose the first lab as the target lab
    target_lab = practical_entries[0].classroom
    if not target_lab or not target_lab.is_lab:
        return False
    
    print(f"      Enforcing: All practical classes for {class_group} on {day} must use {target_lab.name}")
    
    # Check if target lab is available for all periods
    all_available = True
    for entry in practical_entries:
        if not room_allocator._is_room_available(target_lab, day, entry.period, entries):
            all_available = False
            break
    
    if all_available:
        # Assign all practical classes to the target lab
        for entry in practical_entries:
            entry.classroom = target_lab
            entry.save()
        
        # Update room allocator's tracking
        subject_code = practical_entries[0].subject.code
        assignment_key = (class_group, subject_code)
        room_allocator.practical_lab_assignments[assignment_key] = target_lab
        
        return True
    else:
        # Try to free up the target lab by moving conflicting classes
        print(f"      Trying to free up {target_lab.name} for {class_group} on {day}")
        
        # Find alternative labs for conflicting classes
        for entry in practical_entries:
            if entry.classroom != target_lab:
                # Find an alternative lab
                alternative_labs = room_allocator.get_available_labs_for_time(
                    day, entry.period, 1, entries, class_group
                )
                
                if alternative_labs:
                    # Move to alternative lab
                    old_lab = entry.classroom
                    entry.classroom = alternative_labs[0]
                    entry.save()
                    print(f"        Moved {entry.subject.code} P{entry.period} from {old_lab.name} to {alternative_labs[0].name}")
                else:
                    print(f"        No alternative lab available for {entry.subject.code} P{entry.period}")
                    return False
        
        # Now assign all practical classes to the target lab
        for entry in practical_entries:
            entry.classroom = target_lab
            entry.save()
        
        # Update room allocator's tracking
        subject_code = practical_entries[0].subject.code
        assignment_key = (class_group, subject_code)
        room_allocator.practical_lab_assignments[assignment_key] = target_lab
        
        return True


if __name__ == "__main__":
    enforce_room_constraints()
