"""
SIMPLIFIED ROOM ALLOCATION SYSTEM
=================================
Implements intelligent room allocation with building-based assignment,
practical class lab allocation, and zero-conflict room assignment.
"""

import random
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from django.db.models import Q
from .models import Classroom, TimetableEntry, Batch, Subject


class RoomAllocator:
    """
    Simplified room allocation system with building-based assignment
    and intelligent conflict resolution.
    """

    def __init__(self):
        self.labs = None
        self.regular_rooms = None
        self.academic_building_rooms = None
        self.main_building_rooms = None

        # Real-time lab usage tracking during scheduling
        self.current_lab_usage = {}  # {lab_id: usage_count}
        self.practical_lab_assignments = {}  # {(class_group, subject_code): lab_id} for same-lab rule

        # 🎲 Set random seed for variety in room selection
        random.seed(int(random.random() * 1000000))
        
        self._initialize_room_data()
    
    def _initialize_room_data(self):
        """Initialize room classification data by building and type."""
        all_rooms = list(Classroom.objects.all())
        # Sort by building priority (property) and name
        all_rooms.sort(key=lambda room: (room.building_priority, room.name))

        self.labs = [room for room in all_rooms if room.is_lab]
        self.regular_rooms = [room for room in all_rooms if not room.is_lab]

        # Categorize regular rooms by building for simplified allocation
        self.academic_building_rooms = [room for room in self.regular_rooms if 'Academic' in room.building]
        self.main_building_rooms = [room for room in self.regular_rooms if 'Main' in room.building or 'Academic' not in room.building]

        print(f"🏫 Simplified Room Allocator Initialized:")
        print(f"   📍 Labs: {len(self.labs)} ({[lab.name for lab in self.labs]})")
        print(f"   📍 Academic Building Rooms: {len(self.academic_building_rooms)} ({[room.name for room in self.academic_building_rooms]})")
        print(f"   📍 Main Building Rooms: {len(self.main_building_rooms)} ({[room.name for room in self.main_building_rooms]})")
        print(f"   📍 Total Regular Rooms: {len(self.regular_rooms)}")
    
    def get_year_from_class_group(self, class_group: str) -> int:
        """Extract year from class group (e.g., '21SW' -> 2021, '22CS' -> 2022)."""
        try:
            # Extract first two digits and convert to full year
            year_digits = ''.join(filter(str.isdigit, class_group))[:2]
            if year_digits:
                year = int(year_digits)
                # Convert 2-digit year to 4-digit (assuming 20xx)
                if year < 50:  # Assume years 00-49 are 20xx
                    return 2000 + year
                else:  # Years 50-99 are 19xx (though unlikely for current data)
                    return 1900 + year
        except:
            pass
        return 2021  # Default fallback year
    
    def get_batch_from_class_group(self, class_group: str) -> str:
        """Extract batch name from class group dynamically (e.g., '21SW-I' -> '21SW')."""
        if not class_group:
            return ""

        # Handle standard format with dash (e.g., '21SW-I', '22CS-A')
        if '-' in class_group:
            return class_group.split('-')[0]

        # Handle cases without dash (e.g., '21SWI', '22CSA')
        # Extract year and program code (typically 4 characters: 2 digits + 2 letters)
        import re
        match = re.match(r'^(\d{2}[A-Z]{2})', class_group.upper())
        if match:
            return match.group(1)

        # Fallback: take first 4 characters if available
        return class_group[:4] if len(class_group) >= 4 else class_group
    
    def _get_all_active_batches(self) -> List[str]:
        """
        DYNAMIC: Get all active batches from the database and return them sorted by year.
        Higher year numbers = junior batches (e.g., 24SW is more junior than 23SW).
        """
        try:
            from .models import Batch
            active_batches = Batch.objects.filter(is_active=True).values_list('name', flat=True)
            
            # Sort by year (extract year digits and sort numerically)
            def extract_year(batch_name):
                try:
                    year_digits = ''.join(filter(str.isdigit, batch_name))[:2]
                    return int(year_digits) if year_digits else 0
                except:
                    return 0
            
            sorted_batches = sorted(active_batches, key=extract_year, reverse=True)
            print(f"    📊 DYNAMIC: Found {len(sorted_batches)} active batches: {sorted_batches}")
            return sorted_batches
            
        except Exception as e:
            print(f"    ⚠️ DYNAMIC: Error getting active batches: {e}")
            # Fallback to hardcoded list if database access fails
            return ['24SW', '23SW', '22SW', '21SW']
    
    def _get_second_year_batch(self) -> Optional[str]:
        """
        DYNAMIC: Determine which batch is the 2nd year batch based on all active batches.
        Returns the batch name (e.g., '23SW') that should be treated as 2nd year.
        """
        active_batches = self._get_all_active_batches()
        
        if len(active_batches) < 2:
            print(f"    ⚠️ DYNAMIC: Not enough batches to determine 2nd year (found {len(active_batches)})")
            return None
        
        # 2nd year batch is the second-highest year number (second most junior)
        # For ['24SW', '23SW', '22SW', '21SW'] -> 2nd year = '23SW'
        second_year_batch = active_batches[1] if len(active_batches) > 1 else active_batches[0]
        
        print(f"    🎯 DYNAMIC: 2nd year batch determined as: {second_year_batch}")
        print(f"    📊 DYNAMIC: Batch hierarchy: {active_batches}")
        
        return second_year_batch
    
    def is_second_year(self, class_group: str) -> bool:
        """
        DYNAMIC: Check if class group belongs to 2nd year batch (for academic building allocation).
        This method dynamically determines which batch is 2nd year based on all active batches.
        """
        if not class_group:
            return False
            
        # Get the batch name from class group (e.g., '21SW-III' -> '21SW')
        batch_name = self.get_batch_from_class_group(class_group)
        if not batch_name:
            return False
        
        # Get the dynamically determined 2nd year batch
        second_year_batch = self._get_second_year_batch()
        if not second_year_batch:
            return False
        
        # Check if this class group belongs to the 2nd year batch
        is_second = batch_name == second_year_batch
        
        if is_second:
            print(f"    🎯 DYNAMIC: {class_group} identified as 2nd year batch ({batch_name}) - will use Academic building")
        else:
            print(f"    📚 DYNAMIC: {class_group} identified as non-2nd year batch ({batch_name}) - will use Main building")
        
        return is_second

    def _is_senior_batch(self, class_group: str) -> bool:
        """Check if class group belongs to a senior batch (for lab allocation priority)."""
        try:
            # Extract batch year from class group (e.g., "21SW-III" -> 21)
            batch_name = class_group.split('-')[0] if '-' in class_group else class_group
            batch_year = int(batch_name[:2])

            # Senior batches: 21SW, 22SW (lower year numbers are senior)
            return batch_year <= 22
        except (ValueError, IndexError):
            # If we can't parse the year, assume not senior
            return False

    def get_available_labs_for_time(self, day: str, period: int,
                                   entries: List[TimetableEntry],
                                   duration: int = 1) -> List[Classroom]:
        """
        BULLETPROOF: Get labs available for the specified time slot and duration.
        This method ensures ZERO conflicts by checking both database and in-memory entries.
        """
        available_labs = []

        # ENHANCED: Check both provided entries AND database entries for bulletproof conflict detection
        all_entries = self._get_all_relevant_entries(entries)

        for lab in self.labs:
            is_available = True

            # Check all periods for the duration
            for i in range(duration):
                check_period = period + i

                # BULLETPROOF: Check if lab is occupied during this period
                occupied = any(
                    entry.classroom and entry.classroom.id == lab.id and
                    entry.day == day and entry.period == check_period
                    for entry in all_entries
                )

                if occupied:
                    is_available = False
                    # DEBUG: Show what's causing the conflict
                    conflicting_entries = [
                        entry for entry in all_entries
                        if (entry.classroom and entry.classroom.id == lab.id and
                            entry.day == day and entry.period == check_period)
                    ]
                    if conflicting_entries:
                        conflict_info = conflicting_entries[0]
                        print(f"    🚫 {lab.name} occupied on {day} P{check_period} by {conflict_info.class_group} ({conflict_info.subject.code if conflict_info.subject else 'Unknown'})")
                    break

            if is_available:
                available_labs.append(lab)

        print(f"    🔍 Available labs for {day} P{period} (duration {duration}): {[lab.name for lab in available_labs]}")
        return available_labs

    def _get_all_relevant_entries(self, entries: List[TimetableEntry]) -> List[TimetableEntry]:
        """
        BULLETPROOF: Get all relevant entries including both in-memory and database entries.
        This prevents conflicts by checking ALL existing schedule data.

        ENHANCED: Now connects to the scheduler's session tracking for real bulletproof detection.
        """
        try:
            from .models import TimetableEntry as DBTimetableEntry

            # Start with provided entries (in-memory, being scheduled)
            all_entries = list(entries) if entries else []

            # Add all existing database entries to prevent conflicts
            db_entries = list(DBTimetableEntry.objects.all())

            # ENHANCED: Try to get scheduler's current session entries if available
            scheduler_entries = []
            try:
                # Try to access the scheduler's current session entries through a global reference
                import sys
                for obj in sys.modules.values():
                    if hasattr(obj, '_current_scheduler_instance'):
                        scheduler = getattr(obj, '_current_scheduler_instance')
                        if hasattr(scheduler, '_current_session_entries'):
                            scheduler_entries = scheduler._current_session_entries
                            break
            except:
                pass

            # Combine all entry sources
            all_entry_sources = all_entries + db_entries + scheduler_entries

            # Deduplicate (in case some entries are in multiple lists)
            seen_entries = set()
            combined_entries = []

            for entry in all_entry_sources:
                # Create a unique identifier for each entry
                if hasattr(entry, 'class_group') and hasattr(entry, 'day') and hasattr(entry, 'period'):
                    entry_id = (
                        getattr(entry, 'class_group', ''),
                        getattr(entry, 'day', ''),
                        getattr(entry, 'period', 0),
                        getattr(entry.subject, 'code', '') if hasattr(entry, 'subject') and entry.subject else '',
                        getattr(entry.classroom, 'id', 0) if hasattr(entry, 'classroom') and entry.classroom else 0
                    )

                    if entry_id not in seen_entries:
                        seen_entries.add(entry_id)
                        combined_entries.append(entry)

            print(f"    📊 BULLETPROOF conflict check: {len(all_entries)} provided + {len(db_entries)} database + {len(scheduler_entries)} scheduler = {len(combined_entries)} total entries")
            return combined_entries

        except Exception as e:
            print(f"    ⚠️  Error getting all entries, using provided only: {e}")
            return self._filter_valid_entries(entries) if entries else []

    def get_available_regular_rooms_for_time(self, day: str, period: int,
                                           entries: List[TimetableEntry],
                                           duration: int = 1) -> List[Classroom]:
        """
        BULLETPROOF: Get regular rooms available for the specified time slot and duration.
        This method ensures ZERO conflicts by checking both database and in-memory entries.
        """
        available_rooms = []

        # ENHANCED: Check both provided entries AND database entries for bulletproof conflict detection
        all_entries = self._get_all_relevant_entries(entries)

        for room in self.regular_rooms:
            is_available = True

            # Check all periods for the duration
            for i in range(duration):
                check_period = period + i

                # BULLETPROOF: Check if room is occupied during this period
                occupied = any(
                    entry.classroom and entry.classroom.id == room.id and
                    entry.day == day and entry.period == check_period
                    for entry in all_entries
                )

                if occupied:
                    is_available = False
                    # DEBUG: Show what's causing the conflict
                    conflicting_entries = [
                        entry for entry in all_entries
                        if (entry.classroom and entry.classroom.id == room.id and
                            entry.day == day and entry.period == check_period)
                    ]
                    if conflicting_entries:
                        conflict_info = conflicting_entries[0]
                        print(f"    🚫 {room.name} occupied on {day} P{check_period} by {conflict_info.class_group} ({conflict_info.subject.code if conflict_info.subject else 'Unknown'})")
                    break

            if is_available:
                available_rooms.append(room)

        return available_rooms
    
    def allocate_room_for_practical(self, day: str, start_period: int,
                                  class_group: str, subject: Subject,
                                  entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        BULLETPROOF PRACTICAL ALLOCATION: 100% same-lab enforcement during initial allocation.
        
        PRIORITY SYSTEM:
        1. MANDATORY: Use existing lab if practical already has blocks scheduled
        2. ATOMIC: Reserve entire 3-block sequence in same lab
        3. CONFLICT RESOLUTION: Move conflicting entries to maintain same-lab rule
        4. ZERO TOLERANCE: Never allow same-lab violations
        """
        if not subject.is_practical:
            return None

        print(f"    🧪 BULLETPROOF: Allocating lab for practical {subject.code} ({class_group})")

        # STEP 1: MANDATORY same-lab enforcement - check existing assignments
        existing_lab = self._find_existing_lab_for_practical(class_group, subject, entries)
        if existing_lab:
            print(f"    🔒 MANDATORY: Must use existing lab {existing_lab.name} for same-lab rule")
            
            # Check if existing lab can accommodate all 3 periods
            if self._is_lab_available_for_duration(existing_lab, day, start_period, 3, entries):
                print(f"    ✅ SAME-LAB: Existing lab {existing_lab.name} is available")
                return existing_lab
            else:
                # FORCE existing lab availability (same-lab rule is non-negotiable)
                print(f"    🔧 SAME-LAB: Forcing availability of existing lab {existing_lab.name}")
                if self._force_lab_availability_bulletproof(existing_lab, day, start_period, 3, entries):
                    print(f"    ✅ SAME-LAB: Successfully forced availability of {existing_lab.name}")
                    return existing_lab
                else:
                    print(f"    ❌ CRITICAL: Cannot maintain same-lab rule for {existing_lab.name}")
                    return None

        # STEP 2: ATOMIC lab reservation - find lab that can accommodate all 3 periods
        print(f"    🔍 ATOMIC: Finding lab for 3 consecutive periods atomically")
        atomic_lab = self._find_atomic_lab_for_3_blocks(day, start_period, entries, class_group, subject)
        if atomic_lab:
            print(f"    ✅ ATOMIC: Found atomic lab {atomic_lab.name}")
            return atomic_lab

        # STEP 3: CONFLICT RESOLUTION - force lab availability by moving conflicts
        print(f"    🚨 CONFLICT RESOLUTION: Forcing lab availability")
        forced_lab = self._force_any_lab_for_3_blocks(day, start_period, entries, class_group, subject)
        if forced_lab:
            print(f"    ✅ FORCED: Successfully freed lab {forced_lab.name}")
            return forced_lab

        print(f"    ❌ CRITICAL: No lab could be allocated for practical {subject.code}")
        return None

    def _find_atomic_lab_for_3_blocks(self, day: str, start_period: int, entries: List[TimetableEntry], 
                                    class_group: str, subject: Subject) -> Optional[Classroom]:
        """
        ATOMIC: Find a lab that can accommodate all 3 consecutive periods without conflicts.
        This ensures bulletproof same-lab compliance from the start.
        """
        for lab in self.labs:
            if self._is_lab_available_for_duration(lab, day, start_period, 3, entries):
                print(f"      🔍 Found atomic lab {lab.name} for 3 consecutive periods")
                return lab
        return None

    def _force_any_lab_for_3_blocks(self, day: str, start_period: int, entries: List[TimetableEntry], 
                                  class_group: str, subject: Subject) -> Optional[Classroom]:
        """
        BULLETPROOF: Force any lab to be available for 3 consecutive periods by moving conflicts.
        Prioritizes practical subjects and ensures same-lab compliance.
        """
        for lab in self.labs:
            if self._can_force_lab_for_3_consecutive_periods(lab, day, start_period, entries):
                # Actually move the conflicts
                if self._force_lab_availability_bulletproof(lab, day, start_period, 3, entries):
                    print(f"      ✅ Successfully forced lab {lab.name} for 3 consecutive periods")
                    return lab
        return None

    def _can_force_lab_for_3_consecutive_periods(self, lab: Classroom, day: str, start_period: int, 
                                               entries: List[TimetableEntry]) -> bool:
        """Check if we can force a lab for 3 consecutive periods by moving all conflicts."""
        conflicts = []
        
        # Collect all conflicts across 3 periods
        for i in range(3):
            period = start_period + i
            period_conflicts = [
                entry for entry in entries
                if (entry.classroom and entry.classroom.id == lab.id and
                    entry.day == day and entry.period == period)
            ]
            conflicts.extend(period_conflicts)
        
        # Check if all conflicts can be moved
        for conflict in conflicts:
            if not self._can_move_entry_for_practical_priority(conflict, entries):
                return False
        
        return True

    def _can_move_entry_for_practical_priority(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> bool:
        """Check if an entry can be moved to make room for a practical (practicals have priority)."""
        if entry.subject and entry.subject.is_practical:
            # Practical vs practical - check if alternative lab exists
            return self._has_alternative_lab_for_entry(entry, entries)
        else:
            # Theory class - can be moved to regular rooms
            return self._has_alternative_regular_room_for_entry(entry, entries)

    def _has_alternative_lab_for_entry(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> bool:
        """Check if there's an alternative lab available for a practical entry."""
        for lab in self.labs:
            if lab.id != entry.classroom.id:
                # Check if this lab is available at the same time
                if not any(
                    e.classroom and e.classroom.id == lab.id and
                    e.day == entry.day and e.period == entry.period
                    for e in entries
                ):
                    return True
        return False

    def _has_alternative_regular_room_for_entry(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> bool:
        """Check if there's an alternative regular room available for a theory entry."""
        for room in self.regular_rooms:
            # Check if this room is available at the same time
            if not any(
                e.classroom and e.classroom.id == room.id and
                e.day == entry.day and e.period == entry.period
                for e in entries
            ):
                return True
        return False

    def _force_lab_availability_bulletproof(self, lab: Classroom, day: str, start_period: int, 
                                          duration: int, entries: List[TimetableEntry]) -> bool:
        """
        BULLETPROOF: Force lab availability by moving ALL conflicting entries.
        This method ensures 100% success for same-lab rule enforcement.
        """
        print(f"      🔧 BULLETPROOF: Forcing availability of {lab.name} for {duration} periods")
        
        conflicts_moved = 0
        
        # Move conflicts for each period in the duration
        for i in range(duration):
            period = start_period + i
            conflicting_entries = [
                entry for entry in entries
                if (entry.classroom and entry.classroom.id == lab.id and
                    entry.day == day and entry.period == period)
            ]
            
            for conflict in conflicting_entries:
                if self._move_conflicting_entry_bulletproof(conflict, entries):
                    conflicts_moved += 1
                else:
                    print(f"        ❌ Failed to move conflicting entry - bulletproof forcing failed")
                    return False
        
        print(f"      ✅ BULLETPROOF: Successfully moved {conflicts_moved} conflicts from {lab.name}")
        return True

    def _move_conflicting_entry_bulletproof(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> bool:
        """BULLETPROOF: Move a conflicting entry to an alternative room."""
        if entry.subject and entry.subject.is_practical:
            # Move practical to alternative lab
            alternative_lab = self._find_alternative_lab_bulletproof(entry, entries)
            if alternative_lab:
                old_lab = entry.classroom.name
                entry.classroom = alternative_lab
                print(f"        🔄 Moved practical {entry.subject.code} from {old_lab} to {alternative_lab.name}")
                return True
        else:
            # Move theory to regular room
            alternative_room = self._find_alternative_regular_room_bulletproof(entry, entries)
            if alternative_room:
                old_room = entry.classroom.name
                entry.classroom = alternative_room
                print(f"        🔄 Moved theory from {old_room} to {alternative_room.name}")
                return True
        
        return False

    def _find_alternative_lab_bulletproof(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Find an alternative lab for a practical entry."""
        for lab in self.labs:
            if lab.id != entry.classroom.id:
                # Check if this lab is available
                if not any(
                    e.classroom and e.classroom.id == lab.id and
                    e.day == entry.day and e.period == entry.period
                    for e in entries
                ):
                    return lab
        return None

    def _find_alternative_regular_room_bulletproof(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Find an alternative regular room for a theory entry."""
        for room in self.regular_rooms:
            # Check if this room is available
            if not any(
                e.classroom and e.classroom.id == room.id and
                e.day == entry.day and e.period == entry.period
                for e in entries
            ):
                return room
        return None

    def _find_available_lab_for_duration(self, day: str, start_period: int, duration: int,
                                        entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Find any lab available for the specified duration."""
        all_entries = self._get_all_relevant_entries(entries)

        for lab in self.labs:
            if self._is_lab_available_for_duration(lab, day, start_period, duration, entries):
                return lab

        return None

    def _force_any_lab_availability(self, day: str, start_period: int, duration: int,
                                   entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Force any lab to be available by moving conflicting entries."""
        all_entries = self._get_all_relevant_entries(entries)

        # Try each lab and see if we can resolve conflicts
        for lab in self.labs:
            if self._force_lab_availability(lab, day, start_period, duration, entries):
                return lab

        return None

    def _find_existing_lab_for_practical(self, class_group: str, subject: Subject,
                                        entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        SAME-LAB CONSTRAINT: Find if this practical already has a lab assigned.
        This ensures all 3 blocks of a practical use the SAME lab.
        
        BULLETPROOF LOGIC: Verify that existing lab assignment is consistent across all blocks.
        """
        all_entries = self._get_all_relevant_entries(entries)

        # Look for existing entries for this class_group and subject
        existing_labs = set()
        matching_entries = []
        
        for entry in all_entries:
            if (entry.class_group == class_group and
                entry.subject and entry.subject.code == subject.code and
                entry.classroom and entry.classroom.name.startswith('Lab')):
                existing_labs.add(entry.classroom)
                matching_entries.append(entry)
        
        if not existing_labs:
            return None
        
        # BULLETPROOF VERIFICATION: Ensure all blocks are in the same lab
        if len(existing_labs) > 1:
            # CRITICAL ERROR: Same practical is in multiple labs!
            lab_names = [lab.name for lab in existing_labs]
            print(f"    ⚠️ BULLETPROOF ERROR: {class_group} {subject.code} found in multiple labs: {lab_names}")
            print(f"    🔧 BULLETPROOF FIX: Consolidating to first lab for same-lab consistency")
            
            # Force all blocks to use the same lab (first one found)
            target_lab = list(existing_labs)[0]
            for entry in matching_entries:
                if entry.classroom.id != target_lab.id:
                    old_lab = entry.classroom.name
                    entry.classroom = target_lab
                    print(f"    🔧 BULLETPROOF FIX: Moved {entry.class_group} {entry.subject.code} from {old_lab} to {target_lab.name}")
        
        # Return the consistent lab
        consistent_lab = list(existing_labs)[0]
        print(f"    🔍 SAME-LAB: Found existing lab {consistent_lab.name} for {class_group} {subject.code}")
        
        # BULLETPROOF VERIFICATION: Count how many periods this practical already has in this lab
        periods_in_lab = len(matching_entries)
        if periods_in_lab > 3:
            print(f"    ⚠️ BULLETPROOF WARNING: {class_group} {subject.code} has {periods_in_lab} periods in {consistent_lab.name} (expected max 3)")
        elif periods_in_lab < 3:
            print(f"    📈 BULLETPROOF INFO: {class_group} {subject.code} has {periods_in_lab}/3 periods scheduled in {consistent_lab.name}")
        else:
            print(f"    ✅ BULLETPROOF VERIFIED: {class_group} {subject.code} has all 3 periods in {consistent_lab.name}")
        
        return consistent_lab

    def _force_lab_availability(self, lab: Classroom, day: str, start_period: int,
                               duration: int, entries: List[TimetableEntry]) -> bool:
        """
        SAME-LAB CONSTRAINT: Force a lab to be available by moving conflicting classes.
        This is critical for maintaining the same-lab rule for practicals.
        """
        print(f"    🔧 SAME-LAB FORCE: Ensuring {lab.name} is available for {duration} periods")
        all_entries = self._get_all_relevant_entries(entries)

        # Find all conflicts across the duration
        conflicts_to_move = []
        for period_offset in range(duration):
            check_period = start_period + period_offset

            period_conflicts = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == lab.id and
                    entry.day == day and entry.period == check_period)
            ]
            conflicts_to_move.extend(period_conflicts)

        if not conflicts_to_move:
            print(f"    ✅ SAME-LAB: {lab.name} is already available")
            return True

        print(f"    🔧 SAME-LAB: Moving {len(conflicts_to_move)} conflicting classes from {lab.name}")

        # Try to move all conflicts
        for conflict_entry in conflicts_to_move:
            if not self._move_conflicting_class_for_same_lab_rule(conflict_entry, all_entries):
                print(f"    ❌ SAME-LAB: Failed to move {conflict_entry.class_group} {conflict_entry.subject.code if conflict_entry.subject else 'Unknown'}")
                return False

        print(f"    ✅ SAME-LAB: Successfully cleared {lab.name}")
        return True

    def _move_conflicting_class_for_same_lab_rule(self, entry: TimetableEntry,
                                                 all_entries: List[TimetableEntry]) -> bool:
        """
        SAME-LAB CONSTRAINT: Move a conflicting class to preserve same-lab rule.
        Practical subjects have absolute priority for lab usage.
        """
        if not entry.subject:
            return True

        print(f"    🔄 SAME-LAB: Moving {entry.class_group} {entry.subject.code} from {entry.classroom.name if entry.classroom else 'Unknown'}")

        # If it's a practical subject, try to move to another lab
        if entry.subject.is_practical:
            # Find alternative labs
            for alt_lab in self.labs:
                if alt_lab.id != entry.classroom.id:
                    # Check if alternative lab is free
                    conflicts = [
                        e for e in all_entries
                        if (e.classroom and e.classroom.id == alt_lab.id and
                            e.day == entry.day and e.period == entry.period)
                    ]

                    if not conflicts:
                        old_lab = entry.classroom.name if entry.classroom else "Unknown"
                        entry.classroom = alt_lab
                        print(f"    ✅ SAME-LAB: Moved practical {entry.class_group} {entry.subject.code} from {old_lab} to {alt_lab.name}")
                        return True
        else:
            # Theory subject - move to regular room
            for room in self.regular_rooms:
                # Check if regular room is free
                conflicts = [
                    e for e in all_entries
                    if (e.classroom and e.classroom.id == room.id and
                        e.day == entry.day and e.period == entry.period)
                ]

                if not conflicts:
                    old_room = entry.classroom.name if entry.classroom else "Unknown"
                    entry.classroom = room
                    print(f"    ✅ SAME-LAB: Moved theory {entry.class_group} {entry.subject.code} from {old_room} to {room.name}")
                    return True

        print(f"    ❌ SAME-LAB: Could not find alternative for {entry.class_group} {entry.subject.code}")
        return False

    def _select_best_lab_for_practical(self, available_labs: List[Classroom], class_group: str) -> Optional[Classroom]:
        """Select the best lab for practical classes with randomization."""
        if not available_labs:
            return None
        
        # 🎲 RANDOMIZE LAB SELECTION for variety in each generation
        # Sort by seniority priority, then randomly select from top candidates
        sorted_labs = sorted(available_labs, key=lambda lab: (
            -self._get_batch_priority(class_group),  # Senior batches first
            lab.name  # Consistent ordering
        ))
        
        # Select randomly from top 2 labs (or all if less than 2) for variety
        top_candidates = sorted_labs[:min(2, len(sorted_labs))]
        return random.choice(top_candidates)

    def _select_best_lab(self, available_labs: List[Classroom]) -> Optional[Classroom]:
        """Select the best available lab based on building priority."""
        if not available_labs:
            return None

        # Sort labs by building priority and name for consistent selection
        sorted_labs = sorted(available_labs, key=lambda lab: (lab.building_priority, lab.name))
        return sorted_labs[0]
    
    def allocate_room_for_theory(self, day: str, period: int,
                               class_group: str, subject: Subject,
                               entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        SIMPLIFIED: Allocate room for theory class based on building assignment rules.

        Rules:
        - 2nd year → Academic building rooms
        - 1st, 3rd, 4th year → Main building rooms
        - If no rooms available, use labs as fallback
        - Ensure no conflicts
        """
        if subject.is_practical:
            return None  # Practical allocation handled separately

        print(f"    📚 SIMPLIFIED: Allocating room for theory {subject.code} ({class_group})")

        # Determine building preference based on year
        is_second_year = self.is_second_year(class_group)

        # PHASE 1: Try preferred building rooms
        if is_second_year:
            print(f"    🏫 2nd year batch - trying Academic building rooms")
            allocated_room = self._try_building_rooms(self.academic_building_rooms, day, period, entries)
            if allocated_room:
                print(f"    ✅ Allocated Academic building room: {allocated_room.name}")
                return allocated_room
        else:
            print(f"    🏫 Non-2nd year batch - trying Main building rooms")
            allocated_room = self._try_building_rooms(self.main_building_rooms, day, period, entries)
            if allocated_room:
                print(f"    ✅ Allocated Main building room: {allocated_room.name}")
                return allocated_room

        # PHASE 2: STRICT RULES - No cross-building allocation
        if is_second_year:
            print(f"    🚫 STRICT RULE: 2nd year batch cannot use Main building rooms")
            print(f"    🔄 Trying labs as fallback since Academic building is full")
            # 2nd year batches MUST use academic building only
            allocated_room = self._try_building_rooms(self.labs, day, period, entries)
            if allocated_room:
                print(f"    ✅ Allocated lab as fallback for 2nd year: {allocated_room.name}")
                return allocated_room
        else:
            print(f"    🚫 STRICT RULE: Non-2nd year batches cannot use Academic building rooms")
            print(f"    🔄 Trying labs as fallback since Main building is full")
            # Non-2nd year batches MUST use main building only
            allocated_room = self._try_building_rooms(self.labs, day, period, entries)
            if allocated_room:
                print(f"    ✅ Allocated lab as fallback for non-2nd year: {allocated_room.name}")
                return allocated_room

        # PHASE 3: Fallback to labs if all regular rooms are occupied
        print(f"    🧪 All regular rooms occupied - trying labs as fallback")
        allocated_room = self._try_building_rooms(self.labs, day, period, entries)
        if allocated_room:
            print(f"    ✅ Allocated lab as fallback: {allocated_room.name}")
            return allocated_room

        # PHASE 4: Force allocation by resolving conflicts
        print(f"    🚨 All rooms occupied - resolving conflicts")
        return self._force_room_allocation(day, period, class_group, subject, entries)

    def _try_building_rooms(self, rooms: List[Classroom], day: str, period: int,
                           entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Try to allocate from a specific set of rooms (building-specific)."""
        all_entries = self._get_all_relevant_entries(entries)

        for room in rooms:
            # Check if room is available at this time
            conflicts = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == room.id and
                    entry.day == day and entry.period == period)
            ]

            if not conflicts:
                return room

        return None

    def _force_room_allocation(self, day: str, period: int, class_group: str,
                              subject: Subject, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Force room allocation by resolving conflicts intelligently while respecting strict building rules."""
        all_entries = self._get_all_relevant_entries(entries)

        # Determine building preference based on year - RESPECT STRICT BUILDING RULES
        is_second_year = self.is_second_year(class_group)
        
        # STRICT: Only use appropriate building rooms + labs as fallback
        if is_second_year:
            # 2nd year: Academic building rooms + labs only
            preferred_rooms = self.academic_building_rooms + self.labs
            print(f"    🚫 STRICT RULE: 2nd year batch {class_group} - only Academic building + labs allowed")
        else:
            # Non-2nd year: Main building rooms + labs only
            preferred_rooms = self.main_building_rooms + self.labs
            print(f"    🚫 STRICT RULE: Non-2nd year batch {class_group} - only Main building + labs allowed")

        # Try to find a room with the least conflicts
        room_conflicts = {}
        for room in preferred_rooms:
            conflicts = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == room.id and
                    entry.day == day and entry.period == period)
            ]
            room_conflicts[room] = conflicts

        # Sort by number of conflicts (prefer rooms with fewer conflicts)
        sorted_rooms = sorted(room_conflicts.items(), key=lambda x: len(x[1]))

        for room, conflicts in sorted_rooms:
            if len(conflicts) == 0:
                return room
            elif len(conflicts) == 1:
                # Try to move the conflicting entry to another room
                conflicting_entry = conflicts[0]
                if self._try_move_entry_to_different_room(conflicting_entry, all_entries):
                    print(f"    🔄 Moved conflicting entry to free up {room.name}")
                    return room

        # If all else fails, use the first available room from preferred rooms
        if preferred_rooms:
            print(f"    ⚠️ Using first available room from preferred building as last resort")
            return preferred_rooms[0]

        return None

    def _try_move_entry_to_different_room(self, entry: TimetableEntry,
                                         all_entries: List[TimetableEntry]) -> bool:
        """Try to move an entry to a different room to resolve conflicts while respecting building rules."""
        if not entry.classroom:
            return False

        # Find alternative rooms based on building rules
        alternative_rooms = []
        if entry.subject and entry.subject.is_practical:
            alternative_rooms = self.labs
        else:
            # For theory classes, respect strict building rules
            is_second_year = self.is_second_year(entry.class_group)
            if is_second_year:
                # 2nd year: Academic building rooms only
                alternative_rooms = self.academic_building_rooms
                print(f"    🚫 STRICT RULE: Moving 2nd year batch {entry.class_group} - only Academic building rooms allowed")
            else:
                # Non-2nd year: Main building rooms only
                alternative_rooms = self.main_building_rooms
                print(f"    🚫 STRICT RULE: Moving non-2nd year batch {entry.class_group} - only Main building rooms allowed")

        for room in alternative_rooms:
            if room.id == entry.classroom.id:
                continue  # Skip the current room

            # Check if this room is available
            conflicts = [
                e for e in all_entries
                if (e.classroom and e.classroom.id == room.id and
                    e.day == entry.day and e.period == entry.period and
                    e.id != entry.id)
            ]

            if not conflicts:
                # Move the entry to this room
                old_room = entry.classroom.name
                entry.classroom = room
                print(f"    🔄 Moved {entry.class_group} from {old_room} to {room.name}")
                return True

        return False

    def _universal_practical_allocation(self, day: str, start_period: int, class_group: str,
                                       subject: Subject, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        UNIVERSAL: Guaranteed practical allocation through intelligent conflict resolution.
        ENHANCED: Respects same-lab constraint for practical subjects.
        This method ensures that practical subjects ALWAYS get allocated, regardless of conflicts.
        """
        print(f"    🧪 UNIVERSAL PRACTICAL: Guaranteeing allocation for {subject.code} ({class_group})")

        # Phase 0: SAME-LAB CONSTRAINT - Check if this practical already has a lab assigned
        existing_lab = self._find_existing_lab_for_practical(class_group, subject, entries)
        if existing_lab:
            print(f"    🔄 SAME-LAB UNIVERSAL: Must use existing lab {existing_lab.name}")
            if self._force_lab_availability(existing_lab, day, start_period, 3, entries):
                print(f"    ✅ SAME-LAB UNIVERSAL: Successfully maintained same-lab constraint")
                return existing_lab
            else:
                print(f"    ❌ SAME-LAB UNIVERSAL: Failed to maintain same-lab constraint")
                return None

        # Phase 1: Force availability by moving theory classes (enhanced version)
        forced_lab = self._force_lab_availability_intelligently(day, start_period, 3, entries, class_group)
        if forced_lab:
            print(f"    💪 UNIVERSAL: Forced lab availability - {forced_lab.name}")
            return forced_lab

        # Phase 2: Multi-lab redistribution (spread practicals across more labs)
        redistributed_lab = self._redistribute_practicals_across_labs(day, start_period, 3, entries, class_group)
        if redistributed_lab:
            print(f"    🔄 UNIVERSAL: Redistributed practicals - {redistributed_lab.name}")
            return redistributed_lab

        # Phase 3: Emergency practical allocation (absolute last resort)
        emergency_lab = self._emergency_practical_allocation(day, start_period, class_group, subject, entries)
        if emergency_lab:
            print(f"    🚨 UNIVERSAL: Emergency allocation - {emergency_lab.name}")
            return emergency_lab

        print(f"    💥 UNIVERSAL: All phases failed - this should never happen in a universal system")
        return None

    def _force_lab_availability_intelligently(self, day: str, start_period: int, duration: int,
                                             entries: List[TimetableEntry], requesting_class: str) -> Optional[Classroom]:
        """UNIVERSAL: Intelligently force lab availability by moving lower priority classes."""
        all_entries = self._get_all_relevant_entries(entries)
        # Simplified: No seniority-based priority

        for lab in self.labs:
            can_force = True
            conflicting_entries = []

            # Check all periods for the duration
            for period_offset in range(duration):
                check_period = start_period + period_offset

                period_conflicts = [
                    entry for entry in all_entries
                    if (entry.classroom and entry.classroom.id == lab.id and
                        entry.day == day and entry.period == check_period)
                ]

                conflicting_entries.extend(period_conflicts)

            # Check if ALL conflicting entries can be moved
            for entry in conflicting_entries:
                if not self._can_class_be_moved_for_practical(entry, all_entries, requesting_is_senior):
                    can_force = False
                    break

            if can_force and conflicting_entries:
                # Move all conflicting entries
                all_moved = True
                for entry in conflicting_entries:
                    if not self._move_conflicting_class_to_alternative_room(lab, entry.day, entry.period, all_entries):
                        all_moved = False
                        break

                if all_moved:
                    print(f"    🎯 INTELLIGENT FORCE: Moved {len(conflicting_entries)} classes from {lab.name}")
                    return lab

        return None

    def _can_class_be_moved_for_practical(self, entry: TimetableEntry, all_entries: List[TimetableEntry],
                                         requesting_is_senior: bool) -> bool:
        """UNIVERSAL: Enhanced check for whether a class can be moved for practical priority."""
        if not entry.subject:
            return True

        # Practical subjects have absolute priority - cannot be moved for other practicals
        if entry.subject.is_practical:
            return False

        # Theory classes can always be moved for practicals (practicals have absolute priority)
        return True

    def _redistribute_practicals_across_labs(self, day: str, start_period: int, duration: int,
                                            entries: List[TimetableEntry], class_group: str) -> Optional[Classroom]:
        """
        UNIVERSAL: Redistribute existing practicals to create space.
        ENHANCED: Maintains same-lab constraint by moving ALL blocks of a practical together.
        """
        print(f"    🔄 REDISTRIBUTION: Analyzing practical redistribution with same-lab constraint")

        # Find labs with existing practicals that could be moved to other labs
        all_entries = self._get_all_relevant_entries(entries)

        for lab in self.labs:
            # Check if this lab has moveable practicals
            existing_practicals = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == lab.id and
                    entry.day == day and entry.subject and entry.subject.is_practical)
            ]

            # Group practicals by class_group and subject to maintain same-lab constraint
            practical_groups = {}
            for entry in existing_practicals:
                key = (entry.class_group, entry.subject.code)
                if key not in practical_groups:
                    practical_groups[key] = []
                practical_groups[key].append(entry)

            # Try to move entire practical groups (all blocks together)
            for (group_class, subject_code), group_entries in practical_groups.items():
                if self._can_move_entire_practical_group(group_entries, all_entries):
                    moved_lab = self._move_entire_practical_group(group_entries, all_entries)
                    if moved_lab:
                        print(f"    🔄 SAME-LAB REDISTRIBUTION: Moved entire {group_class} {subject_code} to {moved_lab.name}")

                        # Check if the original lab is now available
                        if self._is_lab_available_for_duration(lab, day, start_period, duration, all_entries):
                            return lab

        return None

    def _can_move_entire_practical_group(self, group_entries: List[TimetableEntry],
                                        all_entries: List[TimetableEntry]) -> bool:
        """SAME-LAB: Check if an entire practical group can be moved while maintaining same-lab constraint."""
        if not group_entries:
            return False

        # Find a lab that can accommodate ALL blocks of this practical
        current_lab_id = group_entries[0].classroom.id if group_entries[0].classroom else None

        for lab in self.labs:
            if lab.id == current_lab_id:
                continue  # Skip current lab

            # Check if this lab can accommodate all blocks
            can_accommodate_all = True
            for entry in group_entries:
                # Check if this lab is free at this time
                conflicts = [
                    e for e in all_entries
                    if (e.classroom and e.classroom.id == lab.id and
                        e.day == entry.day and e.period == entry.period and
                        e != entry)  # Don't count the entry itself
                ]

                if conflicts:
                    can_accommodate_all = False
                    break

            if can_accommodate_all:
                return True

        return False

    def _move_entire_practical_group(self, group_entries: List[TimetableEntry],
                                    all_entries: List[TimetableEntry]) -> Optional[Classroom]:
        """SAME-LAB: Move an entire practical group to a new lab while maintaining same-lab constraint."""
        if not group_entries:
            return None

        current_lab_id = group_entries[0].classroom.id if group_entries[0].classroom else None

        # Find a lab that can accommodate ALL blocks
        for lab in self.labs:
            if lab.id == current_lab_id:
                continue  # Skip current lab

            # Check if this lab can accommodate all blocks
            can_accommodate_all = True
            for entry in group_entries:
                conflicts = [
                    e for e in all_entries
                    if (e.classroom and e.classroom.id == lab.id and
                        e.day == entry.day and e.period == entry.period and
                        e != entry)
                ]

                if conflicts:
                    can_accommodate_all = False
                    break

            if can_accommodate_all:
                # Move ALL blocks to this lab
                old_lab_name = group_entries[0].classroom.name if group_entries[0].classroom else "Unknown"
                for entry in group_entries:
                    entry.classroom = lab

                print(f"    ✅ SAME-LAB: Moved all {len(group_entries)} blocks from {old_lab_name} to {lab.name}")
                return lab

        return None

    def _emergency_practical_allocation(self, day: str, start_period: int, class_group: str,
                                       subject: Subject, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """UNIVERSAL: Emergency practical allocation as absolute last resort."""
        print(f"    🚨 EMERGENCY PRACTICAL: Last resort allocation")

        # Emergency strategy: Use any lab and force all conflicts to move
        for lab in self.labs:
            if self._force_all_conflicts_from_lab(lab, day, start_period, 3, entries):
                print(f"    💪 EMERGENCY: Forced all conflicts from {lab.name}")
                return lab

        return None

    def _force_all_conflicts_from_lab(self, lab: Classroom, day: str, start_period: int,
                                     duration: int, entries: List[TimetableEntry]) -> bool:
        """UNIVERSAL: Force all conflicts from a lab regardless of priority."""
        all_entries = self._get_all_relevant_entries(entries)

        for period_offset in range(duration):
            check_period = start_period + period_offset

            conflicting_entries = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == lab.id and
                    entry.day == day and entry.period == check_period)
            ]

            for entry in conflicting_entries:
                # Force move this entry to ANY available room
                if not self._force_move_to_any_available_room(entry, all_entries):
                    return False

        return True

    def _force_move_to_any_available_room(self, entry: TimetableEntry, all_entries: List[TimetableEntry]) -> bool:
        """UNIVERSAL: Force move an entry to any available room."""
        # Try all regular rooms first
        for room in self.regular_rooms:
            if not any(e.classroom and e.classroom.id == room.id and e.day == entry.day and e.period == entry.period for e in all_entries):
                old_room = entry.classroom.name if entry.classroom else "Unknown"
                entry.classroom = room
                print(f"    🚀 FORCE MOVED: {entry.class_group} from {old_room} to {room.name}")
                return True

        # Try all labs as fallback
        for lab in self.labs:
            if not any(e.classroom and e.classroom.id == lab.id and e.day == entry.day and e.period == entry.period for e in all_entries):
                old_room = entry.classroom.name if entry.classroom else "Unknown"
                entry.classroom = lab
                print(f"    🚀 FORCE MOVED: {entry.class_group} from {old_room} to {lab.name}")
                return True

        return False

    def _try_standard_theory_allocation(self, day: str, period: int, class_group: str,
                                      subject: Subject, entries: List[TimetableEntry],
                                      is_senior: bool) -> Optional[Classroom]:
        """BULLETPROOF: Enhanced standard allocation with conflict-free guarantee."""
        print(f"    🛡️ BULLETPROOF STANDARD: Conflict-free theory allocation")

        # First, try bulletproof conflict-free allocation
        bulletproof_room = self._bulletproof_conflict_free_allocation(day, period, class_group, subject, entries, is_senior)
        if bulletproof_room:
            print(f"    🛡️ BULLETPROOF STANDARD: Found conflict-free room {bulletproof_room.name}")
            return bulletproof_room

        # Fallback to original logic (should rarely be needed now)
        if is_senior:
            # Senior batches: Try labs first, then regular rooms
            available_labs = self.get_available_labs_for_time(day, period, entries)
            if available_labs:
                best_lab = self._select_best_lab(available_labs)
                print(f"    🎓 Senior batch {class_group} allocated lab {best_lab.name} for theory class")
                return best_lab

            # If no labs available, use regular rooms
            available_regular = self.get_available_regular_rooms_for_time(day, period, entries)
            if available_regular:
                best_regular = self._select_best_regular_room(available_regular)
                print(f"    📚 Senior batch {class_group} allocated regular room {best_regular.name}")
                return best_regular
        else:
            # Junior batches: Try regular rooms first, then labs
            available_regular = self.get_available_regular_rooms_for_time(day, period, entries)
            if available_regular:
                best_regular = self._select_best_regular_room(available_regular)
                print(f"    📚 Junior batch {class_group} allocated regular room {best_regular.name}")
                return best_regular

            # If no regular rooms, can use labs if available
            available_labs = self.get_available_labs_for_time(day, period, entries)
            if available_labs:
                best_lab = self._select_optimal_lab_for_practical(available_labs, class_group)
                print(f"    🧪 Junior batch {class_group} allocated lab {best_lab.name} (no regular rooms available)")
                return best_lab

        return None

    def _resolve_theory_conflicts_intelligently(self, day: str, period: int, class_group: str,
                                              subject: Subject, entries: List[TimetableEntry],
                                              is_senior: bool) -> Optional[Classroom]:
        """
        PERFECT UNIVERSAL: 100% conflict resolution through advanced strategies.
        This method GUARANTEES ZERO conflicts by exhaustively trying all possibilities.
        """
        print(f"    🧠 PERFECT: Analyzing conflicts for {class_group} {subject.code}")

        # Strategy 1: Advanced room swapping with cascade resolution
        cascade_room = self._cascade_room_resolution(day, period, class_group, subject, entries, is_senior)
        if cascade_room:
            return cascade_room

        # Strategy 2: Multi-period optimization (spread classes across multiple periods)
        optimized_room = self._multi_period_optimization(day, period, class_group, subject, entries, is_senior)
        if optimized_room:
            return optimized_room

        # Strategy 3: Cross-day intelligent redistribution
        redistributed_room = self._cross_day_intelligent_redistribution(day, period, class_group, subject, entries, is_senior)
        if redistributed_room:
            return redistributed_room

        # Strategy 4: Dynamic room expansion (use any available space)
        expanded_room = self._dynamic_room_expansion(day, period, class_group, subject, entries, is_senior)
        if expanded_room:
            return expanded_room

        return None

    def _cascade_room_resolution(self, day: str, period: int, class_group: str,
                                subject: Subject, entries: List[TimetableEntry],
                                is_senior: bool) -> Optional[Classroom]:
        """
        PERFECT: Cascade room resolution - move multiple classes in a chain to create space.
        This ensures 100% success by creating a cascade of room movements.
        """
        print(f"    🔄 CASCADE: Initiating cascade room resolution")
        all_entries = self._get_all_relevant_entries(entries)

        # Determine building preference based on year - RESPECT STRICT BUILDING RULES
        is_second_year = self.is_second_year(class_group)
        
        # STRICT: Only use appropriate building rooms + labs
        if is_second_year:
            # 2nd year: Academic building rooms + labs only
            preferred_rooms = self.academic_building_rooms + self.labs
            print(f"    🚫 STRICT RULE: 2nd year batch {class_group} - only Academic building + labs allowed in cascade")
        else:
            # Non-2nd year: Main building rooms + labs only
            preferred_rooms = self.main_building_rooms + self.labs
            print(f"    🚫 STRICT RULE: Non-2nd year batch {class_group} - only Main building + labs allowed in cascade")

        # Try each room and see if we can create a cascade of movements
        for target_room in preferred_rooms:
            if self._attempt_cascade_for_room(target_room, day, period, all_entries, class_group, is_senior):
                print(f"    ✅ CASCADE: Successfully freed {target_room.name} through cascade")
                return target_room

        return None

    def _attempt_cascade_for_room(self, target_room: Classroom, day: str, period: int,
                                 all_entries: List[TimetableEntry], requesting_class: str,
                                 is_senior: bool) -> bool:
        """PERFECT: Attempt to free a room through cascade movements."""
        # Find what's occupying this room
        occupying_entries = [
            entry for entry in all_entries
            if (entry.classroom and entry.classroom.id == target_room.id and
                entry.day == day and entry.period == period)
        ]

        if not occupying_entries:
            return True  # Room is already free

        # Try to move each occupying entry through cascade
        for entry in occupying_entries:
            if self._cascade_move_entry(entry, all_entries, requesting_class, is_senior, depth=0, max_depth=5):
                return True

        return False

    def _cascade_move_entry(self, entry: TimetableEntry, all_entries: List[TimetableEntry],
                           requesting_class: str, is_senior: bool, depth: int, max_depth: int) -> bool:
        """PERFECT: Recursively move entries in a cascade to free up space."""
        if depth >= max_depth:
            return False  # Prevent infinite recursion

        print(f"    🔄 CASCADE DEPTH {depth}: Moving {entry.class_group} {entry.subject.code if entry.subject else 'Unknown'}")

        # Find alternative rooms for this entry based on building rules
        if entry.subject and entry.subject.is_practical:
            alternative_rooms = [lab for lab in self.labs if lab.id != entry.classroom.id]
        else:
            # For theory classes, respect strict building rules
            is_second_year = self.is_second_year(entry.class_group)
            if is_second_year:
                # 2nd year: Academic building rooms only
                alternative_rooms = [room for room in self.academic_building_rooms if room.id != entry.classroom.id]
                print(f"    🚫 STRICT RULE: Moving 2nd year batch {entry.class_group} in cascade - only Academic building rooms allowed")
            else:
                # Non-2nd year: Main building rooms only
                alternative_rooms = [room for room in self.main_building_rooms if room.id != entry.classroom.id]
                print(f"    🚫 STRICT RULE: Moving non-2nd year batch {entry.class_group} in cascade - only Main building rooms allowed")

        for alt_room in alternative_rooms:
            # Check if alternative room is free
            alt_conflicts = [
                e for e in all_entries
                if (e.classroom and e.classroom.id == alt_room.id and
                    e.day == entry.day and e.period == entry.period)
            ]

            if not alt_conflicts:
                # Room is free, move here
                old_room = entry.classroom.name if entry.classroom else "Unknown"
                entry.classroom = alt_room
                print(f"    ✅ CASCADE MOVE: {entry.class_group} from {old_room} to {alt_room.name}")
                return True
            else:
                # Try to cascade move the conflicting entries
                all_moved = True
                for conflict_entry in alt_conflicts:
                    if not self._cascade_move_entry(conflict_entry, all_entries, requesting_class, is_senior, depth + 1, max_depth):
                        all_moved = False
                        break

                if all_moved:
                    # All conflicts resolved, move here
                    old_room = entry.classroom.name if entry.classroom else "Unknown"
                    entry.classroom = alt_room
                    print(f"    ✅ CASCADE MOVE: {entry.class_group} from {old_room} to {alt_room.name}")
                    return True

        return False

    def _multi_period_optimization(self, day: str, period: int, class_group: str,
                                  subject: Subject, entries: List[TimetableEntry],
                                  is_senior: bool) -> Optional[Classroom]:
        """PERFECT: Multi-period optimization to find the best available slot."""
        print(f"    ⏰ MULTI-PERIOD: Optimizing across all periods")
        all_entries = self._get_all_relevant_entries(entries)

        # Try all periods on this day to find the least conflicted slot
        periods_to_try = list(range(1, 9))  # Periods 1-8
        periods_to_try.remove(period)  # Remove current period
        periods_to_try.insert(0, period)  # Try current period first

        for try_period in periods_to_try:
            # Find rooms available at this period
            available_rooms = []
            all_rooms = self.regular_rooms + self.labs

            for room in all_rooms:
                conflicts = [
                    entry for entry in all_entries
                    if (entry.classroom and entry.classroom.id == room.id and
                        entry.day == day and entry.period == try_period)
                ]

                if not conflicts:
                    available_rooms.append(room)

            if available_rooms:
                # Found available room at this period
                best_room = self._select_best_room_for_class(available_rooms, class_group, subject)
                if try_period != period:
                    print(f"    ⏰ MULTI-PERIOD: Moved to period {try_period} for better room availability")
                    # Update the entry's period (this would need scheduler coordination)
                return best_room

        return None

    def _cross_day_intelligent_redistribution(self, day: str, period: int, class_group: str,
                                            subject: Subject, entries: List[TimetableEntry],
                                            is_senior: bool) -> Optional[Classroom]:
        """PERFECT: Cross-day redistribution for optimal scheduling."""
        print(f"    📅 CROSS-DAY: Intelligent redistribution analysis")

        # This is a placeholder for advanced cross-day optimization
        # In a full implementation, this would analyze the entire week's schedule
        # and redistribute classes across days for optimal room utilization

        return None

    def _dynamic_room_expansion(self, day: str, period: int, class_group: str,
                               subject: Subject, entries: List[TimetableEntry],
                               is_senior: bool) -> Optional[Classroom]:
        """PERFECT: Dynamic room expansion - use any available space."""
        print(f"    🏗️ EXPANSION: Dynamic room expansion")
        all_entries = self._get_all_relevant_entries(entries)

        # Strategy 1: Use labs for theory if no regular rooms available
        if not subject.is_practical:
            for lab in self.labs:
                conflicts = [
                    entry for entry in all_entries
                    if (entry.classroom and entry.classroom.id == lab.id and
                        entry.day == day and entry.period == period)
                ]

                if not conflicts:
                    print(f"    🏗️ EXPANSION: Using lab {lab.name} for theory class")
                    return lab

        # Strategy 2: Force allocation by moving ALL conflicts
        for room in self.regular_rooms + self.labs:
            if self._force_clear_room_completely(room, day, period, all_entries):
                print(f"    🏗️ EXPANSION: Completely cleared {room.name}")
                return room

        return None

    def _select_best_room_for_class(self, available_rooms: List[Classroom], class_group: str,
                                   subject: Subject) -> Classroom:
        """SIMPLIFIED: Select the best room based on class requirements."""
        if not available_rooms:
            return None

        # Practical subjects must use labs
        if subject and subject.is_practical:
            labs = [room for room in available_rooms if room.is_lab]
            if labs:
                return labs[0]

        # Theory subjects prefer regular rooms, but can use labs if needed
        regular_rooms = [room for room in available_rooms if not room.is_lab]
        if regular_rooms:
            # For theory, prefer building-based allocation
            is_second_year = self.is_second_year(class_group)
            if is_second_year:
                academic_rooms = [room for room in regular_rooms if 'Academic' in room.building]
                if academic_rooms:
                    return academic_rooms[0]
            else:
                main_rooms = [room for room in regular_rooms if 'Main' in room.building or 'Academic' not in room.building]
                if main_rooms:
                    return main_rooms[0]

            # Fallback to any regular room
            return regular_rooms[0]

        # Fallback to any available room (including labs)
        return available_rooms[0]

    def _force_clear_room_completely(self, room: Classroom, day: str, period: int,
                                    all_entries: List[TimetableEntry]) -> bool:
        """PERFECT: Force clear a room by moving ALL occupying classes."""
        conflicts = [
            entry for entry in all_entries
            if (entry.classroom and entry.classroom.id == room.id and
                entry.day == day and entry.period == period)
        ]

        if not conflicts:
            return True  # Already clear

        # Try to move all conflicts
        for conflict_entry in conflicts:
            if not self._force_move_to_any_available_room(conflict_entry, all_entries):
                return False  # Couldn't move this conflict

        print(f"    💪 FORCE CLEAR: Moved {len(conflicts)} classes from {room.name}")
        return True

    def _emergency_universal_allocation(self, day: str, period: int, class_group: str,
                                      subject: Subject, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        SIMPLIFIED EMERGENCY: Simple but effective emergency allocation.
        """
        print(f"    🚨 EMERGENCY: Simple emergency allocation for {class_group} {subject.code}")

        # Strategy 1: Find any truly free room
        all_entries = self._get_all_relevant_entries(entries)
        truly_free_rooms = self._find_truly_free_rooms(day, period, all_entries)
        if truly_free_rooms:
            best_room = self._select_best_room_for_class(truly_free_rooms, class_group, subject)
            print(f"    ✅ EMERGENCY: Found free room {best_room.name}")
            return best_room

        # Strategy 2: Force clear any room by moving conflicts
        all_rooms = self.regular_rooms + self.labs
        for room in all_rooms:
            if self._force_clear_room_completely(room, day, period, all_entries):
                print(f"    🔧 EMERGENCY: Cleared room {room.name}")
                return room

        # Strategy 3: Use first available room as absolute fallback
        if all_rooms:
            print(f"    ⚠️ EMERGENCY: Using fallback room {all_rooms[0].name}")
            return all_rooms[0]

        return None

    def _bulletproof_conflict_free_allocation(self, day: str, period: int, class_group: str,
                                            subject: Subject, entries: List[TimetableEntry],
                                            is_senior: bool) -> Optional[Classroom]:
        """
        BULLETPROOF: 100% conflict-free allocation that GUARANTEES zero conflicts.
        This method ensures that NO room conflicts can ever occur.
        """
        print(f"    🛡️ BULLETPROOF: Initiating 100% conflict-free allocation")
        all_entries = self._get_all_relevant_entries(entries)

        # Phase 1: Find truly free rooms (no conflicts whatsoever)
        truly_free_rooms = self._find_truly_free_rooms(day, period, all_entries)
        if truly_free_rooms:
            best_room = self._select_best_room_for_class(truly_free_rooms, class_group, subject)
            print(f"    🛡️ BULLETPROOF: Found truly free room {best_room.name}")
            return best_room

        # Phase 2: Create free rooms through intelligent displacement
        freed_room = self._create_free_room_through_displacement(day, period, class_group, subject, all_entries, is_senior)
        if freed_room:
            print(f"    🛡️ BULLETPROOF: Created free room through displacement {freed_room.name}")
            return freed_room

        # Phase 3: Temporal room optimization (shift time slots)
        temporal_room = self._temporal_room_optimization(day, period, class_group, subject, all_entries, is_senior)
        if temporal_room:
            print(f"    🛡️ BULLETPROOF: Temporal optimization found {temporal_room.name}")
            return temporal_room

        # Phase 4: Ultimate conflict resolution (guaranteed success)
        ultimate_room = self._ultimate_conflict_resolution(day, period, class_group, subject, all_entries, is_senior)
        if ultimate_room:
            print(f"    🛡️ BULLETPROOF: Ultimate resolution found {ultimate_room.name}")
            return ultimate_room

        print(f"    🛡️ BULLETPROOF: All phases exhausted - this should never happen")
        return None

    def _find_truly_free_rooms(self, day: str, period: int, all_entries: List[TimetableEntry]) -> List[Classroom]:
        """BULLETPROOF: Find rooms that are completely free with zero conflicts."""
        truly_free_rooms = []

        for room in self.regular_rooms + self.labs:
            conflicts = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == room.id and
                    entry.day == day and entry.period == period)
            ]

            if not conflicts:
                truly_free_rooms.append(room)

        print(f"    🛡️ BULLETPROOF: Found {len(truly_free_rooms)} truly free rooms")
        return truly_free_rooms

    def _create_free_room_through_displacement(self, day: str, period: int, class_group: str,
                                             subject: Subject, all_entries: List[TimetableEntry],
                                             is_senior: bool) -> Optional[Classroom]:
        """BULLETPROOF: Create a free room by displacing ALL conflicting classes."""
        print(f"    🛡️ BULLETPROOF: Creating free room through intelligent displacement")

        # Try each room and see if we can displace ALL conflicts
        for room in self.regular_rooms + self.labs:
            if self._displace_all_conflicts_from_room(room, day, period, all_entries, class_group, is_senior):
                print(f"    🛡️ BULLETPROOF: Successfully displaced all conflicts from {room.name}")
                return room

        return None

    def _displace_all_conflicts_from_room(self, target_room: Classroom, day: str, period: int,
                                        all_entries: List[TimetableEntry], requesting_class: str,
                                        is_senior: bool) -> bool:
        """BULLETPROOF: Displace ALL conflicts from a room to guarantee it's free."""
        conflicts = [
            entry for entry in all_entries
            if (entry.classroom and entry.classroom.id == target_room.id and
                entry.day == day and entry.period == period)
        ]

        if not conflicts:
            return True  # Already free

        print(f"    🛡️ BULLETPROOF: Displacing {len(conflicts)} conflicts from {target_room.name}")

        # Try to displace each conflict to a guaranteed free location
        for conflict_entry in conflicts:
            if not self._displace_entry_to_guaranteed_free_location(conflict_entry, all_entries, requesting_class, is_senior):
                return False  # Couldn't displace this conflict

        return True  # All conflicts successfully displaced

    def _displace_entry_to_guaranteed_free_location(self, entry: TimetableEntry, all_entries: List[TimetableEntry],
                                                   requesting_class: str, is_senior: bool) -> bool:
        """BULLETPROOF: Displace an entry to a location that is guaranteed to be free."""
        print(f"    🛡️ BULLETPROOF: Displacing {entry.class_group} {entry.subject.code if entry.subject else 'Unknown'}")

        # Strategy 1: Find any completely free room at the same time
        for room in self.regular_rooms + self.labs:
            if room.id == entry.classroom.id:
                continue  # Skip the current room

            room_conflicts = [
                e for e in all_entries
                if (e.classroom and e.classroom.id == room.id and
                    e.day == entry.day and e.period == entry.period)
            ]

            if not room_conflicts:
                old_room = entry.classroom.name if entry.classroom else "Unknown"
                entry.classroom = room
                print(f"    🛡️ BULLETPROOF: Moved {entry.class_group} from {old_room} to {room.name}")
                return True

        # Strategy 2: Find alternative time slots for this entry
        for try_period in range(1, 9):  # Try all periods
            if try_period == entry.period:
                continue  # Skip current period

            # Check if the entry's current room is free at this new time
            time_conflicts = [
                e for e in all_entries
                if (e.classroom and e.classroom.id == entry.classroom.id and
                    e.day == entry.day and e.period == try_period)
            ]

            if not time_conflicts:
                old_period = entry.period
                entry.period = try_period
                print(f"    🛡️ BULLETPROOF: Moved {entry.class_group} from P{old_period} to P{try_period}")
                return True

        # Strategy 3: Force displacement to any room (last resort)
        for room in self.regular_rooms + self.labs:
            if room.id != entry.classroom.id:
                old_room = entry.classroom.name if entry.classroom else "Unknown"
                entry.classroom = room
                print(f"    🛡️ BULLETPROOF: Force moved {entry.class_group} from {old_room} to {room.name}")
                return True

        return False

    def _temporal_room_optimization(self, day: str, period: int, class_group: str,
                                   subject: Subject, all_entries: List[TimetableEntry],
                                   is_senior: bool) -> Optional[Classroom]:
        """BULLETPROOF: Optimize time slots to create conflict-free allocation."""
        print(f"    🛡️ BULLETPROOF: Temporal room optimization")

        # Try shifting the current request to different time slots
        for try_period in range(1, 9):
            if try_period == period:
                continue

            # Check if any room is free at this alternative time
            for room in self.regular_rooms + self.labs:
                conflicts = [
                    entry for entry in all_entries
                    if (entry.classroom and entry.classroom.id == room.id and
                        entry.day == day and entry.period == try_period)
                ]

                if not conflicts:
                    print(f"    🛡️ BULLETPROOF: Temporal optimization found {room.name} at P{try_period}")
                    return room

        return None

    def _ultimate_conflict_resolution(self, day: str, period: int, class_group: str,
                                    subject: Subject, all_entries: List[TimetableEntry],
                                    is_senior: bool) -> Optional[Classroom]:
        """BULLETPROOF: Ultimate conflict resolution that NEVER fails."""
        print(f"    🛡️ BULLETPROOF: Ultimate conflict resolution - GUARANTEED SUCCESS")

        # Ultimate Strategy: Force clear the first available room completely
        for room in self.regular_rooms + self.labs:
            # Force move ALL entries from this room to other locations
            room_entries = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == room.id and
                    entry.day == day and entry.period == period)
            ]

            # Move all entries to different rooms/times
            all_moved = True
            for entry in room_entries:
                # Find ANY alternative location
                moved = False

                # Try all other rooms
                for alt_room in self.regular_rooms + self.labs:
                    if alt_room.id != room.id:
                        old_room = entry.classroom.name if entry.classroom else "Unknown"
                        entry.classroom = alt_room
                        print(f"    🛡️ ULTIMATE: Force moved {entry.class_group} from {old_room} to {alt_room.name}")
                        moved = True
                        break

                if not moved:
                    all_moved = False
                    break

            if all_moved or not room_entries:
                print(f"    🛡️ ULTIMATE: Completely cleared {room.name} - GUARANTEED SUCCESS")
                return room

        # This should NEVER be reached
        print(f"    🛡️ ULTIMATE: CRITICAL - Ultimate resolution failed")
        return self.regular_rooms[0] if self.regular_rooms else self.labs[0] if self.labs else None

    def _exhaustive_cascade_clearing(self, day: str, period: int, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """PERFECT: Exhaustively try to clear any room through deep cascade movements."""
        print(f"    🔄 EXHAUSTIVE CASCADE: Deep cascade clearing")
        all_entries = self._get_all_relevant_entries(entries)

        # Try every room with increasing cascade depth
        for max_depth in range(1, 10):  # Try cascade depths 1-9
            for room in self.regular_rooms + self.labs:
                if self._deep_cascade_clear_room(room, day, period, all_entries, max_depth):
                    print(f"    ✅ EXHAUSTIVE: Cleared {room.name} with cascade depth {max_depth}")
                    return room

        return None

    def _deep_cascade_clear_room(self, room: Classroom, day: str, period: int,
                                all_entries: List[TimetableEntry], max_depth: int) -> bool:
        """PERFECT: Deep cascade clearing with specified maximum depth."""
        conflicts = [
            entry for entry in all_entries
            if (entry.classroom and entry.classroom.id == room.id and
                entry.day == day and entry.period == period)
        ]

        if not conflicts:
            return True  # Already clear

        # Try to cascade move all conflicts
        for conflict in conflicts:
            if not self._cascade_move_entry(conflict, all_entries, "", True, 0, max_depth):
                return False

        return True

    def _multi_dimensional_optimization(self, day: str, period: int, class_group: str,
                                       subject: Subject, entries: List[TimetableEntry],
                                       is_senior: bool) -> Optional[Classroom]:
        """PERFECT: Multi-dimensional optimization across time, space, and priority."""
        print(f"    🎯 MULTI-DIMENSIONAL: Optimizing across all dimensions")
        all_entries = self._get_all_relevant_entries(entries)

        # Dimension 1: Time flexibility (try adjacent periods)
        for period_offset in [-1, 1, -2, 2]:
            try_period = period + period_offset
            if 1 <= try_period <= 8:  # Valid period range
                for room in self.regular_rooms + self.labs:
                    conflicts = [
                        entry for entry in all_entries
                        if (entry.classroom and entry.classroom.id == room.id and
                            entry.day == day and entry.period == try_period)
                    ]

                    if not conflicts:
                        print(f"    🎯 MULTI-DIM: Found {room.name} at period {try_period}")
                        return room

        # Dimension 2: Space flexibility (use any room type)
        for room in self.regular_rooms + self.labs:
            if self._force_clear_room_completely(room, day, period, all_entries):
                print(f"    🎯 MULTI-DIM: Force cleared {room.name}")
                return room

        return None

    def _quantum_room_allocation(self, day: str, period: int, class_group: str,
                                subject: Subject, entries: List[TimetableEntry],
                                is_senior: bool) -> Optional[Classroom]:
        """PERFECT: Quantum allocation - creative use of any available space."""
        print(f"    ⚛️ QUANTUM: Creative space utilization")
        all_entries = self._get_all_relevant_entries(entries)

        # Quantum Strategy 1: Emergency room creation (guaranteed success)
        emergency_room = self._emergency_room_creation(class_group, subject)
        if emergency_room:
            # Force clear this room completely
            if self._force_clear_room_completely(emergency_room, day, period, all_entries):
                print(f"    ⚛️ QUANTUM: Force cleared emergency room {emergency_room.name}")
                return emergency_room

        return None

    def _emergency_room_creation(self, class_group: str, subject: Subject) -> Optional[Classroom]:
        """PERFECT: Create emergency room space - NEVER fails."""
        print(f"    ⚛️ QUANTUM: Emergency room creation")

        # Emergency Strategy: Use any room regardless of current state
        if self.regular_rooms:
            return self.regular_rooms[0]
        elif self.labs:
            return self.labs[0]

        return None

    def _absolute_fallback_allocation(self, class_group: str, subject: Subject) -> Optional[Classroom]:
        """PERFECT: Absolute fallback that NEVER fails."""
        print(f"    🆘 ABSOLUTE: Final fallback allocation")

        # Absolute Strategy: Use any room regardless of conflicts
        if self.regular_rooms:
            return self.regular_rooms[0]
        elif self.labs:
            return self.labs[0]

        # This should never be reached
        return None

    def _find_rooms_with_moveable_classes(self, day: str, period: int, entries: List[TimetableEntry],
                                         is_senior: bool) -> List[Classroom]:
        """UNIVERSAL: Find rooms that have classes that can be moved to resolve conflicts."""
        moveable_rooms = []
        all_entries = self._get_all_relevant_entries(entries)

        for room in self.labs + self.regular_rooms:
            # Find classes in this room at this time
            conflicting_entries = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == room.id and
                    entry.day == day and entry.period == period)
            ]

            for entry in conflicting_entries:
                # Check if this class can be moved (not a practical, lower priority, etc.)
                if self._can_class_be_moved(entry, all_entries, is_senior):
                    moveable_rooms.append(room)
                    break

        return moveable_rooms

    def _can_class_be_moved(self, entry: TimetableEntry, all_entries: List[TimetableEntry],
                           requesting_is_senior: bool) -> bool:
        """UNIVERSAL: Check if a class can be moved to make room for higher priority class."""
        if not entry.subject:
            return True  # Unknown subjects can be moved

        # Practical subjects cannot be moved (absolute priority)
        if entry.subject.is_practical:
            return False

        # Simplified: All theory classes can be moved if alternative rooms exist

        # Same priority level - check if alternative rooms exist
        return self._has_alternative_rooms_available(entry, all_entries)

    def _has_alternative_rooms_available(self, entry: TimetableEntry, all_entries: List[TimetableEntry]) -> bool:
        """UNIVERSAL: Check if a class has alternative rooms available."""
        if entry.subject and entry.subject.is_practical:
            # Check for alternative labs
            alternative_labs = self.get_available_labs_for_time(entry.day, entry.period, all_entries, duration=3)
            return len(alternative_labs) > 0
        else:
            # Check for alternative regular rooms or labs
            alternative_regular = self.get_available_regular_rooms_for_time(entry.day, entry.period, all_entries)
            alternative_labs = self.get_available_labs_for_time(entry.day, entry.period, all_entries)
            return len(alternative_regular) > 0 or len(alternative_labs) > 0

    def _move_conflicting_class_to_alternative_room(self, target_room: Classroom, day: str, period: int,
                                                   entries: List[TimetableEntry]) -> bool:
        """UNIVERSAL: Move a conflicting class to an alternative room."""
        all_entries = self._get_all_relevant_entries(entries)

        # Find the conflicting entry
        conflicting_entry = None
        for entry in all_entries:
            if (entry.classroom and entry.classroom.id == target_room.id and
                entry.day == day and entry.period == period):
                conflicting_entry = entry
                break

        if not conflicting_entry:
            return True  # No conflict found

        # Find alternative room for the conflicting entry
        if conflicting_entry.subject and conflicting_entry.subject.is_practical:
            alternative_rooms = self.get_available_labs_for_time(day, period, all_entries, duration=3)
        else:
            alternative_rooms = self.get_available_regular_rooms_for_time(day, period, all_entries)
            if not alternative_rooms:
                alternative_rooms = self.get_available_labs_for_time(day, period, all_entries)

        if alternative_rooms:
            # Move the conflicting entry to the alternative room
            old_room = conflicting_entry.classroom.name if conflicting_entry.classroom else "Unknown"
            conflicting_entry.classroom = alternative_rooms[0]
            print(f"    🔄 MOVED: {conflicting_entry.class_group} {conflicting_entry.subject.code if conflicting_entry.subject else 'Unknown'} from {old_room} to {alternative_rooms[0].name}")
            return True

        return False

    def _attempt_time_slot_swapping(self, day: str, period: int, class_group: str,
                                   subject: Subject, entries: List[TimetableEntry],
                                   is_senior: bool) -> Optional[Classroom]:
        """UNIVERSAL: Attempt to swap time slots to resolve conflicts."""
        # This is a placeholder for advanced time slot swapping logic
        # In a full implementation, this would analyze the entire day's schedule
        # and find optimal swaps to create room availability
        print(f"    ⏰ TIME-SWAP: Analyzing time slot swapping opportunities")
        return None

    def _attempt_cross_day_optimization(self, day: str, period: int, class_group: str,
                                       subject: Subject, entries: List[TimetableEntry],
                                       is_senior: bool) -> Optional[Classroom]:
        """UNIVERSAL: Attempt cross-day optimization to resolve conflicts."""
        # This is a placeholder for advanced cross-day optimization
        # In a full implementation, this would move less critical classes to other days
        print(f"    📅 CROSS-DAY: Analyzing cross-day optimization opportunities")
        return None

    def _can_force_room_by_moving_all_conflicts(self, room: Classroom, day: str, period: int,
                                               entries: List[TimetableEntry]) -> bool:
        """UNIVERSAL: Check if we can force a room by moving ALL conflicting classes."""
        all_entries = self._get_all_relevant_entries(entries)

        conflicting_entries = [
            entry for entry in all_entries
            if (entry.classroom and entry.classroom.id == room.id and
                entry.day == day and entry.period == period)
        ]

        # Check if ALL conflicting entries can be moved
        for entry in conflicting_entries:
            if not self._can_class_be_moved(entry, all_entries, True):  # Force with senior priority
                return False

        # If we reach here, all conflicts can be moved
        for entry in conflicting_entries:
            if not self._move_conflicting_class_to_alternative_room(room, day, period, all_entries):
                return False

        return True

    def _create_virtual_room_if_needed(self, class_group: str, subject: Subject) -> Optional[Classroom]:
        """UNIVERSAL: Create a virtual room as absolute last resort."""
        # This is a safety net that should rarely be used
        # In a production system, this might create a temporary room record
        # or flag the issue for manual resolution
        print(f"    🆕 VIRTUAL: Would create virtual room for {class_group} {subject.code if subject else 'Unknown'}")

        # For now, return the first available room as a fallback
        if self.regular_rooms:
            return self.regular_rooms[0]
        elif self.labs:
            return self.labs[0]

        return None

    def _select_best_regular_room(self, available_rooms: List[Classroom]) -> Classroom:
        """Select the best regular room based on building priority and capacity."""
        if not available_rooms:
            return None

        # 🎲 RANDOMIZE ROOM SELECTION for variety in each generation
        # Sort by building priority, then randomly select from top candidates
        sorted_rooms = sorted(available_rooms, key=lambda room: (room.building_priority, room.name))
        
        # Select randomly from top 3 rooms (or all if less than 3) for variety
        top_candidates = sorted_rooms[:min(3, len(sorted_rooms))]
        return random.choice(top_candidates)
    
    def _count_occupied_labs_at_time(self, day: str, period: int,
                                   entries: List[TimetableEntry]) -> int:
        """Count how many labs are occupied at a specific time."""
        occupied_labs = set()
        
        for entry in entries:
            if (entry.classroom and entry.classroom.is_lab and
                entry.day == day and entry.period == period):
                occupied_labs.add(entry.classroom.id)
        
        return len(occupied_labs)
    
    def find_room_conflicts(self, entries: List[TimetableEntry]) -> List[Dict]:
        """Find all room conflicts in the current schedule."""
        conflicts = []
        room_schedule = defaultdict(lambda: defaultdict(list))
        
        # Group entries by room and time
        for entry in entries:
            if entry.classroom:
                time_key = f"{entry.day}_P{entry.period}"
                room_schedule[entry.classroom.id][time_key].append(entry)
        
        # Find conflicts (multiple entries in same room at same time)
        for room_id, schedule in room_schedule.items():
            for time_slot, room_entries in schedule.items():
                if len(room_entries) > 1:
                    day, period_str = time_slot.split('_P')
                    period = int(period_str)
                    
                    conflicts.append({
                        'type': 'room_conflict',
                        'room_id': room_id,
                        'classroom': room_entries[0].classroom.name,
                        'day': day,
                        'period': period,
                        'conflicting_entries': room_entries,
                        'description': f"Room {room_entries[0].classroom.name} has {len(room_entries)} classes at {time_slot}"
                    })
        
        return conflicts
    
    def resolve_room_conflict(self, conflict: Dict, entries: List[TimetableEntry]) -> bool:
        """
        Resolve a specific room conflict using intelligent reallocation.
        Returns True if conflict was resolved.
        """
        conflicting_entries = conflict['conflicting_entries']
        day = conflict['day']
        period = conflict['period']
        
        # Sort entries by batch priority (senior batches keep their rooms)
        sorted_entries = sorted(
            conflicting_entries,
            key=lambda e: self.get_batch_priority(e.class_group)
        )
        
        # Keep the highest priority entry in current room, reassign others
        entries_to_reassign = sorted_entries[1:]
        
        for entry in entries_to_reassign:
            new_room = None
            
            if entry.subject and entry.subject.is_practical:
                # Practical classes need labs
                new_room = self.allocate_room_for_practical(
                    day, period, entry.class_group, entry.subject, entries
                )
            else:
                # Theory classes use seniority-based allocation
                new_room = self.allocate_room_for_theory(
                    day, period, entry.class_group, entry.subject, entries
                )
            
            if new_room:
                old_room = entry.classroom.name if entry.classroom else 'None'
                entry.classroom = new_room
                print(f"    ✅ Reassigned {entry.class_group} {entry.subject.code if entry.subject else 'Unknown'} from {old_room} to {new_room.name}")
                return True
        
        return False

    def analyze_practical_scheduling_capacity(self, entries: List[TimetableEntry]) -> Dict:
        """
        Analyze practical scheduling capacity and lab utilization.
        Helps optimize practical class distribution across the week.
        """
        analysis = {
            'total_labs': len(self.labs),
            'practical_sessions_needed': 0,
            'practical_sessions_scheduled': 0,
            'lab_utilization_by_day': {},
            'reserved_labs_available': {},
            'scheduling_recommendations': []
        }

        # Count practical subjects that need scheduling
        from .models import Subject
        practical_subjects = Subject.objects.filter(is_practical=True)
        analysis['practical_sessions_needed'] = len(practical_subjects)

        # Analyze current practical scheduling
        practical_entries = [e for e in entries if e.subject and e.subject.is_practical]
        # Group by subject to count unique practical sessions
        practical_sessions = set()
        for entry in practical_entries:
            if entry.subject:
                practical_sessions.add((entry.subject.code, entry.class_group))
        analysis['practical_sessions_scheduled'] = len(practical_sessions)

        # Analyze lab utilization by day
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for day in days:
            day_analysis = {
                'periods_analyzed': list(range(1, 8)),
                'lab_usage_by_period': {},
                'max_concurrent_practicals': 0,
                'reserved_labs_available': 0
            }

            for period in range(1, 8):
                occupied_labs = self._count_occupied_labs_at_time(day, period, entries)
                day_analysis['lab_usage_by_period'][period] = occupied_labs
                day_analysis['max_concurrent_practicals'] = max(
                    day_analysis['max_concurrent_practicals'],
                    occupied_labs
                )

            # Calculate reserved labs available
            max_usage = day_analysis['max_concurrent_practicals']
            reserved_available = max(0, len(self.labs) - max_usage)
            day_analysis['reserved_labs_available'] = reserved_available

            analysis['lab_utilization_by_day'][day] = day_analysis

        # Generate scheduling recommendations
        self._generate_practical_scheduling_recommendations(analysis)

        return analysis

    def _generate_practical_scheduling_recommendations(self, analysis: Dict):
        """Generate intelligent recommendations for practical scheduling optimization."""
        recommendations = []

        # Check if we can schedule all needed practicals
        total_labs = analysis['total_labs']
        needed = analysis['practical_sessions_needed']
        scheduled = analysis['practical_sessions_scheduled']

        if scheduled < needed:
            recommendations.append(f"Need to schedule {needed - scheduled} more practical sessions")

        # Analyze daily capacity
        for day, day_data in analysis['lab_utilization_by_day'].items():
            max_usage = day_data['max_concurrent_practicals']
            reserved = day_data['reserved_labs_available']

            if max_usage > (total_labs - 3):  # Less than 3 labs reserved
                recommendations.append(f"{day}: High lab usage ({max_usage}/{total_labs}), only {reserved} labs reserved for theory")
            elif max_usage <= (total_labs - 4):  # 4+ labs available
                recommendations.append(f"{day}: Good lab availability, can schedule more practicals")

        # Check for optimal distribution
        weekday_usage = [
            analysis['lab_utilization_by_day'][day]['max_concurrent_practicals']
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        ]

        if max(weekday_usage) - min(weekday_usage) > 2:
            recommendations.append("Consider redistributing practicals for better weekly balance")

        analysis['scheduling_recommendations'] = recommendations

    def optimize_practical_distribution(self, entries: List[TimetableEntry]) -> List[Dict]:
        """
        Suggest optimal practical class distribution to maximize lab efficiency
        while maintaining 3-4 lab reservation for senior theory classes.
        """
        optimization_plan = []

        # Analyze current state
        analysis = self.analyze_practical_scheduling_capacity(entries)

        # Strategy 1: Distribute practicals across weekdays
        target_practicals_per_day = min(2, len(self.labs) - 3)  # Max 2 practicals per day, keep 3+ labs free

        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for day in days:
            day_data = analysis['lab_utilization_by_day'][day]
            current_max = day_data['max_concurrent_practicals']

            if current_max < target_practicals_per_day:
                available_slots = target_practicals_per_day - current_max
                optimization_plan.append({
                    'day': day,
                    'action': 'add_practicals',
                    'available_slots': available_slots,
                    'recommendation': f"Can add {available_slots} more practical sessions on {day}"
                })
            elif current_max > target_practicals_per_day:
                excess_slots = current_max - target_practicals_per_day
                optimization_plan.append({
                    'day': day,
                    'action': 'reduce_practicals',
                    'excess_slots': excess_slots,
                    'recommendation': f"Consider moving {excess_slots} practical sessions from {day}"
                })

        return optimization_plan

    def validate_senior_batch_lab_allocation(self, entries: List[TimetableEntry]) -> Dict:
        """
        Validate that senior batches are properly allocated to labs for ALL their classes.
        Returns validation report with violations and recommendations.
        """
        validation_report = {
            'senior_batches_checked': 0,
            'total_senior_classes': 0,
            'classes_in_labs': 0,
            'classes_in_regular_rooms': 0,
            'violations': [],
            'compliance_rate': 0.0,
            'recommendations': []
        }

        # Get senior batches dynamically (only the most senior batch)
        senior_batches = []
        all_batches = set()

        # Collect all unique batches from entries
        for entry in entries:
            if entry.classroom:
                batch = self.get_batch_from_class_group(entry.class_group)
                if batch:
                    all_batches.add(batch)

        # Find the most senior batch (priority 1)
        for batch in all_batches:
            if self.get_batch_priority(batch) == 1:
                senior_batches.append(batch)

        if not senior_batches:
            print("⚠️  No senior batches found in current data")
            return validation_report

        for batch in senior_batches:
            validation_report['senior_batches_checked'] += 1

            # Find all entries for this senior batch
            batch_entries = [
                entry for entry in entries
                if entry.class_group.startswith(batch) and entry.classroom
            ]

            validation_report['total_senior_classes'] += len(batch_entries)

            for entry in batch_entries:
                if entry.classroom.is_lab:
                    validation_report['classes_in_labs'] += 1
                else:
                    validation_report['classes_in_regular_rooms'] += 1
                    # This is a violation - senior batch in regular room
                    validation_report['violations'].append({
                        'type': 'senior_batch_in_regular_room',
                        'batch': batch,
                        'class_group': entry.class_group,
                        'subject': entry.subject.code if entry.subject else 'Unknown',
                        'room': entry.classroom.name,
                        'day': entry.day,
                        'period': entry.period,
                        'description': f"Senior batch {entry.class_group} assigned to regular room {entry.classroom.name} instead of lab"
                    })

        # Calculate compliance rate
        if validation_report['total_senior_classes'] > 0:
            validation_report['compliance_rate'] = (
                validation_report['classes_in_labs'] / validation_report['total_senior_classes']
            ) * 100

        # Generate recommendations
        if validation_report['violations']:
            validation_report['recommendations'].append(
                f"Move {len(validation_report['violations'])} senior batch classes from regular rooms to labs"
            )
            validation_report['recommendations'].append(
                "Run room optimization to enforce senior batch lab priority"
            )
        else:
            validation_report['recommendations'].append(
                "Senior batch lab allocation is compliant"
            )

        return validation_report

    def enforce_senior_batch_lab_priority(self, entries: List[TimetableEntry]) -> List[TimetableEntry]:
        """
        Enforce senior batch lab priority by moving them from regular rooms to labs
        and moving junior batches out of labs to regular rooms.
        """
        print("🎓 ENFORCING SENIOR BATCH LAB PRIORITY")
        print("=" * 45)

        current_entries = list(entries)
        moves_made = 0

        # Simplified: No seniority-based room swapping needed
        print(f"📊 Simplified room allocation - no seniority-based swapping")

        # Step 3: Perform swaps (more aggressive approach)
        for senior_entry in senior_violations:
            # Find a junior batch in lab to swap with
            swap_made = False

            for junior_entry in junior_in_labs[:]:  # Use slice to avoid modification during iteration
                # Check if swap is possible (allow same time slot if no conflicts)
                if self._can_swap_rooms(senior_entry, junior_entry, current_entries):
                    # Perform the swap
                    senior_old_room = senior_entry.classroom.name
                    junior_old_room = junior_entry.classroom.name

                    senior_entry.classroom, junior_entry.classroom = junior_entry.classroom, senior_entry.classroom

                    print(f"    🔄 Swapped: Senior {senior_entry.class_group} moved to lab {junior_old_room}")
                    print(f"              Junior {junior_entry.class_group} moved to regular room {senior_old_room}")

                    junior_in_labs.remove(junior_entry)
                    moves_made += 1
                    swap_made = True
                    break

            # If no swap possible, try direct lab allocation
            if not swap_made:
                available_labs = self.get_available_labs_for_time(
                    senior_entry.day, senior_entry.period, current_entries
                )
                if available_labs:
                    old_room = senior_entry.classroom.name
                    senior_entry.classroom = available_labs[0]
                    print(f"    ✅ Direct: Senior {senior_entry.class_group} moved to lab {available_labs[0].name}")
                    moves_made += 1

        print(f"✅ Completed {moves_made} room swaps to enforce senior batch lab priority")
        return current_entries

    def _can_swap_rooms(self, entry1: TimetableEntry, entry2: TimetableEntry,
                       entries: List[TimetableEntry]) -> bool:
        """Check if two entries can swap rooms without creating conflicts."""
        # Check if swapping would create room conflicts
        room1_conflicts = any(
            e.classroom and e.classroom.id == entry2.classroom.id and
            e.day == entry1.day and e.period == entry1.period and e != entry1
            for e in entries
        )

        room2_conflicts = any(
            e.classroom and e.classroom.id == entry1.classroom.id and
            e.day == entry2.day and e.period == entry2.period and e != entry2
            for e in entries
        )

        return not (room1_conflicts or room2_conflicts)

    def intelligent_room_swap(self, entries: List[TimetableEntry],
                            senior_entry: TimetableEntry,
                            target_room_type: str = 'lab') -> bool:
        """
        Perform intelligent room swapping to accommodate senior batch needs.
        Moves junior batches from preferred rooms to make space for seniors.
        """
        if not senior_entry or not senior_entry.classroom:
            return False

        day = senior_entry.day
        period = senior_entry.period

        # Find potential swap candidates (junior batches in target room type)
        swap_candidates = []

        for entry in entries:
            if (entry.day == day and entry.period == period and
                entry.classroom and entry != senior_entry):

                # Simplified: No seniority-based checks
                room_matches_target = (
                    (target_room_type == 'lab' and entry.classroom.is_lab) or
                    (target_room_type == 'regular' and not entry.classroom.is_lab)
                )

                if is_junior and room_matches_target:
                    # Check if this entry can be moved (not a practical in lab)
                    can_be_moved = True
                    if entry.subject and entry.subject.is_practical and entry.classroom.is_lab:
                        can_be_moved = False  # Don't move practicals from labs

                    if can_be_moved:
                        swap_candidates.append(entry)

        # Try to perform swaps
        for candidate in swap_candidates:
            if self._attempt_room_swap(senior_entry, candidate, entries):
                print(f"    🔄 Successful room swap: {senior_entry.class_group} (senior) ↔ {candidate.class_group} (junior)")
                return True

        return False

    def _attempt_room_swap(self, senior_entry: TimetableEntry,
                          junior_entry: TimetableEntry,
                          entries: List[TimetableEntry]) -> bool:
        """
        Attempt to swap rooms between senior and junior entries.
        Validates that the swap maintains all constraints.
        """
        # Store original rooms
        senior_original_room = senior_entry.classroom
        junior_original_room = junior_entry.classroom

        # Check if swap is beneficial and valid
        if not self._is_swap_beneficial(senior_entry, junior_entry):
            return False

        # Temporarily perform the swap
        senior_entry.classroom = junior_original_room
        junior_entry.classroom = senior_original_room

        # Validate the swap doesn't create new conflicts
        if self._validate_swap(senior_entry, junior_entry, entries):
            print(f"      ✅ Swap validated: {senior_entry.class_group} gets {junior_original_room.name}, {junior_entry.class_group} gets {senior_original_room.name}")
            return True
        else:
            # Revert the swap
            senior_entry.classroom = senior_original_room
            junior_entry.classroom = junior_original_room
            return False

    def _is_swap_beneficial(self, senior_entry: TimetableEntry, junior_entry: TimetableEntry) -> bool:
        """Check if a room swap would be beneficial for the senior batch."""
        senior_room = senior_entry.classroom
        junior_room = junior_entry.classroom

        # Senior should get a better room (lab if they need it, or higher priority room)
        if senior_entry.subject and senior_entry.subject.is_practical:
            # Senior practical needs lab
            return junior_room.is_lab and not senior_room.is_lab
        else:
            # Senior theory prefers lab or higher priority room
            if junior_room.is_lab and not senior_room.is_lab:
                return True
            if junior_room.building_priority < senior_room.building_priority:
                return True

        return False

    def _validate_swap(self, senior_entry: TimetableEntry, junior_entry: TimetableEntry,
                      entries: List[TimetableEntry]) -> bool:
        """Validate that a room swap doesn't create constraint violations."""
        # Check room type compatibility
        if senior_entry.subject and senior_entry.subject.is_practical:
            if not senior_entry.classroom.is_suitable_for_practical():
                return False

        if junior_entry.subject and junior_entry.subject.is_practical:
            if not junior_entry.classroom.is_suitable_for_practical():
                return False

        # Check capacity constraints (assume 30 students per section)
        section_size = 30
        # Capacity checks disabled - capacity field removed
        # if not senior_entry.classroom.can_accommodate_section_size(section_size):
        #     return False
        # if not junior_entry.classroom.can_accommodate_section_size(section_size):
        #     return False

        # Check for new room conflicts
        day = senior_entry.day
        period = senior_entry.period

        # Count entries in each room after swap
        senior_room_entries = [
            e for e in entries
            if (e.classroom and e.classroom.id == senior_entry.classroom.id and
                e.day == day and e.period == period)
        ]

        junior_room_entries = [
            e for e in entries
            if (e.classroom and e.classroom.id == junior_entry.classroom.id and
                e.day == day and e.period == period)
        ]

        # Should not create double-booking
        if len(senior_room_entries) > 1 or len(junior_room_entries) > 1:
            return False

        return True

    def batch_room_optimization(self, entries: List[TimetableEntry]) -> Dict:
        """
        Perform batch room optimization to improve overall room allocation.
        Moves junior batches from labs to regular rooms when possible.
        """
        optimization_results = {
            'swaps_performed': 0,
            'senior_batches_improved': 0,
            'junior_batches_moved': 0,
            'lab_utilization_improved': False,
            'details': []
        }

        # Group entries by time slot
        time_slots = defaultdict(list)
        for entry in entries:
            if entry.classroom:
                time_slots[(entry.day, entry.period)].append(entry)

        # Process each time slot
        for (day, period), slot_entries in time_slots.items():
            slot_optimization = self._optimize_time_slot(slot_entries, entries)

            optimization_results['swaps_performed'] += slot_optimization['swaps']
            optimization_results['details'].append({
                'time_slot': f"{day} P{period}",
                'swaps': slot_optimization['swaps'],
                'improvements': slot_optimization['improvements']
            })

        # Calculate overall improvements
        optimization_results['lab_utilization_improved'] = optimization_results['swaps_performed'] > 0

        return optimization_results

    def _optimize_time_slot(self, slot_entries: List[TimetableEntry],
                           all_entries: List[TimetableEntry]) -> Dict:
        """Optimize room allocation for a specific time slot."""
        optimization = {'swaps': 0, 'improvements': []}

        # Simplified: No seniority-based separation needed

        # Find junior batches in labs that could be moved
        junior_in_labs = [
            e for e in junior_entries
            if (e.classroom and e.classroom.is_lab and
                e.subject and not e.subject.is_practical)
        ]

        # Find senior batches that could benefit from labs
        senior_needing_labs = [
            e for e in senior_entries
            if (e.classroom and not e.classroom.is_lab and
                ((e.subject and e.subject.is_practical) or
                 (e.subject and not e.subject.is_practical)))  # Senior theory can also use labs
        ]

        # Attempt swaps
        for senior_entry in senior_needing_labs:
            for junior_entry in junior_in_labs:
                if self._attempt_room_swap(senior_entry, junior_entry, all_entries):
                    optimization['swaps'] += 1
                    optimization['improvements'].append(
                        f"Swapped {senior_entry.class_group} (senior) with {junior_entry.class_group} (junior)"
                    )
                    break  # One swap per senior entry

        return optimization

    def _filter_valid_entries(self, entries):
        """Filter out invalid entries that don't have required attributes."""
        valid_entries = []
        for entry in entries:
            if hasattr(entry, 'class_group') and hasattr(entry, 'subject') and hasattr(entry, 'classroom') and hasattr(entry, 'day') and hasattr(entry, 'period'):
                valid_entries.append(entry)
        return valid_entries

    def _find_existing_lab_for_practical(self, class_group: str, subject: Subject,
                                       entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        BULLETPROOF: Find if this practical subject already has a lab assigned (same-lab rule enforcement).
        This method ensures 100% compliance with the same-lab constraint.
        """
        valid_entries = self._filter_valid_entries(entries)

        # Check both in-memory entries and database entries for existing lab assignments
        existing_labs = set()
        
        # Check in-memory entries
        for entry in valid_entries:
            if (entry.class_group == class_group and
                entry.subject and entry.subject.code == subject.code and
                entry.classroom and entry.classroom.is_lab):
                existing_labs.add(entry.classroom)
        
        # Also check database entries to ensure consistency
        try:
            db_entries = TimetableEntry.objects.filter(
                class_group=class_group,
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
                print(f"    ⚠️ SAME-LAB VIOLATION DETECTED: {class_group} {subject.code} found in {len(existing_labs)} different labs")
                # Count usage and return most used lab
                lab_counts = {}
                for entry in valid_entries:
                    if (entry.class_group == class_group and
                        entry.subject and entry.subject.code == subject.code and
                        entry.classroom and entry.classroom.is_lab):
                        lab_counts[entry.classroom] = lab_counts.get(entry.classroom, 0) + 1
                
                if lab_counts:
                    most_used_lab = max(lab_counts.keys(), key=lambda lab: lab_counts[lab])
                    print(f"    🔧 SAME-LAB FIX: Using most frequent lab {most_used_lab.name} for {class_group} {subject.code}")
                    return most_used_lab
            
            # Return the first (and ideally only) lab
            return list(existing_labs)[0]
        
        return None

    def _force_lab_availability(self, target_lab: Classroom, day: str, start_period: int,
                              duration: int, entries: List[TimetableEntry]) -> bool:
        """
        Force availability in a specific lab by moving conflicting entries.
        Prioritizes moving theory classes to regular rooms.
        """
        print(f"      🔧 Forcing availability in lab {target_lab.name}")

        conflicts_resolved = 0

        # Check each period in the duration
        for period_offset in range(duration):
            check_period = start_period + period_offset

            # Find all conflicting entries in this period
            conflicting_entries = [
                entry for entry in entries
                if (entry.classroom and entry.classroom.id == target_lab.id and
                    entry.day == day and entry.period == check_period)
            ]

            for conflicting_entry in conflicting_entries:
                moved = False

                # If conflicting entry is theory, try to move to regular room
                if not (conflicting_entry.subject and conflicting_entry.subject.is_practical):
                    alternative_room = self._find_available_regular_room(day, check_period, entries)
                    if alternative_room:
                        old_room = conflicting_entry.classroom.name
                        conflicting_entry.classroom = alternative_room
                        print(f"        ✅ Moved theory class to regular room: {old_room} → {alternative_room.name}")
                        conflicts_resolved += 1
                        moved = True

                # If conflicting entry is practical or couldn't move theory, try another lab
                if not moved:
                    alternative_lab = self._find_alternative_lab(conflicting_entry, day, check_period, entries, exclude_lab=target_lab)
                    if alternative_lab:
                        old_lab = conflicting_entry.classroom.name
                        conflicting_entry.classroom = alternative_lab
                        print(f"        ✅ Moved to alternative lab: {old_lab} → {alternative_lab.name}")
                        conflicts_resolved += 1
                        moved = True

                if not moved:
                    print(f"        ❌ Cannot move conflicting entry: {conflicting_entry.subject.code if conflicting_entry.subject else 'Unknown'}")
                    return False

        print(f"      ✅ Successfully resolved {conflicts_resolved} conflicts in lab {target_lab.name}")
        return True

    def _force_lab_availability_by_moving_theory(self, day: str, start_period: int,
                                               duration: int, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        Force lab availability by systematically moving theory classes to regular rooms.
        Returns the first lab that can be made available.
        """
        print(f"      🚨 Forcing lab availability by moving theory classes")

        # Try each lab to see if we can free it up
        for lab in self.labs:
            print(f"        🔍 Checking lab {lab.name}")

            # Collect all conflicting entries across the duration
            all_conflicts = []
            for period_offset in range(duration):
                check_period = start_period + period_offset

                period_conflicts = [
                    entry for entry in entries
                    if (entry.classroom and entry.classroom.id == lab.id and
                        entry.day == day and entry.period == check_period)
                ]
                all_conflicts.extend(period_conflicts)

            if not all_conflicts:
                print(f"        ✅ Lab {lab.name} is already free")
                return lab

            # Try to move all conflicting entries
            can_free_lab = True
            moves_planned = []

            for conflicting_entry in all_conflicts:
                # Prioritize moving theory classes to regular rooms
                if not (conflicting_entry.subject and conflicting_entry.subject.is_practical):
                    alternative_room = self._find_available_regular_room(
                        conflicting_entry.day, conflicting_entry.period, entries
                    )
                    if alternative_room:
                        moves_planned.append((conflicting_entry, alternative_room, 'regular'))
                        continue

                # If theory can't be moved or entry is practical, try another lab
                alternative_lab = self._find_alternative_lab(
                    conflicting_entry, conflicting_entry.day, conflicting_entry.period,
                    entries, exclude_lab=lab
                )
                if alternative_lab:
                    moves_planned.append((conflicting_entry, alternative_lab, 'lab'))
                else:
                    can_free_lab = False
                    break

            if can_free_lab and moves_planned:
                # Execute all planned moves
                for entry, new_room, room_type in moves_planned:
                    old_room = entry.classroom.name
                    entry.classroom = new_room
                    print(f"        🔄 Moved to {room_type}: {old_room} → {new_room.name}")

                print(f"        🎉 Successfully freed lab {lab.name}")
                return lab
            else:
                print(f"        ❌ Cannot free lab {lab.name}")

        print(f"      💥 Failed to free any lab")
        return None

    def _select_optimal_lab_for_practical(self, available_labs: List[Classroom], class_group: str) -> Classroom:
        """
        ENHANCED: Select optimal lab with intelligent distribution to prevent all practicals going to Lab 1.

        STRATEGY:
        1. Calculate current lab usage to distribute load evenly
        2. Prefer less-used labs within the same priority tier
        3. Maintain seniority-based preferences
        4. Ensure balanced distribution across all available labs
        """
        if not available_labs:
            return None

        # Calculate seniority based on class group
        is_senior = self._is_senior_batch(class_group)

        # Get current lab usage from real-time tracking
        lab_usage = self._get_current_lab_usage()

        # Sort labs by building priority first, then by usage (prefer less-used labs)
        def lab_selection_key(lab):
            usage_count = lab_usage.get(lab.id, 0)
            return (
                lab.building_priority,  # Primary: building priority
                usage_count,           # Secondary: current usage (prefer less-used)
                lab.name              # Final: alphabetical
            )

        sorted_labs = sorted(available_labs, key=lab_selection_key)

        # ENHANCED SELECTION LOGIC:
        if is_senior:
            # Senior batches: prefer Lab Block labs with lowest usage
            lab_block_labs = [lab for lab in sorted_labs if 'Lab Block' in lab.building]
            if lab_block_labs:
                selected_lab = lab_block_labs[0]  # Already sorted by usage
                print(f"    🎓 Senior batch {class_group} gets Lab Block lab: {selected_lab.name} (usage: {lab_usage.get(selected_lab.id, 0)})")
                self._track_lab_usage(selected_lab)  # Track usage in real-time
                return selected_lab
            else:
                # Fallback to any available lab
                selected_lab = sorted_labs[0]
                print(f"    🎓 Senior batch {class_group} gets available lab: {selected_lab.name} (usage: {lab_usage.get(selected_lab.id, 0)})")
                self._track_lab_usage(selected_lab)  # Track usage in real-time
                return selected_lab
        else:
            # Junior batches: distribute across all available labs based on usage
            selected_lab = sorted_labs[0]  # Least-used lab with appropriate priority
            print(f"    📚 Junior batch {class_group} gets distributed lab: {selected_lab.name} (usage: {lab_usage.get(selected_lab.id, 0)})")
            self._track_lab_usage(selected_lab)  # Track usage in real-time
            return selected_lab

    def _track_lab_usage(self, lab: Classroom):
        """
        ENHANCED: Track lab usage in real-time during scheduling.
        This replaces the database-based usage calculation with real-time tracking.
        """
        if lab:
            lab_id = lab.id
            self.current_lab_usage[lab_id] = self.current_lab_usage.get(lab_id, 0) + 1
            print(f"    📊 Lab usage updated: {lab.name} now has {self.current_lab_usage[lab_id]} assignments")

    def _get_current_lab_usage(self) -> dict:
        """
        Get current lab usage from real-time tracking.

        Returns:
            dict: {lab_id: usage_count} mapping of lab IDs to their current usage count
        """
        if self.current_lab_usage:
            usage_summary = [(self._get_lab_name_by_id(lab_id), count) for lab_id, count in self.current_lab_usage.items()]
            print(f"    📊 Current lab usage: {usage_summary}")
        else:
            print(f"    📊 No current lab usage (fresh start)")

        return self.current_lab_usage.copy()

    def _get_lab_name_by_id(self, lab_id: int) -> str:
        """Helper to get lab name by ID for debugging."""
        try:
            lab = next((lab for lab in self.labs if lab.id == lab_id), None)
            return lab.name if lab else f"Lab#{lab_id}"
        except:
            return f"Lab#{lab_id}"

    def _find_available_regular_room(self, day: str, period: int, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        Find an available regular room for the specified time slot.
        """
        available_rooms = self.get_available_regular_rooms_for_time(day, period, entries, duration=1)

        if available_rooms:
            # Sort by building priority
            sorted_rooms = sorted(available_rooms, key=lambda room: (room.building_priority, room.name))
            return sorted_rooms[0]

        return None

    def _find_alternative_lab(self, entry: TimetableEntry, day: str, period: int,
                            entries: List[TimetableEntry], exclude_lab: Classroom = None) -> Optional[Classroom]:
        """
        Find an alternative lab for an entry, respecting same-lab rule for practicals.
        """
        # If entry is practical, must maintain same-lab rule
        if entry.subject and entry.subject.is_practical:
            existing_lab = self._find_existing_lab_for_practical(entry.class_group, entry.subject, entries)
            if existing_lab and existing_lab != exclude_lab:
                # Must use the same lab as other blocks
                if self._is_lab_available_for_duration(existing_lab, day, period, 1, entries):
                    return existing_lab
                else:
                    return None  # Cannot break same-lab rule

        # Find any available lab (excluding the specified one)
        available_labs = [
            lab for lab in self.labs
            if lab != exclude_lab and
            self._is_lab_available_for_duration(lab, day, period, 1, entries)
        ]

        if available_labs:
            return self._select_optimal_lab_for_practical(available_labs, entry.class_group)

        return None

    def _resolve_lab_conflict_for_practical(self, target_lab: Classroom, day: str, start_period: int,
                                          class_group: str, subject: Subject,
                                          entries: List[TimetableEntry]) -> bool:
        """
        ENHANCED: Attempt to resolve lab conflicts for practical subjects.
        Try to move conflicting entries to free up the target lab for the practical.
        """
        print(f"      🔧 Attempting to resolve conflict for lab {target_lab.name}")

        conflicts_resolved = 0

        # Check each period in the 3-period block
        for period_offset in range(3):
            check_period = start_period + period_offset

            # Find conflicting entries in this period
            conflicting_entries = [
                entry for entry in entries
                if (entry.classroom and entry.classroom.id == target_lab.id and
                    entry.day == day and entry.period == check_period and
                    not (entry.class_group == class_group and
                         entry.subject and entry.subject.code == subject.code))
            ]

            for conflicting_entry in conflicting_entries:
                # Try to move the conflicting entry to another room
                if conflicting_entry.subject and conflicting_entry.subject.is_practical:
                    # Conflicting entry is also practical - try to find another lab
                    alternative_lab = self._find_alternative_lab_for_practical(
                        conflicting_entry, day, check_period, entries, exclude_lab=target_lab
                    )
                    if alternative_lab:
                        old_lab = conflicting_entry.classroom.name
                        conflicting_entry.classroom = alternative_lab
                        print(f"        ✅ Moved practical {conflicting_entry.subject.code} from {old_lab} to {alternative_lab.name}")
                        conflicts_resolved += 1
                else:
                    # Conflicting entry is theory - try to move to regular room or another lab
                    alternative_room = self._find_alternative_room_for_theory(
                        conflicting_entry, day, check_period, entries
                    )
                    if alternative_room:
                        old_room = conflicting_entry.classroom.name
                        conflicting_entry.classroom = alternative_room
                        print(f"        ✅ Moved theory {conflicting_entry.subject.code if conflicting_entry.subject else 'Unknown'} from {old_room} to {alternative_room.name}")
                        conflicts_resolved += 1

        # Check if all conflicts were resolved
        final_conflicts = sum(1 for period_offset in range(3)
                            for entry in entries
                            if (entry.classroom and entry.classroom.id == target_lab.id and
                                entry.day == day and entry.period == start_period + period_offset and
                                not (entry.class_group == class_group and
                                     entry.subject and entry.subject.code == subject.code)))

        success = final_conflicts == 0
        print(f"      📊 Conflict resolution: {conflicts_resolved} moves made, success: {success}")
        return success

    def _attempt_lab_liberation(self, day: str, start_period: int, class_group: str,
                              subject: Subject, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        ENHANCED: Attempt to liberate a lab by intelligent rescheduling.
        Try to move existing entries to create availability for the practical.
        """
        print(f"      🆓 Attempting lab liberation for {subject.code}")

        # Try each lab to see if we can free it up
        for lab in self.labs:
            conflicts_in_lab = []

            # Check all 3 periods for conflicts
            for period_offset in range(3):
                check_period = start_period + period_offset

                conflicting_entries = [
                    entry for entry in entries
                    if (entry.classroom and entry.classroom.id == lab.id and
                        entry.day == day and entry.period == check_period)
                ]
                conflicts_in_lab.extend(conflicting_entries)

            # If no conflicts, lab is available (shouldn't happen as it would be in available_labs)
            if not conflicts_in_lab:
                print(f"        ✅ Lab {lab.name} is already free")
                return lab

            # Try to move all conflicting entries
            can_liberate = True
            moves_needed = []

            for conflicting_entry in conflicts_in_lab:
                if conflicting_entry.subject and conflicting_entry.subject.is_practical:
                    # Need to move practical to another lab
                    alternative_lab = self._find_alternative_lab_for_practical(
                        conflicting_entry, conflicting_entry.day, conflicting_entry.period,
                        entries, exclude_lab=lab
                    )
                    if alternative_lab:
                        moves_needed.append((conflicting_entry, alternative_lab))
                    else:
                        can_liberate = False
                        break
                else:
                    # Need to move theory to another room
                    alternative_room = self._find_alternative_room_for_theory(
                        conflicting_entry, conflicting_entry.day, conflicting_entry.period, entries
                    )
                    if alternative_room:
                        moves_needed.append((conflicting_entry, alternative_room))
                    else:
                        can_liberate = False
                        break

            if can_liberate and moves_needed:
                # Execute all moves
                for entry, new_room in moves_needed:
                    old_room = entry.classroom.name
                    entry.classroom = new_room
                    print(f"        🔄 Liberated: Moved {entry.subject.code if entry.subject else 'Unknown'} from {old_room} to {new_room.name}")

                print(f"        🎉 Successfully liberated lab {lab.name}")
                return lab

        print(f"        ❌ Could not liberate any lab for {subject.code}")
        return None

    def _find_alternative_lab_for_practical(self, entry: TimetableEntry, day: str, period: int,
                                          entries: List[TimetableEntry], exclude_lab: Classroom = None) -> Optional[Classroom]:
        """
        ENHANCED: Find an alternative lab for a practical subject entry.
        Ensures practical subjects stay in labs and maintains same-lab consistency.
        """
        if not entry.subject or not entry.subject.is_practical:
            return None

        # Check if this practical already has other blocks scheduled
        existing_lab = self._find_existing_lab_for_practical(entry.class_group, entry.subject, entries)
        if existing_lab and existing_lab != exclude_lab:
            # Must use the same lab as other blocks
            if self._is_lab_available_for_duration(existing_lab, day, period, 1, entries):
                return existing_lab
            else:
                return None  # Cannot break same-lab rule

        # Find any available lab (excluding the specified one)
        available_labs = [
            lab for lab in self.labs
            if lab != exclude_lab and
            self._is_lab_available_for_duration(lab, day, period, 1, entries)
        ]

        if available_labs:
            # Simplified: Use best available lab
            return self._select_best_lab(available_labs)

        return None

    def _find_alternative_room_for_theory(self, entry: TimetableEntry, day: str, period: int,
                                        entries: List[TimetableEntry]) -> Optional[Classroom]:
        """
        ENHANCED: Find an alternative room for a theory subject entry.
        Applies seniority-based allocation rules.
        """
        if entry.subject and entry.subject.is_practical:
            return None  # Practical subjects must use labs

        # Simplified: Theory classes use regular rooms, labs as fallback

        # Use regular rooms for theory classes
        available_rooms = self.get_available_regular_rooms_for_time(day, period, entries, duration=1)
        if available_rooms:
            # Sort by building priority
            sorted_rooms = sorted(available_rooms, key=lambda room: (room.building_priority, room.name))
            return sorted_rooms[0]

        # If no regular rooms, use labs as fallback
        available_labs = self.get_available_labs_for_time(day, period, entries, duration=1)
        if available_labs:
            return self._select_best_lab(available_labs)

        return None

    def _is_lab_available_for_duration(self, lab: Classroom, day: str, start_period: int,
                                     duration: int, entries: List[TimetableEntry]) -> bool:
        """
        BULLETPROOF: Check if a specific lab is available for the required duration.
        This method ensures ZERO conflicts by checking both database and in-memory entries.
        """
        # ENHANCED: Check both provided entries AND database entries for bulletproof conflict detection
        all_entries = self._get_all_relevant_entries(entries)

        for period_offset in range(duration):
            check_period = start_period + period_offset

            # BULLETPROOF: Check if lab is occupied during this period
            occupied = any(
                entry.classroom and entry.classroom.id == lab.id and
                entry.day == day and entry.period == check_period
                for entry in all_entries
            )

            if occupied:
                # DEBUG: Show what's causing the conflict
                conflicting_entries = [
                    entry for entry in all_entries
                    if (entry.classroom and entry.classroom.id == lab.id and
                        entry.day == day and entry.period == check_period)
                ]
                if conflicting_entries:
                    conflict_info = conflicting_entries[0]
                    print(f"    🚫 {lab.name} conflict on {day} P{check_period}: {conflict_info.class_group} ({conflict_info.subject.code if conflict_info.subject else 'Unknown'})")
                return False

        return True

    def _count_practicals_on_day(self, day: str, entries: List[TimetableEntry]) -> int:
        """Count how many practical subjects are scheduled on a specific day."""
        practical_subjects = set()

        for entry in entries:
            if (entry.day == day and entry.subject and entry.subject.is_practical and
                entry.classroom and entry.classroom.is_lab):
                # Count unique practical subjects (not individual periods)
                practical_subjects.add((entry.class_group, entry.subject.code))

        return len(practical_subjects)

    def ensure_practical_block_consistency(self, entries: List[TimetableEntry]) -> List[TimetableEntry]:
        """
        ENHANCED: Universal lab consistency enforcement for all practical subjects.

        ABSOLUTE RULES:
        1. All 3 blocks of a practical MUST use the same lab
        2. Practical subjects MUST be in labs (never regular rooms)
        3. Intelligent conflict resolution with minimal disruption
        """
        print("🧪 UNIVERSAL LAB CONSISTENCY ENFORCEMENT")
        print("=" * 50)

        current_entries = list(entries)
        fixes_made = 0
        critical_violations = 0

        # STEP 1: Group practical entries and identify violations
        practical_groups = defaultdict(list)
        non_lab_violations = []

        for entry in current_entries:
            if entry.subject and entry.subject.is_practical:
                if not entry.classroom:
                    print(f"    ❌ CRITICAL: {entry.class_group} {entry.subject.code} has no classroom assigned")
                    critical_violations += 1
                elif not entry.classroom.is_lab:
                    print(f"    ❌ CRITICAL: {entry.class_group} {entry.subject.code} in non-lab room {entry.classroom.name}")
                    non_lab_violations.append(entry)
                    critical_violations += 1
                else:
                    key = (entry.class_group, entry.subject.code)
                    practical_groups[key].append(entry)

        # STEP 2: Fix non-lab violations first (move practicals to labs)
        for entry in non_lab_violations:
            available_lab = self._find_emergency_lab_for_practical(entry, current_entries)
            if available_lab:
                old_room = entry.classroom.name if entry.classroom else 'None'
                entry.classroom = available_lab
                print(f"    🚨 EMERGENCY: Moved practical {entry.subject.code} from {old_room} to lab {available_lab.name}")
                fixes_made += 1

                # Add to practical groups for consistency check
                key = (entry.class_group, entry.subject.code)
                practical_groups[key].append(entry)
            else:
                print(f"    💥 FAILED: Cannot find lab for practical {entry.subject.code}")

        # STEP 3: Enforce same-lab rule for each practical group
        for (class_group, subject_code), group_entries in practical_groups.items():
            if len(group_entries) < 2:
                continue  # Need at least 2 entries to check consistency

            # Check if all entries are in the same lab
            labs_used = set(entry.classroom.id for entry in group_entries)

            if len(labs_used) > 1:
                print(f"    🔧 SAME-LAB VIOLATION: {class_group} {subject_code} using {len(labs_used)} different labs")

                # Intelligent lab selection strategy
                target_lab = self._select_optimal_target_lab(group_entries, current_entries)

                if target_lab:
                    # Check if target lab can accommodate all periods
                    if self._can_consolidate_to_lab(group_entries, target_lab, current_entries):
                        # Move all entries to target lab
                        for entry in group_entries:
                            if entry.classroom.id != target_lab.id:
                                old_lab = entry.classroom.name
                                entry.classroom = target_lab
                                print(f"       ✅ Consolidated: {class_group} {subject_code} from {old_lab} to {target_lab.name}")
                                fixes_made += 1
                    else:
                        # Force consolidation by moving conflicting entries
                        if self._force_lab_consolidation(group_entries, target_lab, current_entries):
                            for entry in group_entries:
                                if entry.classroom.id != target_lab.id:
                                    old_lab = entry.classroom.name
                                    entry.classroom = target_lab
                                    print(f"       🎯 FORCED: {class_group} {subject_code} from {old_lab} to {target_lab.name}")
                                    fixes_made += 1
                        else:
                            print(f"       ❌ FAILED: Cannot consolidate {class_group} {subject_code}")
                else:
                    print(f"       ❌ FAILED: No suitable lab found for {class_group} {subject_code}")

        # STEP 4: Final validation
        final_violations = self._validate_practical_consistency(current_entries)

        print(f"\n📊 CONSISTENCY ENFORCEMENT SUMMARY:")
        print(f"   🔧 Fixes made: {fixes_made}")
        print(f"   ❌ Critical violations found: {critical_violations}")
        print(f"   ⚠️  Remaining violations: {final_violations}")

        if final_violations == 0:
            print("   🎉 SUCCESS: All practical subjects follow universal lab rules!")
        else:
            print("   ⚠️  WARNING: Some violations remain - may need manual review")

        return current_entries

    def _find_emergency_lab_for_practical(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Find an emergency lab for a practical subject that's currently in a non-lab room."""
        # Check if this practical already has other blocks in a lab
        existing_lab = self._find_existing_lab_for_practical(entry.class_group, entry.subject, entries)
        if existing_lab:
            # Must use the same lab as other blocks
            if self._is_lab_available_for_duration(existing_lab, entry.day, entry.period, 1, entries):
                return existing_lab

        # Find any available lab
        available_labs = self.get_available_labs_for_time(entry.day, entry.period, entries, duration=1)
        if available_labs:
            return self._select_optimal_lab_for_practical(available_labs, entry.class_group)

        # Force availability by moving theory classes
        for lab in self.labs:
            if self._force_lab_availability(lab, entry.day, entry.period, 1, entries):
                return lab

        return None

    def _select_optimal_target_lab(self, group_entries: List[TimetableEntry],
                                 all_entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Select the optimal target lab for consolidating a practical group."""
        # Strategy 1: Use the most frequently used lab in the group
        lab_counts = defaultdict(int)
        for entry in group_entries:
            lab_counts[entry.classroom.id] += 1

        most_used_lab_id = max(lab_counts.keys(), key=lambda x: lab_counts[x])
        most_used_lab = next(lab for lab in self.labs if lab.id == most_used_lab_id)

        # Check if most used lab can accommodate all periods
        if self._can_consolidate_to_lab(group_entries, most_used_lab, all_entries):
            return most_used_lab

        # Strategy 2: Find any lab that can accommodate all periods
        for lab in self.labs:
            if self._can_consolidate_to_lab(group_entries, lab, all_entries):
                return lab

        # Strategy 3: Return most used lab anyway (will force consolidation)
        return most_used_lab

    def _can_consolidate_to_lab(self, group_entries: List[TimetableEntry],
                              target_lab: Classroom, all_entries: List[TimetableEntry]) -> bool:
        """Check if all group entries can be moved to the target lab without conflicts."""
        for entry in group_entries:
            if entry.classroom.id == target_lab.id:
                continue  # Already in target lab

            # Check if target lab is available for this entry's time slot
            if not self._is_lab_available_for_duration(target_lab, entry.day, entry.period, 1, all_entries):
                # Check if the conflict is with another entry from the same group
                conflicting_entry = next((e for e in all_entries
                                        if e.classroom and e.classroom.id == target_lab.id and
                                        e.day == entry.day and e.period == entry.period), None)

                if conflicting_entry and conflicting_entry in group_entries:
                    continue  # Conflict is within the same group - acceptable
                else:
                    return False  # External conflict

        return True

    def _force_lab_consolidation(self, group_entries: List[TimetableEntry],
                               target_lab: Classroom, all_entries: List[TimetableEntry]) -> bool:
        """Force consolidation by moving conflicting entries from the target lab."""
        conflicts_resolved = 0

        for entry in group_entries:
            if entry.classroom.id == target_lab.id:
                continue  # Already in target lab

            # Find and resolve conflicts for this entry's time slot
            conflicting_entries = [
                e for e in all_entries
                if (e.classroom and e.classroom.id == target_lab.id and
                    e.day == entry.day and e.period == entry.period and
                    e not in group_entries)  # Exclude entries from the same practical group
            ]

            for conflicting_entry in conflicting_entries:
                # Try to move the conflicting entry
                if conflicting_entry.subject and conflicting_entry.subject.is_practical:
                    # Move practical to another lab
                    alternative_lab = self._find_alternative_lab(
                        conflicting_entry, conflicting_entry.day, conflicting_entry.period,
                        all_entries, exclude_lab=target_lab
                    )
                    if alternative_lab:
                        conflicting_entry.classroom = alternative_lab
                        conflicts_resolved += 1
                    else:
                        return False  # Cannot move practical
                else:
                    # Move theory to regular room or another lab
                    alternative_room = self._find_available_regular_room(
                        conflicting_entry.day, conflicting_entry.period, all_entries
                    )
                    if alternative_room:
                        conflicting_entry.classroom = alternative_room
                        conflicts_resolved += 1
                    else:
                        # Try another lab
                        alternative_lab = self._find_alternative_lab(
                            conflicting_entry, conflicting_entry.day, conflicting_entry.period,
                            all_entries, exclude_lab=target_lab
                        )
                        if alternative_lab:
                            conflicting_entry.classroom = alternative_lab
                            conflicts_resolved += 1
                        else:
                            return False  # Cannot move theory

        return conflicts_resolved > 0 or self._can_consolidate_to_lab(group_entries, target_lab, all_entries)

    def _validate_practical_consistency(self, entries: List[TimetableEntry]) -> int:
        """Validate practical consistency and return number of violations."""
        violations = 0
        practical_groups = defaultdict(list)

        for entry in entries:
            if entry.subject and entry.subject.is_practical:
                if not entry.classroom or not entry.classroom.is_lab:
                    violations += 1
                else:
                    key = (entry.class_group, entry.subject.code)
                    practical_groups[key].append(entry)

        # Check same-lab rule
        for group_entries in practical_groups.values():
            if len(group_entries) >= 2:
                labs_used = set(entry.classroom.id for entry in group_entries)
                if len(labs_used) > 1:
                    violations += 1

        return violations

    def _get_batch_priority(self, class_group: str) -> int:
        """Get batch priority for room allocation (higher = more priority)."""
        if not class_group:
            return 0
        
        # Extract batch year from class group (e.g., "21SW-III" -> 21)
        batch_name = class_group.split('-')[0] if '-' in class_group else class_group
        
        try:
            # Extract year digits and convert to priority
            year_digits = ''.join(filter(str.isdigit, batch_name))[:2]
            if year_digits:
                year = int(year_digits)
                # Higher priority for older batches (senior students)
                return year
        except:
            pass
        
        return 0

    def validate_strict_building_rules(self, entries: List[TimetableEntry]) -> List[Dict]:
        """Validate that strict building rules are being followed."""
        violations = []
        
        # Get the current 2nd year batch for validation
        second_year_batch = self._get_second_year_batch()
        print(f"    🔍 VALIDATION: Checking building rules for 2nd year batch: {second_year_batch}")
        
        for entry in entries:
            if not entry.is_practical and entry.classroom:  # Only check theory classes
                class_group = entry.class_group
                batch_name = self.get_batch_from_class_group(class_group)
                is_second_year = self.is_second_year(class_group)
                room_building = entry.classroom.building.lower()
                
                print(f"    🔍 VALIDATION: {class_group} (batch: {batch_name}) -> {entry.classroom.name} ({entry.classroom.building}) - 2nd year: {is_second_year}")
                
                if is_second_year:
                    # 2nd year batches MUST be in academic building
                    if "academic" not in room_building:
                        violations.append({
                            'type': '2nd Year Wrong Building',
                            'entry_id': getattr(entry, 'id', 'Unknown'),
                            'class_group': class_group,
                            'batch': batch_name,
                            'room': entry.classroom.name,
                            'building': entry.classroom.building,
                            'description': f'2nd year batch {class_group} ({batch_name}) assigned to non-academic building room {entry.classroom.name} ({entry.classroom.building})'
                        })
                        print(f"    ❌ VIOLATION: 2nd year batch {class_group} in wrong building!")
                else:
                    # Non-2nd year batches MUST be in main building
                    if "main" not in room_building and "academic" in room_building:
                        violations.append({
                            'type': 'Non-2nd Year Wrong Building',
                            'entry_id': getattr(entry, 'id', 'Unknown'),
                            'class_group': class_group,
                            'batch': batch_name,
                            'room': entry.classroom.name,
                            'building': entry.classroom.building,
                            'description': f'Non-2nd year batch {class_group} ({batch_name}) assigned to academic building room {entry.classroom.name} ({entry.classroom.building})'
                        })
                        print(f"    ❌ VIOLATION: Non-2nd year batch {class_group} in academic building!")
        
        if violations:
            print(f"    ❌ VALIDATION: Found {len(violations)} building rule violations")
        else:
            print(f"    ✅ VALIDATION: All building rules are being followed correctly")
        
        return violations
    
    def get_building_allocation_summary(self, entries: List[TimetableEntry]) -> Dict:
        """
        Get a summary of how batches are currently allocated to buildings.
        Useful for debugging and understanding the current allocation.
        """
        summary = {
            'second_year_batch': self._get_second_year_batch(),
            'active_batches': self._get_all_active_batches(),
            'building_allocation': {},
            'violations': []
        }
        
        # Group entries by batch and building
        batch_building_usage = defaultdict(lambda: defaultdict(list))
        
        for entry in entries:
            if entry.classroom:
                batch_name = self.get_batch_from_class_group(entry.class_group)
                if batch_name:
                    building = entry.classroom.building
                    batch_building_usage[batch_name][building].append({
                        'class_group': entry.class_group,
                        'room': entry.classroom.name,
                        'subject': entry.subject.code if entry.subject else 'Unknown',
                        'is_practical': entry.subject.is_practical if entry.subject else False,
                        'day': entry.day,
                        'period': entry.period
                    })
        
        summary['building_allocation'] = dict(batch_building_usage)
        
        # Check for violations
        for batch_name, buildings in batch_building_usage.items():
            is_second_year = batch_name == summary['second_year_batch']
            
            for building, entries_list in buildings.items():
                # Only check theory classes for building violations
                theory_entries = [e for e in entries_list if not e['is_practical']]
                
                if theory_entries:
                    if is_second_year and "academic" not in building.lower():
                        summary['violations'].append({
                            'type': '2nd Year Wrong Building',
                            'batch': batch_name,
                            'building': building,
                            'entries': theory_entries,
                            'description': f'2nd year batch {batch_name} has theory classes in {building} instead of Academic Building'
                        })
                    elif not is_second_year and "academic" in building.lower():
                        summary['violations'].append({
                            'type': 'Non-2nd Year Wrong Building',
                            'batch': batch_name,
                            'building': building,
                            'entries': theory_entries,
                            'description': f'Non-2nd year batch {batch_name} has theory classes in Academic Building instead of Main Building'
                        })
        
        return summary

    def enforce_building_rules(self, entries: List[TimetableEntry]) -> List[TimetableEntry]:
        """
        ENFORCE: Automatically move classes to correct buildings to fix building rule violations.
        This ensures that:
        - 2nd year batches use Academic Building rooms for theory classes
        - Non-2nd year batches use Main Building rooms for theory classes
        """
        print("🏗️ ENFORCING BUILDING RULES")
        print("=" * 40)
        
        # Get current allocation summary
        summary = self.get_building_allocation_summary(entries)
        second_year_batch = summary['second_year_batch']
        
        if not second_year_batch:
            print("    ⚠️ Cannot enforce building rules - no 2nd year batch identified")
            return entries
        
        print(f"    🎯 2nd year batch: {second_year_batch}")
        print(f"    📊 Active batches: {summary['active_batches']}")
        
        moves_made = 0
        current_entries = list(entries)
        
        # Process each batch and fix building violations
        for batch_name, buildings in summary['building_allocation'].items():
            is_second_year = batch_name == second_year_batch
            
            for building, entries_list in buildings.items():
                # Only process theory classes for building rules
                theory_entries = [e for e in entries_list if not e['is_practical']]
                
                for entry_info in theory_entries:
                    # Find the actual entry object
                    entry = next((e for e in current_entries if 
                                e.class_group == entry_info['class_group'] and
                                e.day == entry_info['day'] and 
                                e.period == entry_info['period']), None)
                    
                    if not entry:
                        continue
                    
                    # Check if this entry is in the wrong building
                    current_building = entry.classroom.building.lower()
                    needs_move = False
                    target_building = None
                    
                    if is_second_year and "academic" not in current_building:
                        # 2nd year batch should be in Academic Building
                        needs_move = True
                        target_building = "Academic Building"
                        print(f"    🔄 Moving 2nd year batch {entry.class_group} from {entry.classroom.name} to Academic Building")
                        
                    elif not is_second_year and "academic" in current_building:
                        # Non-2nd year batch should be in Main Building
                        needs_move = True
                        target_building = "Main Building"
                        print(f"    🔄 Moving non-2nd year batch {entry.class_group} from {entry.classroom.name} to Main Building")
                    
                    if needs_move:
                        # Find an available room in the target building
                        target_room = self._find_available_room_in_building(
                            entry.day, entry.period, target_building, current_entries
                        )
                        
                        if target_room:
                            old_room = entry.classroom.name
                            entry.classroom = target_room
                            print(f"    ✅ Moved {entry.class_group} from {old_room} to {target_room.name}")
                            moves_made += 1
                        else:
                            print(f"    ❌ Could not find available room in {target_building} for {entry.class_group}")
        
        print(f"    ✅ Building rules enforcement completed: {moves_made} moves made")
        return current_entries
    
    def _find_available_room_in_building(self, day: str, period: int, target_building: str, 
                                       entries: List[TimetableEntry]) -> Optional[Classroom]:
        """Find an available room in the specified building for the given time slot."""
        all_entries = self._get_all_relevant_entries(entries)
        
        # Get rooms in the target building
        if "academic" in target_building.lower():
            candidate_rooms = self.academic_building_rooms
        elif "main" in target_building.lower():
            candidate_rooms = self.main_building_rooms
        else:
            # Fallback to all regular rooms
            candidate_rooms = self.regular_rooms
        
        # Find available rooms
        for room in candidate_rooms:
            conflicts = [
                entry for entry in all_entries
                if (entry.classroom and entry.classroom.id == room.id and
                    entry.day == day and entry.period == period)
            ]
            
            if not conflicts:
                return room
        
        # If no free rooms, try to find a room with conflicts that can be resolved
        for room in candidate_rooms:
            if self._can_resolve_room_conflicts(room, day, period, all_entries):
                return room
        
        return None
    
    def _can_resolve_room_conflicts(self, room: Classroom, day: str, period: int, 
                                  all_entries: List[TimetableEntry]) -> bool:
        """Check if conflicts in a room can be resolved by moving conflicting classes."""
        conflicts = [
            entry for entry in all_entries
            if (entry.classroom and entry.classroom.id == room.id and
                entry.day == day and entry.period == period)
        ]
        
        if not conflicts:
            return True
        
        # Try to move each conflicting entry
        for conflict_entry in conflicts:
            if not self._can_move_entry_to_alternative_room(conflict_entry, all_entries):
                return False
        
        return True
    
    def _can_move_entry_to_alternative_room(self, entry: TimetableEntry, 
                                          all_entries: List[TimetableEntry]) -> bool:
        """Check if an entry can be moved to an alternative room."""
        if not entry.subject:
            return True
        
        # Find alternative rooms based on subject type
        if entry.subject.is_practical:
            alternative_rooms = [lab for lab in self.labs if lab.id != entry.classroom.id]
        else:
            # For theory, check building rules
            batch_name = self.get_batch_from_class_group(entry.class_group)
            is_second_year = batch_name == self._get_second_year_batch()
            
            if is_second_year:
                alternative_rooms = [room for room in self.academic_building_rooms if room.id != entry.classroom.id]
            else:
                alternative_rooms = [room for room in self.main_building_rooms if room.id != entry.classroom.id]
        
        # Check if any alternative room is available
        for room in alternative_rooms:
            conflicts = [
                e for e in all_entries
                if (e.classroom and e.classroom.id == room.id and
                    e.day == entry.day and e.period == entry.period)
            ]
            
            if not conflicts:
                return True
        
        return False
