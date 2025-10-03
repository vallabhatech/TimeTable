import random
import math
import time
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging
from django.db import transaction
from django.utils import timezone
from ..models import TimetableEntry, Subject, Teacher, Classroom, ScheduleConfig
from ..services.cross_semester_conflict_detector import CrossSemesterConflictDetector

logger = logging.getLogger(__name__)

class ConstraintType(Enum):
    TEACHER_AVAILABILITY = "teacher_availability"
    ROOM_CAPACITY = "room_capacity"
    ROOM_TYPE = "room_type"
    SUBJECT_FREQUENCY = "subject_frequency"
    SUBJECT_SPACING = "subject_spacing"
    TEACHER_WORKLOAD = "teacher_workload"
    PRACTICAL_BLOCKS = "practical_blocks"
    BREAK_TIME = "break_time"
    DEPARTMENT_RULES = "department_rules"
    CONSECUTIVE_CLASSES = "consecutive_classes"
    CROSS_SEMESTER_CONFLICTS = "cross_semester_conflicts"

@dataclass
class TimeSlot:
    day: str
    period: int
    start_time: datetime.time
    end_time: datetime.time

@dataclass
class SchedulingConstraint:
    constraint_type: ConstraintType
    weight: float
    parameters: Dict
    description: str

@dataclass
class SchedulingSolution:
    entries: List[TimetableEntry]
    fitness_score: float
    constraint_violations: List[str]
    generation: int

