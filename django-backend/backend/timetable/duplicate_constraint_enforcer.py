"""
Centralized Duplicate Theory Constraint Enforcer

This module ensures that no theory class for the same subject is scheduled 
more than once per day for the same section across the entire system.
"""

from typing import List, Dict, Set, Tuple, Optional
from timetable.models import TimetableEntry, Subject


class DuplicateTheoryConstraintEnforcer:
    """
    Centralized enforcer for the "No Duplicate Theory Classes Per Day" constraint.
    
    This constraint ensures that:
    - No theory subject is scheduled more than once per day for the same section
    - The subject can still be scheduled for the same section on different days
    - The subject can still be scheduled for other sections on the same or different days
    """
    
    def __init__(self):
        self.violations_cache = {}
    
    def check_constraint(self, entries: List[TimetableEntry]) -> List[Dict]:
        """
        Check for violations of the duplicate theory constraint.
        
        Args:
            entries: List of timetable entries to check
            
        Returns:
            List of violation dictionaries with details
        """
        violations = []
        
        # Group by class_group, day, and subject
        class_day_subjects = {}
        
        for entry in entries:
            if not entry.subject or entry.is_practical:
                continue
            # EXCEPTION: Thesis subjects are excluded from duplicate-theory constraint
            subj_name = (entry.subject.name or "").lower()
            subj_code = (entry.subject.code or "").lower()
            if "thesis" in subj_name or "thesis" in subj_code:
                continue
                
            class_group = entry.class_group
            day = entry.day
            subject_code = entry.subject.code
            
            if class_group not in class_day_subjects:
                class_day_subjects[class_group] = {}
            if day not in class_day_subjects[class_group]:
                class_day_subjects[class_group][day] = {}
            if subject_code not in class_day_subjects[class_group][day]:
                class_day_subjects[class_group][day][subject_code] = []
                
            class_day_subjects[class_group][day][subject_code].append(entry)
        
        # Check for violations
        for class_group, days in class_day_subjects.items():
            for day, subjects in days.items():
                for subject_code, subject_entries in subjects.items():
                    if len(subject_entries) > 1:
                        violations.append({
                            'class_group': class_group,
                            'day': day,
                            'subject': subject_code,
                            'count': len(subject_entries),
                            'periods': [e.period for e in subject_entries],
                            'entries': subject_entries
                        })
        
        return violations
    
    def can_schedule_theory(self, entries: List[TimetableEntry], 
                           class_group: str, subject_code: str, 
                           day: str, period: int) -> bool:
        """
        Check if a theory class can be scheduled without violating the constraint.
        
        Args:
            entries: Current timetable entries
            class_group: The class group to schedule for
            subject_code: The subject code to schedule
            day: The day to schedule on
            period: The period to schedule at
            
        Returns:
            True if scheduling is allowed, False if it would violate the constraint
        """
        # Check if the slot is already occupied
        for entry in entries:
            if (entry.class_group == class_group and 
                entry.day == day and entry.period == period):
                return False
        
        # EXCEPTION: Thesis subjects are excluded from duplicate-theory constraint
        if subject_code and "thesis" in subject_code.lower():
            # As long as the slot is free (checked above), allow scheduling
            return True

        # Check if this theory subject is already scheduled on this day for this class group
        for entry in entries:
            if (entry.class_group == class_group and 
                entry.day == day and 
                entry.subject and 
                entry.subject.code == subject_code and 
                not entry.is_practical):
                return False
        
        return True
    
    def find_available_slots_for_theory(self, entries: List[TimetableEntry],
                                       class_group: str, subject_code: str,
                                       count: int, 
                                       available_days: List[str] = None,
                                       available_periods: List[int] = None) -> List[Tuple[str, int]]:
        """
        Find available slots for a theory subject that respect the duplicate constraint.
        
        Args:
            entries: Current timetable entries
            class_group: The class group to schedule for
            subject_code: The subject code to schedule
            count: Number of slots needed
            available_days: List of available days (default: all days)
            available_periods: List of available periods (default: all periods)
            
        Returns:
            List of (day, period) tuples for available slots
        """
        if available_days is None:
            available_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        if available_periods is None:
            available_periods = [1, 2, 3, 4, 5, 6, 7]
        
        # Get days where this theory subject is already scheduled for this class group
        used_days = set()
        for entry in entries:
            if (entry.class_group == class_group and 
                entry.subject and 
                entry.subject.code == subject_code and 
                not entry.is_practical):
                used_days.add(entry.day)
        
        # Find available slots
        available_slots = []
        
        for day in available_days:
            # Skip days that already have this theory subject for this class group
            if day in used_days:
                continue
                
            for period in available_periods:
                # Check if the slot is available
                if self.can_schedule_theory(entries, class_group, subject_code, day, period):
                    available_slots.append((day, period))
                    if len(available_slots) >= count:
                        break
            if len(available_slots) >= count:
                break
        
        return available_slots[:count]
    
    def fix_violations(self, entries: List[TimetableEntry]) -> Tuple[List[TimetableEntry], int]:
        """
        Fix violations by redistributing duplicate theory classes.
        
        Args:
            entries: List of timetable entries with violations
            
        Returns:
            Tuple of (fixed_entries, violations_fixed_count)
        """
        violations = self.check_constraint(entries)
        if not violations:
            return entries, 0
        
        # Convert QuerySet to list if needed
        if hasattr(entries, 'copy'):
            fixed_entries = entries.copy()
        else:
            fixed_entries = list(entries)
        violations_fixed = 0
        
        for violation in violations:
            if self._fix_single_violation(fixed_entries, violation):
                violations_fixed += 1
        
        return fixed_entries, violations_fixed
    
    def _fix_single_violation(self, entries: List[TimetableEntry], 
                             violation: Dict) -> bool:
        """
        Fix a single violation by redistributing one of the duplicate classes.
        
        Args:
            entries: List of timetable entries
            violation: Violation dictionary
            
        Returns:
            True if violation was fixed, False otherwise
        """
        class_group = violation['class_group']
        subject_code = violation['subject']
        day = violation['day']
        duplicate_entries = violation['entries']
        
        # Try to move one of the duplicate entries to a different day
        for entry in duplicate_entries[1:]:  # Keep the first one, move the rest
            # Find available slots on other days
            available_slots = self.find_available_slots_for_theory(
                entries, class_group, subject_code, 1,
                available_days=[d for d in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'] 
                               if d != day]
            )
            
            if available_slots:
                new_day, new_period = available_slots[0]
                
                # Update the entry
                entry.day = new_day
                entry.period = new_period
                
                # Update the room allocation if needed
                # (This would need to be handled by the room allocator)
                
                return True
        
        return False
    
    def validate_timetable(self, entries: List[TimetableEntry]) -> Dict:
        """
        Comprehensive validation of a timetable for the duplicate theory constraint.
        
        Args:
            entries: List of timetable entries to validate
            
        Returns:
            Dictionary with validation results
        """
        violations = self.check_constraint(entries)
        
        return {
            'is_valid': len(violations) == 0,
            'violation_count': len(violations),
            'violations': violations,
            'summary': {
                'total_entries': len(entries),
                'theory_entries': len([e for e in entries if e.subject and not e.is_practical]),
                'practical_entries': len([e for e in entries if e.subject and e.is_practical])
            }
        }


# Global instance for easy access
duplicate_constraint_enforcer = DuplicateTheoryConstraintEnforcer()
