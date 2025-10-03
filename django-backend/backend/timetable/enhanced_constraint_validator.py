"""
Simple Enhanced Constraint Validator (minimal implementation for testing)
"""

from typing import List, Dict, Any
from .models import TimetableEntry

class EnhancedConstraintValidator:
    """Simple constraint validator for testing purposes"""
    
    def __init__(self):
        pass
    
    def validate_all_constraints(self, entries: List[TimetableEntry]) -> Dict[str, Any]:
        """Simplified validation that returns no violations"""
        return {
            'total_violations': 0,
            'violations_by_constraint': {},
            'harmony_score': 100.0,
            'overall_compliance': True
        }
