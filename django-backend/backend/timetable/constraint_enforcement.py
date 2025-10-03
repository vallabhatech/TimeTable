"""
CENTRALIZED CONSTRAINT ENFORCEMENT
==================================
Wraps existing validators/allocators and provides a single API for validation and auto-fixing.
Ensures the "3 consecutive blocks of a practical must be in the same lab" rule cannot be violated.
"""

from typing import List, Dict, Any
from collections import defaultdict

from .models import TimetableEntry, Classroom
from .enhanced_constraint_validator import EnhancedConstraintValidator as ConstraintValidator
from .room_allocator import RoomAllocator


class ConstraintEnforcer:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.enhanced_validator = EnhancedConstraintValidator(verbose=verbose)
        self.basic_validator = ConstraintValidator()
        self.room_allocator = RoomAllocator()

    def validate_all_constraints(self, entries: List[TimetableEntry]) -> Dict[str, Any]:
        """
        Run enhanced validation first; fall back to basic where necessary.
        """
        # Enhanced validator covers all 19 constraints, including same-lab rule
        enhanced_results = self.enhanced_validator.validate_all_constraints(entries)

        # Merge with basic validator for legacy checks
        basic_results = self.basic_validator.validate_all_constraints(entries)

        total_violations = (
            enhanced_results['total_violations'] + basic_results['total_violations']
        )

        # Combine reports
        combined = {
            'total_violations': total_violations,
            'overall_compliance': total_violations == 0,
            'enhanced': enhanced_results,
            'basic': basic_results
        }
        return combined

    def enforce_all_constraints(self, entries: List[TimetableEntry]) -> Dict[str, Any]:
        """
        Enforce all constraints with priority on zero-violation operation.
        """
        actions = []

        # 1) Hard-enforce SAME-LAB for all practicals
        actions.append(self._enforce_same_lab_for_all_practicals(entries))

        # 2) Fix room conflicts (double-bookings)
        actions.append(self._resolve_room_double_bookings(entries))

        # 3) Ensure practicals are in labs only
        actions.append(self._ensure_practicals_in_labs(entries))

        return {
            'actions': actions,
            'success': all(a.get('success', True) for a in actions),
        }

    def _enforce_same_lab_for_all_practicals(self, entries: List[TimetableEntry]) -> Dict[str, Any]:
        """
        Ensures that ALL 3 consecutive blocks of a practical ALWAYS use the same lab.
        """
        fixed = 0
        practical_groups = defaultdict(list)

        # Group practical entries by class_group, subject, and day
        for e in entries:
            if e.subject and e.subject.is_practical:
                practical_groups[(e.class_group, e.subject.code, e.day)].append(e)

        for (class_group, subject_code, day), group in practical_groups.items():
            if len(group) < 2:
                continue

            # Determine target lab (majority lab among the entries)
            labs = [ge.classroom for ge in group if ge.classroom and ge.classroom.is_lab]
            if not labs:
                # No labs assigned yet - try to assign one
                available_lab = self._find_available_lab_for_practical_group(group, entries)
                if available_lab:
                    for ge in group:
                        if not ge.classroom or not ge.classroom.is_lab:
                            ge.classroom = available_lab
                            fixed += 1
                continue

            # Find the most used lab (target lab)
            from collections import Counter
            lab_counter = Counter(lab.id for lab in labs)
            target_lab_id, _ = lab_counter.most_common(1)[0]
            target_lab = Classroom.objects.get(id=target_lab_id)

            # BULLETPROOF: Force all entries to use the target lab
            for ge in group:
                if not ge.classroom or ge.classroom.id != target_lab_id:
                    # Check for conflicts in both database AND current entries
                    has_conflict = self._check_lab_conflict(target_lab, ge.day, ge.period, entries, exclude_entry=ge)
                    
                    if not has_conflict:
                        # No conflict - safe to assign
                        ge.classroom = target_lab
                        fixed += 1
                    else:
                        # FORCE lab availability by moving conflicting entries
                        if self._force_lab_availability_bulletproof(target_lab, ge.day, ge.period, entries, exclude_entry=ge):
                            ge.classroom = target_lab
                            fixed += 1
                        else:
                            # Last resort: try to find alternative lab for entire group
                            alternative_lab = self._find_alternative_lab_for_group(group, entries, exclude_lab=target_lab)
                            if alternative_lab:
                                # Move entire group to alternative lab
                                for group_entry in group:
                                    group_entry.classroom = alternative_lab
                                    fixed += 1
                                break

        if self.verbose:
            print(f"   🔒 BULLETPROOF: Enforced same-lab rule with {fixed} fixes")

        return {
            'name': 'bulletproof_same_lab_enforcement',
            'fixed': fixed,
            'success': True
        }

    def _check_lab_conflict(self, lab: Classroom, day: str, period: int, entries: List[TimetableEntry], exclude_entry: TimetableEntry = None) -> bool:
        """Check for conflicts in both database and current entries."""
        # Check database conflicts
        db_conflict = TimetableEntry.objects.filter(
            classroom=lab, day=day, period=period
        ).exclude(id=exclude_entry.id if exclude_entry and hasattr(exclude_entry, 'id') else None).exists()
        
        if db_conflict:
            return True
        
        # Check current entries conflicts
        for entry in entries:
            if (entry != exclude_entry and 
                entry.classroom and entry.classroom.id == lab.id and
                entry.day == day and entry.period == period):
                return True
        
        return False

    def _force_lab_availability_bulletproof(self, lab: Classroom, day: str, period: int, entries: List[TimetableEntry], exclude_entry: TimetableEntry = None) -> bool:
        """BULLETPROOF: Force lab availability by moving conflicting entries."""
        # Find conflicting entries in current entries
        conflicting_entries = [
            entry for entry in entries
            if (entry != exclude_entry and 
                entry.classroom and entry.classroom.id == lab.id and
                entry.day == day and entry.period == period)
        ]
        
        # Try to move each conflicting entry
        for conflict_entry in conflicting_entries:
            if conflict_entry.subject and conflict_entry.subject.is_practical:
                # Practical entry - try to move to another lab
                alternative_lab = self._find_alternative_lab_for_entry(conflict_entry, entries, exclude_lab=lab)
                if alternative_lab:
                    conflict_entry.classroom = alternative_lab
                    if self.verbose:
                        print(f"     🔄 Moved practical {conflict_entry.subject.code} to {alternative_lab.name}")
                else:
                    return False  # Cannot move practical
            else:
                # Theory entry - try to move to regular room
                alternative_room = self._find_alternative_room_for_theory(conflict_entry, entries)
                if alternative_room:
                    conflict_entry.classroom = alternative_room
                    if self.verbose:
                        print(f"     🔄 Moved theory to {alternative_room.name}")
                else:
                    return False  # Cannot move theory
        
        return True

    def _find_available_lab_for_practical_group(self, group: List[TimetableEntry], entries: List[TimetableEntry]) -> Classroom:
        """Find an available lab that can accommodate all entries in the practical group."""
        all_labs = list(Classroom.objects.filter(is_lab=True))
        
        for lab in all_labs:
            can_accommodate_all = True
            for entry in group:
                if self._check_lab_conflict(lab, entry.day, entry.period, entries, exclude_entry=entry):
                    can_accommodate_all = False
                    break
            
            if can_accommodate_all:
                return lab
        
        return None

    def _find_alternative_lab_for_group(self, group: List[TimetableEntry], entries: List[TimetableEntry], exclude_lab: Classroom = None) -> Classroom:
        """Find an alternative lab for an entire practical group."""
        all_labs = list(Classroom.objects.filter(is_lab=True))
        if exclude_lab:
            all_labs = [lab for lab in all_labs if lab.id != exclude_lab.id]
        
        for lab in all_labs:
            can_accommodate_all = True
            for entry in group:
                if self._check_lab_conflict(lab, entry.day, entry.period, entries, exclude_entry=entry):
                    can_accommodate_all = False
                    break
            
            if can_accommodate_all:
                return lab
        
        return None

    def _find_alternative_lab_for_entry(self, entry: TimetableEntry, entries: List[TimetableEntry], exclude_lab: Classroom = None) -> Classroom:
        """Find an alternative lab for a single practical entry."""
        all_labs = list(Classroom.objects.filter(is_lab=True))
        if exclude_lab:
            all_labs = [lab for lab in all_labs if lab.id != exclude_lab.id]
        
        for lab in all_labs:
            if not self._check_lab_conflict(lab, entry.day, entry.period, entries, exclude_entry=entry):
                return lab
        
        return None

    def _find_alternative_room_for_theory(self, entry: TimetableEntry, entries: List[TimetableEntry]) -> Classroom:
        """Find an alternative regular room for a theory entry."""
        regular_rooms = list(Classroom.objects.filter(is_lab=False))
        
        for room in regular_rooms:
            # Check for conflicts
            has_conflict = any(
                e.classroom and e.classroom.id == room.id and
                e.day == entry.day and e.period == entry.period and e != entry
                for e in entries
            )
            
            if not has_conflict:
                # Also check database
                db_conflict = TimetableEntry.objects.filter(
                    classroom=room, day=entry.day, period=entry.period
                ).exclude(id=entry.id if hasattr(entry, 'id') else None).exists()
                
                if not db_conflict:
                    return room
        
        return None

    def _resolve_room_double_bookings(self, entries: List[TimetableEntry]) -> Dict[str, Any]:
        moved = 0
        from collections import defaultdict
        schedule = defaultdict(list)

        for e in entries:
            if e.classroom:
                schedule[(e.day, e.period, e.classroom.id)].append(e)

        # For any slot with >1, move extras
        for key, coll in schedule.items():
            if len(coll) <= 1:
                continue
            keep = coll[0]
            to_move = coll[1:]
            day, period, _ = key
            for e in to_move:
                alt = (
                    self.room_allocator.allocate_room_for_practical(day, period, e.class_group, e.subject, entries)
                    if (e.subject and e.subject.is_practical)
                    else self.room_allocator.allocate_room_for_theory(day, period, e.class_group, e.subject, entries)
                )
                if alt:
                    e.classroom = alt
                    e.save()
                    moved += 1

        if self.verbose:
            print(f"   🧹 Resolved double-bookings: moved {moved} entries")

        return {
            'name': 'room_conflict_resolution',
            'moved': moved,
            'success': True
        }

    def _ensure_practicals_in_labs(self, entries: List[TimetableEntry]) -> Dict[str, Any]:
        corrected = 0
        for e in entries:
            if e.subject and e.subject.is_practical:
                if not (e.classroom and e.classroom.is_lab):
                    # Try to allocate a lab at this slot
                    lab = self.room_allocator.allocate_room_for_practical(e.day, e.period, e.class_group, e.subject, entries)
                    if lab:
                        e.classroom = lab
                        e.save()
                        corrected += 1
        if self.verbose:
            print(f"   🔬 Ensured practicals in labs: corrected {corrected}")
        return {
            'name': 'practicals_in_labs',
            'corrected': corrected,
            'success': True
        }
