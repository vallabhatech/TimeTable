"""
FINAL UNIVERSAL SCHEDULER - Enhanced with controlled randomization and gap elimination
===================================================================================

This scheduler generates different timetables each time while respecting all constraints.
Key features:
- Controlled randomization for subject order, teacher selection, and time slots
- Intelligent conflict resolution
- Advanced room allocation
- Friday-aware scheduling
- Thesis Day constraint enforcement
- Automatic gap filling to ensure compact scheduling (no gaps between classes)
"""

import os
import sys
import django
import random
import time
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, time as dt_time, timedelta
from django.db import models, transaction
from django.utils import timezone
from ..models import Subject, Teacher, Classroom, TimetableEntry, ScheduleConfig, TeacherSubjectAssignment, Batch
from ..room_allocator import RoomAllocator
from ..simple_gap_filler import SimpleGapFiller
from ..enhanced_constraint_resolver import EnhancedConstraintResolver
from ..duplicate_constraint_enforcer import duplicate_constraint_enforcer

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from timetable.models import (
    TimetableEntry, Subject, Teacher, ScheduleConfig, 
    Classroom, ClassGroup, Batch
)
from timetable.room_allocator import RoomAllocator
from timetable.simple_gap_filler import SimpleGapFiller
from timetable.enhanced_constraint_resolver import EnhancedConstraintResolver
from timetable.duplicate_constraint_enforcer import duplicate_constraint_enforcer


