from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
from django.core.exceptions import ValidationError
from .models import Subject, Teacher, Classroom, ScheduleConfig

class ConstraintCategory(Enum):
    TEACHER = "teacher"
    ROOM = "room"
    SUBJECT = "subject"
    TIME = "time"
    WORKLOAD = "workload"
    DEPARTMENT = "department"
    GENERAL = "general"

@dataclass
class ConstraintDefinition:
    """Definition of a scheduling constraint"""
    id: str
    name: str
    category: ConstraintCategory
    description: str
    parameters: Dict[str, Any]
    weight: float
    is_hard: bool  # Hard constraints must be satisfied, soft constraints are preferred
    is_active: bool = True

class ConstraintManager:
    """
    Manages complex scheduling constraints for the academic timetable system.
    Handles validation, optimization, and constraint satisfaction.
    """
    
    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.constraints = self._load_constraints()
        self.validation_errors = []
        
    def _load_constraints(self) -> List[ConstraintDefinition]:
        """Load constraints from configuration"""
        constraints = []
        
        # Default constraints
        default_constraints = [
            ConstraintDefinition(
                id="teacher_availability",
                name="Teacher Availability",
                category=ConstraintCategory.TEACHER,
                description="Teachers cannot be scheduled during their unavailable periods",
                parameters={"type": "availability"},
                weight=10.0,
                is_hard=True
            ),
            ConstraintDefinition(
                id="teacher_workload",
                name="Teacher Workload",
                category=ConstraintCategory.WORKLOAD,
                description="Teachers cannot exceed their maximum daily class limit",
                parameters={"type": "daily_limit"},
                weight=9.0,
                is_hard=True
            ),
            ConstraintDefinition(
                id="room_capacity",
                name="Room Capacity",
                category=ConstraintCategory.ROOM,
                description="Classrooms must have sufficient capacity for class groups",
                parameters={"type": "capacity"},
                weight=8.0,
                is_hard=True
            ),
            ConstraintDefinition(
                id="room_type",
                name="Room Type Compatibility",
                category=ConstraintCategory.ROOM,
                description="Practical subjects must be scheduled in appropriate rooms",
                parameters={"type": "room_type"},
                weight=7.0,
                is_hard=True
            ),
            ConstraintDefinition(
                id="subject_frequency",
                name="Subject Frequency",
                category=ConstraintCategory.SUBJECT,
                description="Subjects must be scheduled the correct number of times per week",
                parameters={"type": "frequency"},
                weight=6.0,
                is_hard=True
            ),
            ConstraintDefinition(
                id="subject_spacing",
                name="Subject Spacing",
                category=ConstraintCategory.SUBJECT,
                description="Subjects should not be scheduled on consecutive days",
                parameters={"type": "spacing", "min_gap_days": 1},
                weight=5.0,
                is_hard=False
            ),
            ConstraintDefinition(
                id="practical_blocks",
                name="Practical Blocks",
                category=ConstraintCategory.TIME,
                description="Practical subjects must be scheduled in 3-hour blocks",
                parameters={"type": "block", "duration_hours": 3},
                weight=8.0,
                is_hard=True
            ),
            ConstraintDefinition(
                id="break_time",
                name="Break Time",
                category=ConstraintCategory.TIME,
                description="Students should have adequate breaks between classes",
                parameters={"type": "break", "min_break_minutes": 15},
                weight=4.0,
                is_hard=False
            ),
            ConstraintDefinition(
                id="consecutive_classes",
                name="Consecutive Classes",
                category=ConstraintCategory.TIME,
                description="Limit consecutive classes to prevent fatigue",
                parameters={"type": "consecutive", "max_consecutive": 4},
                weight=5.0,
                is_hard=False
            ),
            ConstraintDefinition(
                id="department_rules",
                name="Department Rules",
                category=ConstraintCategory.DEPARTMENT,
                description="Department-specific scheduling rules",
                parameters={"type": "department"},
                weight=6.0,
                is_hard=False
            )
        ]
        
        # Add custom constraints from config
        if hasattr(self.config, 'constraints') and self.config.constraints:
            for constraint_data in self.config.constraints:
                if isinstance(constraint_data, dict):
                    constraint = self._create_constraint_from_dict(constraint_data)
                    if constraint:
                        constraints.append(constraint)
        
        # Add default constraints
        constraints.extend(default_constraints)
        
        return constraints
    
    def _create_constraint_from_dict(self, constraint_data: Dict) -> Optional[ConstraintDefinition]:
        """Create constraint from dictionary data"""
        try:
            return ConstraintDefinition(
                id=constraint_data.get('id', f"custom_{len(self.constraints)}"),
                name=constraint_data.get('name', 'Custom Constraint'),
                category=ConstraintCategory(constraint_data.get('category', 'general')),
                description=constraint_data.get('description', ''),
                parameters=constraint_data.get('parameters', {}),
                weight=float(constraint_data.get('weight', 5.0)),
                is_hard=constraint_data.get('is_hard', False),
                is_active=constraint_data.get('is_active', True)
            )
        except (KeyError, ValueError) as e:
            self.validation_errors.append(f"Invalid constraint data: {e}")
            return None
    
    def validate_constraints(self) -> bool:
        """Validate all constraints for consistency"""
        self.validation_errors = []
        
        # Check for conflicting constraints
        self._check_conflicting_constraints()
        
        # Validate constraint parameters
        for constraint in self.constraints:
            if not self._validate_constraint_parameters(constraint):
                return False
        
        return len(self.validation_errors) == 0
    
    def _check_conflicting_constraints(self):
        """Check for conflicting constraint definitions"""
        constraint_ids = [c.id for c in self.constraints]
        if len(constraint_ids) != len(set(constraint_ids)):
            self.validation_errors.append("Duplicate constraint IDs found")
        
        # Check for conflicting time constraints
        time_constraints = [c for c in self.constraints if c.category == ConstraintCategory.TIME]
        for i, constraint1 in enumerate(time_constraints):
            for constraint2 in time_constraints[i+1:]:
                if self._constraints_conflict(constraint1, constraint2):
                    self.validation_errors.append(
                        f"Conflicting constraints: {constraint1.name} and {constraint2.name}"
                    )
    
    def _constraints_conflict(self, constraint1: ConstraintDefinition, 
                            constraint2: ConstraintDefinition) -> bool:
        """Check if two constraints conflict"""
        # Example: practical blocks vs break time
        if (constraint1.parameters.get('type') == 'block' and 
            constraint2.parameters.get('type') == 'break'):
            return True
        return False
    
    def _validate_constraint_parameters(self, constraint: ConstraintDefinition) -> bool:
        """Validate constraint parameters"""
        try:
            if constraint.category == ConstraintCategory.TEACHER:
                return self._validate_teacher_constraint(constraint)
            elif constraint.category == ConstraintCategory.ROOM:
                return self._validate_room_constraint(constraint)
            elif constraint.category == ConstraintCategory.SUBJECT:
                return self._validate_subject_constraint(constraint)
            elif constraint.category == ConstraintCategory.TIME:
                return self._validate_time_constraint(constraint)
            elif constraint.category == ConstraintCategory.WORKLOAD:
                return self._validate_workload_constraint(constraint)
            else:
                return True
        except Exception as e:
            self.validation_errors.append(f"Constraint validation error: {e}")
            return False
    
    def _validate_teacher_constraint(self, constraint: ConstraintDefinition) -> bool:
        """Validate teacher-related constraints"""
        if constraint.parameters.get('type') == 'availability':
            # Check if teacher availability data exists
            teachers = Teacher.objects.all()
            for teacher in teachers:
                if hasattr(teacher, 'unavailable_periods'):
                    if not isinstance(teacher.unavailable_periods, dict):
                        self.validation_errors.append(
                            f"Invalid unavailable_periods format for teacher {teacher.name}"
                        )
                        return False
        return True
    
    def _validate_room_constraint(self, constraint: ConstraintDefinition) -> bool:
        """Validate room-related constraints"""
        if constraint.parameters.get('type') == 'capacity':
            # Capacity validation removed - no longer needed
            return True
        return True
    
    def _validate_subject_constraint(self, constraint: ConstraintDefinition) -> bool:
        """Validate subject-related constraints"""
        if constraint.parameters.get('type') == 'frequency':
            # Check if subjects have credit information
            subjects = Subject.objects.all()
            for subject in subjects:
                if not hasattr(subject, 'credits') or subject.credits <= 0:
                    self.validation_errors.append(
                        f"Invalid credits for subject {subject.name}"
                    )
                    return False
        return True
    
    def _validate_time_constraint(self, constraint: ConstraintDefinition) -> bool:
        """Validate time-related constraints"""
        if constraint.parameters.get('type') == 'block':
            duration = constraint.parameters.get('duration_hours', 3)
            if duration <= 0 or duration > 8:
                self.validation_errors.append("Invalid block duration")
                return False
        elif constraint.parameters.get('type') == 'break':
            min_break = constraint.parameters.get('min_break_minutes', 15)
            if min_break < 0:
                self.validation_errors.append("Invalid break time")
                return False
        return True
    
    def _validate_workload_constraint(self, constraint: ConstraintDefinition) -> bool:
        """Validate workload-related constraints"""
        if constraint.parameters.get('type') == 'daily_limit':
            # Check if teachers have max_classes_per_day
            teachers = Teacher.objects.all()
            for teacher in teachers:
                if not hasattr(teacher, 'max_classes_per_day') or teacher.max_classes_per_day <= 0:
                    self.validation_errors.append(
                        f"Invalid max_classes_per_day for teacher {teacher.name}"
                    )
                    return False
        return True
    
    def get_active_constraints(self) -> List[ConstraintDefinition]:
        """Get all active constraints"""
        return [c for c in self.constraints if c.is_active]
    
    def get_constraints_by_category(self, category: ConstraintCategory) -> List[ConstraintDefinition]:
        """Get constraints by category"""
        return [c for c in self.constraints if c.category == category and c.is_active]
    
    def get_hard_constraints(self) -> List[ConstraintDefinition]:
        """Get all hard constraints"""
        return [c for c in self.constraints if c.is_hard and c.is_active]
    
    def get_soft_constraints(self) -> List[ConstraintDefinition]:
        """Get all soft constraints"""
        return [c for c in self.constraints if not c.is_hard and c.is_active]
    
    def add_constraint(self, constraint: ConstraintDefinition):
        """Add a new constraint"""
        self.constraints.append(constraint)
    
    def remove_constraint(self, constraint_id: str):
        """Remove a constraint by ID"""
        self.constraints = [c for c in self.constraints if c.id != constraint_id]
    
    def update_constraint(self, constraint_id: str, updates: Dict):
        """Update constraint parameters"""
        for constraint in self.constraints:
            if constraint.id == constraint_id:
                for key, value in updates.items():
                    if hasattr(constraint, key):
                        setattr(constraint, key, value)
                break
    
    def get_constraint_summary(self) -> Dict:
        """Get summary of all constraints"""
        return {
            'total_constraints': len(self.constraints),
            'active_constraints': len(self.get_active_constraints()),
            'hard_constraints': len(self.get_hard_constraints()),
            'soft_constraints': len(self.get_soft_constraints()),
            'categories': {
                category.value: len(self.get_constraints_by_category(category))
                for category in ConstraintCategory
            },
            'validation_errors': self.validation_errors
        }
    
    def export_constraints(self) -> Dict:
        """Export constraints for API response"""
        return {
            'constraints': [
                {
                    'id': c.id,
                    'name': c.name,
                    'category': c.category.value,
                    'description': c.description,
                    'parameters': c.parameters,
                    'weight': c.weight,
                    'is_hard': c.is_hard,
                    'is_active': c.is_active
                }
                for c in self.constraints
            ],
            'summary': self.get_constraint_summary()
        } 