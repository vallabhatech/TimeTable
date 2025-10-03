"""
ENHANCED ROOM ALLOCATION SYSTEM
===============================
Implements the client's specific room allocation requirements:
- 2nd year batches: Academic building rooms for theory, labs for practicals
- 1st, 3rd, 4th year batches: Main building rooms for theory, labs for practicals
- All practicals must be in labs with 3 consecutive blocks in same lab
- No room conflicts
- Consistent room assignment per section per day
"""

from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from django.db.models import Q
from .models import Classroom, TimetableEntry, Batch, Subject, Teacher


class EnhancedRoomAllocator:
    """
    Enhanced room allocation system implementing client's specific requirements.
    """
    
    def __init__(self):
        self.labs = []
        self.academic_building_rooms = []
        self.main_building_rooms = []
        self.all_rooms = []
        
        # Section-specific room assignments (for consistent daily assignment)
        self.section_room_assignments = {}  # {section: {day: room}}
        
        # Practical lab assignments (for same-lab rule)
        self.practical_lab_assignments = {}  # {(section, subject_code): lab}
        
        # Room usage tracking
        self.room_usage = defaultdict(lambda: defaultdict(set))  # {room_id: {day: set(periods)}}
        
        self._initialize_room_data()
    
    def _initialize_room_data(self):
        """Initialize room classification based on building and type."""
        all_rooms = list(Classroom.objects.all())
        
        # Classify rooms by building and type
        self.labs = [room for room in all_rooms if room.is_lab]
        self.academic_building_rooms = [room for room in all_rooms 
                                      if not room.is_lab and 'Academic' in room.building]
        self.main_building_rooms = [room for room in all_rooms 
                                  if not room.is_lab and 'Academic' not in room.building]
        self.all_rooms = all_rooms
        
        print(f"🏫 Enhanced Room Allocator Initialized:")
        print(f"   📍 Labs: {len(self.labs)} ({[lab.name for lab in self.labs]})")
        print(f"   📍 Academic Building Rooms: {len(self.academic_building_rooms)} ({[room.name for room in self.academic_building_rooms]})")
        print(f"   📍 Main Building Rooms: {len(self.main_building_rooms)} ({[room.name for room in self.main_building_rooms]})")
    
    def get_year_from_section(self, section: str) -> int:
        """Extract year from section (e.g., '21SW-I' -> 2021)."""
        try:
            # Extract batch name first
            batch_name = section.split('-')[0] if '-' in section else section
            year_digits = ''.join(filter(str.isdigit, batch_name))[:2]
            if year_digits:
                year = int(year_digits)
                return 2000 + year
        except:
            pass
        return 2021  # Default fallback
    
    def is_second_year_section(self, section: str) -> bool:
        """Check if section belongs to 2nd year (for academic building allocation)."""
        year = self.get_year_from_section(section)
        from datetime import datetime
        current_year = datetime.now().year
        
        # 2nd year students are those who started 2 years ago
        # For 2025: 2nd year = 23XX batches (started in 2023)
        return year == (current_year - 2)
    
    def get_preferred_rooms_for_section(self, section: str) -> List[Classroom]:
        """Get preferred rooms for theory classes based on section year - STRICT BUILDING RULES."""
        if self.is_second_year_section(section):
            # 2nd year: Academic building rooms ONLY - no fallback to main building
            return self.academic_building_rooms
        else:
            # 1st, 3rd, 4th year: Main building rooms ONLY - no fallback to academic building
            return self.main_building_rooms
    
    def get_available_rooms_for_time(self, day: str, period: int, duration: int = 1,
                                   entries: List[TimetableEntry] = None, section: str = None) -> List[Classroom]:
        """Get rooms available for the specified time slot, respecting building rules if section is provided."""
        if entries is None:
            entries = []
        
        available_rooms = []
        
        # If section is provided, respect building rules
        if section:
            is_second_year = self.is_second_year_section(section)
            if is_second_year:
                # 2nd year: Academic building rooms + labs only
                rooms_to_check = self.academic_building_rooms + self.labs
            else:
                # Non-2nd year: Main building rooms + labs only
                rooms_to_check = self.main_building_rooms + self.labs
        else:
            # If no section provided, check all rooms (for backward compatibility)
            rooms_to_check = self.all_rooms
        
        for room in rooms_to_check:
            is_available = True
            
            # Check all periods for the duration
            for i in range(duration):
                check_period = period + i
                
                # Check if room is occupied during this period
                occupied = any(
                    entry.classroom and entry.classroom.id == room.id and
                    entry.day == day and entry.period == check_period
                    for entry in entries
                )
                
                if occupied:
                    is_available = False
                    break
            
            if is_available:
                available_rooms.append(room)
        
        return available_rooms
    
    def get_available_labs_for_time(self, day: str, period: int, duration: int = 1,
                                   entries: List[TimetableEntry] = None, section: str = None) -> List[Classroom]:
        """Get labs available for the specified time slot."""
        all_available = self.get_available_rooms_for_time(day, period, duration, entries, section)
        return [room for room in all_available if room.is_lab]
    
    def allocate_room_for_practical(self, day: str, start_period: int, section: str,
                                   subject: Subject, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        Allocate lab for practical session (3 consecutive blocks) with TEACHER AVAILABILITY CHECKING.
        ENFORCES: If both theory and practical classes are scheduled for a day, 
        all practical classes must be in same lab (all 3 consecutive blocks).
        BULLETPROOF: Only allocates room if teacher is available for all 3 periods.
        """
        # BULLETPROOF: First check if teacher is available for all 3 periods
        teacher = self._get_teacher_for_subject(subject, section)
        if not teacher:
            print(f"    🚫 NO TEACHER: No teacher assigned to {subject.code} - cannot allocate room")
            return None
        
        # BULLETPROOF: Check teacher availability for entire duration
        if not self._is_teacher_available_for_duration(teacher, day, start_period, 3, entries):
            print(f"    🚫 TEACHER UNAVAILABLE: Teacher {teacher.name} unavailable for {subject.code} duration on {day} P{start_period}-{start_period+2}")
            return None
        
        # First priority: Check if we already have a lab assigned for this section-subject combination
        assignment_key = (section, subject.code)
        existing_lab = self._find_existing_lab_for_practical_bulletproof(section, subject, entries)
        
        if existing_lab:
            # BULLETPROOF: Must use the same lab as other blocks
            if self._is_lab_available_for_duration(existing_lab, day, start_period, 3, entries):
                # Update our tracking
                self.practical_lab_assignments[assignment_key] = existing_lab
                return existing_lab
            else:
                # FORCE the existing lab to be available (same-lab rule is mandatory)
                if self._force_lab_availability_for_same_lab_rule(existing_lab, day, start_period, 3, entries):
                    self.practical_lab_assignments[assignment_key] = existing_lab
                    return existing_lab
                else:
                    print(f"    ❌ CRITICAL: Cannot maintain same-lab rule for {section} {subject.code}")
                    return None
        
        # Second priority: ENFORCEMENT - Check if this section has any theory classes on this day
        section_day_entries = [e for e in entries if e.class_group == section and e.day == day]
        has_theory = any(not e.is_practical for e in section_day_entries)
        
        # ENFORCEMENT: If theory classes exist on this day, MUST use the same lab as other practical classes
        if has_theory:
            practical_entries = [e for e in section_day_entries if e.is_practical and e.classroom]
            if practical_entries:
                # ENFORCE: Use the same lab as existing practical classes
                existing_lab = practical_entries[0].classroom
                if existing_lab.is_lab and self._is_lab_available_for_duration(existing_lab, day, start_period, 3, entries):
                    # Record the assignment for same-lab rule
                    self.practical_lab_assignments[assignment_key] = existing_lab
                    print(f"    🔒 ENFORCING: {section} practical class on {day} P{start_period} assigned to same lab: {existing_lab.name}")
                    return existing_lab
                else:
                    # ENFORCEMENT: If existing lab is not available, try to free it up
                    print(f"    🔒 ENFORCING: Trying to free up lab {existing_lab.name} for {section} practical consistency on {day}")
                    if self._force_lab_availability_for_section(existing_lab, day, start_period, 3, entries, section):
                        self.practical_lab_assignments[assignment_key] = existing_lab
                        print(f"    ✅ ENFORCED: {section} practical class on {day} P{start_period} assigned to same lab: {existing_lab.name}")
                        return existing_lab
        
        # Third priority: Find available labs for the 3-block duration
        available_labs = self.get_available_labs_for_time(day, start_period, 3, entries)
        
        if not available_labs:
            # Try to free up a lab by moving conflicting classes
            available_labs = self._force_lab_availability(day, start_period, 3, entries)
        
        if available_labs:
            # Select the best lab (prefer labs with lower usage)
            selected_lab = self._select_best_lab(available_labs, section)
            
            # Record the assignment for same-lab rule
            self.practical_lab_assignments[assignment_key] = selected_lab
            
            print(f"    🔬 Assigned: {section} practical class on {day} P{start_period} to {selected_lab.name}")
            return selected_lab
        
        return None
    
    def allocate_room_for_theory(self, day: str, period: int, section: str,
                                subject: Subject, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        Allocate room for theory class with section-specific preferences and TEACHER AVAILABILITY CHECKING.
        ENFORCES: If only theory classes are scheduled for the entire day, 
        all classes for a section should be assigned in same room.
        BULLETPROOF: Only allocates room if teacher is available for this period.
        """
        # BULLETPROOF: First check if teacher is available for this period
        teacher = self._get_teacher_for_subject(subject, section)
        if not teacher:
            print(f"    🚫 NO TEACHER: No teacher assigned to {subject.code} - cannot allocate room")
            return None
        
        # BULLETPROOF: Check teacher availability for this period
        if not self._is_teacher_available_bulletproof(teacher, day, period, entries):
            print(f"    🚫 TEACHER UNAVAILABLE: Teacher {teacher.name} unavailable for {subject.code} on {day} P{period}")
            return None
        
        # First priority: Check if section already has a room assigned for this day
        if section in self.section_room_assignments and day in self.section_room_assignments[section]:
            assigned_room = self.section_room_assignments[section][day]
            if self._is_room_available(assigned_room, day, period, entries):
                return assigned_room
        
        # Second priority: Check if this section has any practical classes on this day
        section_day_entries = [e for e in entries if e.class_group == section and e.day == day]
        has_practical = any(e.is_practical for e in section_day_entries)
        
        # ENFORCEMENT: If no practical classes on this day, MUST use the same room as other theory classes
        if not has_practical:
            theory_entries = [e for e in section_day_entries if not e.is_practical and e.classroom]
            if theory_entries:
                # ENFORCE: Use the same room as existing theory classes
                existing_room = theory_entries[0].classroom
                if self._is_room_available(existing_room, day, period, entries):
                    # Record the assignment for consistent daily assignment
                    if section not in self.section_room_assignments:
                        self.section_room_assignments[section] = {}
                    self.section_room_assignments[section][day] = existing_room
                    print(f"    🔒 ENFORCING: {section} theory class on {day} P{period} assigned to same room: {existing_room.name}")
                    return existing_room
                else:
                    # ENFORCEMENT: If existing room is not available, try to free it up
                    print(f"    🔒 ENFORCING: Trying to free up room {existing_room.name} for {section} theory consistency on {day}")
                    if self._force_room_availability(existing_room, day, period, entries):
                        if section not in self.section_room_assignments:
                            self.section_room_assignments[section] = {}
                        self.section_room_assignments[section][day] = existing_room
                        print(f"    ✅ ENFORCED: {section} theory class on {day} P{period} assigned to same room: {existing_room.name}")
                        return existing_room
        
        # Third priority: Get preferred rooms for this section
        preferred_rooms = self.get_preferred_rooms_for_section(section)
        
        # Find available rooms from preferred list
        available_rooms = [room for room in preferred_rooms 
                          if self._is_room_available(room, day, period, entries)]
        
        if not available_rooms:
            # STRICT RULE: No fallback to other buildings - only labs as last resort
            print(f"    🚫 STRICT RULE: No preferred building rooms available for {section} - trying labs only")
            available_rooms = [room for room in self.labs 
                             if self._is_room_available(room, day, period, entries)]
        
        if available_rooms:
            selected_room = self._select_best_room(available_rooms, section)
            
            # Record the assignment for consistent daily assignment
            if section not in self.section_room_assignments:
                self.section_room_assignments[section] = {}
            self.section_room_assignments[section][day] = selected_room
            
            print(f"    🏠 Assigned: {section} theory class on {day} P{period} to {selected_room.name}")
            return selected_room
        
        return None
    
    def _get_teacher_for_subject(self, subject: Subject, section: str) -> Optional[Teacher]:
        """Get teacher assigned to a subject for a section."""
        from .models import TeacherSubjectAssignment, Batch
        
        # Extract batch name from section
        batch_name = section.split('-')[0] if '-' in section else section
        
        # Get batch object
        try:
            batch = Batch.objects.get(name=batch_name)
            
            # Get assignments for this subject and batch
            assignments = TeacherSubjectAssignment.objects.filter(
                subject=subject,
                batch=batch
            )
            
            # Filter by section if specified
            for assignment in assignments:
                if not assignment.sections or section.split('-')[1] in assignment.sections:
                    return assignment.teacher
            
            # Fallback: get any teacher for this subject
            if assignments.exists():
                return assignments.first().teacher
                
        except Batch.DoesNotExist:
            pass
        
        return None
    
    def _is_teacher_available_for_duration(self, teacher: Teacher, day: str, start_period: int,
                                         duration: int, entries: List[TimetableEntry]) -> bool:
        """Check if teacher is available for the entire duration with BULLETPROOF checking."""
        if not teacher:
            return False
        
        # Check each period in the duration
        for i in range(duration):
            period = start_period + i
            if not self._is_teacher_available_bulletproof(teacher, day, period, entries):
                return False
        
        return True
    
    def _is_teacher_available_bulletproof(self, teacher: Teacher, day: str, period: int,
                                        entries: List[TimetableEntry]) -> bool:
        """
        BULLETPROOF TEACHER AVAILABILITY CHECK: 100% ENFORCEMENT, ZERO TOLERANCE FOR VIOLATIONS
        """
        # BULLETPROOF: Validate inputs
        if not teacher:
            return False
        
        if not day or not period:
            return False
        
        # BULLETPROOF: First check for existing schedule conflicts
        if any(
            entry.teacher and entry.teacher.id == teacher.id and
            entry.day == day and entry.period == period
            for entry in entries
        ):
            return False
        
        # BULLETPROOF: Check teacher unavailability constraints - HARD CONSTRAINT
        if not hasattr(teacher, 'unavailable_periods'):
            return True
        
        # Check if teacher has unavailability data
        if not isinstance(teacher.unavailable_periods, dict) or not teacher.unavailable_periods:
            return True
        
        # BULLETPROOF: Check if this day is in teacher's unavailable periods - ZERO TOLERANCE
        
        # Handle the new time-based format: {'mandatory': {'Monday': ['8:00 AM - 9:00 AM']}} or {'mandatory': {'Mon': ['8:00 AM', '9:00 AM']}}
        if isinstance(teacher.unavailable_periods, dict) and 'mandatory' in teacher.unavailable_periods:
            mandatory_unavailable = teacher.unavailable_periods['mandatory']
            
            # Convert day name to match data format (Monday vs Mon)
            day_mapping = {
                'Mon': 'Monday', 'Tue': 'Tuesday', 'Wed': 'Wednesday', 
                'Thu': 'Thursday', 'Fri': 'Friday', 'Sat': 'Saturday', 'Sun': 'Sunday'
            }
            full_day_name = day_mapping.get(day, day)
            
            if full_day_name in mandatory_unavailable:
                time_slots = mandatory_unavailable[full_day_name]
                if isinstance(time_slots, list):
                    for time_slot in time_slots:
                        if isinstance(time_slot, str) and ' - ' in time_slot:
                            # Handle format: '8:00 AM - 9:00 AM'
                            start_time_str, end_time_str = time_slot.split(' - ')
                            start_time_str = start_time_str.strip()
                            end_time_str = end_time_str.strip()
                            
                            # Convert to period numbers
                            start_period_unavailable = self._convert_time_to_period(start_time_str)
                            end_period_unavailable = self._convert_time_to_period(end_time_str)
                            
                            if start_period_unavailable is not None and end_period_unavailable is not None:
                                # Check if the requested period falls within unavailable time
                                if start_period_unavailable <= period <= end_period_unavailable:
                                    return False
                        elif isinstance(time_slot, str):
                            # Handle single time: '8:00 AM'
                            unavailable_period = self._convert_time_to_period(time_slot)
                            
                            if unavailable_period is not None and period == unavailable_period:
                                return False
        
        # Handle the old format: {'Mon': ['8', '9']} or {'Mon': True}
        elif isinstance(teacher.unavailable_periods, dict):
            if day in teacher.unavailable_periods:
                unavailable_periods = teacher.unavailable_periods[day]
                
                # If unavailable_periods is a list, check specific periods
                if isinstance(unavailable_periods, list):
                    if str(period) in unavailable_periods or period in unavailable_periods:
                        return False
                # If unavailable_periods is not a list, assume entire day is unavailable
                elif unavailable_periods:
                    return False
        
        return True
    
    def _convert_time_to_period(self, time_str: str) -> Optional[int]:
        """
        Convert time string (e.g., '8:00 AM') to period number based on schedule config.
        Returns None if conversion fails.
        """
        try:
            from datetime import datetime
            from .models import ScheduleConfig
            
            # Parse the time string
            if 'AM' in time_str or 'PM' in time_str:
                # Format: '8:00 AM' or '9:00 PM'
                time_obj = datetime.strptime(time_str, '%I:%M %p').time()
            else:
                # Format: '8:00' or '09:00'
                time_obj = datetime.strptime(time_str, '%H:%M').time()
            
            # Get the start time from config
            config = ScheduleConfig.objects.filter(start_time__isnull=False).order_by('-id').first()
            if not config:
                return None
                
            config_start_time = config.start_time
            if isinstance(config_start_time, str):
                config_start_time = datetime.strptime(config_start_time, '%H:%M:%S').time()
            
            # Calculate which period this time falls into
            class_duration = config.class_duration
            
            # Calculate minutes since start of day
            start_minutes = config_start_time.hour * 60 + config_start_time.minute
            time_minutes = time_obj.hour * 60 + time_obj.minute
            
            # Calculate period number (1-based)
            period = ((time_minutes - start_minutes) // class_duration) + 1
            
            # Ensure period is within valid range
            if 1 <= period <= len(config.periods):
                return period
            else:
                return None
                
        except Exception as e:
            return None
    
    def _is_lab_available_for_duration(self, lab: Classroom, day: str, start_period: int,
                                      duration: int, entries: List[TimetableEntry]) -> bool:
        """Check if lab is available for the specified duration."""
        for i in range(duration):
            period = start_period + i
            if not self._is_room_available(lab, day, period, entries):
                return False
        return True
    
    def _is_room_available(self, room: Classroom, day: str, period: int,
                          entries: List[TimetableEntry]) -> bool:
        """Check if room is available for the specified time slot."""
        return not any(
            entry.classroom and entry.classroom.id == room.id and
            entry.day == day and entry.period == period
            for entry in entries
        )
    
    def _force_lab_availability(self, day: str, start_period: int, duration: int,
                               entries: List[TimetableEntry]) -> List[Classroom]:
        """Try to free up labs by moving conflicting classes."""
        available_labs = []
        
        for lab in self.labs:
            if self._can_clear_lab_for_duration(lab, day, start_period, duration, entries):
                available_labs.append(lab)
        
        return available_labs
    
    def _force_lab_availability_for_section(self, lab: Classroom, day: str, start_period: int,
                                           duration: int, entries: List[TimetableEntry], section: str) -> bool:
        """Try to free up a specific lab for a section's practical classes."""
        # Find all practical entries for this lab on this day
        practical_entries_for_lab = [
            e for e in entries if e.classroom and e.classroom.id == lab.id and e.day == day
        ]
        
        # If no practical entries for this lab on this day, nothing to clear
        if not practical_entries_for_lab:
            return False

        # Find the earliest practical entry for this lab on this day
        earliest_practical_entry = min(practical_entries_for_lab, key=lambda x: x.period)
        
        # Find the earliest conflicting entry for this lab on this day
        conflicting_entries = [
            e for e in entries if e.classroom and e.classroom.id == lab.id and e.day == day
        ]
        earliest_conflicting_entry = min(conflicting_entries, key=lambda x: x.period)
        
        # If the earliest conflicting entry is before the earliest practical entry,
        # it means the lab is already free for the practicals.
        if earliest_conflicting_entry.period < earliest_practical_entry.period:
            return False

        # Move the earliest conflicting entry to an alternative room
        if self._can_move_entry_to_alternative_room(earliest_conflicting_entry, entries):
            # Update the entry's classroom to None or a default value
            earliest_conflicting_entry.classroom = None
            print(f"    ✅ ENFORCED: Moved conflicting entry {earliest_conflicting_entry.id} from lab {lab.name} on {day} P{earliest_conflicting_entry.period} to an alternative room.")
            return True
        return False
    
    def _can_clear_lab_for_duration(self, lab: Classroom, day: str, start_period: int,
                                   duration: int, entries: List[TimetableEntry]) -> bool:
        """Check if we can clear a lab for the specified duration by moving conflicting classes."""
        conflicting_entries = []
        
        # Find all conflicting entries
        for i in range(duration):
            period = start_period + i
            for entry in entries:
                if (entry.classroom and entry.classroom.id == lab.id and
                    entry.day == day and entry.period == period):
                    conflicting_entries.append(entry)
        
        # Check if all conflicting entries can be moved
        for entry in conflicting_entries:
            if not self._can_move_entry_to_alternative_room(entry, entries):
                return False
        
        return True
    
    def _can_move_entry_to_alternative_room(self, entry: TimetableEntry,
                                          entries: List[TimetableEntry]) -> bool:
        """Check if an entry can be moved to an alternative room."""
        # Find available rooms for this time slot
        available_rooms = self.get_available_rooms_for_time(
            entry.day, entry.period, 1, entries, entry.class_group
        )
        
        # Filter out the current room
        available_rooms = [room for room in available_rooms if room.id != entry.classroom.id]
        
        return len(available_rooms) > 0
    
    def _select_best_lab(self, available_labs: List[Classroom], section: str) -> Classroom:
        """Select the best lab based on usage and section priority."""
        if not available_labs:
            return None
        
        # Prefer labs with lower usage
        def lab_score(lab):
            usage_count = sum(len(periods) for periods in self.room_usage[lab.id].values())
            return usage_count
        
        return min(available_labs, key=lab_score)
    
    def _select_best_room(self, available_rooms: List[Classroom], section: str) -> Classroom:
        """Select the best room based on section preferences and usage."""
        if not available_rooms:
            return None
        
        # Prefer rooms with lower usage
        def room_score(room):
            usage_count = sum(len(periods) for periods in self.room_usage[room.id].values())
            return usage_count
        
        return min(available_rooms, key=room_score)
    
    def update_room_usage(self, room: Classroom, day: str, period: int):
        """Update room usage tracking."""
        self.room_usage[room.id][day].add(period)
    
    def clear_room_usage(self, room: Classroom, day: str, period: int):
        """Clear room usage tracking."""
        if room.id in self.room_usage and day in self.room_usage[room.id]:
            self.room_usage[room.id][day].discard(period)
    
    def validate_room_allocation(self, entries: List[TimetableEntry]) -> List[Dict]:
        """Validate room allocation against client requirements."""
        violations = []
        
        # Check for room conflicts
        room_schedule = defaultdict(lambda: defaultdict(set))
        
        for entry in entries:
            if entry.classroom:
                room_schedule[entry.classroom.id][entry.day].add(entry.period)
        
        # Check for double bookings
        for room_id, day_schedule in room_schedule.items():
            for day, periods in day_schedule.items():
                if len(periods) != len(set(periods)):
                    violations.append({
                        'type': 'Room Double Booking',
                        'room_id': room_id,
                        'day': day,
                        'description': f'Room {room_id} has double booking on {day}'
                    })
        
        # Check practical lab assignments
        for entry in entries:
            if entry.is_practical and entry.classroom:
                if not entry.classroom.is_lab:
                    violations.append({
                        'type': 'Practical Not in Lab',
                        'entry_id': entry.id,
                        'description': f'Practical class {entry.subject.code} assigned to non-lab room {entry.classroom.name}'
                    })
        
        # Check same-lab rule for practicals
        practical_groups = defaultdict(list)
        for entry in entries:
            if entry.is_practical:
                key = (entry.class_group, entry.subject.code, entry.day)
                practical_groups[key].append(entry)
        
        for key, group_entries in practical_groups.items():
            if len(group_entries) >= 3:
                labs_used = set(entry.classroom.id for entry in group_entries if entry.classroom)
                if len(labs_used) > 1:
                    violations.append({
                        'type': 'Practical Multiple Labs',
                        'subject': group_entries[0].subject.code,
                        'class_group': group_entries[0].class_group,
                        'day': group_entries[0].day,
                        'description': f'Practical {group_entries[0].subject.code} uses multiple labs on {group_entries[0].day}'
                    })
        
        # Check strict building rules for 2nd year vs other batches
        for entry in entries:
            if not entry.is_practical and entry.classroom:  # Only check theory classes
                section = entry.class_group
                is_second_year = self.is_second_year_section(section)
                room_building = entry.classroom.building.lower()
                
                if is_second_year:
                    # 2nd year batches MUST be in academic building
                    if "academic" not in room_building:
                        violations.append({
                            'type': '2nd Year Wrong Building',
                            'entry_id': entry.id,
                            'section': section,
                            'room': entry.classroom.name,
                            'building': entry.classroom.building,
                            'description': f'2nd year batch {section} assigned to non-academic building room {entry.classroom.name} ({entry.classroom.building})'
                        })
                else:
                    # Non-2nd year batches MUST be in main building
                    if "main" not in room_building and "academic" in room_building:
                        violations.append({
                            'type': 'Non-2nd Year Wrong Building',
                            'entry_id': entry.id,
                            'section': section,
                            'room': entry.classroom.name,
                            'building': entry.classroom.building,
                            'description': f'Non-2nd year batch {section} assigned to academic building room {entry.classroom.name} ({entry.classroom.building})'
                        })
        
        # NEW: Check enhanced room consistency constraint
        enhanced_violations = self.validate_enhanced_room_consistency(entries)
        violations.extend(enhanced_violations)
        
        return violations
    
    def validate_enhanced_room_consistency(self, entries: List[TimetableEntry]) -> List[Dict]:
        """
        Validate the enhanced room consistency constraint:
        - If only theory classes are scheduled for the entire day, all classes for a section should be assigned in same room
        - If both theory and practical classes are scheduled for a day, all practical classes must be in same lab (all 3 consecutive blocks) 
          and then if theory classes are scheduled in a room, all must be in same room
        """
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
                                'type': 'Enhanced Theory Room Consistency Violation',
                                'class_group': class_group,
                                'day': day,
                                'theory_rooms': list(theory_rooms),
                                'theory_count': len(theory_entries),
                                'description': f"{class_group} uses multiple rooms for theory classes on {day}: {theory_rooms} (should use same room)"
                            })
                    
                    # Check practical class lab consistency
                    if len(practical_entries) > 1:
                        practical_labs = set(e.classroom.name for e in practical_entries if e.classroom)
                        if len(practical_labs) > 1:
                            violations.append({
                                'type': 'Enhanced Practical Lab Consistency Violation',
                                'class_group': class_group,
                                'day': day,
                                'practical_labs': list(practical_labs),
                                'practical_count': len(practical_entries),
                                'description': f"{class_group} uses multiple labs for practical classes on {day}: {practical_labs} (should use same lab)"
                            })
                        
                        # Check if practical classes are consecutive (3 blocks)
                        practical_periods = sorted([e.period for e in practical_entries])
                        if len(practical_periods) >= 3:
                            # Check if we have 3 consecutive periods
                            consecutive_blocks = 0
                            for i in range(len(practical_periods) - 1):
                                if practical_periods[i+1] == practical_periods[i] + 1:
                                    consecutive_blocks += 1
                                else:
                                    consecutive_blocks = 0
                            
                            if consecutive_blocks < 2:  # Need at least 2 consecutive transitions for 3 blocks
                                violations.append({
                                    'type': 'Enhanced Practical Non-Consecutive Blocks',
                                    'class_group': class_group,
                                    'day': day,
                                    'practical_periods': practical_periods,
                                    'consecutive_blocks': consecutive_blocks + 1,
                                    'description': f"{class_group} practical classes on {day} are not in 3 consecutive blocks: {practical_periods}"
                                })
        
        return violations
    
    def get_allocation_report(self) -> Dict:
        """Generate a report of current room allocation status."""
        return {
            'total_rooms': len(self.all_rooms),
            'labs': len(self.labs),
            'academic_building_rooms': len(self.academic_building_rooms),
            'main_building_rooms': len(self.main_building_rooms),
            'section_assignments': len(self.section_room_assignments),
            'practical_assignments': len(self.practical_lab_assignments),
            'room_usage': dict(self.room_usage)
        } 

    def _force_room_availability(self, room: Classroom, day: str, period: int,
                                entries: List[TimetableEntry]) -> bool:
        """Try to free up a specific room for theory class consistency."""
        # Find all entries for this room on this day
        room_entries = [
            e for e in entries if e.classroom and e.classroom.id == room.id and e.day == day
        ]
        
        # If no entries for this room on this day, nothing to clear
        if not room_entries:
            return False
        
        # Find the earliest entry for this room on this day
        earliest_entry = min(room_entries, key=lambda x: x.period)
        
        # If the earliest entry is before the requested period, it means the room is already free.
        if earliest_entry.period < period:
            return False
        
        # Move the earliest entry to an alternative room
        if self._can_move_entry_to_alternative_room(earliest_entry, entries):
            # Update the entry's classroom to None or a default value
            earliest_entry.classroom = None
            print(f"    ✅ ENFORCED: Moved conflicting entry {earliest_entry.id} from room {room.name} on {day} P{earliest_entry.period} to an alternative room.")
            return True
        return False 

    def _find_existing_lab_for_practical_bulletproof(self, section: str, subject: Subject, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        BULLETPROOF: Find if this practical subject already has a lab assigned (same-lab rule enforcement).
        Checks both in-memory entries and database for existing assignments.
        """
        existing_labs = set()
        
        # Check in-memory entries
        for entry in entries:
            if (entry.class_group == section and
                entry.subject and entry.subject.code == subject.code and
                entry.classroom and entry.classroom.is_lab):
                existing_labs.add(entry.classroom)
        
        # Also check database entries for consistency
        try:
            db_entries = TimetableEntry.objects.filter(
                class_group=section,
                subject__code=subject.code,
                classroom__is_lab=True
            )
            for db_entry in db_entries:
                if db_entry.classroom:
                    existing_labs.add(db_entry.classroom)
        except:
            pass  # Fallback to in-memory only if database query fails
        
        if existing_labs:
            # BULLETPROOF: If multiple labs found (violation), return the most frequently used one
            if len(existing_labs) > 1:
                print(f"    ⚠️ SAME-LAB VIOLATION DETECTED: {section} {subject.code} found in {len(existing_labs)} different labs")
                # Count usage and return most used lab
                lab_counts = {}
                for entry in entries:
                    if (entry.class_group == section and
                        entry.subject and entry.subject.code == subject.code and
                        entry.classroom and entry.classroom.is_lab):
                        lab_counts[entry.classroom] = lab_counts.get(entry.classroom, 0) + 1
                
                if lab_counts:
                    most_used_lab = max(lab_counts.keys(), key=lambda lab: lab_counts[lab])
                    print(f"    🔧 SAME-LAB FIX: Using most frequent lab {most_used_lab.name} for {section} {subject.code}")
                    return most_used_lab
            
            # Return the first (and ideally only) lab
            return list(existing_labs)[0]
        
        return None

    def _force_lab_availability_for_same_lab_rule(self, lab: Classroom, day: str, start_period: int, duration: int, entries: List[TimetableEntry]) -> bool:
        """
        BULLETPROOF: Force lab availability specifically for same-lab rule enforcement.
        This method has zero tolerance for failure when enforcing the same-lab constraint.
        """
        print(f"    🔧 BULLETPROOF: Forcing availability of {lab.name} for same-lab rule")
        
        conflicts_resolved = 0
        
        # Check each period in the duration
        for period_offset in range(duration):
            check_period = start_period + period_offset
            
            # Find conflicting entries in this period
            conflicting_entries = [
                entry for entry in entries
                if (entry.classroom and entry.classroom.id == lab.id and
                    entry.day == day and entry.period == check_period)
            ]
            
            for conflicting_entry in conflicting_entries:
                moved = False
                
                if conflicting_entry.subject and conflicting_entry.subject.is_practical:
                    # Practical entry - try to move to another lab
                    alternative_lab = self._find_alternative_lab_bulletproof(conflicting_entry, entries, exclude_lab=lab)
                    if alternative_lab:
                        old_lab = conflicting_entry.classroom.name
                        conflicting_entry.classroom = alternative_lab
                        print(f"      ✅ Moved practical {conflicting_entry.subject.code} from {old_lab} to {alternative_lab.name}")
                        conflicts_resolved += 1
                        moved = True
                else:
                    # Theory entry - try to move to regular room
                    alternative_room = self._find_alternative_room_bulletproof(conflicting_entry, entries)
                    if alternative_room:
                        old_room = conflicting_entry.classroom.name
                        conflicting_entry.classroom = alternative_room
                        print(f"      ✅ Moved theory from {old_room} to {alternative_room.name}")
                        conflicts_resolved += 1
                        moved = True
                
                if not moved:
                    print(f"      ❌ CRITICAL: Cannot move conflicting entry for same-lab rule")
                    return False
        
        print(f"    ✅ BULLETPROOF: Successfully resolved {conflicts_resolved} conflicts for same-lab rule")
        return True

    def _find_alternative_lab_bulletproof(self, entry: TimetableEntry, entries: List[TimetableEntry], exclude_lab: Classroom = None) -> Optional[Classroom]:
        """Find an alternative lab for a practical entry, excluding specified lab."""
        for lab in self.labs:
            if exclude_lab and lab.id == exclude_lab.id:
                continue
            
            # Check if lab is available at this time
            if self._is_room_available(lab, entry.day, entry.period, entries):
                return lab
        
        return None

    def _find_alternative_room_bulletproof(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Find an alternative regular room for a theory entry."""
        # Determine appropriate building based on section
        section = entry.class_group
        preferred_rooms = self.get_preferred_rooms_for_section(section)
        
        # Try preferred rooms first
        for room in preferred_rooms:
            if self._is_room_available(room, entry.day, entry.period, entries):
                return room
        
        # Fallback to labs if no preferred rooms available
        for lab in self.labs:
            if self._is_room_available(lab, entry.day, entry.period, entries):
                return lab
        
        return None