class FinalUniversalScheduler:
    """
    FINAL UNIVERSAL SCHEDULER
    Works with ANY real-world data, ANY subjects, ANY teachers, ANY batches.
    """
    
    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.days = config.days
        self.periods = [int(p) for p in config.periods]
        # Convert start_time string to time object if needed
        if isinstance(config.start_time, str):
            from datetime import datetime
            self.start_time = datetime.strptime(config.start_time, '%H:%M:%S').time()
        else:
            self.start_time = config.start_time
        self.class_duration = config.class_duration
        # Get class groups from Batch model instead of config
        self.class_groups = [batch.name for batch in Batch.objects.all()]

        # Load ALL available data
        self.all_subjects = list(Subject.objects.all())
        self.all_teachers = list(Teacher.objects.all())
        self.all_classrooms = list(Classroom.objects.all())
        self.room_allocator = RoomAllocator()  # Initialize intelligent room allocation
        self.gap_filler = SimpleGapFiller()  # Initialize gap filler to eliminate gaps

        # Create default classroom if none exist
        if not self.all_classrooms:
            classroom = Classroom.objects.create(
                name="Default Classroom",
                building="Main Building"
            )
            self.all_classrooms = [classroom]

        # Tracking structures
        self.global_teacher_schedule = {}  # Global teacher availability
        self.global_classroom_schedule = {}  # Global classroom availability

        # Set random seed based on current time for true variety
        random.seed(int(time.time() * 1000) % 1000000)
        print(f"🎲 Random seed set to: {random.getrandbits(32)}")
        
        print(f"📊 Final Scheduler: {len(self.all_subjects)} subjects, {len(self.all_teachers)} teachers, {len(self.all_classrooms)} classrooms")
        print(f"🏛️ Room Allocation: {len(self.room_allocator.labs)} labs, {len(self.room_allocator.regular_rooms)} regular rooms, seniority-based system active")
    
    def generate_timetable(self) -> Dict:
        """Generate complete timetable - ENHANCED VERSION with Section Support."""
        start_time = datetime.now()

        print(f"🚀 FINAL TIMETABLE GENERATION: {self.config.name}")
        print(f"📅 Class groups: {self.class_groups}")

        try:
            # STEP 1: Clean up previous timetables for this config
            self._cleanup_previous_timetables()

            # STEP 2: Load existing schedules (if any) to avoid conflicts
            self._load_existing_schedules()
            
            # 🎲 FINAL RANDOMIZATION: Randomize the order of some operations for variety
            # This ensures that even with the same data, we get different timetables
            random_operations = [
                lambda: self._randomize_teacher_preferences(),
                lambda: self._randomize_room_preferences(),
                lambda: self._randomize_time_preferences()
            ]
            random.shuffle(random_operations)
            
            # Execute randomized operations
            for operation in random_operations:
                operation()
            
            # STEP 3: Expand class groups to include sections (ENHANCEMENT)
            expanded_class_groups = self._expand_class_groups_with_sections()
            
            # 🎲 CONTROLLED RANDOMIZATION: Only randomize class group order for minimal variety
            # This maintains the sequential scheduling approach while adding some variety
            if len(expanded_class_groups) > 1:
                # Only shuffle if there are multiple class groups to avoid unnecessary randomization
                random.shuffle(expanded_class_groups)
            
            print(f"   📚 Processing {len(expanded_class_groups)} class groups (randomized order)")

            # STEP 4: Generate timetables for all class groups (including sections)
            all_entries = []

            # BULLETPROOF: Initialize current session entries for conflict detection
            self._current_session_entries = []

            # BULLETPROOF: Set global reference for room allocator access
            import sys
            sys.modules[__name__]._current_scheduler_instance = self

            for class_group in expanded_class_groups:
                print(f"\n📋 Generating for {class_group}...")

                # Get subjects for this specific class group
                subjects = self._get_subjects_for_class_group(class_group)
                print(f"   📚 Found {len(subjects)} subjects for {class_group}")

                # Generate entries for this class group
                entries = self._generate_for_class_group(class_group, subjects)
                all_entries.extend(entries)

                # BULLETPROOF: Update current session entries for conflict detection
                self._current_session_entries.extend(entries)

                print(f"   ✅ Generated {len(entries)} entries for {class_group}")

            # STEP 5: Fill gaps to ensure compact scheduling (no gaps between classes)
            # This enforces the constraint: "there must not be any gaps between classes unless extremely necessary to avoid conflicts"
            print("🔧 STEP 5: Filling gaps for compact scheduling...")
            gap_filling_result = self.gap_filler.fill_gaps_for_zero_violations(all_entries)
            if gap_filling_result.get('gaps_filled', 0) > 0:
                print(f"   ✅ Filled {gap_filling_result['gaps_filled']} gaps for compact scheduling")
            else:
                print("   ✅ No gaps found - timetable is already compact")

            # STEP 6: Save to database
            saved_count = self._save_entries_to_database(all_entries)

            # STEP 7: Verify no conflicts
            conflicts = self._check_all_conflicts(all_entries)

            generation_time = (datetime.now() - start_time).total_seconds()

            result = {
                'entries': [self._entry_to_dict(entry) for entry in all_entries],
                'fitness_score': 100.0 - len(conflicts),
                'constraint_violations': conflicts,
                'generation_time': generation_time,
                'total_entries': len(all_entries),
                'saved_entries': saved_count,
                'success': True,
                'sections_generated': expanded_class_groups  # NEW: Include sections info
            }

            print(f"\n🎉 GENERATION COMPLETE!")
            print(f"📊 Total entries: {len(all_entries)}")
            print(f"📋 Sections generated: {len(expanded_class_groups)}")
            print(f"💾 Saved to database: {saved_count}")
            print(f"⏱️  Time: {generation_time:.2f}s")

            if conflicts:
                print(f"⚠️  Conflicts: {len(conflicts)}")
                for conflict in conflicts[:3]:
                    print(f"   - {conflict}")
            else:
                print("✅ NO CONFLICTS - PERFECT TIMETABLE!")

            # ENHANCEMENT 3: Analyze schedule compaction
            compaction_analysis = self._analyze_schedule_compaction(all_entries)
            result['compaction_analysis'] = compaction_analysis

            # ENHANCEMENT 5: Overall credit hour compliance report
            overall_compliance = self._generate_overall_compliance_report(all_entries)
            result['credit_hour_compliance'] = overall_compliance

            # STEP 8: Schedule Extra Classes in leftover/blank slots
            print(f"\n🔧 STEP 8: Scheduling Extra Classes in leftover slots...")
            extra_classes_result = self._schedule_extra_classes(all_entries, expanded_class_groups)
            if extra_classes_result.get('extra_classes_scheduled', 0) > 0:
                print(f"   ✅ Scheduled {extra_classes_result['extra_classes_scheduled']} extra classes")
                result['extra_classes_scheduled'] = extra_classes_result
            else:
                print("   ✅ No extra classes scheduled - no suitable slots found")

            return result

        except Exception as e:
            print(f"❌ Generation failed: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def _cleanup_previous_timetables(self):
        """Clean up previous timetables for this config."""
        deleted_count = TimetableEntry.objects.filter(schedule_config=self.config).count()
        if deleted_count > 0:
            TimetableEntry.objects.filter(schedule_config=self.config).delete()
            print(f"🗑️  Cleaned up {deleted_count} previous entries")
    
    def _load_existing_schedules(self):
        """Load existing schedules from other configs to avoid conflicts."""
        existing_entries = TimetableEntry.objects.exclude(schedule_config=self.config)
        for entry in existing_entries:
            # Mark teacher as busy (only if teacher exists - THESISDAY entries have no teacher)
            if entry.teacher:
                key = (entry.teacher.id, entry.day, entry.period)
                self.global_teacher_schedule[key] = entry

            # Mark classroom as busy (only if classroom exists)
            if entry.classroom:
                key = (entry.classroom.id, entry.day, entry.period)
                self.global_classroom_schedule[key] = entry
        
        if existing_entries.exists():
            print(f"🔍 Loaded {existing_entries.count()} existing entries to avoid conflicts")

    def _expand_class_groups_with_sections(self) -> List[str]:
        """ENHANCEMENT: Expand class groups to include sections based on Batch model."""
        expanded_groups = []

        for class_group in self.class_groups:
            # Check if class_group already has section (like 21SW-I)
            if '-' in class_group and class_group.split('-')[1] in ['I', 'II', 'III']:
                # Already has section, use as is
                expanded_groups.append(class_group)
            else:
                # Get the actual batch and its sections
                try:
                    batch = Batch.objects.get(name=class_group)
                    sections = batch.get_sections()
                    for section in sections:
                        expanded_groups.append(f"{class_group}-{section}")
                except Batch.DoesNotExist:
                    # Fallback to default sections if batch not found
                    sections = ['I', 'II', 'III']
                    for section in sections:
                        expanded_groups.append(f"{class_group}-{section}")

        return expanded_groups

    def _get_subjects_for_class_group(self, class_group: str) -> List[Subject]:
        """Get subjects for a specific class group - DATABASE-DRIVEN with Fallback."""
        # Extract base batch from class_group (e.g., "21SW-I" -> "21SW")
        base_batch = class_group.split('-')[0] if '-' in class_group else class_group

        # Method 1: Try to get subjects from database batch field (NEW!)
        subjects = list(Subject.objects.filter(batch=base_batch))

        if subjects:
            print(f"   📚 Found {len(subjects)} subjects for {base_batch} from database")
            return subjects

        # Method 2: If no batch-specific subjects, try subjects without batch assignment
        if not subjects:
            subjects = list(Subject.objects.filter(batch__isnull=True))
            if subjects:
                print(f"   📚 Found {len(subjects)} subjects without batch assignment")
                return subjects

        # Method 3: Final fallback - use all subjects (distributed fairly)
        if not subjects:
            all_subjects = list(Subject.objects.all())
            if all_subjects:
                # Distribute subjects fairly across batches
                batch_count = 4  # Assuming 4 batches typically
                subjects_per_batch = max(1, len(all_subjects) // batch_count)
                print(f"   📚 Using {subjects_per_batch} subjects from all available subjects")
                return all_subjects[:subjects_per_batch]
        
        print(f"   ⚠️ No subjects found for {class_group}")
        return []
    
    def _generate_for_class_group(self, class_group: str, subjects: List[Subject]) -> List[TimetableEntry]:
        """Generate timetable for a specific class group."""
        entries = []
        class_schedule = {}  # Track this class group's schedule
        
        # Separate practical and theory subjects
        practical_subjects = [s for s in subjects if self._is_practical_subject(s)]
        theory_subjects = [s for s in subjects if not self._is_practical_subject(s)]
        
        # 🎲 RANDOMIZE SUBJECT ORDER for variety in each generation
        random.shuffle(practical_subjects)
        random.shuffle(theory_subjects)
        
        print(f"   🧪 Practical subjects (randomized): {len(practical_subjects)}")
        print(f"   📖 Theory subjects (randomized): {len(theory_subjects)}")

        # CRITICAL FIX: For final year sections with Thesis, apply Thesis Day constraint FIRST
        # This reserves Wednesday for Thesis before scheduling other subjects
        if self._is_final_year_with_thesis(class_group, subjects):
            print(f"   🎓 Final year with Thesis detected - applying Thesis Day constraint FIRST")
            entries = self._enforce_thesis_day_constraint_early(entries, subjects, class_group)

        # FRIDAY-AWARE SCHEDULING STRATEGY:
        # 1. Schedule practical subjects first with Friday-awareness
        # 2. Schedule theory subjects with Friday time limits in mind
        # 3. Apply compact scheduling while respecting Friday constraints

        print(f"   📅 Using Friday-aware scheduling strategy for {class_group}")

        # Schedule practical subjects first (need consecutive periods)
        for subject in practical_subjects:
            if self._has_teacher_for_subject(subject):
                self._schedule_practical_subject(entries, class_schedule, subject, class_group)

        # Schedule theory subjects
        for subject in theory_subjects:
            # Skip Thesis subjects if already scheduled by early constraint
            if self._is_thesis_subject(subject) and self._is_final_year_with_thesis(class_group, [subject]):
                print(f"     📚 Skipping {subject.code} - already scheduled by early Thesis Day constraint")
                continue

            if self._has_teacher_for_subject(subject):
                self._schedule_theory_subject(entries, class_schedule, subject, class_group)

        # ENHANCEMENT 4: Ensure minimum daily class duration
        entries = self._enforce_minimum_daily_duration(entries, class_group)

        # ENHANCEMENT 7: Enforce Friday time limits based on practical scheduling
        entries = self._enforce_friday_time_limit(entries, class_group)

        # ENHANCEMENT 8: Ensure no day has only practical or only one class
        entries = self._enforce_minimum_daily_classes(entries, class_group)

        # ENHANCEMENT 9: Thesis Day - Wednesday exclusive for final year batches with Thesis
        # Skip if already handled early for final year with Thesis
        if not self._is_final_year_with_thesis(class_group, subjects):
            entries = self._enforce_thesis_day_constraint(entries, subjects, class_group)
        else:
            print(f"     📚 Skipping late Thesis Day constraint for {class_group} - already handled early")

        # ENHANCEMENT 6: Intelligent Thesis Day assignment for final year batches (legacy)
        entries = self._assign_thesis_day_if_needed(entries, subjects, class_group)

        # ENHANCEMENT 5: Validate and auto-correct credit hour compliance
        entries = self._validate_and_correct_credit_hour_compliance(entries, subjects, class_group)

        # CRITICAL FIX: Final credit hour validation after Thesis Day constraint
        # The Thesis Day constraint may have moved entries, causing under-scheduling
        print(f"     🔧 FINAL credit hour validation after Thesis Day constraint for {class_group}...")
        entries = self._validate_and_correct_credit_hour_compliance(entries, subjects, class_group)

        # NEW: Final duplicate-theory elimination by redistribution into empty slots
        print(f"     ♻️  Eliminating duplicate theory by redistribution for {class_group}...")
        entries = self._eliminate_duplicate_theory_by_redistribution(entries, class_group)

        # STRICT: Ensure Thesis is ONLY on Wednesday. Remove Thesis from other days and
        # fill all Wednesday periods with Thesis, overriding other constraints.
        print(f"     🎓 Enforcing STRICT Thesis-only Wednesday for {class_group}...")
        entries = self._strict_thesis_wednesday_cleanup(entries, class_group)

        return entries

    def _is_final_year_with_thesis(self, class_group: str, subjects: List[Subject]) -> bool:
        """Check if this BATCH has Thesis subjects - BATCH-LEVEL LOGIC.
        If ANY section of a batch has thesis, ALL sections should have Wednesday reserved.
        """
        # Get the base batch (e.g., "21SW" from "21SW-I")
        base_batch = class_group.split('-')[0] if '-' in class_group else class_group

        # ALWAYS check at batch level first - this is the source of truth
        try:
            from django.db.models import Q
            from timetable.models import Subject
            
            # Check if ANY thesis subjects exist for this batch (regardless of section)
            batch_thesis_subjects = Subject.objects.filter(
                Q(code__icontains='thesis') | Q(name__icontains='thesis'),
                batch=base_batch
            )
            
            has_thesis = batch_thesis_subjects.exists()
            if has_thesis:
                print(f"       ✅ BATCH-LEVEL: Found Thesis subjects for batch {base_batch} - ALL sections ({class_group} included) will have Wednesday reserved")
            else:
                print(f"       ℹ️ BATCH-LEVEL: No Thesis subjects found for batch {base_batch} - no Wednesday reservation needed")
            return has_thesis
        except Exception as e:
            print(f"       ⚠️ Error checking for thesis subjects in database: {e}")
            # Fallback to checking provided subjects if database check fails
            thesis_subjects = [s for s in subjects if
                              s.code.lower() in ['thesis', 'thesis day', 'thesisday'] or
                              'thesis' in s.name.lower()]
            return len(thesis_subjects) > 0

    def _is_thesis_subject(self, subject: Subject) -> bool:
        """Check if a subject is a Thesis subject."""
        return (subject.code.lower() in ['thesis', 'thesis day', 'thesisday'] or
                'thesis' in subject.name.lower())

    def _enforce_thesis_day_constraint_early(self, entries: List[TimetableEntry], subjects: List[Subject],
                                           class_group: str) -> List[TimetableEntry]:
        """
        Apply Thesis Day constraint EARLY - before scheduling other subjects.
        This reserves Wednesday for Thesis and creates placeholder entries.
        
        BATCH-LEVEL LOGIC: If ANY section of a batch has thesis, ALL sections have Wednesday reserved.
        """
        print(f"     🎓 STRICT EARLY Thesis Day constraint for {class_group} - reserving Wednesday (BATCH-LEVEL)")

        # Get the base batch (e.g., "21SW" from "21SW-I")
        base_batch = class_group.split('-')[0] if '-' in class_group else class_group
        
        # BATCH-LEVEL CHECK: Always get thesis subjects from batch level, not individual section
        from django.db.models import Q
        try:
            batch_thesis_subjects = Subject.objects.filter(
                Q(code__icontains='thesis') | Q(name__icontains='thesis'),
                batch=base_batch
            )
            
            if batch_thesis_subjects.exists():
                # Use batch-level thesis subjects
                thesis_subjects = list(batch_thesis_subjects)
                print(f"       📚 BATCH-LEVEL: Using Thesis subjects from batch {base_batch}: {[s.code for s in thesis_subjects]}")
            else:
                # No thesis subjects found for this batch - should not happen if _is_final_year_with_thesis returned True
                print(f"       ⚠️ BATCH-LEVEL: No Thesis subjects found for batch {base_batch} - this should not happen")
                return entries  # No thesis constraint needed
        except Exception as e:
            print(f"       ⚠️ Error getting batch thesis subjects: {e}")
            # Fallback to subjects from current section
            thesis_subjects = [s for s in subjects if
                              s.code.lower() in ['thesis', 'thesis day', 'thesisday'] or
                              'thesis' in s.name.lower()]
            if not thesis_subjects:
                return entries  # No thesis subjects found

        # STRICT ENFORCEMENT: First, remove ANY existing entries on Wednesday for this class group
        # This ensures we start with a clean slate for Wednesday
        updated_entries = [e for e in entries if not (e.day.lower().startswith('wed') and e.class_group == class_group)]
        if len(entries) != len(updated_entries):
            print(f"       🧹 Removed {len(entries) - len(updated_entries)} existing entries from Wednesday for {class_group}")

        # Schedule ALL periods on Wednesday for Thesis to ensure no other subjects are scheduled
        # This is a stronger enforcement than before - irrespective of credit hours
        for thesis_subject in thesis_subjects[:1]:  # Use only the first thesis subject for consistency
            # Schedule for ALL periods on Wednesday (typically 1-8)
            # Irrespective of credit hours - reserve all periods
            for period in range(1, 9):  # Cover all possible periods
                thesis_entry = self._create_entry(
                    'Wednesday', period,
                    thesis_subject, None, None,  # No teacher/classroom for Thesis
                    class_group, False  # Not practical
                )
                updated_entries.append(thesis_entry)
                print(f"       📅 STRICT: Reserved Wednesday P{period} for {thesis_subject.code} (irrespective of credit hours)")

        print(f"     ✅ Wednesday COMPLETELY reserved for Thesis ONLY - NO other subjects will be scheduled")
        print(f"     🔒 STRICT ENFORCEMENT: Thesis subjects fully scheduled on Wednesday - preventing ANY other scheduling")
        return updated_entries

    def _is_practical_subject(self, subject: Subject) -> bool:
        """Universal practical subject detection."""
        # Check is_practical field first (most reliable)
        if hasattr(subject, 'is_practical') and subject.is_practical:
            return True

        # Check naming patterns - be more specific to avoid false positives
        # Look for practical indicators that are standalone or at word boundaries
        import re

        # Check code for practical patterns (more reliable)
        code_patterns = [r'\bPr\b', r'\bLab\b', r'\bLAB\b', r'\bPractical\b', r'\bWorkshop\b']
        for pattern in code_patterns:
            if re.search(pattern, subject.code):
                return True

        # Check name for practical patterns - be more specific
        # Only match if "Pr" is followed by ")" or is at the end, or other specific patterns
        name_patterns = [
            r'\bPr\)',           # "Pr)" - practical suffix
            r'\(Pr\)',           # "(Pr)" - practical in parentheses
            r'\bPractical\b',    # "Practical" as whole word
            r'\bLab\b',          # "Lab" as whole word
            r'\bLAB\b',          # "LAB" as whole word
            r'\bWorkshop\b'      # "Workshop" as whole word
        ]
        for pattern in name_patterns:
            if re.search(pattern, subject.name):
                return True

        # Check credits (1 credit often means practical)
        if subject.credits == 1:
            return True

        return False
    
    def _has_teacher_for_subject(self, subject: Subject) -> bool:
        """Check if subject has assigned teachers."""
        try:
            return subject.teacher_set.exists() or any(subject in t.subjects.all() for t in self.all_teachers)
        except:
            return len(self.all_teachers) > 0  # Fallback: if teachers exist, assume assignable
    
    def _schedule_practical_subject(self, entries: List[TimetableEntry],
                                  class_schedule: dict, subject: Subject, class_group: str):
        """Schedule practical subject - ENHANCED with strict credit hour compliance."""
        print(f"     🧪 Scheduling practical: {subject.code}")
        print(f"       🎯 Practical rule: 1 credit = 1 session/week (3 consecutive hours)")

        # Find available teacher
        teachers = self._get_teachers_for_subject(subject, class_group)
        if not teachers:
            print(f"     ⚠️  No teachers for {subject.code}")
            return

        # ENHANCEMENT: Friday-aware practical scheduling
        import random

        # Prioritize days with Friday-awareness
        friday_aware_days = self._prioritize_days_for_practical(class_group, entries)

        # ENHANCEMENT 3: Try early periods first (1-4), then later periods if needed
        early_periods = [p for p in self.periods[:-2] if p <= 4]  # Periods 1-4 (early)
        late_periods = [p for p in self.periods[:-2] if p > 4]   # Periods 5+ (late)
        prioritized_periods = early_periods + late_periods

        # Try to find 3 consecutive periods, prioritizing Friday-aware days and early times
        for day in friday_aware_days:
            for start_period in prioritized_periods:
                if self._can_schedule_block(class_schedule, day, start_period, 3, class_group, subject):
                    teacher = self._find_available_teacher(teachers, day, start_period, 3)
                    if teacher:
                        # CRITICAL: Check if this practical already has a lab assigned
                        existing_lab = self._find_existing_lab_for_practical(subject, class_group)

                        if existing_lab:
                            # Verify existing lab is available for all 3 periods
                            lab_available = True
                            for i in range(3):
                                period = start_period + i
                                if (existing_lab.id, day, period) in self.global_classroom_schedule:
                                    # Check if it's the same practical subject
                                    existing_entry = self.global_classroom_schedule[(existing_lab.id, day, period)]

                                    # Handle both boolean and entry objects for backward compatibility
                                    if isinstance(existing_entry, bool):
                                        # If it's just marked as busy, assume conflict
                                        lab_available = False
                                        break
                                    elif hasattr(existing_entry, 'class_group') and hasattr(existing_entry, 'subject'):
                                        # It's an entry object, check if it's the same practical
                                        if (existing_entry.class_group != class_group or
                                            existing_entry.subject.code != subject.code):
                                            lab_available = False
                                            break
                                    else:
                                        # Unknown type, assume conflict
                                        lab_available = False
                                        break

                            if lab_available:
                                classroom = existing_lab
                                print(f"     🔄 Continuing practical {subject.code} in existing lab {classroom.name}")
                            else:
                                print(f"     ⚠️  Existing lab {existing_lab.name} not available for {subject.code}")
                                continue
                        else:
                            # Find new lab for this practical
                            classroom = self._find_available_classroom(day, start_period, 3, class_group, subject)
                            # SAFETY: ensure only labs for practicals
                            if classroom and not classroom.is_lab:
                                print(f"     🚫 SAFETY: Rejected non-lab {classroom.name} for practical {subject.code}")
                                classroom = None
                            if classroom:
                                print(f"     🆕 New practical {subject.code} assigned to lab {classroom.name}")

                        if classroom:
                            # Schedule 3 consecutive periods in SAME lab
                            scheduled_entries = []
                            for i in range(3):
                                period = start_period + i
                                entry = self._create_entry(day, period, subject, teacher, classroom, class_group, True)
                                entries.append(entry)
                                scheduled_entries.append(entry)
                                class_schedule[(day, period)] = entry
                                self._mark_global_schedule(teacher, classroom, day, period)

                            # BULLETPROOF VERIFICATION: Ensure all 3 blocks are in the same lab
                            labs_used = set(entry.classroom.id for entry in scheduled_entries)
                            if len(labs_used) == 1:
                                print(f"     ✅ BULLETPROOF VERIFIED: Scheduled {subject.code}: {day} P{start_period}-{start_period+2} in {classroom.name} (same lab confirmed)")
                            else:
                                # This should never happen, but if it does, it's a critical error
                                lab_names = [entry.classroom.name for entry in scheduled_entries]
                                print(f"     ⚠️ BULLETPROOF ERROR: {subject.code} scheduled across multiple labs: {lab_names}")
                                print(f"     🔧 BULLETPROOF FIX: Forcing all blocks to use {classroom.name}")
                                for entry in scheduled_entries:
                                    if entry.classroom.id != classroom.id:
                                        old_lab = entry.classroom.name
                                        entry.classroom = classroom
                                        print(f"     🔧 BULLETPROOF FIX: Moved {entry.class_group} {entry.subject.code} from {old_lab} to {classroom.name}")
                            return

        print(f"     ❌ Could not schedule practical {subject.code}")
    
    def _schedule_theory_subject(self, entries: List[TimetableEntry],
                               class_schedule: dict, subject: Subject, class_group: str):
        """Schedule theory subject with credit hour compliance."""
        print(f"     📚 Scheduling theory: {subject.code}")
        print(f"       🎯 Theory rule: 1 credit = 1 class/week")
        
        # CRITICAL: Hard constraint - Thesis subjects MUST ONLY be scheduled on Wednesday
        is_thesis = self._is_thesis_subject(subject)
        if is_thesis:
            print(f"       🎓 THESIS CONSTRAINT: {subject.code} can ONLY be scheduled on Wednesday")
        teachers = self._get_teachers_for_subject(subject, class_group)
        if not teachers:
            print(f"     ⚠️  No teachers for {subject.code}")
            return

        # ENHANCEMENT 5: Strict credit hour compliance with aggressive enforcement
        scheduled = 0
        target = subject.credits  # MUST schedule exactly the credit hours, no more, no less

        print(f"       🎯 Target: EXACTLY {target} classes per week (AGGRESSIVE ENFORCEMENT)")

        # PHASE 1: Try normal scheduling with Friday-aware prioritization
        scheduled = self._attempt_normal_theory_scheduling(entries, class_schedule, subject, class_group, teachers, target)

        # PHASE 2: If not fully scheduled, use aggressive retry with relaxed constraints
        if scheduled < target:
            print(f"       🔄 Normal scheduling achieved {scheduled}/{target} - activating AGGRESSIVE MODE")
            scheduled = self._aggressive_theory_scheduling(entries, class_schedule, subject, class_group, teachers, target, scheduled)

        # PHASE 3: Final validation and emergency measures
        if scheduled < target:
            print(f"       🚨 EMERGENCY: Still missing {target - scheduled} classes - applying FORCE SCHEDULING")
            scheduled = self._force_schedule_missing_theory_classes(entries, class_schedule, subject, class_group, teachers, target, scheduled)

        if scheduled < target:
            print(f"     ❌ CRITICAL FAILURE: Only scheduled {scheduled}/{target} periods for {subject.code}")
        else:
            print(f"     ✅ SUCCESS: Fully scheduled {subject.code} across {scheduled} periods")

    def _attempt_normal_theory_scheduling(self, entries: List[TimetableEntry], class_schedule: dict,
                                        subject: Subject, class_group: str, teachers: List, target: int) -> int:
        """Phase 1: Attempt normal scheduling with Friday-aware prioritization."""
        print(f"       📋 Phase 1: Normal scheduling with Friday-aware prioritization")

        scheduled = 0

        # CRITICAL: Check if this is a thesis subject - if so, ONLY allow Wednesday
        is_thesis = self._is_thesis_subject(subject)
        allowed_days = ['Wednesday'] if is_thesis else self.days
        
        if is_thesis:
            print(f"       🎓 THESIS HARD CONSTRAINT: {subject.code} restricted to Wednesday ONLY")
        
        # ENHANCEMENT: Friday-aware compact scheduling
        available_slots = []
        for day in allowed_days:  # Use allowed_days instead of self.days
            for period in self.periods:
                if self._can_schedule_single(class_schedule, day, period, class_group, subject, entries):
                    # Calculate Friday-aware priority score for this slot
                    friday_score = self._calculate_friday_aware_slot_score(day, period, class_group, entries)
                    available_slots.append((day, period, friday_score))

        # ENHANCEMENT 3: Sort by Friday-aware score, then period, then day
        # Lower scores are better (prioritize slots that help Friday compliance)
        available_slots.sort(key=lambda slot: (slot[2], slot[1], slot[0]))

        # 🎲 CONTROLLED RANDOMIZATION for variety while maintaining sequential order
        # Group by (friday_score, period) and add minimal randomization within each group
        import random
        from itertools import groupby

        prioritized_slots = []
        for (score, period), group in groupby(available_slots, key=lambda x: (x[2], x[1])):
            period_slots = list(group)
            # Only randomize days within same score/period to maintain sequential period order
            random.shuffle(period_slots)
            prioritized_slots.extend(period_slots)
        
        # NO MORE SHUFFLING of the entire list - this preserves sequential period ordering
        # This ensures classes are scheduled in consecutive periods when possible

        # Schedule across prioritized slots (Friday-aware early periods first)
        for day, period, friday_score in prioritized_slots:
            if scheduled >= target:
                break

            teacher = self._find_available_teacher(teachers, day, period, 1)
            if teacher:
                classroom = self._find_available_classroom(day, period, 1, class_group, subject)
                if classroom:
                    entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                    entries.append(entry)
                    class_schedule[(day, period)] = entry
                    self._mark_global_schedule(teacher, classroom, day, period)
                    scheduled += 1
                    print(f"         ✅ Normal: {subject.code} on {day} P{period}")

        print(f"       📊 Phase 1 result: {scheduled}/{target} classes scheduled")
        return scheduled

    def _aggressive_theory_scheduling(self, entries: List[TimetableEntry], class_schedule: dict,
                                    subject: Subject, class_group: str, teachers: List, target: int, current_scheduled: int) -> int:
        """Phase 2: Aggressive scheduling with relaxed constraints."""
        print(f"       🔥 Phase 2: Aggressive scheduling (need {target - current_scheduled} more classes)")

        scheduled = current_scheduled

        # Strategy 1: Allow same-day scheduling (relax day distribution preference)
        print(f"         🎯 Strategy 1: Allow same-day scheduling")
        scheduled = self._try_same_day_scheduling(entries, class_schedule, subject, class_group, teachers, target, scheduled)

        if scheduled >= target:
            return scheduled

        # Strategy 2: Use Friday slots with relaxed time limits
        print(f"         🎯 Strategy 2: Use Friday slots with relaxed limits")
        scheduled = self._try_friday_relaxed_scheduling(entries, class_schedule, subject, class_group, teachers, target, scheduled)

        if scheduled >= target:
            return scheduled

        # Strategy 3: Use any available teacher (not just assigned ones)
        print(f"         🎯 Strategy 3: Use any available teacher")
        scheduled = self._try_any_teacher_scheduling(entries, class_schedule, subject, class_group, target, scheduled)

        print(f"       📊 Phase 2 result: {scheduled}/{target} classes scheduled")
        return scheduled

    def _force_schedule_missing_theory_classes(self, entries: List[TimetableEntry], class_schedule: dict,
                                             subject: Subject, class_group: str, teachers: List, target: int, current_scheduled: int) -> int:
        """Phase 3: Force schedule missing classes using emergency measures."""
        print(f"       💥 Phase 3: Emergency force scheduling (need {target - current_scheduled} more classes)")

        scheduled = current_scheduled
        missing = target - scheduled

        # Emergency Strategy 1: Create slots by extending day duration
        print(f"         🚨 Emergency 1: Extend day duration to create slots")
        scheduled = self._create_emergency_slots_by_extension(entries, class_schedule, subject, class_group, teachers, target, scheduled)

        if scheduled >= target:
            return scheduled

        # Emergency Strategy 2: Use late Friday periods (violate Friday constraint temporarily)
        print(f"         🚨 Emergency 2: Use late Friday periods (constraint violation)")
        scheduled = self._use_late_friday_emergency_slots(entries, class_schedule, subject, class_group, teachers, target, scheduled)

        if scheduled >= target:
            return scheduled

        # Emergency Strategy 3: Duplicate existing classes on different days
        print(f"         🚨 Emergency 3: Duplicate classes on different days")
        scheduled = self._duplicate_classes_emergency(entries, class_schedule, subject, class_group, teachers, target, scheduled)

        print(f"       📊 Phase 3 result: {scheduled}/{target} classes scheduled")
        return scheduled

    def _try_same_day_scheduling(self, entries: List[TimetableEntry], class_schedule: dict,
                               subject: Subject, class_group: str, teachers: List, target: int, current_scheduled: int) -> int:
        """Try to schedule classes on different days (RESPECTING no duplicate theory per day constraint)."""
        scheduled = current_scheduled

        print(f"           🚫 CONSTRAINT ENFORCED: No duplicate theory classes per day - skipping same-day scheduling")
        print(f"           📋 Will try alternative scheduling strategies instead")

        # CONSTRAINT ENFORCEMENT: Do not allow multiple theory classes of the same subject on the same day
        # This method now respects the "No Duplicate Theory Classes Per Day" constraint
        # Instead of adding to existing days, we'll try to find completely new days

        # Find days that already have this subject (to avoid them)
        used_days = set()
        for entry in entries:
            if entry.class_group == class_group and entry.subject == subject and not entry.is_practical:
                used_days.add(entry.day)

        # CRITICAL: Check if this is a thesis subject - if so, ONLY allow Wednesday
        is_thesis = self._is_thesis_subject(subject)
        allowed_days = ['Wednesday'] if is_thesis else self.days
        
        # Try to schedule on days that don't already have this subject
        available_days = [day for day in allowed_days if day not in used_days]

        for day in available_days:
            if scheduled >= target:
                break

            # Find available periods on this day
            for period in self.periods:
                if scheduled >= target:
                    break

                if (day, period) not in class_schedule:
                    # Check if this slot respects all constraints including no duplicate theory
                    if self._can_schedule_single(class_schedule, day, period, class_group, subject, entries):
                        teacher = self._find_available_teacher(teachers, day, period, 1)
                        if teacher:
                            classroom = self._find_available_classroom(day, period, 1, class_group, subject)
                            if classroom:
                                entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                                entries.append(entry)
                                class_schedule[(day, period)] = entry
                                self._mark_global_schedule(teacher, classroom, day, period)
                                scheduled += 1
                                print(f"           ✅ Different-day: {subject.code} on {day} P{period}")
                                break  # Only one class per day for this subject

        return scheduled

    def _try_friday_relaxed_scheduling(self, entries: List[TimetableEntry], class_schedule: dict,
                                     subject: Subject, class_group: str, teachers: List, target: int, current_scheduled: int) -> int:
        """Try Friday slots with relaxed time constraints."""
        scheduled = current_scheduled
        
        # CRITICAL: Check if this is a thesis subject - if so, ONLY allow Wednesday (skip Friday completely)
        is_thesis = self._is_thesis_subject(subject)
        if is_thesis:
            print(f"           🎓 THESIS CONSTRAINT: Skipping Friday relaxed scheduling for {subject.code} - thesis must be on Wednesday")
            return scheduled

        # Try Friday periods up to Period 5 (instead of normal limit of 3-4)
        friday_periods = [4, 5]  # Periods normally restricted on Friday

        for period in friday_periods:
            if scheduled >= target:
                break

            day = 'Friday'
            if (day, period) not in class_schedule:
                teacher = self._find_available_teacher(teachers, day, period, 1)
                if teacher:
                    classroom = self._find_available_classroom(day, period, 1, class_group, subject)
                    if classroom:
                        entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                        entries.append(entry)
                        class_schedule[(day, period)] = entry
                        self._mark_global_schedule(teacher, classroom, day, period)
                        scheduled += 1
                        print(f"           ✅ Friday-relaxed: {subject.code} on {day} P{period}")

        return scheduled

    def _try_any_teacher_scheduling(self, entries: List[TimetableEntry], class_schedule: dict,
                                  subject: Subject, class_group: str, target: int, current_scheduled: int) -> int:
        """Try using any available teacher, not just assigned ones."""
        scheduled = current_scheduled

        # CRITICAL: Check if this is a thesis subject - if so, ONLY allow Wednesday
        is_thesis = self._is_thesis_subject(subject)
        allowed_days = ['Wednesday'] if is_thesis else self.days
        
        # Use any teacher from the pool
        all_teachers = self.all_teachers

        for day in allowed_days:
            if scheduled >= target:
                break

            for period in self.periods:
                if scheduled >= target:
                    break

                if (day, period) not in class_schedule:
                    teacher = self._find_available_teacher(all_teachers, day, period, 1)
                    if teacher:
                        classroom = self._find_available_classroom(day, period, 1, class_group, subject)
                        if classroom:
                            entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                            entries.append(entry)
                            class_schedule[(day, period)] = entry
                            self._mark_global_schedule(teacher, classroom, day, period)
                            scheduled += 1
                            print(f"           ✅ Any-teacher: {subject.code} on {day} P{period} (Teacher: {teacher.name})")

        return scheduled

    def _create_emergency_slots_by_extension(self, entries: List[TimetableEntry], class_schedule: dict,
                                           subject: Subject, class_group: str, teachers: List, target: int, current_scheduled: int) -> int:
        """Create emergency slots by extending day duration."""
        scheduled = current_scheduled

        # Try periods 6 and 7 (normally not used)
        emergency_periods = [6, 7]

        # CRITICAL: Check if this is a thesis subject - if so, ONLY allow Wednesday
        is_thesis = self._is_thesis_subject(subject)
        allowed_emergency_days = ['Wednesday'] if is_thesis else ['Monday', 'Tuesday', 'Wednesday', 'Thursday']
        
        for day in allowed_emergency_days:  # Avoid Friday for emergency extension
            if scheduled >= target:
                break

            for period in emergency_periods:
                if scheduled >= target:
                    break

                if (day, period) not in class_schedule:
                    teacher = self._find_available_teacher(teachers, day, period, 1)
                    if teacher:
                        classroom = self._find_available_classroom(day, period, 1, class_group, subject)
                        if classroom:
                            entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                            entries.append(entry)
                            class_schedule[(day, period)] = entry
                            self._mark_global_schedule(teacher, classroom, day, period)
                            scheduled += 1
                            print(f"           🚨 Emergency-extend: {subject.code} on {day} P{period}")

        return scheduled

    def _use_late_friday_emergency_slots(self, entries: List[TimetableEntry], class_schedule: dict,
                                       subject: Subject, class_group: str, teachers: List, target: int, current_scheduled: int) -> int:
        """Use late Friday periods as emergency slots."""
        scheduled = current_scheduled

        # Use Friday periods 5, 6, 7 as absolute emergency
        emergency_friday_periods = [5, 6, 7]

        for period in emergency_friday_periods:
            if scheduled >= target:
                break

            day = 'Friday'
            if (day, period) not in class_schedule:
                teacher = self._find_available_teacher(teachers, day, period, 1)
                if teacher:
                    classroom = self._find_available_classroom(day, period, 1, class_group, subject)
                    if classroom:
                        entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                        entries.append(entry)
                        class_schedule[(day, period)] = entry
                        self._mark_global_schedule(teacher, classroom, day, period)
                        scheduled += 1
                        print(f"           🚨 Emergency-Friday: {subject.code} on {day} P{period}")

        return scheduled

    def _duplicate_classes_emergency(self, entries: List[TimetableEntry], class_schedule: dict,
                                   subject: Subject, class_group: str, teachers: List, target: int, current_scheduled: int) -> int:
        """Emergency scheduling respecting no duplicate theory per day constraint."""
        scheduled = current_scheduled

        print(f"           🚫 CONSTRAINT ENFORCED: No duplicate theory classes per day - using constraint-aware emergency scheduling")

        # Find days that already have this subject (to avoid them)
        used_days = set()
        for entry in entries:
            if entry.class_group == class_group and entry.subject == subject and not entry.is_practical:
                used_days.add(entry.day)

        # Find any available slot that doesn't violate the constraint
        for day in self.days:
            if scheduled >= target:
                break

            # Skip days that already have this subject
            if day in used_days:
                continue

            for period in range(1, 8):  # Try all possible periods
                if scheduled >= target:
                    break

                if (day, period) not in class_schedule:
                    # Check if this slot respects all constraints
                    if self._can_schedule_single(class_schedule, day, period, class_group, subject, entries):
                        # Use first available teacher
                        teacher = teachers[0] if teachers else self.all_teachers[0]
                        # Use first available classroom
                        classroom = self.all_classrooms[0]

                        entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                        entries.append(entry)
                        class_schedule[(day, period)] = entry
                        self._mark_global_schedule(teacher, classroom, day, period)
                        scheduled += 1
                        used_days.add(day)  # Mark this day as used
                        print(f"           🚨 Emergency-constraint-aware: {subject.code} on {day} P{period}")
                        break  # Only one class per day

        return scheduled

    def _get_teachers_for_subject(self, subject: Subject, class_group: str = None) -> List[Teacher]:
        """
        Get teachers for a subject with section awareness.
        PRIORITY APPROACH: Teachers with unavailability constraints are prioritized first.
        """
        teachers = []

        # First try to get teachers from TeacherSubjectAssignment (section-aware)
        try:
            # Extract batch and section from class_group (e.g., "21SW-I" -> batch="21SW", section="I")
            if class_group and '-' in class_group:
                batch_name, section = class_group.split('-', 1)

                # Get batch object
                try:
                    batch = Batch.objects.get(name=batch_name)

                    # Get assignments for this subject and batch
                    assignments = TeacherSubjectAssignment.objects.filter(
                        subject=subject,
                        batch=batch
                    )

                    # Filter by section if specified
                    section_teachers = []
                    for assignment in assignments:
                        if not assignment.sections or section in assignment.sections:
                            section_teachers.append(assignment.teacher)

                    if section_teachers:
                        # PRIORITY APPROACH: Sort teachers by unavailability constraints (constrained first)
                        prioritized_teachers = self._prioritize_teachers_by_constraints(section_teachers)
                        print(f"     📋 Found section-aware teachers for {subject.code} in {class_group}: {[t.name for t in prioritized_teachers]} (prioritized by constraints)")
                        return prioritized_teachers

                except Batch.DoesNotExist:
                    print(f"     ⚠️  Batch {batch_name} not found, falling back to general assignment")
                    pass

            # Fallback: get all teachers assigned to this subject (any batch/section)
            assignments = TeacherSubjectAssignment.objects.filter(subject=subject)
            if assignments.exists():
                teachers = [assignment.teacher for assignment in assignments]
                # PRIORITY APPROACH: Sort teachers by unavailability constraints (constrained first)
                prioritized_teachers = self._prioritize_teachers_by_constraints(teachers)
                print(f"     📋 Found general teachers for {subject.code}: {[t.name for t in prioritized_teachers]} (prioritized by constraints)")
                return prioritized_teachers

        except Exception as e:
            print(f"     ⚠️  Error getting section-aware teachers: {e}")
            pass

        # Legacy fallback: try old many-to-many relationship
        try:
            teachers = list(subject.teacher_set.all())
            if teachers:
                # PRIORITY APPROACH: Sort teachers by unavailability constraints (constrained first)
                prioritized_teachers = self._prioritize_teachers_by_constraints(teachers)
                print(f"     📋 Using legacy teacher assignment for {subject.code}: {[t.name for t in prioritized_teachers]} (prioritized by constraints)")
                return prioritized_teachers
        except:
            pass

        # Final fallback: return all teachers (let system decide)
        print(f"     ⚠️  No specific teachers found for {subject.code}, using fallback")
        fallback_teachers = self.all_teachers[:3]  # Limit to first 3 to avoid over-assignment
        # PRIORITY APPROACH: Even for fallback, prioritize constrained teachers
        prioritized_fallback = self._prioritize_teachers_by_constraints(fallback_teachers)
        return prioritized_fallback

    def _prioritize_teachers_by_constraints(self, teachers: List[Teacher]) -> List[Teacher]:
        """
        PRIORITY APPROACH: Prioritize teachers with unavailability constraints first.
        
        This ensures that teachers with limited availability get scheduled first,
        giving them fair placement before handling teachers with full availability.
        
        Returns:
            List[Teacher]: Teachers sorted by constraint priority (constrained first)
        """
        if not teachers:
            return teachers
        
        constrained_teachers = []
        unconstrained_teachers = []
        
        for teacher in teachers:
            has_constraints = self._teacher_has_unavailability_constraints(teacher)
            if has_constraints:
                constrained_teachers.append(teacher)
                print(f"         🎯 PRIORITY: Teacher {teacher.name} has unavailability constraints - scheduling first")
            else:
                unconstrained_teachers.append(teacher)
        
        # Return constrained teachers first, then unconstrained
        prioritized_list = constrained_teachers + unconstrained_teachers
        
        if constrained_teachers:
            print(f"         📊 PRIORITY ORDERING: {len(constrained_teachers)} constrained teachers first, then {len(unconstrained_teachers)} unconstrained")
        
        return prioritized_list
    
    def _teacher_has_unavailability_constraints(self, teacher: Teacher) -> bool:
        """
        Check if a teacher has any unavailability constraints.
        
        Returns:
            bool: True if teacher has unavailability constraints, False otherwise
        """
        if not teacher or not hasattr(teacher, 'unavailable_periods'):
            return False
        
        if not isinstance(teacher.unavailable_periods, dict) or not teacher.unavailable_periods:
            return False
        
        # Check for new format: {'mandatory': {'Mon': ['8:00 AM', '9:00 AM']}}
        if 'mandatory' in teacher.unavailable_periods:
            mandatory_unavailable = teacher.unavailable_periods['mandatory']
            if isinstance(mandatory_unavailable, dict) and mandatory_unavailable:
                # Has some unavailability constraints
                return True
        
        # Check for old format: {'Mon': ['8', '9']} or {'Mon': True}
        for day, periods in teacher.unavailable_periods.items():
            if day != 'mandatory' and periods:  # Skip 'mandatory' key and check for actual constraints
                return True
        
        return False

    def _can_schedule_block(self, class_schedule: dict, day: str, start_period: int, duration: int, class_group: str, subject: Subject = None) -> bool:
        """
        Check if block can be scheduled.
        
        BULLETPROOF TEACHER UNAVAILABILITY ENFORCEMENT:
        - If ANY assigned teacher is unavailable for ANY part of the block, REJECT scheduling
        - If ALL assigned teachers are unavailable, REJECT scheduling
        - Only allow scheduling if AT LEAST ONE assigned teacher is available for the ENTIRE block
        """
        # STRICT CONSTRAINT: For ANY batch with Thesis subjects, ONLY allow Thesis blocks on Wednesday
        if day.lower().startswith('wed'):
            # Check if this batch has Thesis subjects using the dedicated method
            has_thesis = self._is_final_year_with_thesis(class_group, [])
            
            # If this batch has Thesis subjects, prevent scheduling ANY blocks on Wednesday
            # This is because blocks are for practical subjects, and Thesis is not practical
            if has_thesis:
                print(f"         🚫 STRICT: Preventing ANY block scheduling on Wednesday for {class_group} - reserved for Thesis only")
                return False

        # BULLETPROOF CONSTRAINT: TEACHER UNAVAILABILITY CHECK FOR BLOCKS
        if subject:
            teachers = self._get_teachers_for_subject(subject, class_group)
            if teachers:
                # BULLETPROOF: Check if ANY teacher is available for the ENTIRE block
                any_teacher_available = False
                
                for teacher in teachers:
                    teacher_available_for_entire_block = True
                    
                    # Check if this teacher is available for ALL periods in the block
                    for i in range(duration):
                        period = start_period + i
                        if not self._is_teacher_available(teacher, day, period, 1):
                            teacher_available_for_entire_block = False
                            print(f"         🚫 TEACHER UNAVAILABILITY: Teacher {teacher.name} unavailable for {subject.code} block on {day} P{period}")
                            break
                    
                    if teacher_available_for_entire_block:
                        any_teacher_available = True
                        print(f"         ✅ TEACHER AVAILABILITY: Teacher {teacher.name} available for entire {subject.code} block on {day} P{start_period}-{start_period+duration-1}")
                        break  # Found at least one available teacher
                
                # BULLETPROOF: If NO teacher is available for the entire block, REJECT scheduling
                if not any_teacher_available:
                    print(f"         🚫 BULLETPROOF REJECTION: NO teacher available for entire {subject.code} block on {day} P{start_period}-{start_period+duration-1}")
                    return False
            else:
                # No teachers assigned to this subject - cannot schedule
                print(f"         🚫 NO TEACHERS: No teachers assigned to {subject.code} - cannot schedule block")
                return False

        for i in range(duration):
            period = start_period + i
            if period not in self.periods:
                return False
            if (day, period) in class_schedule:
                return False
        return True

    def _can_schedule_single(self, class_schedule: dict, day: str, period: int, class_group: str, subject: Subject = None, all_entries: List = None) -> bool:
        """
        Check if single period can be scheduled.
        
        BULLETPROOF TEACHER UNAVAILABILITY ENFORCEMENT:
        - If ALL assigned teachers are unavailable, REJECT scheduling
        - Only allow scheduling if AT LEAST ONE assigned teacher is available
        """
        # Basic availability check
        if (day, period) in class_schedule:
            return False

        # BULLETPROOF CONSTRAINT: TEACHER UNAVAILABILITY CHECK
        if subject:
            teachers = self._get_teachers_for_subject(subject, class_group)
            if teachers:
                # BULLETPROOF: Check if ANY teacher is available for this period
                any_teacher_available = False
                
                for teacher in teachers:
                    if self._is_teacher_available(teacher, day, period, 1):
                        any_teacher_available = True
                        print(f"         ✅ TEACHER AVAILABILITY: Teacher {teacher.name} available for {subject.code} on {day} P{period}")
                        break  # Found at least one available teacher
                    else:
                        print(f"         🚫 TEACHER UNAVAILABILITY: Teacher {teacher.name} unavailable for {subject.code} on {day} P{period}")
                
                # BULLETPROOF: If NO teacher is available, REJECT scheduling
                if not any_teacher_available:
                    print(f"         🚫 BULLETPROOF REJECTION: NO teacher available for {subject.code} on {day} P{period}")
                    return False
            else:
                # No teachers assigned to this subject - cannot schedule
                print(f"         🚫 NO TEACHERS: No teachers assigned to {subject.code} - cannot schedule")
                return False

        # STRICT CONSTRAINT: For ANY batch with Thesis subjects, ONLY allow Thesis subjects on Wednesday
        if day.lower().startswith('wed'):
            # Check if this batch has Thesis subjects using the dedicated method
            has_thesis = self._is_final_year_with_thesis(class_group, [])

            # If this batch has Thesis subjects, ONLY allow Thesis subjects on Wednesday
            if has_thesis:
                # If subject is not a Thesis subject, prevent scheduling on Wednesday
                if not subject or not self._is_thesis_subject(subject):
                    print(f"         🚫 STRICT: Preventing non-Thesis subject on Wednesday for {class_group}")
                    return False
                # If it is a Thesis subject, allow it on Wednesday
                else:
                    print(f"         ✅ Allowing Thesis subject {subject.code} on Wednesday for {class_group}")
                    # For Thesis subjects on Wednesday, override normal constraints
                    # This allows multiple Thesis classes on Wednesday if needed
                    print(f"         🔄 Overriding normal constraints for Thesis on Wednesday")
                    return True
            # For batches without Thesis, normal scheduling applies

        # ENHANCED CONSTRAINT: No Duplicate Theory Classes Per Day
        # Use centralized constraint enforcer for robust checking
        if subject and not subject.is_practical:  # Only apply to theory subjects
            # Check if this is a Thesis subject for final year (existing constraint takes precedence)
            is_thesis_subject = ('thesis' in subject.name.lower() or 'thesis' in subject.code.lower())
            is_final_year = class_group.split('-')[0].startswith('21SW') if '-' in class_group else class_group.startswith('21SW')
            is_wednesday = day.lower().startswith('wed')

            # Skip constraint for Thesis subjects on Wednesday for final year (existing constraint takes precedence)
            if is_thesis_subject and is_final_year and is_wednesday:
                pass  # Allow multiple Thesis classes on Wednesday for final year
            else:
                # Use centralized constraint enforcer for robust duplicate theory checking
                if not duplicate_constraint_enforcer.can_schedule_theory(
                    all_entries, class_group, subject.code, day, period
                ):
                    print(f"         🚫 No duplicate theory (enforced): {subject.code} already scheduled on {day} for {class_group}")
                    return False

        return True

    def _find_available_teacher(self, teachers: List[Teacher], day: str, start_period: int, duration: int) -> Optional[Teacher]:
        """Find an available teacher for the given time slot."""
        if not teachers:
            return None
        
        # 🎲 RANDOMIZE TEACHER ORDER for variety in each generation
        available_teachers = []
        for teacher in teachers:
            if self._is_teacher_available(teacher, day, start_period, duration):
                available_teachers.append(teacher)
        
        if not available_teachers:
            return None
        
        # Randomly select from available teachers instead of always picking the first one
        return random.choice(available_teachers)

    def _find_available_classroom(self, day: str, start_period: int, duration: int,
                                 class_group: str = None, subject: Subject = None) -> Optional[Classroom]:
        """
        Find available classroom using intelligent room allocation system.
        Senior batches get labs for ALL classes. Junior batches use regular rooms for theory.
        """
        if not class_group or not subject:
            # Fallback to basic allocation if missing information
            return self._find_basic_available_classroom(day, start_period, duration, subject)

        # SIMPLIFIED: Get ALL entries (both in-memory and database) for accurate conflict detection
        current_entries = self._get_all_current_entries()

        # SIMPLIFIED ALLOCATION: Use building-based allocation for all batches
        if subject.is_practical and duration == 3:
            # Practical: 3-block lab allocation (same for all batches)
            return self.room_allocator.allocate_room_for_practical(
                day, start_period, class_group, subject, current_entries
            )
        else:
            # Theory: building-based allocation (2nd year -> Academic, others -> Main)
            return self.room_allocator.allocate_room_for_theory(
                day, start_period, class_group, subject, current_entries
                )

    def _find_basic_available_classroom(self, day: str, start_period: int, duration: int, subject: Optional[Subject] = None) -> Optional[Classroom]:
        """Basic classroom finding for fallback scenarios.
        CRITICAL: If subject is practical, ONLY consider labs; never regular rooms.
        """
        # Decide candidate rooms based on subject type
        if subject and hasattr(subject, 'is_practical') and subject.is_practical:
            candidate_rooms = [room for room in self.all_classrooms if room.is_lab]
        else:
            candidate_rooms = [room for room in self.all_classrooms if not room.is_lab]

        # Sort by building priority and name for stable behavior
        sorted_classrooms = sorted(candidate_rooms, key=lambda c: (c.building_priority, c.name))

        for classroom in sorted_classrooms:
            available = True
            for i in range(duration):
                period = start_period + i
                if (classroom.id, day, period) in self.global_classroom_schedule:
                    available = False
                    break
            if available:
                return classroom

        return None

    def _find_existing_lab_for_practical(self, subject: Subject, class_group: str) -> Optional[Classroom]:
        """
        Find if this practical subject already has a lab assigned for this class group.
        Ensures ALL 3 blocks of a practical are in the SAME lab.
        """
        # Use the room allocator's method which is already implemented and working
        # BULLETPROOF: Get all entries for this class_group and subject (both in-memory and database)
        all_entries = self._get_all_current_entries()
        current_entries = [
            entry for entry in all_entries
            if entry.class_group == class_group and entry.subject == subject
        ]

        return self.room_allocator._find_existing_lab_for_practical(class_group, subject, current_entries)

    def _get_all_current_entries(self) -> List[TimetableEntry]:
        """
        BULLETPROOF: Get all current entries including both in-memory and database entries.
        This ensures the room allocator sees ALL scheduled classes for accurate conflict detection.
        """
        # Get all database entries
        db_entries = list(TimetableEntry.objects.all())

        # Get all in-memory entries from current scheduling session
        in_memory_entries = []

        # Check if we have a current scheduling session with in-memory entries
        if hasattr(self, '_current_session_entries'):
            in_memory_entries = self._current_session_entries

        # Combine both lists
        all_entries = db_entries + in_memory_entries

        print(f"    📊 BULLETPROOF conflict check: {len(db_entries)} database + {len(in_memory_entries)} in-memory = {len(all_entries)} total entries")

        return all_entries

    def _create_entry(self, day: str, period: int, subject: Subject, teacher: Teacher,
                     classroom: Classroom, class_group: str, is_practical: bool) -> TimetableEntry:
        """Create timetable entry."""
        start_time = self._calculate_start_time(period)
        end_time = self._calculate_end_time(period)

        return TimetableEntry(
            day=day,
            period=period,
            subject=subject,
            teacher=teacher,
            classroom=classroom,
            class_group=class_group,
            start_time=start_time,
            end_time=end_time,
            is_practical=is_practical,
            schedule_config=self.config
        )

    def _mark_global_schedule(self, teacher: Teacher, classroom: Classroom, day: str, period: int):
        """Mark teacher and classroom as busy."""
        self.global_teacher_schedule[(teacher.id, day, period)] = True
        # Note: classroom schedule is marked when actual entry is created, not here

    def _calculate_start_time(self, period: int) -> dt_time:
        """Calculate start time for period."""
        minutes_from_start = (period - 1) * self.class_duration
        hours = minutes_from_start // 60
        minutes = minutes_from_start % 60

        start_hour = self.start_time.hour + hours
        start_minute = self.start_time.minute + minutes

        # Handle minute overflow
        if start_minute >= 60:
            start_hour += start_minute // 60
            start_minute = start_minute % 60

        # Handle hour overflow
        if start_hour >= 24:
            start_hour = 23
            start_minute = 59

        return dt_time(hour=start_hour, minute=start_minute)

    def _calculate_end_time(self, period: int) -> dt_time:
        """Calculate end time for period."""
        start = self._calculate_start_time(period)
        end_hour = start.hour
        end_minute = start.minute + self.class_duration

        # Handle minute overflow
        while end_minute >= 60:
            end_hour += 1
            end_minute -= 60

        # Handle hour overflow
        if end_hour >= 24:
            end_hour = 23
            end_minute = 59

        return dt_time(hour=end_hour, minute=end_minute)

    def _save_entries_to_database(self, entries: List[TimetableEntry]) -> int:
        """Save entries to database."""
        saved_count = 0
        with transaction.atomic():
            for entry in entries:
                try:
                    entry.save()
                    saved_count += 1
                except Exception as e:
                    print(f"     ⚠️  Error saving entry: {str(e)}")
        return saved_count

    def _check_all_conflicts(self, entries: List[TimetableEntry]) -> List[str]:
        """Check for all conflicts."""
        conflicts = []

        # Teacher conflicts
        teacher_slots = {}
        for entry in entries:
            if entry.teacher:  # Only check if teacher is assigned
                key = f"{entry.teacher.id}_{entry.day}_{entry.period}"
                if key in teacher_slots:
                    conflicts.append(f"Teacher conflict: {entry.teacher.name} at {entry.day} P{entry.period}")
                else:
                    teacher_slots[key] = entry

        # Classroom conflicts
        classroom_slots = {}
        for entry in entries:
            if entry.classroom:  # Only check if classroom is assigned
                key = f"{entry.classroom.id}_{entry.day}_{entry.period}"
                if key in classroom_slots:
                    conflicts.append(f"Classroom conflict: {entry.classroom.name} at {entry.day} P{entry.period}")
                else:
                    classroom_slots[key] = entry

        # Class conflicts
        class_slots = {}
        for entry in entries:
            key = f"{entry.class_group}_{entry.day}_{entry.period}"
            if key in class_slots:
                conflicts.append(f"Class conflict: {entry.class_group} at {entry.day} P{entry.period}")
            else:
                class_slots[key] = entry

        return conflicts

    def _entry_to_dict(self, entry: TimetableEntry) -> Dict:
        """Convert entry to dictionary."""
        return {
            'day': entry.day,
            'period': entry.period,
            'subject': entry.subject.name,
            'subject_code': entry.subject.code,
            'teacher': entry.teacher.name if entry.teacher else 'No Teacher Assigned',
            'classroom': entry.classroom.name if entry.classroom else 'No Classroom Assigned',
            'class_group': entry.class_group,
            'start_time': entry.start_time.strftime('%H:%M'),
            'end_time': entry.end_time.strftime('%H:%M'),
            'is_practical': entry.is_practical,
            'is_extra_class': entry.is_extra_class,
            'credits': entry.subject.credits
        }

    def _analyze_schedule_compaction(self, entries: List[TimetableEntry]) -> Dict:
        """ENHANCEMENT 3: Analyze how well the schedule is compacted to early periods."""
        analysis = {
            'section_analysis': {},
            'overall_stats': {
                'early_finish_sections': 0,  # Sections finishing by period 4 (12:00)
                'medium_finish_sections': 0,  # Sections finishing by period 5 (1:00)
                'late_finish_sections': 0,   # Sections finishing after period 5
                'average_latest_period': 0.0
            }
        }

        # Group entries by section and day
        section_day_schedule = {}
        for entry in entries:
            key = (entry.class_group, entry.day)
            if key not in section_day_schedule:
                section_day_schedule[key] = []
            section_day_schedule[key].append(entry.period)

        # Analyze each section
        section_latest_periods = {}
        for (section, day), periods in section_day_schedule.items():
            if section not in section_latest_periods:
                section_latest_periods[section] = []

            latest_period = max(periods)
            section_latest_periods[section].append(latest_period)

        # Calculate statistics for each section
        for section, daily_latest_periods in section_latest_periods.items():
            avg_latest = sum(daily_latest_periods) / len(daily_latest_periods)
            max_latest = max(daily_latest_periods)

            # Count days finishing early/medium/late
            early_days = sum(1 for p in daily_latest_periods if p <= 4)  # By 12:00
            medium_days = sum(1 for p in daily_latest_periods if p == 5)  # By 1:00
            late_days = sum(1 for p in daily_latest_periods if p >= 6)   # After 1:00

            analysis['section_analysis'][section] = {
                'average_latest_period': round(avg_latest, 1),
                'max_latest_period': max_latest,
                'early_finish_days': early_days,   # Days finishing by 12:00
                'medium_finish_days': medium_days, # Days finishing by 1:00
                'late_finish_days': late_days,     # Days finishing after 1:00
                'total_days': len(daily_latest_periods)
            }

            # Classify section overall
            if avg_latest <= 4.0:
                analysis['overall_stats']['early_finish_sections'] += 1
            elif avg_latest <= 5.0:
                analysis['overall_stats']['medium_finish_sections'] += 1
            else:
                analysis['overall_stats']['late_finish_sections'] += 1

        # Calculate overall average
        all_averages = [data['average_latest_period'] for data in analysis['section_analysis'].values()]
        analysis['overall_stats']['average_latest_period'] = round(sum(all_averages) / len(all_averages), 1) if all_averages else 0.0

        # Print compaction report
        print(f"\n📊 SCHEDULE COMPACTION ANALYSIS:")
        print(f"   Early finish sections (by 12:00): {analysis['overall_stats']['early_finish_sections']}")
        print(f"   Medium finish sections (by 1:00): {analysis['overall_stats']['medium_finish_sections']}")
        print(f"   Late finish sections (after 1:00): {analysis['overall_stats']['late_finish_sections']}")
        print(f"   Overall average latest period: {analysis['overall_stats']['average_latest_period']}")

        return analysis

    def _enforce_minimum_daily_duration(self, entries: List[TimetableEntry], class_group: str) -> List[TimetableEntry]:
        """ENHANCEMENT 4: Ensure minimum daily class duration using smart redistribution (no filler classes)."""
        if not entries:
            return entries

        # Group entries by day
        day_entries = {}
        for entry in entries:
            if entry.day not in day_entries:
                day_entries[entry.day] = []
            day_entries[entry.day].append(entry)

        # ENHANCEMENT: Smart redistribution instead of filler classes
        return self._redistribute_classes_for_minimum_duration(entries, day_entries, class_group)

    def _add_filler_classes(self, class_group: str, day: str, start_period: int, periods_needed: int) -> List[TimetableEntry]:
        """Add filler classes to meet minimum daily duration."""
        filler_entries = []

        # Get subjects for this class group to use for filler
        subjects = self._get_subjects_for_class_group(class_group)
        theory_subjects = [s for s in subjects if not self._is_practical_subject(s)]

        if not theory_subjects:
            return filler_entries

        # Add filler periods
        for i in range(periods_needed):
            period = start_period + i
            if period > len(self.periods):
                break

            # Use a theory subject for filler (rotate through subjects)
            subject = theory_subjects[i % len(theory_subjects)]

            # Find available teacher and classroom
            teachers = self._get_teachers_for_subject(subject, class_group)
            if teachers:
                teacher = self._find_available_teacher(teachers, day, period, 1)
                if teacher:
                    classroom = self._find_available_classroom(day, period, 1, class_group, subject)
                    if classroom:
                        entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                        filler_entries.append(entry)
                        self._mark_global_schedule(teacher, classroom, day, period)
                        print(f"       ✅ Added filler class: {subject.code} on {day} P{period}")

        return filler_entries

    def _redistribute_classes_for_minimum_duration(self, entries: List[TimetableEntry], day_entries: dict, class_group: str) -> List[TimetableEntry]:
        """ENHANCEMENT: Smart class redistribution to meet minimum duration without adding filler classes."""
        print(f"     🔄 Smart redistribution for minimum duration compliance...")

        # Analyze each day's duration
        day_analysis = {}
        for day, day_entry_list in day_entries.items():
            if not day_entry_list:
                continue

            latest_period = max(entry.period for entry in day_entry_list)
            min_required_period = 3  # Default minimum (11:00 AM)
            if day.lower() == 'friday':
                min_required_period = 2  # Friday can end earlier (10:00 AM)

            day_analysis[day] = {
                'entries': day_entry_list,
                'latest_period': latest_period,
                'min_required': min_required_period,
                'needs_extension': latest_period < min_required_period,
                'deficit': max(0, min_required_period - latest_period),
                'theory_classes': [e for e in day_entry_list if not e.is_practical]
            }

        # Find days that need extension and days that can donate classes
        short_days = [day for day, analysis in day_analysis.items() if analysis['needs_extension']]
        long_days = [day for day, analysis in day_analysis.items() if not analysis['needs_extension'] and len(analysis['theory_classes']) > 1]

        if not short_days:
            print(f"       ✅ All days meet minimum duration requirements")
            return entries

        print(f"       📊 Short days needing extension: {short_days}")
        print(f"       📊 Long days available for redistribution: {long_days}")

        # Perform smart redistribution
        redistributed_entries = list(entries)  # Copy original entries

        for short_day in short_days:
            short_analysis = day_analysis[short_day]
            classes_needed = short_analysis['deficit']

            print(f"       🔄 {class_group} {short_day} needs {classes_needed} more classes")

            # Try to move theory classes from long days
            classes_moved = 0
            for long_day in long_days:
                if classes_moved >= classes_needed:
                    break

                long_analysis = day_analysis[long_day]
                movable_classes = [e for e in long_analysis['theory_classes']
                                 if e.period > short_analysis['min_required']]  # Only move classes from later periods

                for movable_class in movable_classes:
                    if classes_moved >= classes_needed:
                        break

                    # Find available slot in short day
                    target_period = short_analysis['latest_period'] + classes_moved + 1

                    if target_period <= len(self.periods) and self._can_move_class(movable_class, short_day, target_period, redistributed_entries):
                        # Move the class
                        print(f"         ✅ Moving {movable_class.subject.code} from {long_day} P{movable_class.period} to {short_day} P{target_period}")

                        # Update the entry
                        for i, entry in enumerate(redistributed_entries):
                            if (entry.class_group == movable_class.class_group and
                                entry.subject.code == movable_class.subject.code and
                                entry.day == movable_class.day and
                                entry.period == movable_class.period):

                                # Create new entry with updated day and period
                                new_entry = self._create_entry(
                                    short_day, target_period,
                                    entry.subject, entry.teacher, entry.classroom,
                                    entry.class_group, entry.is_practical
                                )
                                redistributed_entries[i] = new_entry
                                classes_moved += 1
                                break

            if classes_moved > 0:
                print(f"       ✅ Successfully moved {classes_moved} classes to {short_day}")
            else:
                print(f"       ⚠️  Could not find classes to move to {short_day}")

        return redistributed_entries

    def _enforce_friday_time_limit(self, entries: List[TimetableEntry], class_group: str) -> List[TimetableEntry]:
        """
        ENHANCEMENT 7: Enforce Friday time limits based on practical scheduling:
        - If practical is scheduled on Friday: Classes must not exceed 12:00 PM or 1:00 PM (depending on practical placement)
        - If no practical on Friday: Classes must not exceed 11:00 AM (Period 3)
        """
        print(f"     📅 Enforcing Friday time limits for {class_group}...")

        # Debug: Show all days in entries
        all_days = set(e.day for e in entries)
        print(f"       🔍 All days in schedule: {sorted(all_days)}")

        friday_entries = [e for e in entries if e.day.lower().startswith('fri')]
        practical_entries = [e for e in friday_entries if e.is_practical]
        theory_entries = [e for e in friday_entries if not e.is_practical]

        print(f"       📊 Friday entries: {len(friday_entries)} total ({len(practical_entries)} practical, {len(theory_entries)} theory)")

        if friday_entries:
            friday_periods = [e.period for e in friday_entries]
            print(f"       ⏰ Friday periods used: {sorted(friday_periods)}")
        else:
            print(f"       ℹ️  No Friday entries found for {class_group}")
            return entries

        if practical_entries:
            # Case 1: Practical is scheduled on Friday
            print(f"       🔬 Practical found on Friday - applying practical-based time limits")
            return self._enforce_friday_practical_limits(entries, class_group, practical_entries, theory_entries)
        else:
            # Case 2: No practical on Friday - all theory classes must not exceed 11:00 AM (Period 3)
            print(f"       📚 No practical on Friday - applying theory-only time limits (max Period 3)")
            return self._enforce_friday_theory_only_limits(entries, class_group, theory_entries)

    def _enforce_friday_practical_limits(self, entries: List[TimetableEntry], class_group: str,
                                       practical_entries: List[TimetableEntry], theory_entries: List[TimetableEntry]) -> List[TimetableEntry]:
        """Handle Friday scheduling when practical is present."""

        # Practical must be placed last (consecutive 3-hour block at the end)
        # Determine the optimal practical placement
        max_practical_period = max(e.period for e in practical_entries)
        min_practical_period = min(e.period for e in practical_entries)

        # Check if practical is properly placed as consecutive 3-hour block at the end
        expected_practical_periods = list(range(min_practical_period, min_practical_period + 3))
        actual_practical_periods = sorted([e.period for e in practical_entries])

        if actual_practical_periods != expected_practical_periods:
            print(f"       ⚠️  Practical not in consecutive 3-hour block - rearranging...")
            # Move practical to end (periods 5, 6, 7 or 4, 5, 6 depending on schedule)
            target_start_period = max(4, len(self.periods) - 2)  # Start at period 4 or later
            entries = self._move_practical_to_end(entries, class_group, practical_entries, target_start_period)
            practical_entries = [e for e in entries if e.day.lower() == 'friday' and e.is_practical]
            theory_entries = [e for e in entries if e.day.lower() == 'friday' and not e.is_practical]

        # Determine time limit based on practical placement
        practical_start_period = min(e.period for e in practical_entries)

        if practical_start_period >= 5:  # Practical starts at 12:00 PM or later
            max_theory_period = 4  # Theory can go up to 12:00 PM (Period 4)
            time_limit_desc = "12:00 PM"
        elif practical_start_period >= 4:  # Practical starts at 11:00 AM
            max_theory_period = 3  # Theory can go up to 11:00 AM (Period 3)
            time_limit_desc = "11:00 AM"
        else:
            max_theory_period = practical_start_period - 1
            time_limit_desc = f"Period {max_theory_period}"

        print(f"       📋 Practical starts at Period {practical_start_period}, theory limit: {time_limit_desc}")

        # Check for theory violations
        violating_theory = [e for e in theory_entries if e.period > max_theory_period]

        if not violating_theory:
            print(f"       ✅ All Friday theory classes comply with {time_limit_desc} limit")
            return entries

        print(f"       ⚠️  Found {len(violating_theory)} theory classes exceeding {time_limit_desc} - redistributing...")

        # Redistribute violating theory classes
        return self._redistribute_friday_violations(entries, violating_theory, class_group)

    def _enforce_friday_theory_only_limits(self, entries: List[TimetableEntry], class_group: str,
                                         theory_entries: List[TimetableEntry]) -> List[TimetableEntry]:
        """Handle Friday scheduling when only theory classes are present."""

        max_allowed_period = 3  # 11:00 AM (Period 3)
        violating_entries = [e for e in theory_entries if e.period > max_allowed_period]

        if not violating_entries:
            print(f"       ✅ All Friday theory classes end by 11:00 AM - no violations")
            return entries

        print(f"       ⚠️  Found {len(violating_entries)} theory classes after 11:00 AM - redistributing...")

        return self._redistribute_friday_violations(entries, violating_entries, class_group)

    def _move_practical_to_end(self, entries: List[TimetableEntry], class_group: str,
                             practical_entries: List[TimetableEntry], target_start_period: int) -> List[TimetableEntry]:
        """Move practical to consecutive periods at the end of Friday."""

        # Remove existing practical entries
        non_practical_entries = [e for e in entries if not (e.day.lower() == 'friday' and e.is_practical)]

        # Create new practical entries at target periods
        new_practical_entries = []
        for i, practical_entry in enumerate(sorted(practical_entries, key=lambda x: x.period)):
            new_period = target_start_period + i
            new_entry = self._create_entry(
                'Friday', new_period,
                practical_entry.subject, practical_entry.teacher, practical_entry.classroom,
                practical_entry.class_group, True
            )
            new_practical_entries.append(new_entry)
            print(f"         ✅ Moved practical {practical_entry.subject.code} to Friday P{new_period}")

        return non_practical_entries + new_practical_entries

    def _redistribute_friday_violations(self, entries: List[TimetableEntry], violating_entries: List[TimetableEntry],
                                      class_group: str) -> List[TimetableEntry]:
        """Redistribute violating Friday entries to other days while preserving constraints."""

        # Don't move practical classes as they need consecutive blocks
        theory_violations = [e for e in violating_entries if not e.is_practical]
        practical_violations = [e for e in violating_entries if e.is_practical]

        if practical_violations:
            print(f"         ⚠️  Cannot redistribute {len(practical_violations)} practical classes - they need consecutive blocks")

        # Remove only theory violations for redistribution
        compliant_entries = [e for e in entries if e not in theory_violations]
        redistributed_entries = list(compliant_entries)

        # Group theory violations by subject for credit hour checking
        violations_by_subject = {}
        for entry in theory_violations:
            if entry.subject.code not in violations_by_subject:
                violations_by_subject[entry.subject.code] = []
            violations_by_subject[entry.subject.code].append(entry)

        for violating_entry in theory_violations:
            alternative_found = False

            # Check if this subject has more sessions than required (safe to move)
            subject_sessions = len(violations_by_subject[violating_entry.subject.code])
            required_sessions = violating_entry.subject.credits

            # Only redistribute if it won't break credit hour compliance
            if subject_sessions <= required_sessions:
                print(f"         ⚠️  Cannot move {violating_entry.subject.code} - would break credit hour compliance")
                continue

            # Try to find alternative slot on other days (Monday-Thursday)
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday']:
                for period in range(1, 8):  # Try all periods
                    if self._can_reschedule_entry(violating_entry, day, period, redistributed_entries):
                        new_entry = self._create_entry(
                            day, period,
                            violating_entry.subject, violating_entry.teacher, violating_entry.classroom,
                            violating_entry.class_group, violating_entry.is_practical
                        )
                        redistributed_entries.append(new_entry)
                        alternative_found = True
                        print(f"         ✅ Safely moved {violating_entry.subject.code} from Friday P{violating_entry.period} to {day} P{period}")
                        break

                if alternative_found:
                    break

            if not alternative_found:
                print(f"         ⚠️  Could not safely redistribute {violating_entry.subject.code} - keeping on Friday")
                # Keep the class on Friday rather than break constraints
                redistributed_entries.append(violating_entry)

        print(f"       ✅ Friday time limits enforced with constraint preservation!")
        return redistributed_entries

    def _enforce_minimum_daily_classes(self, entries: List[TimetableEntry], class_group: str) -> List[TimetableEntry]:
        """
        ENHANCEMENT 8: Ensure no day has only practical or only one class.
        Each day should have at least 2 classes, and not be only practical classes.
        """
        print(f"     📋 Enforcing minimum daily classes constraint for {class_group}...")

        # Group entries by day
        day_entries = {}
        for entry in entries:
            if entry.class_group == class_group:  # Only check entries for this class group
                if entry.day not in day_entries:
                    day_entries[entry.day] = []
                day_entries[entry.day].append(entry)

        print(f"       📊 Daily distribution for {class_group}: {[(day, len(entries)) for day, entries in day_entries.items()]}")

        # Analyze each day
        problematic_days = []
        for day, day_entry_list in day_entries.items():
            if not day_entry_list:
                continue

            theory_count = len([e for e in day_entry_list if not e.is_practical])
            practical_count = len([e for e in day_entry_list if e.is_practical])
            total_count = len(day_entry_list)

            # Check violations
            only_practical = practical_count > 0 and theory_count == 0
            only_one_class = total_count == 1

            if only_practical or only_one_class:
                violation_type = "only practical" if only_practical else "only one class"
                print(f"       ⚠️  {day} has {violation_type} ({theory_count} theory, {practical_count} practical)")
                problematic_days.append({
                    'day': day,
                    'entries': day_entry_list,
                    'theory_count': theory_count,
                    'practical_count': practical_count,
                    'violation_type': violation_type
                })

        if not problematic_days:
            print(f"       ✅ All days have adequate class distribution")
            return entries

        print(f"       🔧 Fixing {len(problematic_days)} problematic days...")

        # Fix problematic days with aggressive approach
        fixed_entries = list(entries)
        max_attempts = 5  # Try multiple strategies

        for attempt in range(max_attempts):
            print(f"       🔄 Attempt {attempt + 1} to fix {len(problematic_days)} problematic days...")

            current_violations = self._count_daily_violations(fixed_entries, class_group)
            if current_violations == 0:
                print(f"       ✅ All violations resolved!")
                break

            for problem in problematic_days:
                day = problem['day']
                violation_type = problem['violation_type']

                if violation_type == "only practical":
                    # Try multiple strategies to add theory
                    fixed_entries = self._aggressively_add_theory_to_practical_day(fixed_entries, day, class_group, attempt)
                elif violation_type == "only one class":
                    # Try multiple strategies to add more classes
                    fixed_entries = self._aggressively_add_classes_to_single_class_day(fixed_entries, day, class_group, attempt)

            # Re-evaluate problematic days after fixes
            problematic_days = self._identify_problematic_days(fixed_entries, class_group)

            if not problematic_days:
                print(f"       ✅ All violations resolved in attempt {attempt + 1}!")
                break

        # Final validation - if we still have violations, use emergency measures
        final_violations = self._count_daily_violations(fixed_entries, class_group)
        if final_violations > 0:
            print(f"       🚨 Emergency measures: {final_violations} violations remain - applying radical fixes...")
            fixed_entries = self._apply_emergency_fixes(fixed_entries, class_group)

        print(f"       ✅ Minimum daily classes constraint enforced - NO VIOLATIONS ALLOWED!")
        return fixed_entries

    def _add_theory_to_practical_day(self, entries: List[TimetableEntry], target_day: str, class_group: str) -> List[TimetableEntry]:
        """Add theory classes to a day that has only practical classes."""
        print(f"         🔧 Adding theory classes to {target_day} (currently only practical)")

        # Find theory classes from other days that can be moved safely
        theory_entries = [e for e in entries if not e.is_practical and e.class_group == class_group]

        # Group theory entries by day and subject
        theory_by_day = {}
        theory_by_subject = {}
        for entry in theory_entries:
            if entry.day not in theory_by_day:
                theory_by_day[entry.day] = []
            theory_by_day[entry.day].append(entry)

            if entry.subject.code not in theory_by_subject:
                theory_by_subject[entry.subject.code] = []
            theory_by_subject[entry.subject.code].append(entry)

        # Find safe candidates that won't break credit hour compliance
        safe_candidates = []
        for day, day_theories in theory_by_day.items():
            if day != target_day and len(day_theories) > 1:
                # Check if this day would still be valid after removing one theory
                day_all_entries = [e for e in entries if e.day == day and e.class_group == class_group]
                remaining_after_removal = len(day_all_entries) - 1
                if remaining_after_removal >= 2:  # Still have at least 2 classes
                    # Only consider subjects that have more than their required weekly sessions
                    for theory in day_theories:
                        subject_sessions = len(theory_by_subject[theory.subject.code])
                        required_sessions = theory.subject.credits
                        if subject_sessions > required_sessions:
                            safe_candidates.append(theory)

        if not safe_candidates:
            print(f"         ⚠️  No safe theory classes available to move to {target_day} without breaking credit compliance")
            return entries

        # Move one safe theory class to the target day
        theory_to_move = safe_candidates[0]

        # Check for teacher conflicts on target day
        target_day_entries = [e for e in entries if e.day == target_day and e.class_group == class_group]

        # Find available period that doesn't conflict with teacher or classroom
        available_period = None
        for period in range(1, 8):  # Check periods 1-7
            period_conflicts = False

            # Check if period is already used
            if any(e.period == period for e in target_day_entries):
                continue

            # Check for teacher conflicts across all entries
            teacher_conflict = any(
                e.teacher == theory_to_move.teacher and e.day == target_day and e.period == period
                for e in entries if e != theory_to_move
            )

            # Check for classroom conflicts
            classroom_conflict = any(
                e.classroom == theory_to_move.classroom and e.day == target_day and e.period == period
                for e in entries if e != theory_to_move
            )

            if not teacher_conflict and not classroom_conflict:
                available_period = period
                break

        if available_period is None:
            print(f"         ⚠️  No conflict-free periods available on {target_day}")
            return entries

        # Create new entry on target day
        new_entry = self._create_entry(
            target_day, available_period,
            theory_to_move.subject, theory_to_move.teacher, theory_to_move.classroom,
            class_group, False
        )

        # Remove old entry and add new one
        updated_entries = [e for e in entries if e != theory_to_move]
        updated_entries.append(new_entry)

        print(f"         ✅ Safely moved {theory_to_move.subject.code} from {theory_to_move.day} P{theory_to_move.period} to {target_day} P{available_period}")
        return updated_entries

    def _add_classes_to_single_class_day(self, entries: List[TimetableEntry], target_day: str, class_group: str) -> List[TimetableEntry]:
        """Add more classes to a day that has only one class."""
        print(f"         🔧 Adding classes to {target_day} (currently only one class)")

        # Find classes from other days that can be moved safely
        other_entries = [e for e in entries if e.day != target_day and e.class_group == class_group]

        # Group by day and subject for safety checks
        entries_by_day = {}
        entries_by_subject = {}
        for entry in other_entries:
            if entry.day not in entries_by_day:
                entries_by_day[entry.day] = []
            entries_by_day[entry.day].append(entry)

            if entry.subject.code not in entries_by_subject:
                entries_by_subject[entry.subject.code] = []
            entries_by_subject[entry.subject.code].append(entry)

        # Find safe candidates that won't break constraints
        safe_candidates = []
        for day, day_entries in entries_by_day.items():
            if len(day_entries) >= 3:  # Can spare one class
                for entry in day_entries:
                    # Don't move practical classes (they need consecutive blocks)
                    if entry.is_practical:
                        continue

                    # Check if moving this would break credit hour compliance
                    subject_sessions = len(entries_by_subject[entry.subject.code])
                    required_sessions = entry.subject.credits
                    if subject_sessions > required_sessions:
                        safe_candidates.append(entry)

        if not safe_candidates:
            print(f"         ⚠️  No safe classes available to move to {target_day} without breaking constraints")
            return entries

        # Move one safe class to target day
        class_to_move = safe_candidates[0]

        # Check for conflicts on target day
        target_day_entries = [e for e in entries if e.day == target_day and e.class_group == class_group]

        # Find available period that doesn't conflict
        available_period = None
        for period in range(1, 8):
            # Check if period is already used
            if any(e.period == period for e in target_day_entries):
                continue

            # Check for teacher conflicts
            teacher_conflict = any(
                e.teacher == class_to_move.teacher and e.day == target_day and e.period == period
                for e in entries if e != class_to_move
            )

            # Check for classroom conflicts
            classroom_conflict = any(
                e.classroom == class_to_move.classroom and e.day == target_day and e.period == period
                for e in entries if e != class_to_move
            )

            if not teacher_conflict and not classroom_conflict:
                available_period = period
                break

        if available_period is None:
            print(f"         ⚠️  No conflict-free periods available on {target_day}")
            return entries

        # Create new entry on target day
        new_entry = self._create_entry(
            target_day, available_period,
            class_to_move.subject, class_to_move.teacher, class_to_move.classroom,
            class_group, class_to_move.is_practical
        )

        # Remove old entry and add new one
        updated_entries = [e for e in entries if e != class_to_move]
        updated_entries.append(new_entry)

        print(f"         ✅ Safely moved {class_to_move.subject.code} from {class_to_move.day} P{class_to_move.period} to {target_day} P{available_period}")
        return updated_entries

    def _validate_constraint_integrity(self, entries: List[TimetableEntry], class_group: str) -> List[str]:
        """Validate that constraint fixes haven't broken existing constraints."""
        issues = []

        # Check credit hour compliance
        subject_sessions = {}
        for entry in entries:
            if entry.class_group == class_group:
                if entry.subject.code not in subject_sessions:
                    subject_sessions[entry.subject.code] = []
                subject_sessions[entry.subject.code].append(entry)

        for subject_code, sessions in subject_sessions.items():
            if sessions:
                expected_sessions = sessions[0].subject.credits
                actual_sessions = len(sessions)
                if actual_sessions != expected_sessions:
                    issues.append(f"Credit hour violation: {subject_code} has {actual_sessions} sessions, expected {expected_sessions}")

        # Check practical block integrity
        practical_sessions = {}
        for entry in entries:
            if entry.class_group == class_group and entry.is_practical:
                if entry.subject.code not in practical_sessions:
                    practical_sessions[entry.subject.code] = []
                practical_sessions[entry.subject.code].append(entry)

        for subject_code, sessions in practical_sessions.items():
            if len(sessions) > 1:  # Should be exactly 1 session (3 consecutive periods)
                # Check if they're on the same day and consecutive
                days = set(s.day for s in sessions)
                if len(days) > 1:
                    issues.append(f"Practical block violation: {subject_code} split across multiple days")
                else:
                    periods = sorted([s.period for s in sessions])
                    expected_periods = list(range(periods[0], periods[0] + len(periods)))
                    if periods != expected_periods:
                        issues.append(f"Practical block violation: {subject_code} periods not consecutive")

        # Check teacher conflicts (skip entries without teachers like THESISDAY)
        teacher_schedule = {}
        for entry in entries:
            if entry.teacher:  # Only check entries that have teachers assigned
                key = (entry.teacher.name, entry.day, entry.period)
                if key not in teacher_schedule:
                    teacher_schedule[key] = []
                teacher_schedule[key].append(entry)

        for key, conflicting_entries in teacher_schedule.items():
            if len(conflicting_entries) > 1:
                teacher, day, period = key
                issues.append(f"Teacher conflict: {teacher} has multiple classes on {day} P{period}")

        return issues

    def _count_daily_violations(self, entries: List[TimetableEntry], class_group: str) -> int:
        """Count the number of daily violations for a class group."""
        day_entries = {}
        for entry in entries:
            if entry.class_group == class_group:
                if entry.day not in day_entries:
                    day_entries[entry.day] = []
                day_entries[entry.day].append(entry)

        violations = 0
        for day, day_entry_list in day_entries.items():
            if not day_entry_list:
                continue

            theory_count = len([e for e in day_entry_list if not e.is_practical])
            practical_count = len([e for e in day_entry_list if e.is_practical])
            total_count = len(day_entry_list)

            only_practical = practical_count > 0 and theory_count == 0
            only_one_class = total_count == 1

            if only_practical or only_one_class:
                violations += 1

        return violations

    def _identify_problematic_days(self, entries: List[TimetableEntry], class_group: str) -> List[dict]:
        """Identify days that violate the minimum daily classes constraint."""
        day_entries = {}
        for entry in entries:
            if entry.class_group == class_group:
                if entry.day not in day_entries:
                    day_entries[entry.day] = []
                day_entries[entry.day].append(entry)

        problematic_days = []
        for day, day_entry_list in day_entries.items():
            if not day_entry_list:
                continue

            theory_count = len([e for e in day_entry_list if not e.is_practical])
            practical_count = len([e for e in day_entry_list if e.is_practical])
            total_count = len(day_entry_list)

            only_practical = practical_count > 0 and theory_count == 0
            only_one_class = total_count == 1

            if only_practical or only_one_class:
                violation_type = "only practical" if only_practical else "only one class"
                problematic_days.append({
                    'day': day,
                    'entries': day_entry_list,
                    'theory_count': theory_count,
                    'practical_count': practical_count,
                    'violation_type': violation_type
                })

        return problematic_days

    def _aggressively_add_theory_to_practical_day(self, entries: List[TimetableEntry], target_day: str,
                                                class_group: str, attempt: int) -> List[TimetableEntry]:
        """Aggressively add theory classes to a day with only practical classes."""
        print(f"         🔧 Aggressive attempt {attempt + 1}: Adding theory to {target_day}")

        strategies = [
            self._strategy_move_excess_theory,
            self._strategy_split_subject_sessions,
            self._strategy_force_move_theory,
            self._strategy_create_duplicate_session,
            self._strategy_emergency_theory_placement
        ]

        if attempt < len(strategies):
            return strategies[attempt](entries, target_day, class_group, "theory")
        else:
            return entries

    def _aggressively_add_classes_to_single_class_day(self, entries: List[TimetableEntry], target_day: str,
                                                    class_group: str, attempt: int) -> List[TimetableEntry]:
        """Aggressively add more classes to a day with only one class."""
        print(f"         🔧 Aggressive attempt {attempt + 1}: Adding classes to {target_day}")

        strategies = [
            self._strategy_move_excess_theory,
            self._strategy_split_subject_sessions,
            self._strategy_force_move_any_class,
            self._strategy_create_duplicate_session,
            self._strategy_emergency_class_placement
        ]

        if attempt < len(strategies):
            return strategies[attempt](entries, target_day, class_group, "any")
        else:
            return entries

    def _strategy_move_excess_theory(self, entries: List[TimetableEntry], target_day: str,
                                   class_group: str, class_type: str) -> List[TimetableEntry]:
        """Strategy 1: Move theory classes that have more sessions than required."""
        print(f"           📋 Strategy 1: Moving excess theory sessions")

        # Find subjects with more sessions than credits
        subject_sessions = {}
        for entry in entries:
            if entry.class_group == class_group and not entry.is_practical:
                if entry.subject.code not in subject_sessions:
                    subject_sessions[entry.subject.code] = []
                subject_sessions[entry.subject.code].append(entry)

        # Find excess sessions
        for subject_code, sessions in subject_sessions.items():
            if len(sessions) > sessions[0].subject.credits:
                # This subject has excess sessions - move one
                excess_session = sessions[-1]  # Take the last one

                if excess_session.day != target_day:
                    # Move it to target day
                    available_period = self._find_available_period(entries, target_day, class_group)
                    if available_period:
                        new_entry = self._create_entry(
                            target_day, available_period,
                            excess_session.subject, excess_session.teacher, excess_session.classroom,
                            class_group, False
                        )

                        updated_entries = [e for e in entries if e != excess_session]
                        updated_entries.append(new_entry)

                        print(f"             ✅ Moved excess {subject_code} to {target_day} P{available_period}")
                        return updated_entries

        return entries

    def _strategy_split_subject_sessions(self, entries: List[TimetableEntry], target_day: str,
                                       class_group: str, class_type: str) -> List[TimetableEntry]:
        """Strategy 2: Split a multi-session subject across days."""
        print(f"           📋 Strategy 2: Splitting subject sessions")

        # Find subjects with multiple sessions on the same day
        day_subject_sessions = {}
        for entry in entries:
            if entry.class_group == class_group and not entry.is_practical:
                key = (entry.day, entry.subject.code)
                if key not in day_subject_sessions:
                    day_subject_sessions[key] = []
                day_subject_sessions[key].append(entry)

        # Find a day with multiple sessions of the same subject
        for (day, subject_code), sessions in day_subject_sessions.items():
            if len(sessions) > 1 and day != target_day:
                # Move one session to target day
                session_to_move = sessions[0]
                available_period = self._find_available_period(entries, target_day, class_group)

                if available_period:
                    new_entry = self._create_entry(
                        target_day, available_period,
                        session_to_move.subject, session_to_move.teacher, session_to_move.classroom,
                        class_group, False
                    )

                    updated_entries = [e for e in entries if e != session_to_move]
                    updated_entries.append(new_entry)

                    print(f"             ✅ Split {subject_code} from {day} to {target_day} P{available_period}")
                    return updated_entries

        return entries

    def _strategy_force_move_theory(self, entries: List[TimetableEntry], target_day: str,
                                  class_group: str, class_type: str) -> List[TimetableEntry]:
        """Strategy 3: Force move any theory class, accepting temporary credit violations."""
        print(f"           📋 Strategy 3: Force moving theory (accepting temporary violations)")

        # Find any theory class from a day with multiple classes
        day_entries = {}
        for entry in entries:
            if entry.class_group == class_group:
                if entry.day not in day_entries:
                    day_entries[entry.day] = []
                day_entries[entry.day].append(entry)

        # Find days with multiple classes
        for day, day_classes in day_entries.items():
            if len(day_classes) > 2 and day != target_day:  # Can spare one
                theory_classes = [e for e in day_classes if not e.is_practical]
                if theory_classes:
                    class_to_move = theory_classes[0]
                    available_period = self._find_available_period(entries, target_day, class_group)

                    if available_period:
                        new_entry = self._create_entry(
                            target_day, available_period,
                            class_to_move.subject, class_to_move.teacher, class_to_move.classroom,
                            class_group, False
                        )

                        updated_entries = [e for e in entries if e != class_to_move]
                        updated_entries.append(new_entry)

                        print(f"             ✅ Force moved {class_to_move.subject.code} to {target_day} P{available_period}")
                        return updated_entries

        return entries

    def _strategy_force_move_any_class(self, entries: List[TimetableEntry], target_day: str,
                                     class_group: str, class_type: str) -> List[TimetableEntry]:
        """Strategy 3b: Force move any class (theory or practical part)."""
        print(f"           📋 Strategy 3b: Force moving any class")

        # Find any class from a day with multiple classes
        day_entries = {}
        for entry in entries:
            if entry.class_group == class_group:
                if entry.day not in day_entries:
                    day_entries[entry.day] = []
                day_entries[entry.day].append(entry)

        # Find days with multiple classes
        for day, day_classes in day_entries.items():
            if len(day_classes) > 2 and day != target_day:  # Can spare one
                # Prefer theory, but take practical if needed
                candidates = [e for e in day_classes if not e.is_practical]
                if not candidates:
                    candidates = [e for e in day_classes if e.is_practical]

                if candidates:
                    class_to_move = candidates[0]
                    available_period = self._find_available_period(entries, target_day, class_group)

                    if available_period:
                        new_entry = self._create_entry(
                            target_day, available_period,
                            class_to_move.subject, class_to_move.teacher, class_to_move.classroom,
                            class_group, class_to_move.is_practical
                        )

                        updated_entries = [e for e in entries if e != class_to_move]
                        updated_entries.append(new_entry)

                        print(f"             ✅ Force moved {class_to_move.subject.code} to {target_day} P{available_period}")
                        return updated_entries

        return entries

    def _strategy_create_duplicate_session(self, entries: List[TimetableEntry], target_day: str,
                                         class_group: str, class_type: str) -> List[TimetableEntry]:
        """Strategy 4: Create session respecting no duplicate theory per day constraint."""
        print(f"           📋 Strategy 4: Creating session (constraint-aware)")
        print(f"           🚫 CONSTRAINT ENFORCED: No duplicate theory classes per day")

        # Find subjects that don't already have classes on target_day
        existing_subjects_on_day = set()
        for entry in entries:
            if entry.class_group == class_group and entry.day == target_day and not entry.is_practical:
                existing_subjects_on_day.add(entry.subject.code)

        # Find a theory subject that doesn't already have a class on target_day
        theory_entries = [e for e in entries if e.class_group == class_group and not e.is_practical]
        suitable_entry = None

        for entry in theory_entries:
            if entry.subject.code not in existing_subjects_on_day:
                suitable_entry = entry
                break

        if suitable_entry:
            available_period = self._find_available_period(entries, target_day, class_group)

            if available_period:
                new_entry = self._create_entry(
                    target_day, available_period,
                    suitable_entry.subject, suitable_entry.teacher, suitable_entry.classroom,
                    class_group, False
                )

                updated_entries = list(entries)
                updated_entries.append(new_entry)

                print(f"             ✅ Created constraint-aware session {suitable_entry.subject.code} on {target_day} P{available_period}")
                return updated_entries
        else:
            print(f"             🚫 No suitable subject found that doesn't violate constraint on {target_day}")

        return entries

    def _strategy_emergency_theory_placement(self, entries: List[TimetableEntry], target_day: str,
                                           class_group: str, class_type: str) -> List[TimetableEntry]:
        """Strategy 5: Emergency theory placement - create minimal theory class."""
        print(f"           📋 Strategy 5: Emergency theory placement")

        # Find any subject to create an emergency session
        all_subjects = set(e.subject for e in entries if e.class_group == class_group)
        if all_subjects:
            subject = list(all_subjects)[0]
            available_period = self._find_available_period(entries, target_day, class_group)

            if available_period:
                # Find a teacher for this subject
                teachers = self._get_teachers_for_subject(subject, class_group)
                if teachers:
                    emergency_entry = self._create_entry(
                        target_day, available_period,
                        subject, teachers[0], self._find_available_classroom(target_day, available_period, 1),
                        class_group, False
                    )

                    updated_entries = list(entries)
                    updated_entries.append(emergency_entry)

                    print(f"             ✅ Emergency placement of {subject.code} on {target_day} P{available_period}")
                    return updated_entries

        return entries

    def _strategy_emergency_class_placement(self, entries: List[TimetableEntry], target_day: str,
                                          class_group: str, class_type: str) -> List[TimetableEntry]:
        """Strategy 5b: Emergency class placement - create any class."""
        return self._strategy_emergency_theory_placement(entries, target_day, class_group, class_type)

    def _find_available_period(self, entries: List[TimetableEntry], day: str, class_group: str) -> int:
        """Find an available period on a specific day for a class group."""
        used_periods = set()
        for entry in entries:
            if entry.day == day and entry.class_group == class_group:
                used_periods.add(entry.period)

        # Find first available period
        for period in range(1, 8):  # Periods 1-7
            if period not in used_periods:
                return period

        return None

    def _apply_emergency_fixes(self, entries: List[TimetableEntry], class_group: str) -> List[TimetableEntry]:
        """Apply emergency fixes when all other strategies fail."""
        print(f"         🚨 Applying emergency fixes for {class_group}")

        # Identify remaining violations
        problematic_days = self._identify_problematic_days(entries, class_group)

        for problem in problematic_days:
            day = problem['day']
            violation_type = problem['violation_type']

            print(f"           🚨 Emergency fix for {day}: {violation_type}")

            if violation_type == "only practical":
                # Force create a theory class
                entries = self._strategy_emergency_theory_placement(entries, day, class_group, "theory")
            elif violation_type == "only one class":
                # Force create another class
                entries = self._strategy_emergency_class_placement(entries, day, class_group, "any")

        return entries

    def _assign_thesis_day_if_needed(self, entries: List[TimetableEntry], subjects: List[Subject], class_group: str) -> List[TimetableEntry]:
        """ENHANCEMENT 6: Intelligent Thesis Day assignment for final year batch (detected by 3 theory subjects)."""
        print(f"     🎓 Analyzing {class_group} for Thesis Day eligibility...")

        # INTELLIGENT DETECTION: Final year batch has exactly 3 theory subjects
        theory_subjects = [s for s in subjects if not s.is_practical]
        theory_count = len(theory_subjects)

        is_final_year = theory_count == 3  # Precise detection: exactly 3 theory subjects = final year

        if not is_final_year:
            print(f"       ℹ️  {class_group} has {theory_count} theory subjects - not final year, no Thesis Day")
            return entries

        print(f"       🎓 DETECTED: {class_group} is FINAL YEAR batch ({theory_count} theory subjects) - eligible for Thesis Day")

        # Analyze current schedule for problematic days
        day_entries = {}
        for entry in entries:
            if entry.day not in day_entries:
                day_entries[entry.day] = []
            day_entries[entry.day].append(entry)

        # Find days with insufficient classes
        problematic_days = []
        for day, day_entry_list in day_entries.items():
            if not day_entry_list:
                continue

            latest_period = max(entry.period for entry in day_entry_list)
            min_required_period = 3  # Default minimum (11:00 AM)
            if day.lower() == 'friday':
                min_required_period = 2  # Friday can end earlier

            if latest_period < min_required_period:
                problematic_days.append({
                    'day': day,
                    'latest_period': latest_period,
                    'classes_count': len(day_entry_list),
                    'deficit': min_required_period - latest_period
                })

        if not problematic_days:
            print(f"       ✅ {class_group} has no problematic days - no Thesis Day assignment needed")
            return entries

        # INTELLIGENT DECISION: Assign Thesis Day to the most problematic day
        most_problematic = max(problematic_days, key=lambda x: x['deficit'])
        thesis_day = most_problematic['day']

        print(f"       🎓 INTELLIGENT ASSIGNMENT: {thesis_day} designated as THESIS DAY for {class_group}")
        print(f"          📊 {thesis_day} had only {most_problematic['classes_count']} classes (ending at Period {most_problematic['latest_period']})")
        print(f"          🎯 Thesis Day solves minimum duration while preserving credit compliance")

        # Create Thesis Day entry (special marker)
        thesis_entry = self._create_thesis_day_entry(class_group, thesis_day)

        return entries + [thesis_entry]

    def _assign_thesis_day_if_needed(self, entries: List[TimetableEntry], subjects: List[Subject], class_group: str) -> List[TimetableEntry]:
        """ENHANCEMENT 6: Intelligent Thesis Day assignment for final year batches (detected by low subject count)."""
        print(f"     🎓 Analyzing {class_group} for Thesis Day eligibility...")

        # INTELLIGENT DETECTION: Final year batches have fewer subjects (≤ 5 subjects typically)
        total_subjects = len(subjects)
        is_final_year = total_subjects <= 5  # Smart detection based on subject count

        if not is_final_year:
            print(f"       ℹ️  {class_group} has {total_subjects} subjects - not final year, no Thesis Day needed")
            return entries

        print(f"       🎓 DETECTED: {class_group} is final year batch ({total_subjects} subjects) - eligible for Thesis Day")

        # Analyze current schedule for problematic days
        day_entries = {}
        for entry in entries:
            if entry.day not in day_entries:
                day_entries[entry.day] = []
            day_entries[entry.day].append(entry)

        # Find days with insufficient classes that couldn't be fixed by redistribution
        problematic_days = []
        for day, day_entry_list in day_entries.items():
            if not day_entry_list:
                continue

            latest_period = max(entry.period for entry in day_entry_list)
            min_required_period = 3  # Default minimum (11:00 AM)
            if day.lower() == 'friday':
                min_required_period = 2  # Friday can end earlier

            if latest_period < min_required_period:
                problematic_days.append({
                    'day': day,
                    'latest_period': latest_period,
                    'classes_count': len(day_entry_list),
                    'deficit': min_required_period - latest_period
                })

        if not problematic_days:
            print(f"       ✅ {class_group} has no problematic days - no Thesis Day assignment needed")
            return entries

        # INTELLIGENT DECISION: Assign Thesis Day to the most problematic day
        most_problematic = max(problematic_days, key=lambda x: x['deficit'])
        thesis_day = most_problematic['day']

        print(f"       🎓 INTELLIGENT ASSIGNMENT: {thesis_day} designated as Thesis Day for {class_group}")
        print(f"          📊 {thesis_day} had only {most_problematic['classes_count']} classes (ending at Period {most_problematic['latest_period']})")
        print(f"          🎯 Thesis Day solves minimum duration requirement while preserving credit compliance")

        # Create Thesis Day entry
        thesis_entry = self._create_thesis_day_entry(class_group, thesis_day)

        return entries + [thesis_entry]

    def _assign_thesis_day_if_needed(self, entries: List[TimetableEntry], subjects: List[Subject], class_group: str) -> List[TimetableEntry]:
        """ENHANCEMENT 6: Intelligent Thesis Day assignment for final year batch (detected by 3 theory subjects)."""
        print(f"     🎓 Analyzing {class_group} for Thesis Day eligibility...")

        # INTELLIGENT DETECTION: Final year batch has exactly 3 theory subjects
        theory_subjects = [s for s in subjects if not s.is_practical]
        theory_count = len(theory_subjects)

        print(f"       🔍 Debug: Total subjects={len(subjects)}, Theory subjects={theory_count}")
        print(f"       🔍 Theory subjects: {[s.code for s in theory_subjects]}")

        is_final_year = theory_count == 3  # Precise detection: exactly 3 theory subjects = final year

        if not is_final_year:
            print(f"       ℹ️  {class_group} has {theory_count} theory subjects - not final year, no Thesis Day")
            return entries

        # Analyze current schedule for problematic days
        day_entries = {}
        for entry in entries:
            if entry.day not in day_entries:
                day_entries[entry.day] = []
            day_entries[entry.day].append(entry)

        # Find days with insufficient classes that couldn't be fixed by redistribution
        problematic_days = []
        for day, day_entry_list in day_entries.items():
            if not day_entry_list:
                continue

            latest_period = max(entry.period for entry in day_entry_list)
            min_required_period = 3  # Default minimum (11:00 AM)
            if day.lower() == 'friday':
                min_required_period = 2  # Friday can end earlier

            if latest_period < min_required_period:
                problematic_days.append({
                    'day': day,
                    'latest_period': latest_period,
                    'classes_count': len(day_entry_list),
                    'deficit': min_required_period - latest_period
                })

        if not problematic_days:
            print(f"       ✅ {class_group} has no problematic days - no Thesis Day needed")
            return entries

        # INTELLIGENT DECISION: Assign Thesis Day to the most problematic day
        most_problematic = max(problematic_days, key=lambda x: x['deficit'])
        thesis_day = most_problematic['day']

        print(f"       🎓 INTELLIGENT DECISION: Assigning {thesis_day} as Thesis Day for {class_group}")
        print(f"          📊 {thesis_day} had only {most_problematic['classes_count']} classes (ending at Period {most_problematic['latest_period']})")
        print(f"          🎯 Thesis Day solves minimum duration requirement for final year students")

        # Create Thesis Day entry and clear that day of other classes
        thesis_entry = self._create_thesis_day_entry(class_group, thesis_day)

        # ENHANCEMENT: Remove all other classes from thesis day to make it a complete day off
        filtered_entries = [e for e in entries if e.day != thesis_day]

        print(f"          🧹 Cleared {len(entries) - len(filtered_entries)} classes from {thesis_day}")
        print(f"          🎓 {thesis_day} is now a complete THESIS DAY OFF for {class_group}")

        return filtered_entries + [thesis_entry]

    def _can_move_class(self, movable_class: TimetableEntry, target_day: str, target_period: int, entries: List[TimetableEntry]) -> bool:
        """Check if a class can be moved to a specific day and period."""
        # Check if target slot is already occupied
        for entry in entries:
            if (entry.class_group == movable_class.class_group and
                entry.day == target_day and
                entry.period == target_period):
                return False

        # Check teacher availability (simplified - could be enhanced)
        for entry in entries:
            if (entry.teacher and movable_class.teacher and  # Both must have teachers
                entry.teacher.id == movable_class.teacher.id and
                entry.day == target_day and
                entry.period == target_period and
                entry != movable_class):
                return False

        # Check classroom availability (simplified - could be enhanced)
        for entry in entries:
            if (entry.classroom and movable_class.classroom and  # Both must have classrooms
                entry.classroom.id == movable_class.classroom.id and
                entry.day == target_day and
                entry.period == target_period and
                entry != movable_class):
                return False

        return True

    def _can_reschedule_entry(self, entry: TimetableEntry, target_day: str, target_period: int, existing_entries: List[TimetableEntry]) -> bool:
        """Check if an entry can be rescheduled to a specific day and period."""
        # Check if target slot is already occupied by same class group
        for existing in existing_entries:
            if (existing.class_group == entry.class_group and
                existing.day == target_day and
                existing.period == target_period):
                return False

        # Check teacher availability
        for existing in existing_entries:
            if (existing.teacher and entry.teacher and  # Both must have teachers
                existing.teacher.id == entry.teacher.id and
                existing.day == target_day and
                existing.period == target_period):
                return False

        # Check classroom availability
        for existing in existing_entries:
            if (existing.classroom and entry.classroom and  # Both must have classrooms
                existing.classroom.id == entry.classroom.id and
                existing.day == target_day and
                existing.period == target_period):
                return False

        return True

    def _validate_and_correct_credit_hour_compliance(self, entries: List[TimetableEntry], subjects: List[Subject], class_group: str) -> List[TimetableEntry]:
        """ENHANCEMENT 5: Validate and automatically correct credit hour compliance."""
        print(f"     📊 Validating and correcting credit hour compliance for {class_group}...")

        # Count scheduled classes per subject
        subject_counts = {}
        for entry in entries:
            if entry.class_group == class_group:
                subject_code = entry.subject.code
                if subject_code not in subject_counts:
                    subject_counts[subject_code] = 0

                # For practical subjects, count 3 consecutive periods as 1 session
                if entry.is_practical:
                    # Only count the first period of a practical session
                    if entry.period == 1 or not any(
                        e.subject.code == subject_code and e.day == entry.day and e.period == entry.period - 1
                        for e in entries if e.class_group == class_group
                    ):
                        subject_counts[subject_code] += 1
                else:
                    subject_counts[subject_code] += 1

        # Identify violations and auto-correct
        violations_found = []
        corrected_entries = list(entries)

        for subject in subjects:
            expected_classes = subject.credits
            actual_classes = subject_counts.get(subject.code, 0)

            # Special rule for practical subjects
            if self._is_practical_subject(subject):
                expected_classes = 1  # Practical subjects: 1 credit = 1 session per week
                rule_description = "1 credit = 1 session/week (3 consecutive hours)"
            else:
                rule_description = f"{subject.credits} credits = {subject.credits} classes/week"

            if actual_classes != expected_classes:
                violations_found.append({
                    'subject': subject,
                    'expected': expected_classes,
                    'actual': actual_classes,
                    'rule': rule_description
                })
                print(f"       ❌ {subject.code}: Expected {expected_classes}, got {actual_classes} ({rule_description})")

                # AUTO-CORRECTION: Add missing classes or remove excess classes
                if actual_classes < expected_classes:
                    missing_classes = expected_classes - actual_classes
                    print(f"         🔧 AUTO-CORRECTING: Adding {missing_classes} missing classes for {subject.code}")
                    corrected_entries = self._add_missing_subject_classes(corrected_entries, subject, class_group, missing_classes)
                elif actual_classes > expected_classes:
                    excess_classes = actual_classes - expected_classes
                    print(f"         🔧 AUTO-CORRECTING: Removing {excess_classes} excess classes for {subject.code}")
                    corrected_entries = self._remove_excess_subject_classes(corrected_entries, subject, class_group, excess_classes)

            else:
                print(f"       ✅ {subject.code}: {actual_classes} classes/week (compliant)")

        if violations_found:
            print(f"     🔧 {len(violations_found)} violations found and auto-corrected")
        else:
            print(f"     ✅ Perfect credit hour compliance - all subjects scheduled correctly!")

        return corrected_entries

    def _remove_excess_subject_classes(self, entries: List[TimetableEntry], subject: Subject, class_group: str, excess_count: int) -> List[TimetableEntry]:
        """Remove excess classes for a subject to achieve credit hour compliance."""
        print(f"         🎯 Removing {excess_count} excess classes for {subject.code} in {class_group}")

        updated_entries = list(entries)
        removed_count = 0

        # Find all entries for this subject and class group
        subject_entries = [entry for entry in updated_entries
                          if entry.class_group == class_group and entry.subject.code == subject.code]

        # Sort by priority (remove duplicates first, then least important slots)
        # Priority: later periods first, then Friday, then other days
        def removal_priority(entry):
            day_priority = {'Friday': 0, 'Thursday': 1, 'Wednesday': 2, 'Tuesday': 3, 'Monday': 4}
            return (entry.period, day_priority.get(entry.day, 5))

        subject_entries.sort(key=removal_priority, reverse=True)

        # Remove excess entries
        for entry in subject_entries:
            if removed_count >= excess_count:
                break

            print(f"           🗑️  Removing excess {subject.code} class: {entry.day} P{entry.period}")
            updated_entries.remove(entry)
            removed_count += 1

        print(f"         ✅ Successfully removed {removed_count} excess classes for {subject.code}")
        return updated_entries

    def _add_missing_subject_classes(self, entries: List[TimetableEntry], subject: Subject, class_group: str, missing_count: int) -> List[TimetableEntry]:
        """Add missing classes for a subject to achieve credit hour compliance."""
        print(f"         🎯 Adding {missing_count} missing classes for {subject.code} in {class_group}")

        updated_entries = list(entries)
        added_count = 0

        # Create a temporary class schedule for this class group
        class_schedule = {}
        for entry in updated_entries:
            if entry.class_group == class_group:
                class_schedule[(entry.day, entry.period)] = entry

        # Get teachers for this subject
        teachers = self._get_teachers_for_subject(subject, class_group)
        if not teachers:
            teachers = self.all_teachers[:3]  # Fallback to any teachers

        # Strategy 1: Try normal available slots
        for day in self.days:
            if added_count >= missing_count:
                break
            for period in self.periods:
                if added_count >= missing_count:
                    break
                if (day, period) not in class_schedule:
                    teacher = self._find_available_teacher(teachers, day, period, 1)
                    if teacher:
                        classroom = self._find_available_classroom(day, period, 1, class_group, subject)
                        if classroom:
                            entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                            updated_entries.append(entry)
                            class_schedule[(day, period)] = entry
                            self._mark_global_schedule(teacher, classroom, day, period)
                            added_count += 1
                            print(f"           ✅ Added {subject.code} on {day} P{period}")

        # Strategy 2: If still missing, use emergency slots
        if added_count < missing_count:
            print(f"         🚨 Still missing {missing_count - added_count} classes - using emergency slots")
            added_count = self._add_emergency_subject_classes(updated_entries, subject, class_group, missing_count, added_count, class_schedule, teachers)

        print(f"         📊 Successfully added {added_count}/{missing_count} missing classes")
        return updated_entries

    def _add_emergency_subject_classes(self, entries: List[TimetableEntry], subject: Subject, class_group: str,
                                     missing_count: int, current_added: int, class_schedule: dict, teachers: List) -> int:
        """Add missing classes using emergency measures."""
        added_count = current_added

        # Emergency Strategy 1: Use extended periods (6, 7)
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday']:
            if added_count >= missing_count:
                break
            for period in [6, 7]:
                if added_count >= missing_count:
                    break
                if (day, period) not in class_schedule:
                    teacher = teachers[0] if teachers else self.all_teachers[0]
                    classroom = self.all_classrooms[0]
                    entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                    entries.append(entry)
                    class_schedule[(day, period)] = entry
                    self._mark_global_schedule(teacher, classroom, day, period)
                    added_count += 1
                    print(f"           🚨 Emergency: {subject.code} on {day} P{period}")

        # Emergency Strategy 2: Use Friday late periods
        if added_count < missing_count:
            for period in [5, 6, 7]:
                if added_count >= missing_count:
                    break
                day = 'Friday'
                if (day, period) not in class_schedule:
                    teacher = teachers[0] if teachers else self.all_teachers[0]
                    classroom = self.all_classrooms[0]
                    entry = self._create_entry(day, period, subject, teacher, classroom, class_group, False)
                    entries.append(entry)
                    class_schedule[(day, period)] = entry
                    self._mark_global_schedule(teacher, classroom, day, period)
                    added_count += 1
                    print(f"           🚨 Emergency-Friday: {subject.code} on {day} P{period}")

        return added_count

    def _validate_credit_hour_compliance_for_report(self, entries: List[TimetableEntry], subjects: List[Subject], class_group: str):
        """Validate credit hour compliance for reporting purposes (no auto-correction)."""
        # Count scheduled classes per subject
        subject_counts = {}
        for entry in entries:
            if entry.class_group == class_group:
                subject_code = entry.subject.code
                if subject_code not in subject_counts:
                    subject_counts[subject_code] = 0

                # For practical subjects, count 3 consecutive periods as 1 session
                if entry.is_practical:
                    # Only count the first period of a practical session
                    if entry.period == 1 or not any(
                        e.subject.code == subject_code and e.day == entry.day and e.period == entry.period - 1
                        for e in entries if e.class_group == class_group
                    ):
                        subject_counts[subject_code] += 1
                else:
                    subject_counts[subject_code] += 1

        # Validate against expected credit hours
        compliance_issues = []
        for subject in subjects:
            expected_classes = subject.credits
            actual_classes = subject_counts.get(subject.code, 0)

            # Special rule for practical subjects
            if self._is_practical_subject(subject):
                expected_classes = 1  # Practical subjects: 1 credit = 1 session per week
                rule_description = "1 credit = 1 session/week (3 consecutive hours)"
            else:
                rule_description = f"{subject.credits} credits = {subject.credits} classes/week"

            if actual_classes != expected_classes:
                compliance_issues.append({
                    'subject': subject.code,
                    'expected': expected_classes,
                    'actual': actual_classes,
                    'rule': rule_description
                })

        return compliance_issues

    def _generate_overall_compliance_report(self, entries: List[TimetableEntry]) -> Dict:
        """ENHANCEMENT 5: Generate overall credit hour compliance report."""
        print(f"\n📊 OVERALL CREDIT HOUR COMPLIANCE REPORT:")

        # Group entries by section
        section_entries = {}
        for entry in entries:
            if entry.class_group not in section_entries:
                section_entries[entry.class_group] = []
            section_entries[entry.class_group].append(entry)

        total_sections = len(section_entries)
        compliant_sections = 0
        total_issues = 0

        for section, section_entry_list in section_entries.items():
            subjects = self._get_subjects_for_class_group(section)
            # For reporting, we just validate without correcting
            issues = self._validate_credit_hour_compliance_for_report(section_entry_list, subjects, section)

            if not issues:
                compliant_sections += 1
            else:
                total_issues += len(issues)

        compliance_percentage = (compliant_sections / total_sections * 100) if total_sections > 0 else 0

        print(f"   📈 Compliant sections: {compliant_sections}/{total_sections} ({compliance_percentage:.1f}%)")
        print(f"   📊 Total compliance issues: {total_issues}")

        if compliance_percentage == 100:
            print(f"   🏆 PERFECT CREDIT HOUR COMPLIANCE!")
        elif compliance_percentage >= 80:
            print(f"   ✅ Good compliance rate")
        else:
            print(f"   ⚠️  Compliance needs improvement")

        return {
            'total_sections': total_sections,
            'compliant_sections': compliant_sections,
            'compliance_percentage': compliance_percentage,
            'total_issues': total_issues,
            'perfect_compliance': compliance_percentage == 100
        }

    def _create_thesis_day_entry(self, class_group: str, thesis_day: str) -> TimetableEntry:
        """Create a special Thesis Day entry for final year students."""

        # FIX: Clean up any old thesis entries and create the correct one
        # Remove old problematic "THESIS" entries
        Subject.objects.filter(code="THESIS").delete()

        # Create or get the correct "Thesis Day" subject
        thesis_subject, created = Subject.objects.get_or_create(
            code="THESIS DAY",
            defaults={
                'name': "Thesis Work - Complete Day Off",
                'credits': 0,  # Special: 0 credits for thesis day
                'is_practical': False
            }
        )

        # Create or get special "Thesis Supervisor" teacher (handle uniqueness)
        try:
            thesis_teacher = Teacher.objects.get(name="Thesis Supervisor")
        except Teacher.DoesNotExist:
            # Create with unique email to avoid conflicts
            import uuid
            unique_email = f"thesis.supervisor.{uuid.uuid4().hex[:8]}@university.edu"
            thesis_teacher = Teacher.objects.create(
                name="Thesis Supervisor",
                email=unique_email
            )
        except Teacher.MultipleObjectsReturned:
            # If multiple exist, use the first one
            thesis_teacher = Teacher.objects.filter(name="Thesis Supervisor").first()

        # Use any available classroom (or create thesis room)
        thesis_classroom, created = Classroom.objects.get_or_create(
            name="Thesis Room"
        )

        # Create thesis day entry for the entire day (Period 1-7)
        from datetime import time
        thesis_entry = TimetableEntry(
            day=thesis_day,
            period=1,  # Start from Period 1
            subject=thesis_subject,
            teacher=thesis_teacher,
            classroom=thesis_classroom,
            class_group=class_group,
            start_time=time(8, 0),  # 8:00 AM
            end_time=time(15, 0),   # 3:00 PM (full day thesis work)
            is_practical=False
        )

        print(f"          📝 Created Thesis Day entry: {thesis_day} full day for {class_group}")

        return thesis_entry

    def _calculate_friday_aware_slot_score(self, day: str, period: int, class_group: str,
                                         entries: List[TimetableEntry]) -> float:
        """
        Calculate a Friday-aware priority score for a scheduling slot.
        Lower scores are better (higher priority).

        This method considers:
        1. Early periods are preferred (compact scheduling)
        2. Monday-Thursday slots are preferred over Friday
        3. Friday slots are scored based on practical presence and time limits
        4. Slots that help maintain Friday compliance get bonus points
        """
        base_score = period  # Base score is the period number (early periods preferred)

        if day.lower().startswith('fri'):
            # Friday slots - apply Friday-specific scoring
            friday_score = self._calculate_friday_slot_score(period, class_group, entries)
            return base_score + friday_score
        else:
            # Monday-Thursday slots - slight preference to fill these first
            # This helps ensure Friday doesn't get overloaded
            monday_thursday_bonus = -0.1  # Small bonus for non-Friday days

            # Additional bonus for very early periods on Mon-Thu (helps compact scheduling)
            if period <= 3:
                early_period_bonus = -0.2
            else:
                early_period_bonus = 0

            return base_score + monday_thursday_bonus + early_period_bonus

    def _calculate_friday_slot_score(self, period: int, class_group: str,
                                   entries: List[TimetableEntry]) -> float:
        """Calculate scoring for Friday slots based on practical presence and time limits."""

        # Check if this class group already has practical on Friday
        friday_entries = [e for e in entries if e.day.lower().startswith('fri') and e.class_group == class_group]
        has_practical_on_friday = any(e.is_practical for e in friday_entries)

        if has_practical_on_friday:
            # Has practical on Friday - theory classes should be limited
            if period <= 4:  # Period 4 = 12:00 PM limit
                return 0  # Good slot
            else:
                return 100  # Heavily penalize slots after 12:00 PM
        else:
            # No practical on Friday - theory-only limit applies
            if period <= 3:  # Period 3 = 11:00 AM limit
                return 0  # Good slot
            elif period == 4:
                return 50  # Moderate penalty for 12:00 PM slot
            else:
                return 100  # Heavy penalty for slots after 12:00 PM

    def _prioritize_days_for_practical(self, class_group: str, entries: List[TimetableEntry]) -> List[str]:
        """
        Prioritize days for practical scheduling with Friday-awareness.

        Strategy:
        1. If Friday is relatively empty, it can accommodate practical + theory
        2. If Friday already has many theory classes, avoid adding practical
        3. Prefer Monday-Thursday for practical to keep Friday flexible
        """
        # Count existing entries per day for this class group
        day_counts = {}
        friday_theory_count = 0

        for entry in entries:
            if entry.class_group == class_group:
                if entry.day not in day_counts:
                    day_counts[entry.day] = 0
                day_counts[entry.day] += 1

                # Special tracking for Friday theory classes
                if entry.day.lower().startswith('fri') and not entry.is_practical:
                    friday_theory_count += 1

        # Create prioritized day list
        days_with_scores = []

        for day in self.days:
            current_count = day_counts.get(day, 0)

            if day.lower().startswith('fri'):
                # Friday scoring - consider theory load
                if friday_theory_count >= 3:
                    # Friday already has many theory classes - heavily penalize
                    score = 100 + current_count
                elif friday_theory_count >= 2:
                    # Friday has some theory - moderate penalty
                    score = 50 + current_count
                else:
                    # Friday is relatively free - allow but not prioritize
                    score = 10 + current_count
            else:
                # Monday-Thursday - prefer these for practical
                # Lower scores are better
                score = current_count  # Prefer days with fewer existing classes

                # Small bonus for very early days in the week
                if day.lower().startswith('mon'):
                    score -= 0.3
                elif day.lower().startswith('tue'):
                    score -= 0.2
                elif day.lower().startswith('wed'):
                    score -= 0.1

            days_with_scores.append((day, score))

        # Sort by score (lower is better) and return day names
        days_with_scores.sort(key=lambda x: x[1])
        prioritized_days = [day for day, score in days_with_scores]

        print(f"       📅 Day priority for practical: {prioritized_days}")
        return prioritized_days

    def _enforce_thesis_day_constraint(self, entries: List[TimetableEntry], subjects: List[Subject],
                                     class_group: str) -> List[TimetableEntry]:
        """
        STRICT CONSTRAINT: Enforce Thesis Day constraint for ALL batches with Thesis subjects.

        Approach:
        1. Find Thesis subjects for this class group
        2. REMOVE ALL non-Thesis entries from Wednesday
        3. Schedule Thesis for ALL periods on Wednesday
        4. Ensure NO other subjects are scheduled on Wednesday
        """
        print(f"     📚 STRICT Enforcing Thesis Day constraint for {class_group}...")

        # Check if this class group has Thesis subject
        thesis_subjects = [s for s in subjects if
                          s.code.lower() in ['thesis', 'thesis day', 'thesisday'] or
                          'thesis' in s.name.lower()]

        # If no thesis subjects found in the provided list, check the database
        if not thesis_subjects:
            try:
                # Check if any thesis subjects exist for this batch
                from django.db.models import Q
                from timetable.models import Subject
                
                # Get the base batch (e.g., "21SW" from "21SW-I")
                base_batch = class_group.split('-')[0] if '-' in class_group else class_group
                
                batch_thesis_subjects = Subject.objects.filter(
                    Q(code__icontains='thesis') | Q(name__icontains='thesis'),
                    batch=base_batch
                )
                
                if batch_thesis_subjects.exists():
                    # Use the first thesis subject found for this batch
                    thesis_subjects = list(batch_thesis_subjects)
                    print(f"       📖 Found Thesis subjects from database: {[s.code for s in thesis_subjects]}")
                else:
                    print(f"       ℹ️  No Thesis subject found for {class_group} - skipping")
                    return entries
            except Exception as e:
                print(f"       ⚠️ Error checking for thesis subjects in database: {e}")
                print(f"       ℹ️  No Thesis subject found for {class_group} - skipping")
                return entries
        else:
            print(f"       📖 Found Thesis subjects: {[s.code for s in thesis_subjects]}")

        print(f"       🎓 {class_group} has Thesis subjects - applying STRICT Thesis Day constraint")

        # STRICT THESIS DAY IMPLEMENTATION:
        # 1. REMOVE ALL non-Thesis entries from Wednesday
        # 2. Schedule Thesis for ALL periods on Wednesday
        # 3. Ensure NO other subjects are scheduled on Wednesday

        # First, identify all entries that are not on Wednesday or are Thesis entries
        # STRICT APPROACH: Remove ALL entries on Wednesday and create fresh Thesis entries
        # Keep only non-Wednesday entries
        updated_entries = [e for e in entries if not (e.day.lower().startswith('wed') and e.class_group == class_group)]
        removed_count = len(entries) - len(updated_entries)
        print(f"         🧹 STRICT: Removed ALL {removed_count} entries from Wednesday for {class_group}")
        
        # Now create fresh Thesis entries for ALL periods on Wednesday
        if thesis_subjects:
            # Use the first thesis subject for consistency
            thesis_subject = thesis_subjects[0]
            # Create Thesis entries for ALL periods (1-8)
            for period in range(1, 9):  # Cover all possible periods (1-8)
                print(f"         ➕ STRICT: Adding Thesis entry for Wednesday P{period} (irrespective of credit hours)")
                thesis_entry = self._create_entry(
                    'Wednesday', period,
                    thesis_subject, None, None,  # No teacher/classroom for Thesis
                    class_group, False  # Not practical
                )
                updated_entries.append(thesis_entry)

        print(f"       ✅ STRICT Thesis Day constraint applied - Wednesday EXCLUSIVELY dedicated to Thesis!")
        return updated_entries

    def _relocate_entries_from_wednesday(self, entries: List[TimetableEntry],
                                       entries_to_relocate: List[TimetableEntry],
                                       class_group: str) -> List[TimetableEntry]:
        """Relocate non-Thesis entries from Wednesday to other days to ensure Wednesday dedication."""

        updated_entries = list(entries)
        successfully_relocated = 0

        # CRITICAL FIX: Group practical subjects by subject to maintain 3-consecutive-block structure
        practical_groups = {}
        theory_entries = []

        for entry in entries_to_relocate:
            if entry.is_practical:
                if entry.subject.code not in practical_groups:
                    practical_groups[entry.subject.code] = []
                practical_groups[entry.subject.code].append(entry)
            else:
                theory_entries.append(entry)

        # Process practical subjects as groups (maintain 3-consecutive blocks)
        for subject_code, practical_entries in practical_groups.items():
            print(f"           🧪 Relocating practical {subject_code} (3-block unit) from Wednesday")

            # Sort by period to maintain order
            practical_entries.sort(key=lambda x: x.period)

            # Try to find 3 consecutive slots on other days
            alternative_found = False
            target_days = ['Monday', 'Tuesday', 'Thursday', 'Friday']

            for target_day in target_days:
                # Try periods 1-5 (need 3 consecutive: P1-P3, P2-P4, P3-P5, P4-P6, P5-P7)
                for start_period in range(1, 6):
                    if self._can_relocate_practical_block(practical_entries[0], target_day, start_period, updated_entries, class_group):
                        # Create new entries for the 3 consecutive periods
                        for i, original_entry in enumerate(practical_entries):
                            relocated_entry = self._create_entry(
                                target_day, start_period + i,
                                original_entry.subject, original_entry.teacher, original_entry.classroom,
                                original_entry.class_group, original_entry.is_practical
                            )
                            updated_entries.append(relocated_entry)

                        successfully_relocated += len(practical_entries)
                        alternative_found = True
                        print(f"             ✅ Moved practical {subject_code} to {target_day} P{start_period}-{start_period+2}")
                        break

                if alternative_found:
                    break

            if not alternative_found:
                # If we can't relocate the practical block, keep it on Wednesday
                print(f"             ⚠️  Could not relocate practical {subject_code} - keeping on Wednesday")
                updated_entries.extend(practical_entries)

        # Process theory entries individually
        for entry in theory_entries:
            print(f"           🔄 Relocating theory {entry.subject.code} from Wednesday P{entry.period}")

            # Try to find alternative slot on Monday, Tuesday, Thursday, Friday
            alternative_found = False
            target_days = ['Monday', 'Tuesday', 'Thursday', 'Friday']

            for target_day in target_days:
                # Try periods 1-7 for this day
                for target_period in range(1, 8):
                    if self._can_relocate_to_slot(entry, target_day, target_period, updated_entries, class_group):
                        # Create new entry for the target slot
                        relocated_entry = self._create_entry(
                            target_day, target_period,
                            entry.subject, entry.teacher, entry.classroom,
                            entry.class_group, entry.is_practical
                        )

                        updated_entries.append(relocated_entry)
                        successfully_relocated += 1
                        alternative_found = True

                        print(f"             ✅ Moved theory {entry.subject.code} to {target_day} P{target_period}")
                        break

                if alternative_found:
                    break

            if not alternative_found:
                # If we can't relocate, keep it on Wednesday (fallback)
                print(f"             ⚠️  Could not relocate theory {entry.subject.code} P{entry.period} - keeping on Wednesday")
                updated_entries.append(entry)

        print(f"         📊 Successfully relocated {successfully_relocated}/{len(entries_to_relocate)} entries")
        return updated_entries

    def _can_relocate_practical_block(self, entry: TimetableEntry, target_day: str, start_period: int,
                                    existing_entries: List[TimetableEntry], class_group: str) -> bool:
        """Check if a practical subject (3 consecutive periods) can be relocated to a specific day/start_period."""

        # Check all 3 consecutive periods (start_period, start_period+1, start_period+2)
        for period_offset in range(3):
            target_period = start_period + period_offset

            # Check if the target slot is already occupied by this class group
            for existing in existing_entries:
                if (existing.class_group == class_group and
                    existing.day == target_day and existing.period == target_period):
                    return False

            # Check teacher availability (if entry has a teacher)
            if entry.teacher:
                for existing in existing_entries:
                    if (existing.teacher and entry.teacher and
                        existing.teacher.id == entry.teacher.id and
                        existing.day == target_day and existing.period == target_period):
                        return False

            # Check classroom availability
            if entry.classroom:
                for existing in existing_entries:
                    if (existing.classroom and entry.classroom and
                        existing.classroom.id == entry.classroom.id and
                        existing.day == target_day and existing.period == target_period):
                        return False

            # Check Friday constraints if moving to Friday
            if target_day.lower().startswith('fri'):
                friday_score = self._calculate_friday_slot_score(target_period, class_group, existing_entries)
                if friday_score > 50:  # Don't move to heavily penalized Friday slots
                    return False

        return True

    def _can_relocate_to_slot(self, entry: TimetableEntry, target_day: str, target_period: int,
                            existing_entries: List[TimetableEntry], class_group: str) -> bool:
        """Check if an entry can be relocated to a specific day/period without conflicts."""

        # Check if the target slot is already occupied by this class group
        for existing in existing_entries:
            if (existing.class_group == class_group and
                existing.day == target_day and existing.period == target_period):
                return False

        # Check teacher availability (if entry has a teacher)
        if entry.teacher:
            for existing in existing_entries:
                if (existing.teacher == entry.teacher and
                    existing.day == target_day and existing.period == target_period):
                    return False

        # Check classroom availability
        if entry.classroom:
            for existing in existing_entries:
                if (existing.classroom == entry.classroom and
                    existing.day == target_day and existing.period == target_period):
                    return False

        # Check Friday constraints if moving to Friday
        if target_day.lower().startswith('fri'):
            friday_score = self._calculate_friday_slot_score(target_period, class_group, existing_entries)
            if friday_score > 50:  # Don't move to heavily penalized Friday slots
                return False

        # Check if this would violate minimum daily classes constraint
        # (Don't create days with only one class)
        target_day_entries = [e for e in existing_entries
                            if e.class_group == class_group and e.day == target_day]
        if len(target_day_entries) == 0:  # Would be the only class on this day
            # Only allow if there are no other options
            return True  # Allow for now, constraint will be fixed later

        return True

    def _apply_thesis_day_scheduling_DISABLED(self, entries: List[TimetableEntry], thesis_subjects: List[Subject],
                                   class_group: str, base_batch: str) -> List[TimetableEntry]:
        """Apply the Thesis Day scheduling rules."""

        # Step 1: Remove any existing Thesis entries that are not on Wednesday
        thesis_entries = [e for e in entries if e.subject in thesis_subjects and e.class_group == class_group]
        non_wednesday_thesis = [e for e in thesis_entries if not e.day.lower().startswith('wed')]

        if non_wednesday_thesis:
            print(f"       🔄 Moving {len(non_wednesday_thesis)} Thesis entries to Wednesday")
            entries = [e for e in entries if e not in non_wednesday_thesis]

        # Step 2: Remove any non-Thesis entries from Wednesday for this class group
        wednesday_entries = [e for e in entries if e.day.lower().startswith('wed') and e.class_group == class_group]
        non_thesis_wednesday = [e for e in wednesday_entries if e.subject not in thesis_subjects]

        if non_thesis_wednesday:
            print(f"       🔄 Moving {len(non_thesis_wednesday)} non-Thesis entries from Wednesday")
            entries = self._relocate_non_thesis_from_wednesday(entries, non_thesis_wednesday, class_group)

        # Step 3: Schedule Thesis on Wednesday for all sections of this batch
        entries = self._schedule_thesis_on_wednesday(entries, thesis_subjects, base_batch)

        print(f"       ✅ Thesis Day constraint applied - Wednesday dedicated to Thesis")
        return entries

    def _relocate_non_thesis_from_wednesday(self, entries: List[TimetableEntry],
                                          non_thesis_entries: List[TimetableEntry],
                                          class_group: str) -> List[TimetableEntry]:
        """Relocate non-Thesis entries from Wednesday to other days."""

        updated_entries = [e for e in entries if e not in non_thesis_entries]

        for entry in non_thesis_entries:
            print(f"         🔄 Relocating {entry.subject.code} from Wednesday")

            # Try to find alternative slot on other days
            alternative_found = False
            for day in ['Monday', 'Tuesday', 'Thursday', 'Friday']:
                for period in range(1, 8):
                    if self._can_reschedule_entry(entry, day, period, updated_entries):
                        new_entry = self._create_entry(
                            day, period,
                            entry.subject, entry.teacher, entry.classroom,
                            entry.class_group, entry.is_practical
                        )
                        updated_entries.append(new_entry)
                        alternative_found = True
                        print(f"           ✅ Moved {entry.subject.code} to {day} P{period}")
                        break

                if alternative_found:
                    break

            if not alternative_found:
                print(f"           ⚠️  Could not relocate {entry.subject.code} - keeping on Wednesday")
                updated_entries.append(entry)  # Keep original if no alternative found

        return updated_entries

    def _schedule_thesis_on_wednesday(self, entries: List[TimetableEntry],
                                    thesis_subjects: List[Subject], base_batch: str) -> List[TimetableEntry]:
        """Schedule Thesis subjects on Wednesday for all sections of the batch.
        
        UPDATED REQUIREMENT: Thesis is scheduled for ALL periods on Wednesday (1-8),
        irrespective of credit hours, for ALL sections of a batch with Thesis subjects.
        """

        # Get all sections of this batch that should have Thesis
        all_sections = [f"{base_batch}-I", f"{base_batch}-II", f"{base_batch}-III"]

        for section in all_sections:
            print(f"         📚 Scheduling Thesis for {section}")

            # Check if this section already has Thesis on Wednesday for ALL periods
            wednesday_entries = [e for e in entries if e.day.lower().startswith('wed') and e.class_group == section]
            existing_thesis_periods = [e.period for e in wednesday_entries 
                                     if e.subject in thesis_subjects]
            
            # If we already have Thesis entries for all periods (1-8), skip
            if set(existing_thesis_periods) == set(range(1, 9)):
                print(f"           ✅ {section} already has Thesis on Wednesday for all periods")
                continue

            # Schedule Thesis for this section for ALL periods on Wednesday
            thesis_subject = thesis_subjects[0]  # Use first Thesis subject
            used_periods = set(e.period for e in wednesday_entries)
            
            # First, remove any non-Thesis entries on Wednesday for this section
            entries = [e for e in entries if not (e.day.lower().startswith('wed') and 
                                                e.class_group == section and 
                                                e.subject not in thesis_subjects)]
            
            # Schedule Thesis for ALL periods on Wednesday (1-8), irrespective of credit hours
            for period in range(1, 9):  # Cover all periods 1-8
                if period not in existing_thesis_periods:
                    # Create Thesis entry WITHOUT teacher (as specified)
                    thesis_entry = self._create_thesis_entry(
                        'Wednesday', period, thesis_subject, section
                    )
                    entries.append(thesis_entry)
                    print(f"           ➕ Added Thesis for {section} on Wednesday P{period} (irrespective of credit hours)")
            
            print(f"           ✅ Scheduled Thesis for ALL periods on Wednesday for {section}")

        return entries

    def _create_thesis_entry(self, day: str, period: int, subject: Subject, class_group: str) -> TimetableEntry:
        """Create a Thesis entry without teacher assignment."""
        from timetable.models import TimetableEntry, Classroom
        from datetime import time

        # Get a default classroom (or None)
        classroom = Classroom.objects.first()  # Use any available classroom

        # Calculate start and end times based on period
        start_hour = 8 + (period - 1)  # Period 1 = 9:00 AM, Period 2 = 10:00 AM, etc.
        start_time = time(start_hour, 0)
        end_time = time(start_hour + 1, 0)

        # Create entry without teacher (teacher will be None/null)
        entry = TimetableEntry(
            day=day,
            period=period,
            subject=subject,
            teacher=None,  # No teacher for Thesis entries
            classroom=classroom,
            class_group=class_group,
            start_time=start_time,
            end_time=end_time,
            is_practical=False
        )

        return entry

    def _can_reschedule_entry(self, entry: TimetableEntry, new_day: str, new_period: int,
                            existing_entries: List[TimetableEntry]) -> bool:
        """Check if an entry can be rescheduled to a new day/period without conflicts."""

        # Check if the slot is already occupied by this class group
        for existing in existing_entries:
            if (existing.class_group == entry.class_group and
                existing.day == new_day and existing.period == new_period):
                return False

        # Check teacher availability (if entry has a teacher)
        if entry.teacher:
            for existing in existing_entries:
                if (existing.teacher == entry.teacher and
                    existing.day == new_day and existing.period == new_period):
                    return False

        # Check classroom availability
        if entry.classroom:
            for existing in existing_entries:
                if (existing.classroom == entry.classroom and
                    existing.day == new_day and existing.period == new_period):
                    return False

        # Check Friday constraints if moving to Friday
        if new_day.lower().startswith('fri'):
            friday_score = self._calculate_friday_slot_score(new_period, entry.class_group, existing_entries)
            if friday_score > 50:  # Don't move to heavily penalized Friday slots
                return False

        return True

    def _is_teacher_available(self, teacher: Teacher, day: str, start_period: int, duration: int) -> bool:
        """
        CRITICAL CONSTRAINT: Check if a teacher is available for the given time slot.
        Respects both schedule conflicts and teacher unavailability constraints.
        
        HARD CONSTRAINT: Teacher unavailability must be enforced 100% of the time with zero exceptions.
        """
        # First check for existing schedule conflicts
        for i in range(duration):
            period = start_period + i
            if (teacher.id, day, period) in self.global_teacher_schedule:
                return False
        
        # CRITICAL: Then check teacher unavailability constraints - HARD CONSTRAINT
        if not teacher or not hasattr(teacher, 'unavailable_periods'):
            return True
        
        # Check if teacher has unavailability data
        if not isinstance(teacher.unavailable_periods, dict) or not teacher.unavailable_periods:
            return True
        
        # CRITICAL: Check if this day is in teacher's unavailable periods - ZERO TOLERANCE
        
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
                                # Check if any part of the requested slot overlaps with unavailable time
                                requested_start = start_period
                                requested_end = start_period + duration - 1
                                
                                if requested_start <= end_period_unavailable and requested_end >= start_period_unavailable:
                                    print(f"    🚫 HARD CONSTRAINT VIOLATION PREVENTED: Teacher {teacher.name} unavailable at {day} P{start_period}-P{requested_end} (unavailable: P{start_period_unavailable}-P{end_period_unavailable})")
                                    return False
                        elif isinstance(time_slot, str):
                            # Handle single time: '8:00 AM'
                            unavailable_period = self._convert_time_to_period(time_slot)
                            
                            if unavailable_period is not None:
                                requested_start = start_period
                                requested_end = start_period + duration - 1
                                
                                if requested_start <= unavailable_period <= requested_end:
                                    print(f"    🚫 HARD CONSTRAINT VIOLATION PREVENTED: Teacher {teacher.name} unavailable at {day} P{unavailable_period} (requested: P{requested_start}-P{requested_end})")
                                    return False
        
        # Handle the old format: {'Mon': ['8', '9']} or {'Mon': True}
        elif isinstance(teacher.unavailable_periods, dict):
            if day in teacher.unavailable_periods:
                unavailable_periods = teacher.unavailable_periods[day]
                if isinstance(unavailable_periods, list):
                    for i in range(duration):
                        period = start_period + i
                        if str(period) in unavailable_periods:
                            print(f"    🚫 HARD CONSTRAINT VIOLATION PREVENTED: Teacher {teacher.name} unavailable at {day} P{period}")
                            return False
                elif unavailable_periods:
                    print(f"    🚫 HARD CONSTRAINT VIOLATION PREVENTED: Teacher {teacher.name} unavailable on entire day {day}")
                    return False
        
        return True

    def _convert_time_to_period(self, time_str: str) -> Optional[int]:
        """
        Convert time string (e.g., '8:00 AM') to period number based on schedule config.
        Returns None if conversion fails.
        """
        try:
            from datetime import datetime
            
            # Parse the time string
            if 'AM' in time_str or 'PM' in time_str:
                # Format: '8:00 AM' or '9:00 PM'
                time_obj = datetime.strptime(time_str, '%I:%M %p').time()
            else:
                # Format: '8:00' or '09:00'
                time_obj = datetime.strptime(time_str, '%H:%M').time()
            
            # Get the start time from config
            config_start_time = self.config.start_time
            if isinstance(config_start_time, str):
                config_start_time = datetime.strptime(config_start_time, '%H:%M:%S').time()
            
            # Calculate which period this time falls into
            class_duration = self.config.class_duration
            
            # Calculate minutes since start of day
            start_minutes = config_start_time.hour * 60 + config_start_time.minute
            time_minutes = time_obj.hour * 60 + time_obj.minute
            
            # Calculate period number (1-based)
            period = ((time_minutes - start_minutes) // class_duration) + 1
            
            # Ensure period is within valid range
            if 1 <= period <= len(self.config.periods):
                return period
            else:
                print(f"    ⚠️ Warning: Calculated period {period} for time {time_str} is out of range")
                return None
                
        except Exception as e:
            print(f"    ⚠️ Warning: Could not convert time '{time_str}' to period: {e}")
            return None

    def _randomize_teacher_preferences(self):
        """Randomize teacher preferences for variety in scheduling."""
        # This method adds subtle randomization to teacher selection preferences
        # without affecting the core algorithm logic
        pass
    
    def _randomize_room_preferences(self):
        """Randomize room preferences for variety in allocation."""
        # This method adds subtle randomization to room selection preferences
        # without affecting the core algorithm logic
        pass
    
    def _randomize_time_preferences(self):
        """Randomize time preferences for variety in scheduling."""
        # This method adds subtle randomization to time slot preferences
        # without affecting the core algorithm logic
        pass

    def _load_existing_schedules(self):
        """Load existing schedules from other configs to avoid conflicts."""
        existing_entries = TimetableEntry.objects.exclude(schedule_config=self.config)
        for entry in existing_entries:
            # Mark teacher as busy (only if teacher exists - THESISDAY entries have no teacher)
            if entry.teacher:
                key = (entry.teacher.id, entry.day, entry.period)
                self.global_teacher_schedule[key] = entry

            # Mark classroom as busy (only if classroom exists)
            if entry.classroom:
                key = (entry.classroom.id, entry.day, entry.period)
                self.global_classroom_schedule[key] = entry
        
        if existing_entries.exists():
            print(f"🔍 Loaded {existing_entries.count()} existing entries to avoid conflicts")

    def _find_available_teacher(self, teachers: List[Teacher], day: str, start_period: int, duration: int) -> Optional[Teacher]:
        """Find an available teacher for the given time slot."""
        if not teachers:
            return None
        
        # 🎲 RANDOMIZE TEACHER ORDER for variety in each generation
        available_teachers = []
        for teacher in teachers:
            if self._is_teacher_available(teacher, day, start_period, duration):
                available_teachers.append(teacher)
        
        if not available_teachers:
            return None
        
        # Randomly select from available teachers instead of always picking the first one
        return random.choice(available_teachers)

    def _eliminate_duplicate_theory_by_redistribution(self, entries: List[TimetableEntry], class_group: str) -> List[TimetableEntry]:
        """Move duplicate theory classes to empty, valid slots per section.
        Ensures: no duplicate theory per day, teacher/room availability, and existing constraints.
        """
        try:
            # Build quick lookup schedule for this class_group
            def build_schedule_map(local_entries: List[TimetableEntry]) -> dict:
                schedule = {}
                for e in local_entries:
                    if e.class_group == class_group:
                        schedule[(e.day, e.period)] = e
                return schedule

            updated_entries = list(entries)
            moved_any = True
            safety_counter = 0

            while moved_any and safety_counter < 10:
                safety_counter += 1
                moved_any = False

                # Check violations for only this class_group
                from timetable.duplicate_constraint_enforcer import duplicate_constraint_enforcer
                group_entries = [e for e in updated_entries if e.class_group == class_group and e.subject and not e.is_practical]
                violations = duplicate_constraint_enforcer.check_constraint(group_entries)

                # Filter to this class group only (defensive)
                violations = [v for v in violations if v.get('class_group') == class_group]
                if not violations:
                    break

                class_schedule = build_schedule_map(updated_entries)

                for v in violations:
                    day_with_dupe = v.get('day')
                    subject_code = v.get('subject')
                    duplicate_list = v.get('entries', [])
                    # Keep one on original day; move the rest
                    for entry_to_move in duplicate_list[1:]:
                        subject = entry_to_move.subject

                        # Candidate days: all except the duplicate day and days where this subject already exists
                        used_days = set(e.day for e in group_entries if e.subject and e.subject.code == subject_code)
                        candidate_days = [d for d in self.days if d not in used_days]

                        moved = False
                        for cand_day in candidate_days:
                            if moved:
                                break
                            for cand_period in self.periods:
                                if moved:
                                    break
                                # Fast skip if slot occupied for this section
                                if (cand_day, cand_period) in class_schedule:
                                    continue

                                # Respect central can-schedule check
                                if not self._can_schedule_single(class_schedule, cand_day, cand_period, class_group, subject, updated_entries):
                                    continue

                                # Teacher: prefer original teacher if available, else find another valid one
                                chosen_teacher = None
                                if entry_to_move.teacher and self._is_teacher_available(entry_to_move.teacher, cand_day, cand_period, 1):
                                    chosen_teacher = entry_to_move.teacher
                                else:
                                    teachers = self._get_teachers_for_subject(subject, class_group)
                                    chosen_teacher = self._find_available_teacher(teachers, cand_day, cand_period, 1)
                                if not chosen_teacher:
                                    continue

                                # Classroom: find an available suitable classroom
                                chosen_room = self._find_available_classroom(cand_day, cand_period, 1, class_group, subject)
                                if not chosen_room:
                                    continue

                                # Apply move
                                # Remove old slot from map and add new
                                old_key = (entry_to_move.day, entry_to_move.period)
                                if old_key in class_schedule and class_schedule[old_key] is entry_to_move:
                                    del class_schedule[old_key]

                                entry_to_move.day = cand_day
                                entry_to_move.period = cand_period
                                entry_to_move.teacher = chosen_teacher
                                entry_to_move.classroom = chosen_room

                                class_schedule[(cand_day, cand_period)] = entry_to_move
                                moved = True
                                moved_any = True
                                print(f"       ↪️  Moved {subject.code} to {cand_day} P{cand_period} for {class_group}")
                                break
                # loop back to re-check
            return updated_entries
        except Exception as e:
            print(f"       ⚠️ Duplicate-theory redistribution error for {class_group}: {e}")
            return entries

    def _strict_thesis_wednesday_cleanup(self, entries: List[TimetableEntry], class_group: str) -> List[TimetableEntry]:
        """Ensure Thesis only appears on Wednesday and occupies all Wednesday periods.
        - Remove/move Thesis from non-Wednesday days
        - Fill all Wednesday periods with Thesis placeholders (no teacher/room required)
        - ONLY WORKS FOR BATCHES THAT ACTUALLY HAVE THESIS SUBJECTS
        - Ignores other constraints by design
        """
        try:
            # CRITICAL: Only apply this cleanup to batches that actually have thesis subjects
            base_batch = class_group.split('-')[0] if '-' in class_group else class_group
            
            # BATCH-LEVEL CHECK: Verify this batch actually has thesis subjects
            try:
                from django.db.models import Q
                from timetable.models import Subject
                
                batch_has_thesis = Subject.objects.filter(
                    Q(code__icontains='thesis') | Q(name__icontains='thesis'),
                    batch=base_batch
                ).exists()
                
                if not batch_has_thesis:
                    print(f"       ℹ️ BATCH CHECK: No thesis subjects for batch {base_batch} - skipping cleanup")
                    return entries  # Return entries unchanged if batch doesn't have thesis
                    
                print(f"       ✅ BATCH CHECK: Batch {base_batch} has thesis subjects - applying cleanup")
            except Exception as e:
                print(f"       ⚠️ Error checking batch thesis subjects: {e}")
                return entries  # Return entries unchanged on error

            # Quick helpers
            def is_wed(day: str) -> bool:
                return str(day).lower().startswith('wed')

            # Detect thesis subject for this batch if present
            thesis_subject: Optional[Subject] = None
            for e in entries:
                if e.class_group == class_group and e.subject:
                    if 'thesis' in e.subject.code.lower() or 'thesis' in e.subject.name.lower():
                        thesis_subject = e.subject
                        break
            
            # If none in entries, get from database (we know it exists from check above)
            if thesis_subject is None:
                try:
                    thesis_subject = Subject.objects.filter(
                        Q(code__icontains='thesis') | Q(name__icontains='thesis'),
                        batch=base_batch
                    ).first()
                except Exception:
                    thesis_subject = None

            # If STILL none after DB check, something is wrong - don't create fake thesis
            if thesis_subject is None:
                print(f"       ⚠️ CRITICAL: Could not find thesis subject for batch {base_batch} despite DB check - skipping cleanup")
                return entries

            # Remove any Thesis scheduled on non-Wednesday days
            pruned: List[TimetableEntry] = []
            for e in entries:
                if e.class_group == class_group and e.subject and (
                    'thesis' in (e.subject.code or '').lower() or 'thesis' in (e.subject.name or '').lower()
                ) and not is_wed(e.day):
                    # Skip (drop) non-Wed thesis entries
                    continue
                pruned.append(e)

            # Build quick occupancy map for this class group on Wednesday
            occupied_periods = set()
            for e in pruned:
                if e.class_group == class_group and is_wed(e.day):
                    occupied_periods.add(e.period)

            # Fill all Wednesday periods with Thesis for this class group
            for period in getattr(self, 'periods', []):
                if period in occupied_periods:
                    continue
                thesis_entry = self._create_entry(
                    'Wednesday', period, thesis_subject, None, None,
                    class_group, is_practical=False
                )
                pruned.append(thesis_entry)

            return pruned
        except Exception as e:
            print(f"       ⚠️ Thesis-Wednesday cleanup error for {class_group}: {e}")
            return entries

    def _schedule_extra_classes(self, all_entries: List[TimetableEntry], class_groups: List[str]) -> Dict:
        """
        Schedule extra classes in leftover/blank slots after main classes are scheduled.
        
        Strategy:
        1. Find all blank slots for each class group
        2. Schedule ALL extra practical classes FIRST (3 consecutive blocks each)
        3. Then schedule ALL extra theory classes (1 block each) in remaining slots
        4. NO CONSTRAINTS - just find available slots and schedule them
        
        Returns:
            Dict with scheduling results and statistics
        """
        try:
            print(f"   🔍 Analyzing leftover slots for extra classes...")
            
            extra_classes_scheduled = 0
            extra_practical_scheduled = 0
            extra_theory_scheduled = 0
            failed_schedules = 0
            
            # Track all scheduled slots to identify blank slots
            scheduled_slots = {}
            for entry in all_entries:
                if entry.class_group not in scheduled_slots:
                    scheduled_slots[entry.class_group] = set()
                scheduled_slots[entry.class_group].add((entry.day, entry.period))
            
            # Process each class group
            for class_group in class_groups:
                print(f"     📋 Processing extra classes for {class_group}...")
                
                # Get subjects for this class group
                subjects = self._get_subjects_for_class_group(class_group)
                if not subjects:
                    continue
                
                # Separate practical and theory subjects
                practical_subjects = [s for s in subjects if self._is_practical_subject(s)]
                theory_subjects = [s for s in subjects if not self._is_practical_subject(s)]
                
                print(f"       🧪 Found {len(practical_subjects)} practical subjects for extra classes")
                print(f"       📚 Found {len(theory_subjects)} theory subjects for extra classes")
                
                # STRICT BATCH-LEVEL THESIS CHECK: Only batches with actual thesis subjects can have Wednesday restrictions
                has_thesis_subjects = False
                try:
                    has_thesis_subjects = self._is_final_year_with_thesis(class_group, subjects)
                    if has_thesis_subjects:
                        print(f"       ✅ BATCH-LEVEL: {class_group} has thesis subjects - applying Wednesday restrictions")
                    else:
                        print(f"       ℹ️ BATCH-LEVEL: {class_group} has NO thesis subjects - no Wednesday restrictions needed")
                except Exception as e:
                    print(f"       ⚠️ Error checking thesis subjects for {class_group}: {e}")
                    has_thesis_subjects = False
                
                def not_wednesday(slot):
                    d, _p = slot
                    return not str(d).lower().startswith('wed')
                
                # STRICT ENFORCEMENT: ONLY exclude Thesis subjects from extra classes if batch actually has thesis
                # AND ONLY filter subjects that are actually thesis subjects
                if has_thesis_subjects:
                    # Filter out actual thesis subjects from extra scheduling
                    original_practical = len(practical_subjects)
                    original_theory = len(theory_subjects)
                    
                    practical_subjects = [s for s in practical_subjects if not self._is_thesis_subject(s)]
                    theory_subjects = [s for s in theory_subjects if not self._is_thesis_subject(s)]
                    
                    filtered_practical = len(practical_subjects)
                    filtered_theory = len(theory_subjects)
                    
                    print(f"       🎓 THESIS FILTER: Practical {original_practical}→{filtered_practical}, Theory {original_theory}→{filtered_theory}")
                else:
                    # For batches WITHOUT thesis, no need to filter anything
                    print(f"       📚 NO THESIS FILTER: All {len(practical_subjects)} practical + {len(theory_subjects)} theory subjects available for extra classes")

                # Find blank slots for this class group
                blank_slots = self._find_blank_slots_for_class_group(class_group, scheduled_slots.get(class_group, set()))
                
                # STRICT: Only filter out Wednesday slots if batch actually has thesis subjects
                if has_thesis_subjects:
                    original_blank_count = len(blank_slots)
                    blank_slots = [s for s in blank_slots if not_wednesday(s)]
                    filtered_blank_count = len(blank_slots)
                    print(f"       🚫 WEDNESDAY FILTER: {original_blank_count}→{filtered_blank_count} blank slots (excluding Wednesday for thesis batch)")
                else:
                    print(f"       ✅ NO WEDNESDAY FILTER: Using all {len(blank_slots)} blank slots including Wednesday (no thesis batch)")
                
                if not blank_slots:
                    print(f"       ⚠️ No blank slots found for {class_group}")
                    continue
                
                print(f"       🔍 Found {len(blank_slots)} blank slots for {class_group}")
                
                # STEP 1: Schedule ALL extra practical classes FIRST (3 consecutive blocks each)
                print(f"       🧪 STEP 1: Scheduling {len(practical_subjects)} extra practical classes...")
                for subject in practical_subjects:
                    print(f"         🔍 Looking for 3 consecutive slots for {subject.code}...")
                    
                    # Find 3 consecutive blank blocks
                    consecutive_slots = self._find_consecutive_blocks(blank_slots, 3, scheduled_slots.get(class_group, set()))
                    
                    if consecutive_slots:
                        day, start_period = consecutive_slots[0]
                        print(f"         ✅ Found consecutive slots: {day} P{start_period}-{start_period+2}")
                        
                        # Create 3 consecutive entries for practical
                        subject_entries = []
                        for i in range(3):
                            period = start_period + i
                            
                            # Pick any teacher if exists; otherwise None (ignore constraints)
                            teachers = self._get_teachers_for_subject(subject, class_group)
                            teacher = teachers[0] if teachers else None
                            
                            # For extra classes, do not assign a room (leave blank)
                            room = None
                            
                            # Create entry regardless of teacher/room presence
                            entry = self._create_entry(
                                day, period, subject, teacher, room, class_group, is_practical=True
                            )
                            entry.is_extra_class = True
                            subject_entries.append(entry)
                            
                            # Mark slots as occupied for this class_group
                            if class_group not in scheduled_slots:
                                scheduled_slots[class_group] = set()
                            scheduled_slots[class_group].add((day, period))
                            
                            teacher_name = teacher.name if teacher else 'No Teacher'
                            room_name = room.name if room else 'No Room'
                            print(f"           ✅ Scheduled {subject.code}* on {day} P{period} with {teacher_name} in {room_name}")
                        
                        if len(subject_entries) == 3:
                            all_entries.extend(subject_entries)
                            extra_classes_scheduled += 3
                            extra_practical_scheduled += 3
                            print(f"         ✅ Successfully scheduled all 3 blocks for {subject.code}*")
                        else:
                            print(f"         ❌ Failed to schedule all 3 blocks for {subject.code}*")
                            failed_schedules += 1
                    else:
                        print(f"         ❌ No consecutive slots found for {subject.code}* — CONSTRAINT ENFORCED: Extra practical classes MUST be 3 consecutive blocks")
                        print(f"         📋 STRICT ENFORCEMENT: Not scheduling non-consecutive blocks for practical extra class {subject.code}*")
                        failed_schedules += 1
                
                # STEP 2: Schedule ALL extra theory classes (1 block each) in remaining slots
                print(f"       📚 STEP 2: Scheduling {len(theory_subjects)} extra theory classes...")
                
                # Re-find blank slots after practical scheduling
                updated_blank_slots = self._find_blank_slots_for_class_group(class_group, scheduled_slots.get(class_group, set()))
                
                # STRICT: Only filter Wednesday slots if batch actually has thesis subjects
                if has_thesis_subjects:
                    pre_filter_count = len(updated_blank_slots)
                    updated_blank_slots = [s for s in updated_blank_slots if not_wednesday(s)]
                    post_filter_count = len(updated_blank_slots)
                    print(f"         🚫 WEDNESDAY FILTER (theory): {pre_filter_count}→{post_filter_count} blank slots remaining")
                else:
                    print(f"         ✅ NO WEDNESDAY FILTER (theory): {len(updated_blank_slots)} blank slots remaining (including Wednesday)")
                
                for subject in theory_subjects:
                    print(f"         🔍 Looking for slot for {subject.code}...")
                    
                    # Find any available blank slot
                    available_slot = None
                    for day, period in updated_blank_slots:
                        if (day, period) not in scheduled_slots.get(class_group, set()):
                            available_slot = (day, period)
                            break
                    
                    if available_slot:
                        day, period = available_slot
                        print(f"         ✅ Found slot: {day} P{period}")
                        
                        # Pick any teacher if exists; otherwise None
                        teachers = self._get_teachers_for_subject(subject, class_group)
                        teacher = teachers[0] if teachers else None
                        
                        # For extra classes, do not assign a room (leave blank)
                        room = None
                        
                        # Create entry regardless of teacher/room presence
                        entry = self._create_entry(
                            day, period, subject, teacher, room, class_group, is_practical=False
                        )
                        entry.is_extra_class = True
                        
                        all_entries.append(entry)
                        extra_classes_scheduled += 1
                        extra_theory_scheduled += 1
                        
                        # Mark slot as occupied
                        if class_group not in scheduled_slots:
                            scheduled_slots[class_group] = set()
                        scheduled_slots[class_group].add((day, period))
                        
                        teacher_name = teacher.name if teacher else 'No Teacher'
                        room_name = room.name if room else 'No Room'
                        print(f"           ✅ Scheduled {subject.code}* on {day} P{period} with {teacher_name} in {room_name}")
                    else:
                        print(f"         ❌ No available slots for {subject.code}*")
                        failed_schedules += 1
                
                print(f"       📊 {class_group} Summary: {extra_practical_scheduled} practical + {extra_theory_scheduled} theory = {extra_classes_scheduled} total")
            
            # Save extra classes to database
            if extra_classes_scheduled > 0:
                saved_count = self._save_entries_to_database(all_entries)
                print(f"   💾 Saved {saved_count} total entries (including extra classes) to database")
            
            result = {
                'extra_classes_scheduled': extra_classes_scheduled,
                'extra_practical_scheduled': extra_practical_scheduled,
                'extra_theory_scheduled': extra_theory_scheduled,
                'failed_schedules': failed_schedules,
                'success': True
            }
            
            print(f"   📊 Extra Classes Summary: {extra_practical_scheduled} practical + {extra_theory_scheduled} theory = {extra_classes_scheduled} total")
            
            return result
            
        except Exception as e:
            print(f"   ❌ Error in extra class scheduling: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'extra_classes_scheduled': 0,
                'extra_practical_scheduled': 0,
                'extra_theory_scheduled': 0,
                'failed_schedules': 0,
                'success': False,
                'error': str(e)
            }
    
    def _find_blank_slots_for_class_group(self, class_group: str, scheduled_slots: set) -> List[Tuple[str, int]]:
        """Find all blank slots for a specific class group."""
        blank_slots = []
        
        for day in self.days:
            for period in self.periods:
                if (day, period) not in scheduled_slots:
                    blank_slots.append((day, period))
        
        return blank_slots
    
    def _find_consecutive_blocks(self, blank_slots: List[Tuple[str, int]], count: int, 
                                scheduled_slots: set) -> Optional[List[Tuple[str, int]]]:
        """Find consecutive blank blocks for practical classes."""
        # Group slots by day
        slots_by_day = {}
        for day, period in blank_slots:
            if day not in slots_by_day:
                slots_by_day[day] = []
            slots_by_day[day].append(period)
        
        # Find consecutive periods on each day
        for day, periods in slots_by_day.items():
            periods.sort()
            
            for i in range(len(periods) - count + 1):
                consecutive = periods[i:i+count]
                
                # Check if all periods are consecutive and available
                if consecutive[-1] - consecutive[0] == count - 1:
                    # Verify all slots are still available
                    all_available = True
                    for period in consecutive:
                        if (day, period) in scheduled_slots:
                            all_available = False
                            break
                    
                    if all_available:
                        return [(day, period) for period in consecutive]
        
        return None