class AdvancedTimetableScheduler:
    """
    Advanced timetable scheduler with constraint satisfaction and genetic algorithm optimization.
    Handles complex academic scheduling requirements with multiple constraint types.
    """
    
    def __init__(self, config: ScheduleConfig):
        if config is None:
            raise ValueError("Config cannot be None")
        self.config = config
        self.days = config.days
        self.periods = config.periods
        self.start_time = config.start_time
        self.class_duration = config.class_duration
        self.class_groups = config.class_groups
        self.constraints = config.constraints
        
        # Data structures (optimized queries with auto-cleanup)
        self.subjects = list(Subject.objects.all())
        self.teachers = self._load_and_cleanup_teachers()
        self.classrooms = list(Classroom.objects.all())
        
        # Genetic algorithm parameters (optimized for speed and reliability)
        self.population_size = 20  # Further reduced for faster testing
        self.generations = 30      # Reduced for faster convergence
        self.mutation_rate = 0.2   # Higher for better exploration
        self.crossover_rate = 0.8
        self.elite_size = 2        # Smaller elite size

        # Add timeout protection
        self.max_attempts_per_subject = 100  # Prevent infinite loops

        # Enhanced logging system (optional)
        try:
            self.logger = self._setup_detailed_logging()
        except:
            self.logger = None

        self.generation_stats = {
            'start_time': None,
            'end_time': None,
            'iterations': 0,
            'conflicts_resolved': 0,
            'duplicates_handled': 0,
            'teacher_assignments': 0,
            'classroom_assignments': 0
        }
        
        # Constraint weights
        self.constraint_weights = {
            ConstraintType.TEACHER_AVAILABILITY: 10.0,
            ConstraintType.ROOM_CAPACITY: 8.0,
            ConstraintType.ROOM_TYPE: 7.0,
            ConstraintType.SUBJECT_FREQUENCY: 6.0,
            ConstraintType.SUBJECT_SPACING: 5.0,
            ConstraintType.TEACHER_WORKLOAD: 9.0,
            ConstraintType.PRACTICAL_BLOCKS: 8.0,
            ConstraintType.BREAK_TIME: 4.0,
            ConstraintType.DEPARTMENT_RULES: 6.0,
            ConstraintType.CONSECUTIVE_CLASSES: 5.0,
            ConstraintType.CROSS_SEMESTER_CONFLICTS: 15.0  # Highest priority
        }
        
        # Initialize time slots
        self.time_slots = self._create_time_slots()

        # Initialize cross-semester conflict detector
        self.conflict_detector = CrossSemesterConflictDetector(config)

        # Tracking structures
        self.teacher_workload = {}
        self.subject_frequency = {}
        self.room_usage = {}
        
    def _create_time_slots(self) -> List[TimeSlot]:
        """Create time slots based on configuration"""
        if self.start_time is None:
            raise ValueError("self.start_time is None in _create_time_slots")
            
        slots = []
        current_time = datetime.combine(datetime.today(), self.start_time)
        
        # Create time slots for all day-period combinations
        for day in self.days:
            day_start_time = datetime.combine(datetime.today(), self.start_time)
            for period in range(len(self.periods)):
                end_time = day_start_time + timedelta(minutes=self.class_duration)
                slots.append(TimeSlot(
                    day=day,
                    period=period + 1,
                    start_time=day_start_time.time(),
                    end_time=end_time.time()
                ))
                day_start_time = end_time
            
        return slots
    
    def generate_timetable(self) -> Dict:
        """
        Generate timetable using genetic algorithm with constraint satisfaction.
        Returns comprehensive result with fitness score and violations.
        """
        start_time = time.time()
        if hasattr(self, 'generation_stats'):
            self.generation_stats['start_time'] = start_time

        if self.logger:
            self.logger.info(f"🚀 Starting timetable generation for {self.config.name}")
            self.logger.info(f"📊 Data loaded: {len(self.subjects)} subjects, {len(self.teachers)} teachers, {len(self.classrooms)} classrooms")
            self.logger.info(f"⚙️  Algorithm parameters: Population={self.population_size}, Generations={self.generations}")

        try:
            # Initialize population
            self.logger.info("🧬 Initializing population...")
            population = self._initialize_population()
            self.logger.info(f"✅ Created {len(population)} initial solutions")
            
            best_solution = None
            best_fitness = float('-inf')
            last_best_fitness = float('-inf')
            no_improvement_count = 0

            # Genetic algorithm evolution
            for generation in range(self.generations):
                # Evaluate population
                for solution in population:
                    fitness, violations = self._evaluate_solution(solution)
                    solution.fitness_score = fitness
                    solution.constraint_violations = violations
                    solution.generation = generation
                    
                    if fitness > best_fitness:
                        best_fitness = fitness
                        best_solution = solution
                
                # Sort by fitness
                population.sort(key=lambda x: x.fitness_score, reverse=True)
                
                # Elitism - keep best solutions
                new_population = population[:self.elite_size]
                
                # Generate new population through crossover and mutation
                while len(new_population) < self.population_size:
                    parent1 = self._tournament_selection(population)
                    parent2 = self._tournament_selection(population)
                    
                    if random.random() < self.crossover_rate:
                        child = self._crossover(parent1, parent2)
                    else:
                        child = parent1
                    
                    if random.random() < self.mutation_rate:
                        child = self._mutate(child)
                    
                    new_population.append(child)
                
                population = new_population
                
                # Log progress
                if generation % 10 == 0:
                    logger.info(f"Generation {generation}: Best fitness = {best_fitness}")
                
                # Early stopping if no improvement for 20 generations
                if best_fitness > last_best_fitness:
                    last_best_fitness = best_fitness
                    no_improvement_count = 0
                else:
                    no_improvement_count += 1
                
                if no_improvement_count >= 20:
                    logger.info(f"Early stopping at generation {generation} - no improvement for 20 generations")
                    break
            
            # Return best solution
            if best_solution:
                return self._format_solution(best_solution, time.time() - start_time)
            else:
                raise Exception("No valid solution found")
                
        except Exception as e:
            logger.error(f"Timetable generation failed: {str(e)}")
            raise
    
    def _initialize_population(self) -> List[SchedulingSolution]:
        """Initialize population with random solutions"""
        population = []
        
        for _ in range(self.population_size):
            solution = self._create_random_solution()
            population.append(solution)
        
        return population
    
    def _create_random_solution(self) -> SchedulingSolution:
        """Create a random timetable solution"""
        entries = []
        
        # Schedule practical subjects first (they need consecutive blocks)
        for class_group in self.class_groups:
            practical_subjects = [s for s in self.subjects if s.is_practical]
            for subject in practical_subjects:
                self._schedule_practical_block_random(entries, subject, class_group)
        
        # Schedule theory subjects
        for class_group in self.class_groups:
            theory_subjects = [s for s in self.subjects if not s.is_practical]
            for subject in theory_subjects:
                self._schedule_theory_subject_random(entries, subject, class_group)
        
        return SchedulingSolution(
            entries=entries,
            fitness_score=0.0,
            constraint_violations=[],
            generation=0
        )
    
    def _schedule_practical_block_random(self, entries: List[TimetableEntry], 
                                       subject: Subject, class_group: str):
        """Schedule a practical block randomly"""
        # Find available 3-hour block
        attempts = 0
        max_attempts = 50
        
        while attempts < max_attempts:
            day = random.choice(self.days)
            start_period = random.randint(1, len(self.periods) - 2)  # Need 3 consecutive periods
            
            if self._can_schedule_practical_block(entries, day, start_period, subject, class_group):
                teacher = self._find_available_teacher(entries, subject, day, start_period, 3)
                classroom = self._find_available_classroom(entries, day, start_period, 3, subject)
                
                if teacher and classroom:
                    # Schedule 3-hour block
                    for i in range(3):
                        period = start_period + i
                        time_slot = self._get_time_slot(day, period)
                        
                        entry = TimetableEntry(
                            day=day,
                            period=period,
                            subject=subject,
                            teacher=teacher,
                            classroom=classroom,
                            class_group=class_group,
                            start_time=time_slot.start_time,
                            end_time=time_slot.end_time,
                            is_practical=True
                        )
                        entries.append(entry)
                    return True
            
            attempts += 1
        
        return False
    
    def _schedule_theory_subject_random(self, entries: List[TimetableEntry], 
                                      subject: Subject, class_group: str):
        """Schedule theory subject randomly"""
        classes_needed = self._get_classes_per_week(subject)
        classes_scheduled = 0
        
        attempts = 0
        max_attempts = 100
        
        while classes_scheduled < classes_needed and attempts < max_attempts:
            day = random.choice(self.days)
            period = random.randint(1, len(self.periods))
            
            if self._can_schedule_theory(entries, day, period, subject, class_group):
                teacher = self._find_available_teacher(entries, subject, day, period, 1)
                classroom = self._find_available_classroom(entries, day, period, 1, subject)
                
                if teacher and classroom:
                    time_slot = self._get_time_slot(day, period)
                    
                    entry = TimetableEntry(
                        day=day,
                        period=period,
                        subject=subject,
                        teacher=teacher,
                        classroom=classroom,
                        class_group=class_group,
                        start_time=time_slot.start_time,
                        end_time=time_slot.end_time,
                        is_practical=False
                    )
                    entries.append(entry)
                    classes_scheduled += 1
            
            attempts += 1
    
    def _can_schedule_practical_block(self, entries: List[TimetableEntry], 
                                    day: str, start_period: int, 
                                    subject: Subject, class_group: str) -> bool:
        """Check if practical block can be scheduled"""
        # Check if all 3 periods are available
        for i in range(3):
            period = start_period + i
            if period > len(self.periods):
                return False
            
            # Check if slot is already occupied
            for entry in entries:
                if (entry.day == day and entry.period == period and 
                    entry.class_group == class_group):
                    return False
        
        return True
    
    def _can_schedule_theory(self, entries: List[TimetableEntry], 
                           day: str, period: int, 
                           subject: Subject, class_group: str) -> bool:
        """Check if theory class can be scheduled"""
        # Check if slot is available
        for entry in entries:
            if (entry.day == day and entry.period == period and 
                entry.class_group == class_group):
                return False
        
        return True
    
    def _find_available_teacher(self, entries: List[TimetableEntry],
                              subject: Subject, day: str,
                              period: int, duration: int) -> Optional[Teacher]:
        """
        Find available teacher with cross-semester conflict detection and load balancing.
        
        BULLETPROOF TEACHER UNAVAILABILITY ENFORCEMENT:
        - Only return a teacher if they are available for ALL periods in the duration
        - Return None if ALL assigned teachers are unavailable for ANY part of the duration
        PRIORITY APPROACH: Teachers with unavailability constraints are prioritized first.
        """
        from collections import defaultdict

        # Get teacher workloads across ALL existing timetables (cross-semester)
        teacher_workloads = defaultdict(int)

        # Count existing workloads from database
        from timetable.models import TimetableEntry as DBTimetableEntry
        for db_entry in DBTimetableEntry.objects.select_related('teacher'):
            if db_entry.teacher:
                teacher_workloads[db_entry.teacher.id] += 1

        # Count workloads from current generation
        for entry in entries:
            if entry.teacher:
                teacher_workloads[entry.teacher.id] += 1

        # PRIORITY APPROACH: Sort teachers by unavailability constraints (constrained first)
        prioritized_teachers = self._prioritize_teachers_by_constraints(self.teachers)

        available_teachers = []

        for teacher in prioritized_teachers:
            # Check if teacher can teach this subject
            teacher_subjects = list(teacher.subjects.all())
            if subject not in teacher_subjects:
                continue

            # BULLETPROOF: Check teacher unavailability constraints - HARD CONSTRAINT
            teacher_available_for_duration = True
            for i in range(duration):
                check_period = period + i
                if not self._is_teacher_available_for_period(teacher, day, check_period):
                    teacher_available_for_duration = False
                    print(f"      🚫 TEACHER UNAVAILABILITY: Teacher {teacher.name} unavailable for {subject.code} on {day} P{check_period}")
                    break
            
            if not teacher_available_for_duration:
                continue

            # Check availability in current generation
            available_in_current = True
            for i in range(duration):
                check_period = period + i
                for entry in entries:
                    if (entry.day == day and entry.period == check_period and
                        entry.teacher == teacher):
                        available_in_current = False
                        break
                if not available_in_current:
                    break

            if not available_in_current:
                continue

            # Check cross-semester availability (database)
            available_cross_semester = True
            for i in range(duration):
                check_period = period + i
                existing_conflict = DBTimetableEntry.objects.filter(
                    teacher=teacher,
                    day=day,
                    period=check_period
                ).exists()

                if existing_conflict:
                    available_cross_semester = False
                    break

            if available_cross_semester:
                # Add teacher with their current workload for load balancing
                available_teachers.append((teacher, teacher_workloads[teacher.id]))
                print(f"      ✅ TEACHER AVAILABILITY: Teacher {teacher.name} available for entire {subject.code} duration on {day} P{period}-{period+duration-1}")

        if not available_teachers:
            print(f"      🚫 BULLETPROOF REJECTION: NO teacher available for entire {subject.code} duration on {day} P{period}-{period+duration-1}")
            return None

        # INTELLIGENT SELECTION: Choose teacher with lowest workload (load balancing)
        available_teachers.sort(key=lambda x: x[1])  # Sort by workload

        # Select from teachers with lowest workload (with some randomness for variety)
        min_workload = available_teachers[0][1]
        best_teachers = [t for t, w in available_teachers if w == min_workload]

        return random.choice(best_teachers) if best_teachers else available_teachers[0][0]
    
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
            else:
                unconstrained_teachers.append(teacher)
        
        # Return constrained teachers first, then unconstrained
        return constrained_teachers + unconstrained_teachers
    
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
    
    def _is_teacher_available_for_period(self, teacher: Teacher, day: str, period: int) -> bool:
        """
        CRITICAL CONSTRAINT: Check if a teacher is available for a specific period.
        
        HARD CONSTRAINT: Teacher unavailability must be enforced 100% of the time with zero exceptions.
        """
        if not teacher or not hasattr(teacher, 'unavailable_periods'):
            return True
        
        if not isinstance(teacher.unavailable_periods, dict) or not teacher.unavailable_periods:
            return True
        
        # CRITICAL: Check teacher unavailability constraints - ZERO TOLERANCE
        
        # Handle the new time-based format: {'mandatory': {'Mon': ['8:00 AM', '9:00 AM']}}
        if 'mandatory' in teacher.unavailable_periods:
            mandatory_unavailable = teacher.unavailable_periods['mandatory']
            if isinstance(mandatory_unavailable, dict) and day in mandatory_unavailable:
                time_slots = mandatory_unavailable[day]
                if isinstance(time_slots, list):
                    if len(time_slots) >= 2:
                        # Two time slots: start and end time
                        start_time_str = time_slots[0]  # e.g., '8:00 AM'
                        end_time_str = time_slots[1]    # e.g., '9:00 AM'
                        
                        # Convert to period numbers
                        start_period_unavailable = self._convert_time_to_period(start_time_str)
                        end_period_unavailable = self._convert_time_to_period(end_time_str)
                        
                        if start_period_unavailable is not None and end_period_unavailable is not None:
                            # Check if the requested period falls within unavailable time
                            if start_period_unavailable <= period <= end_period_unavailable:
                                return False
                    elif len(time_slots) == 1:
                        # Single time slot: teacher unavailable for that entire hour
                        time_str = time_slots[0]  # e.g., '8:00 AM'
                        unavailable_period = self._convert_time_to_period(time_str)
                        
                        if unavailable_period is not None and period == unavailable_period:
                            return False
        
        # Handle the old format: {'Mon': ['8', '9']} or {'Mon': True}
        elif day in teacher.unavailable_periods:
            unavailable_periods = teacher.unavailable_periods[day]
            
            # If unavailable_periods is a list, check specific periods
            if isinstance(unavailable_periods, list):
                if str(period) in unavailable_periods or period in unavailable_periods:
                    return False
            # If unavailable_periods is not a list, assume entire day is unavailable
            elif unavailable_periods:
                return False
        
        return True
    
    def _find_available_classroom(self, entries: List[TimetableEntry], 
                                day: str, period: int, 
                                duration: int, subject: Subject) -> Optional[Classroom]:
        """Find available classroom for the given slot"""
        available_classrooms = []
        
        for classroom in self.classrooms:
            # Check if classroom is available for all periods
            available = True
            for i in range(duration):
                check_period = period + i
                for entry in entries:
                    if (entry.day == day and entry.period == check_period and 
                        entry.classroom == classroom):
                        available = False
                        break
                if not available:
                    break
            
            # Check room type compatibility
            if available and self._is_room_compatible(classroom, subject):
                available_classrooms.append(classroom)
        
        return random.choice(available_classrooms) if available_classrooms else None
    
    def _is_room_compatible(self, classroom: Classroom, subject: Subject) -> bool:
        """Check if room is compatible with subject type"""
        if subject.is_practical:
            # Practical subjects need labs or special rooms
            return "lab" in classroom.name.lower() or "practical" in classroom.name.lower()
        else:
            # Theory subjects can use regular classrooms
            return True
    
    def _get_time_slot(self, day: str, period: int) -> TimeSlot:
        """Get time slot for given day and period"""
        for slot in self.time_slots:
            if slot.day == day and slot.period == period:
                return slot
        return None
    
    def _get_classes_per_week(self, subject: Subject) -> int:
        """Get number of classes per week for a subject"""
        if subject.credits >= 3:
            return 5  # 5 classes per week for 3+ credit subjects
        else:
            return 4  # 4 classes per week for 2 credit subjects
    
    def _evaluate_solution(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Evaluate solution fitness and constraint violations"""
        violations = []
        total_penalty = 0.0
        
        # Check all constraint types
        for constraint_type in ConstraintType:
            penalty, constraint_violations = self._check_constraint_type(
                solution, constraint_type
            )
            total_penalty += penalty * self.constraint_weights[constraint_type]
            violations.extend(constraint_violations)
        
        # Check theory-practical balance constraint (additional constraint)
        penalty, constraint_violations = self._check_theory_practical_balance(solution)
        total_penalty += penalty * 15.0  # High weight for this constraint
        violations.extend(constraint_violations)
        
        # Calculate fitness (higher is better)
        fitness = 1000.0 - total_penalty
        
        return fitness, violations
    
    def _check_constraint_type(self, solution: SchedulingSolution, 
                             constraint_type: ConstraintType) -> Tuple[float, List[str]]:
        """Check specific constraint type"""
        penalty = 0.0
        violations = []
        
        if constraint_type == ConstraintType.TEACHER_AVAILABILITY:
            penalty, violations = self._check_teacher_availability(solution)
        elif constraint_type == ConstraintType.ROOM_CAPACITY:
            penalty, violations = self._check_room_capacity(solution)
        elif constraint_type == ConstraintType.ROOM_TYPE:
            penalty, violations = self._check_room_type_compatibility(solution)
        elif constraint_type == ConstraintType.SUBJECT_FREQUENCY:
            penalty, violations = self._check_subject_frequency(solution)
        elif constraint_type == ConstraintType.SUBJECT_SPACING:
            penalty, violations = self._check_subject_spacing(solution)
        elif constraint_type == ConstraintType.TEACHER_WORKLOAD:
            penalty, violations = self._check_teacher_workload(solution)
        elif constraint_type == ConstraintType.PRACTICAL_BLOCKS:
            penalty, violations = self._check_practical_blocks(solution)
        elif constraint_type == ConstraintType.BREAK_TIME:
            penalty, violations = self._check_break_time(solution)
        elif constraint_type == ConstraintType.CONSECUTIVE_CLASSES:
            penalty, violations = self._check_consecutive_classes(solution)
        elif constraint_type == ConstraintType.CROSS_SEMESTER_CONFLICTS:
            penalty, violations = self._check_cross_semester_conflicts(solution)

        return penalty, violations
    
    def _check_teacher_availability(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """
        CRITICAL HARD CONSTRAINT: Check teacher availability constraints.
        
        This is a ZERO TOLERANCE constraint - any violation is unacceptable.
        Supports both old and new unavailability formats.
        """
        penalty = 0.0
        violations = []
        
        for entry in solution.entries:
            teacher = entry.teacher
            if not teacher:
                continue
            
            # Check if teacher has unavailability data
            if not hasattr(teacher, 'unavailable_periods') or not teacher.unavailable_periods:
                continue
            
            if not isinstance(teacher.unavailable_periods, dict):
                continue
            
            # CRITICAL: Check teacher unavailability constraints - ZERO TOLERANCE
            
            # Handle the new time-based format: {'mandatory': {'Mon': ['8:00 AM', '9:00 AM']}}
            if 'mandatory' in teacher.unavailable_periods:
                mandatory_unavailable = teacher.unavailable_periods['mandatory']
                if isinstance(mandatory_unavailable, dict) and entry.day in mandatory_unavailable:
                    time_slots = mandatory_unavailable[entry.day]
                    if isinstance(time_slots, list):
                        if len(time_slots) >= 2:
                            # Two time slots: start and end time
                            start_time_str = time_slots[0]  # e.g., '8:00 AM'
                            end_time_str = time_slots[1]    # e.g., '9:00 AM'
                            
                            # Convert to period numbers
                            start_period_unavailable = self._convert_time_to_period(start_time_str)
                            end_period_unavailable = self._convert_time_to_period(end_time_str)
                            
                            if start_period_unavailable is not None and end_period_unavailable is not None:
                                # Check if the entry period falls within unavailable time
                                if start_period_unavailable <= entry.period <= end_period_unavailable:
                                    penalty += 100.0  # MASSIVE penalty for hard constraint violation
                                    violations.append(f"CRITICAL VIOLATION: Teacher {teacher.name} scheduled at {entry.day} P{entry.period} but unavailable P{start_period_unavailable}-P{end_period_unavailable}")
                        elif len(time_slots) == 1:
                            # Single time slot: teacher unavailable for that entire hour
                            time_str = time_slots[0]  # e.g., '8:00 AM'
                            unavailable_period = self._convert_time_to_period(time_str)
                            
                            if unavailable_period is not None and entry.period == unavailable_period:
                                penalty += 100.0  # MASSIVE penalty for hard constraint violation
                                violations.append(f"CRITICAL VIOLATION: Teacher {teacher.name} scheduled at {entry.day} P{entry.period} but unavailable at P{unavailable_period}")
            
            # Handle the old format: {'Mon': ['8', '9']} or {'Mon': True}
            elif entry.day in teacher.unavailable_periods:
                unavailable_periods = teacher.unavailable_periods[entry.day]
                
                # If unavailable_periods is a list, check specific periods
                if isinstance(unavailable_periods, list):
                    if str(entry.period) in unavailable_periods or entry.period in unavailable_periods:
                        penalty += 100.0  # MASSIVE penalty for hard constraint violation
                        violations.append(f"CRITICAL VIOLATION: Teacher {teacher.name} scheduled at {entry.day} P{entry.period} but unavailable periods: {unavailable_periods}")
                # If unavailable_periods is not a list, assume entire day is unavailable
                elif unavailable_periods:
                    penalty += 100.0  # MASSIVE penalty for hard constraint violation
                    violations.append(f"CRITICAL VIOLATION: Teacher {teacher.name} scheduled at {entry.day} P{entry.period} but unavailable entire day")
        
        return penalty, violations
    
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
            
            # Calculate which period this time falls into
            class_duration = self.class_duration
            
            # Calculate minutes since start of day
            start_minutes = self.start_time.hour * 60 + self.start_time.minute
            time_minutes = time_obj.hour * 60 + time_obj.minute
            
            # Calculate period number (1-based)
            period = ((time_minutes - start_minutes) // class_duration) + 1
            
            # Ensure period is within valid range
            if 1 <= period <= len(self.periods):
                return period
            else:
                return None
                
        except Exception as e:
            return None
    
    def _check_room_capacity(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check room capacity constraints"""
        penalty = 0.0
        violations = []
        
        # This would need class group size information
        # For now, assume all rooms are adequate
        return penalty, violations
    
    def _check_room_type_compatibility(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check room type compatibility with subjects"""
        penalty = 0.0
        violations = []
        
        for entry in solution.entries:
            if not self._is_room_compatible(entry.classroom, entry.subject):
                penalty += 5.0
                violations.append(f"Incompatible room {entry.classroom.name} for {entry.subject.name}")
        
        return penalty, violations
    
    def _check_subject_frequency(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check subject frequency constraints"""
        penalty = 0.0
        violations = []
        
        for class_group in self.class_groups:
            for subject in self.subjects:
                classes_scheduled = sum(1 for entry in solution.entries 
                                     if entry.class_group == class_group and entry.subject == subject)
                expected_classes = self._get_classes_per_week(subject)
                
                if classes_scheduled != expected_classes:
                    penalty += abs(classes_scheduled - expected_classes) * 2.0
                    violations.append(f"Subject {subject.name} has {classes_scheduled} classes, expected {expected_classes}")
        
        return penalty, violations
    
    def _check_subject_spacing(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check subject spacing constraints"""
        penalty = 0.0
        violations = []
        
        for class_group in self.class_groups:
            for subject in self.subjects:
                subject_entries = [e for e in solution.entries 
                                 if e.class_group == class_group and e.subject == subject]
                
                # Check for consecutive days
                for i, entry1 in enumerate(subject_entries):
                    for entry2 in subject_entries[i+1:]:
                        day1_idx = self.days.index(entry1.day)
                        day2_idx = self.days.index(entry2.day)
                        if abs(day1_idx - day2_idx) == 1:  # Consecutive days
                            penalty += 3.0
                            violations.append(f"Subject {subject.name} on consecutive days")
        
        return penalty, violations
    
    def _check_teacher_workload(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check teacher workload constraints"""
        penalty = 0.0
        violations = []
        
        teacher_daily_workload = {}
        
        for entry in solution.entries:
            teacher = entry.teacher
            if teacher:
                day = entry.day
                if teacher.id not in teacher_daily_workload:
                    teacher_daily_workload[teacher.id] = {}
                if day not in teacher_daily_workload[teacher.id]:
                    teacher_daily_workload[teacher.id][day] = 0
                
                teacher_daily_workload[teacher.id][day] += 1
                
                if teacher_daily_workload[teacher.id][day] > teacher.max_classes_per_day:
                    penalty += 5.0
                    violations.append(f"Teacher {teacher.name} exceeds daily limit")
        
        return penalty, violations
    
    def _check_practical_blocks(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check practical block constraints - 1 credit = 3 consecutive periods"""
        penalty = 0.0
        violations = []
        
        for class_group in self.class_groups:
            practical_entries = [e for e in solution.entries 
                              if e.class_group == class_group and e.is_practical]
            
            # Group by day and check for consecutive periods
            for day in self.days:
                day_entries = [e for e in practical_entries if e.day == day]
                day_entries.sort(key=lambda x: x.period)
                
                # Check for 3 consecutive periods (1 credit = 3 periods)
                for i in range(len(day_entries) - 2):
                    if (day_entries[i+1].period == day_entries[i].period + 1 and
                        day_entries[i+2].period == day_entries[i].period + 2):
                        # Good 3-period block
                        break
                else:
                    if day_entries:  # If there are practical entries but no 3-period block
                        penalty += 10.0  # Higher penalty for practical block violation
                        violations.append(f"Practical subject not in 3 consecutive periods for {class_group} on {day}")
        
        return penalty, violations
    
    def _check_break_time(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check break time constraints"""
        penalty = 0.0
        violations = []
        
        # Check for consecutive classes without breaks
        for class_group in self.class_groups:
            for day in self.days:
                day_entries = [e for e in solution.entries 
                             if e.class_group == class_group and e.day == day]
                day_entries.sort(key=lambda x: x.period)
                
                for i in range(len(day_entries) - 1):
                    if day_entries[i+1].period - day_entries[i].period > 1:
                        penalty += 2.0
                        violations.append(f"Long gap between classes for {class_group}")
        
        return penalty, violations
    
    def _check_consecutive_classes(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check consecutive class constraints"""
        penalty = 0.0
        violations = []
        
        for class_group in self.class_groups:
            for day in self.days:
                day_entries = [e for e in solution.entries 
                             if e.class_group == class_group and e.day == day]
                day_entries.sort(key=lambda x: x.period)
                
                # Check for too many consecutive classes
                consecutive_count = 1
                for i in range(len(day_entries) - 1):
                    if day_entries[i+1].period == day_entries[i].period + 1:
                        consecutive_count += 1
                    else:
                        consecutive_count = 1
                    
                    if consecutive_count > 4:  # Max 4 consecutive classes
                        penalty += 3.0
                        violations.append(f"Too many consecutive classes for {class_group}")
        
        return penalty, violations
    
    def _check_theory_practical_balance(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check that no day has only practical classes (must have theory classes)"""
        penalty = 0.0
        violations = []
        
        for class_group in self.class_groups:
            for day in self.days:
                day_entries = [e for e in solution.entries 
                             if e.class_group == class_group and e.day == day]
                
                if day_entries:  # If there are classes on this day
                    practical_entries = [e for e in day_entries if e.is_practical]
                    theory_entries = [e for e in day_entries if not e.is_practical]
                    
                    # If there are practical classes but no theory classes
                    if practical_entries and not theory_entries:
                        penalty += 15.0  # High penalty for this constraint violation
                        violations.append(f"Day {day} for {class_group} has only practical classes - must have theory classes")
        
        return penalty, violations
    
    def _tournament_selection(self, population: List[SchedulingSolution]) -> SchedulingSolution:
        """Tournament selection for genetic algorithm"""
        tournament_size = 3
        tournament = random.sample(population, tournament_size)
        return max(tournament, key=lambda x: x.fitness_score)
    
    def _crossover(self, parent1: SchedulingSolution, parent2: SchedulingSolution) -> SchedulingSolution:
        """Crossover operation for genetic algorithm"""
        # Simple crossover: take half entries from each parent
        mid_point = len(parent1.entries) // 2
        child_entries = parent1.entries[:mid_point] + parent2.entries[mid_point:]
        
        return SchedulingSolution(
            entries=child_entries,
            fitness_score=0.0,
            constraint_violations=[],
            generation=0
        )
    
    def _mutate(self, solution: SchedulingSolution) -> SchedulingSolution:
        """Mutation operation for genetic algorithm"""
        mutated_entries = solution.entries.copy()
        
        # Randomly swap some entries
        if len(mutated_entries) > 1:
            for _ in range(random.randint(1, 3)):  # 1-3 mutations
                idx1 = random.randint(0, len(mutated_entries) - 1)
                idx2 = random.randint(0, len(mutated_entries) - 1)
                
                if idx1 != idx2:
                    mutated_entries[idx1], mutated_entries[idx2] = mutated_entries[idx2], mutated_entries[idx1]
        
        return SchedulingSolution(
            entries=mutated_entries,
            fitness_score=0.0,
            constraint_violations=[],
            generation=0
        )
    
    def _format_solution(self, solution: SchedulingSolution, generation_time: float) -> Dict:
        """Format solution for API response"""
        return {
            'success': True,
            'generation_time': generation_time,
            'fitness_score': solution.fitness_score,
            'constraint_violations': solution.constraint_violations,
            'generation': solution.generation,
            'days': self.days,
            'timeSlots': [f"{ts.start_time.strftime('%I:%M %p')} - {ts.end_time.strftime('%I:%M %p')}" 
                         for ts in self.time_slots],
            'entries': [{
                'day': entry.day,
                'period': entry.period,
                'subject': f"{entry.subject.name}{' (PR)' if entry.is_practical else ''}",
                'teacher': entry.teacher.name if entry.teacher else '',
                'classroom': entry.classroom.name if entry.classroom else '',
                'class_group': entry.class_group,
                'start_time': entry.start_time.strftime("%H:%M:%S"),
                'end_time': entry.end_time.strftime("%H:%M:%S"),
                'is_practical': entry.is_practical
            } for entry in solution.entries]
        }

    def _check_cross_semester_conflicts(self, solution: SchedulingSolution) -> Tuple[float, List[str]]:
        """Check for conflicts with existing timetables from other semesters"""
        penalty = 0.0
        violations = []

        for entry in solution.entries:
            if not entry.teacher:
                continue

            # Check if this teacher has conflicts in other semesters
            has_conflict, conflict_descriptions = self.conflict_detector.check_teacher_conflict(
                entry.teacher.id, entry.day, entry.period
            )

            if has_conflict:
                penalty += 15.0  # High penalty for cross-semester conflicts
                violations.extend([
                    f"Cross-semester conflict for {entry.teacher.name} on {entry.day} Period {entry.period}: {desc}"
                    for desc in conflict_descriptions
                ])

        return penalty, violations

    def _load_and_cleanup_teachers(self) -> List[Teacher]:
        """Load teachers with automatic duplicate detection and resolution"""
        from collections import defaultdict

        # Load all teachers with prefetched subjects
        all_teachers = list(Teacher.objects.prefetch_related('subjects').all())

        # Group by name to detect duplicates
        name_groups = defaultdict(list)
        for teacher in all_teachers:
            name_groups[teacher.name].append(teacher)

        # Handle duplicates automatically
        cleaned_teachers = []
        duplicates_handled = 0

        for name, teachers in name_groups.items():
            if len(teachers) == 1:
                # No duplicates
                cleaned_teachers.append(teachers[0])
            else:
                # Handle duplicates intelligently
                duplicates_handled += len(teachers) - 1

                # Strategy: Keep the teacher with most subject assignments
                best_teacher = max(teachers, key=lambda t: t.subjects.count())

                # Merge subject assignments from duplicates
                all_subjects = set()
                for teacher in teachers:
                    all_subjects.update(teacher.subjects.all())

                # Assign all subjects to the best teacher
                for subject in all_subjects:
                    best_teacher.subjects.add(subject)

                cleaned_teachers.append(best_teacher)

                print(f"🔧 Auto-resolved duplicate teacher: {name} ({len(teachers)} instances → 1)")

        if hasattr(self, 'generation_stats'):
            self.generation_stats['duplicates_handled'] = duplicates_handled
        if duplicates_handled > 0:
            print(f"✅ Algorithm auto-handled {duplicates_handled} duplicate teachers")

        return cleaned_teachers

    def _setup_detailed_logging(self):
        """Setup comprehensive logging system"""
        import logging

        # Create logger
        logger = logging.getLogger(f'TimetableScheduler_{self.config.name}')
        logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers
        if logger.handlers:
            logger.handlers.clear()

        # Create console handler with detailed formatting
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger