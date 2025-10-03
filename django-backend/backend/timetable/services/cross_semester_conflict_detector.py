"""
Cross-Semester Conflict Detection Service

This service handles detection and prevention of scheduling conflicts
across different semesters and academic periods.
"""

from typing import List, Dict, Tuple, Set
from django.db.models import Q
from ..models import TimetableEntry, ScheduleConfig, Teacher
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class CrossSemesterConflictDetector:
    """
    Detects and prevents scheduling conflicts across different semesters.
    
    This class ensures that when generating a new timetable for a semester,
    it considers existing timetables from previous semesters to prevent
    teacher scheduling conflicts.
    """
    
    def __init__(self, current_config: ScheduleConfig):
        """
        Initialize the conflict detector with the current schedule configuration.
        
        Args:
            current_config: The ScheduleConfig for the semester being generated
        """
        self.current_config = current_config
        self.current_semester = current_config.semester
        self.current_academic_year = current_config.academic_year
        
        # Load existing timetable entries from other semesters
        self.existing_entries = self._load_existing_entries()
        
        # Build conflict maps for quick lookup
        self.teacher_conflicts = self._build_teacher_conflict_map()
        
    def _load_existing_entries(self) -> List[TimetableEntry]:
        """
        Load all existing timetable entries from other semesters/configs.
        
        Returns:
            List of TimetableEntry objects from other semesters
        """
        # Get all entries that are NOT from the current semester
        existing_entries = TimetableEntry.objects.exclude(
            Q(semester=self.current_semester) & 
            Q(academic_year=self.current_academic_year)
        ).select_related('teacher', 'subject', 'classroom', 'schedule_config')
        
        logger.info(f"Loaded {existing_entries.count()} existing entries from other semesters")
        return list(existing_entries)
    
    def _build_teacher_conflict_map(self) -> Dict[int, Dict[str, Dict[int, List[TimetableEntry]]]]:
        """
        Build a conflict map for quick teacher availability lookup.
        
        Structure: {teacher_id: {day: {period: [entries]}}}
        
        Returns:
            Dictionary mapping teacher conflicts by day and period
        """
        conflict_map = {}
        
        for entry in self.existing_entries:
            if not entry.teacher:
                continue
                
            teacher_id = entry.teacher.id
            day = entry.day
            period = entry.period
            
            if teacher_id not in conflict_map:
                conflict_map[teacher_id] = {}
            if day not in conflict_map[teacher_id]:
                conflict_map[teacher_id][day] = {}
            if period not in conflict_map[teacher_id][day]:
                conflict_map[teacher_id][day][period] = []
                
            conflict_map[teacher_id][day][period].append(entry)
        
        return conflict_map
    
    def check_teacher_conflict(self, teacher_id: int, day: str, period: int) -> Tuple[bool, List[str]]:
        """
        Check if a teacher has conflicts at the specified time slot.
        
        Args:
            teacher_id: ID of the teacher to check
            day: Day of the week (e.g., 'Monday')
            period: Period number
            
        Returns:
            Tuple of (has_conflict, list_of_conflict_descriptions)
        """
        if teacher_id not in self.teacher_conflicts:
            return False, []
        
        if day not in self.teacher_conflicts[teacher_id]:
            return False, []
        
        if period not in self.teacher_conflicts[teacher_id][day]:
            return False, []
        
        conflicts = self.teacher_conflicts[teacher_id][day][period]
        conflict_descriptions = []
        
        for conflict_entry in conflicts:
            description = (
                f"Teacher already scheduled in {conflict_entry.semester} "
                f"({conflict_entry.academic_year}) for {conflict_entry.subject.name} "
                f"with {conflict_entry.class_group} in {conflict_entry.classroom.name}"
            )
            conflict_descriptions.append(description)
        
        return len(conflicts) > 0, conflict_descriptions
    
    def get_teacher_availability(self, teacher_id: int) -> Dict[str, Set[int]]:
        """
        Get available time slots for a teacher across all semesters.
        
        Args:
            teacher_id: ID of the teacher
            
        Returns:
            Dictionary mapping days to sets of available periods
        """
        # Start with all possible time slots from current config
        all_periods = set(range(1, len(self.current_config.periods) + 1))
        availability = {}
        
        for day in self.current_config.days:
            availability[day] = all_periods.copy()
        
        # Remove periods where teacher has conflicts
        if teacher_id in self.teacher_conflicts:
            for day, day_conflicts in self.teacher_conflicts[teacher_id].items():
                if day in availability:
                    for period in day_conflicts.keys():
                        availability[day].discard(period)
        
        return availability
    
    def validate_timetable_entries(self, proposed_entries: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate a list of proposed timetable entries against cross-semester conflicts.
        
        Args:
            proposed_entries: List of dictionaries containing entry data
            
        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []
        
        for entry_data in proposed_entries:
            teacher_id = entry_data.get('teacher_id')
            day = entry_data.get('day')
            period = entry_data.get('period')
            
            if teacher_id and day and period:
                has_conflict, conflict_descriptions = self.check_teacher_conflict(
                    teacher_id, day, period
                )
                
                if has_conflict:
                    violations.extend(conflict_descriptions)
        
        return len(violations) == 0, violations
    
    def get_conflict_summary(self) -> Dict:
        """
        Get a summary of all potential conflicts for reporting.
        
        Returns:
            Dictionary containing conflict statistics and details
        """
        summary = {
            'total_existing_entries': len(self.existing_entries),
            'teachers_with_conflicts': len(self.teacher_conflicts),
            'semesters_involved': set(),
            'academic_years_involved': set(),
            'conflict_details': []
        }
        
        for entry in self.existing_entries:
            summary['semesters_involved'].add(entry.semester)
            summary['academic_years_involved'].add(entry.academic_year)
        
        # Convert sets to lists for JSON serialization
        summary['semesters_involved'] = list(summary['semesters_involved'])
        summary['academic_years_involved'] = list(summary['academic_years_involved'])
        
        # Add detailed conflict information
        for teacher_id, teacher_conflicts in self.teacher_conflicts.items():
            try:
                teacher = Teacher.objects.get(id=teacher_id)
                teacher_name = teacher.name
            except Teacher.DoesNotExist:
                teacher_name = f"Teacher ID {teacher_id}"
            
            total_conflicts = sum(
                len(periods) for day_conflicts in teacher_conflicts.values() 
                for periods in day_conflicts.values()
            )
            
            summary['conflict_details'].append({
                'teacher_id': teacher_id,
                'teacher_name': teacher_name,
                'total_conflict_slots': total_conflicts,
                'days_with_conflicts': list(teacher_conflicts.keys())
            })
        
        return summary
    
    def suggest_alternative_slots(self, teacher_id: int, preferred_day: str = None) -> List[Dict]:
        """
        Suggest alternative time slots for a teacher when conflicts exist.
        
        Args:
            teacher_id: ID of the teacher
            preferred_day: Optional preferred day of the week
            
        Returns:
            List of suggested alternative slots
        """
        availability = self.get_teacher_availability(teacher_id)
        suggestions = []
        
        # Prioritize preferred day if specified
        days_to_check = [preferred_day] if preferred_day and preferred_day in availability else availability.keys()
        
        for day in days_to_check:
            available_periods = availability[day]
            for period in sorted(available_periods):
                suggestions.append({
                    'day': day,
                    'period': period,
                    'start_time': self._get_period_start_time(period),
                    'end_time': self._get_period_end_time(period)
                })
        
        return suggestions[:10]  # Return top 10 suggestions
    
    def _get_period_start_time(self, period: int) -> str:
        """Calculate start time for a given period."""
        if not self.current_config.start_time or not self.current_config.class_duration:
            return "Unknown"
        
        start_minutes = (
            self.current_config.start_time.hour * 60 + 
            self.current_config.start_time.minute + 
            (period - 1) * self.current_config.class_duration
        )
        
        hours = start_minutes // 60
        minutes = start_minutes % 60
        return f"{hours:02d}:{minutes:02d}"
    
    def _get_period_end_time(self, period: int) -> str:
        """Calculate end time for a given period."""
        if not self.current_config.start_time or not self.current_config.class_duration:
            return "Unknown"
        
        start_minutes = (
            self.current_config.start_time.hour * 60 + 
            self.current_config.start_time.minute + 
            period * self.current_config.class_duration
        )
        
        hours = start_minutes // 60
        minutes = start_minutes % 60
        return f"{hours:02d}:{minutes:02d}"
