# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a Django backend for an academic timetable generation system that creates class schedules for university departments. It features sophisticated constraint-based scheduling algorithms, user management, and data isolation capabilities.

## Architecture

### Core Components

**Django Apps:**
- `timetable` - Main scheduling functionality with models, algorithms, and APIs
- `users` - Custom user management with Firebase authentication
- `backend` - Django project settings and configuration

**Key Models (timetable/models.py):**
- `Subject` - Academic subjects with credits and practical/theory classification
- `Teacher` - Faculty with availability constraints and subject assignments
- `Classroom` - Rooms with building information and lab classification
- `Batch` - Student groups (21SW, 22SW, etc.) with semester information
- `TeacherSubjectAssignment` - Links teachers to subjects by batch and sections
- `TimetableEntry` - Generated schedule entries with time slots and constraints
- `ScheduleConfig` - Scheduling parameters and time configurations
- `Department`/`UserDepartment` - Multi-tenant data isolation system

**Scheduling Algorithms (timetable/algorithms/):**
- `working_scheduler.py` - Fast, deterministic scheduler (primary)
- `advanced_scheduler.py` - Genetic algorithm with complex constraints
- `constraint_enforced_scheduler.py` - Active constraint enforcement during generation
- `final_scheduler.py` - Universal scheduler with enhanced features

### Data Architecture

**Multi-Tenant Design:**
- Data isolation by department and user ownership
- Shared access controls between users
- Firebase UID integration for authentication

**Constraint System:**
- Teacher availability (unavailable periods with time ranges)
- Room type matching (labs for practicals, regular for theory)
- Subject frequency based on credits
- Cross-semester conflict detection
- Building priority for room allocation

## Common Development Commands

### Project Setup
```powershell
# Install dependencies (requirements.txt not present - use pip install as needed)
pip install django djangorestframework django-cors-headers celery

# Database setup
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Data Management
```powershell
# Populate database with sample data
python scripts/populate_fall_semester_data.py
python scripts/populate_spring_semester_data.py

# Clean all data (DESTRUCTIVE)
python scripts/cleanup_all.py

# Clean only timetable entries (preserves subjects/teachers)
python scripts/cleanup_timetable.py

# Generate timetables for all batches
python generate_all_batches.py
```

### Database Operations
```powershell
# Make migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Database shell
python manage.py dbshell

# Django shell for data exploration
python manage.py shell
```

### Debugging and Testing
```powershell
# Check for issues
python manage.py check

# Run with debug toolbar (already installed)
python manage.py runserver

# Test constraint validation
python check_constraint_status.py

# Fix specific constraint violations
python fix_duplicates.py
python fix_room_allocation.py
python fix_building_violations.py
```

### Celery (Async Task Processing)
```powershell
# Start Celery worker (for async timetable generation)
celery -A backend worker --loglevel=info

# Monitor Celery tasks
celery -A backend flower
```

## Scheduling System

### Algorithm Selection
- **Primary**: `WorkingTimetableScheduler` - Fast, reliable, conflict-free
- **Advanced**: `AdvancedTimetableScheduler` - Genetic algorithm with complex constraints
- **Constraint-Enforced**: `ConstraintEnforcedScheduler` - Active constraint enforcement

### Key Constraints
1. **Teacher Availability** - Hard constraint, zero tolerance for violations
2. **Room Type Matching** - Labs for practicals, regular rooms for theory
3. **Subject Frequency** - Credits determine weekly class count
4. **Practical Blocks** - 3 consecutive periods for practical subjects
5. **Cross-Semester Conflicts** - Prevent teacher double-booking across batches
6. **Building Priority** - Lab Block > Main Block > Academic Building
7. **Time Limits** - 8:00 AM to 3:00 PM working hours

### Timetable Generation Process
```python
# Via API endpoint
POST /api/timetables/generate-fast/
{
    "config_id": 1,
    "algorithm": "working"  # or "advanced", "constraint_enforced"
}

# Or direct algorithm usage
from timetable.algorithms.working_scheduler import WorkingTimetableScheduler
scheduler = WorkingTimetableScheduler(config)
result = scheduler.generate_timetable()
```

## API Architecture

### REST Endpoints
- `/api/subjects/` - Subject management
- `/api/teachers/` - Teacher management with availability
- `/api/classrooms/` - Classroom management
- `/api/batches/` - Student batch management
- `/api/teacher-assignments/` - Teacher-subject assignments
- `/api/schedule-configs/` - Scheduling configurations
- `/api/timetables/` - Timetable entries and generation

### Authentication
- JWT tokens via `rest_framework_simplejwt`
- Firebase UID integration
- Custom User model extending AbstractUser

## Configuration

### Settings (backend/settings.py)
- **Database**: SQLite for development (`db.sqlite3`)
- **Celery**: SQLite broker for async tasks
- **CORS**: Enabled for localhost:3000 (React frontend)
- **Debug Toolbar**: Enabled for development
- **JWT**: 60-minute access tokens, 1-day refresh tokens

### Time Configuration
- Default start time: 8:00 AM
- Class duration: 60 minutes
- Working days: Monday-Friday
- Periods: Configurable via ScheduleConfig

## Development Workflow

### Adding New Constraints
1. Update constraint validation in `enhanced_constraint_validator.py`
2. Modify scheduling algorithms to enforce during generation
3. Add constraint checking in `_evaluate_solution()` methods
4. Update constraint weights in scheduler initialization

### Adding New Algorithms
1. Create new file in `timetable/algorithms/`
2. Implement base interface with `generate_timetable()` method
3. Register in `views.py` scheduling endpoints
4. Add algorithm selection in generation APIs

### Data Model Changes
1. Modify models in `timetable/models.py`
2. Create migrations: `python manage.py makemigrations`
3. Apply migrations: `python manage.py migrate`
4. Update serializers in `serializers.py`
5. Update any affected algorithms

## Testing and Validation

### Constraint Validation
```powershell
# Check all constraints status
python check_constraint_status.py

# Validate specific timetable
python enhanced_constraint_validator.py

# Test teacher availability
python -c "from timetable.models import Teacher; t = Teacher.objects.first(); print(t.unavailable_periods)"
```

### Performance Testing
```python
# Test scheduling algorithms
from timetable.algorithms.working_scheduler import WorkingTimetableScheduler
from timetable.models import ScheduleConfig
config = ScheduleConfig.objects.first()
scheduler = WorkingTimetableScheduler(config)
result = scheduler.generate_timetable()
print(f"Generation time: {result['generation_time']:.2f}s")
```

## Troubleshooting

### Common Issues
1. **Migration conflicts** - Reset migrations with `python manage.py migrate --fake-initial`
2. **Teacher availability violations** - Check `unavailable_periods` JSON format
3. **Room allocation failures** - Ensure lab rooms exist for practical subjects
4. **Cross-semester conflicts** - Clear conflicting timetable entries
5. **Celery tasks stuck** - Restart Celery worker

### Debug Mode
- Enable detailed logging in algorithms by setting logger level to DEBUG
- Use Django Debug Toolbar for SQL query optimization
- Check constraint violation messages in timetable generation responses

## Architecture Principles

1. **Constraint-First Design** - All scheduling respects hard constraints absolutely
2. **Algorithm Modularity** - Multiple scheduling approaches for different needs  
3. **Data Isolation** - Multi-tenant architecture with department-based separation
4. **Performance Optimization** - Fast deterministic scheduling for real-time use
5. **Extensible Constraints** - Easy to add new scheduling requirements
6. **Cross-Semester Awareness** - Prevents conflicts across different academic terms
