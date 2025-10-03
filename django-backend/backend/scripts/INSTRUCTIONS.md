# Database Management Scripts

This directory contains utility scripts for managing the timetable database. All scripts should be run from the `django-backend/backend` directory.

## 📋 Available Scripts

### 1. `populate_data.py` - Complete Data Population
**Purpose**: Populates the database with all necessary data for timetable generation.

**What it creates**:
- ✅ **Teachers** (26 faculty members with emails)
- ✅ **Subjects** (25 subjects assigned to appropriate batches)
  - 21SW: 6 subjects (Final Year)
  - 22SW: 7 subjects (3rd Year) 
  - 23SW: 6 subjects (2nd Year)
  - 24SW: 7 subjects (1st Year)
- ✅ **Classrooms** (10 rooms and labs)
- ✅ **Teacher Assignments** (Subject-Teacher-Section mappings)

**Usage**:
```bash
cd django-backend/backend
python scripts/populate_data.py
```

**Safe to run multiple times**: Yes, it will skip existing records and only create missing ones.

---

### 2. `cleanup_all.py` - Complete Database Wipe
**Purpose**: Removes ALL data from the database (except default batches).

**What it deletes**:
- ❌ All Teachers
- ❌ All Subjects  
- ❌ All Classrooms
- ❌ All Teacher Assignments
- ❌ All Timetable Entries
- ❌ All Configurations
- ❌ All Class Groups
- ❌ Custom Batches (keeps 21SW, 22SW, 23SW, 24SW)

**Usage**:
```bash
cd django-backend/backend
python scripts/cleanup_all.py
```

**⚠️ WARNING**: This will delete ALL data! You must type "DELETE ALL" to confirm.

---

### 3. `cleanup_timetable.py` - Timetable-Only Cleanup
**Purpose**: Removes ONLY timetable entries, preserves all other data.

**What it deletes**:
- ❌ Timetable Entries ONLY

**What it preserves**:
- ✅ Teachers
- ✅ Subjects
- ✅ Classrooms
- ✅ Batches
- ✅ Teacher Assignments
- ✅ Configurations

**Usage**:
```bash
cd django-backend/backend
python scripts/cleanup_timetable.py
```

**When to use**: After generating a timetable and wanting to generate a fresh one.

---

## 🚀 Common Workflows

### Fresh Start (New Installation)
```bash
cd django-backend/backend

# 1. Clean everything
python scripts/cleanup_all.py

# 2. Populate with fresh data
python scripts/populate_data.py

# 3. Ready for timetable generation!
```

### Reset Timetable Only
```bash
cd django-backend/backend

# Clear only timetable data
python scripts/cleanup_timetable.py

# Generate new timetable via frontend or API
```

### Update Data (Add New Teachers/Subjects)
```bash
cd django-backend/backend

# Just run populate script - it will add missing data
python scripts/populate_data.py
```

---

## 📊 Data Structure

### Teachers (26 total)
- Faculty members with proper email addresses
- Ready for assignment to subjects and sections

### Subjects by Batch
- **21SW** (Final Year): SM, FYP2, SQE, CC + 2 labs
- **22SW** (3rd Year): SPM, TSW, DS, DSA2, MAD + 2 labs  
- **23SW** (2nd Year): ABIS, ISEC, HCI, SCD, SP + 1 lab
- **24SW** (1st Year): DBS, DSA, SRE, OR, SEM + 2 labs

### Classrooms (10 total)
- 5 Regular rooms (capacity 35-45)
- 3 Labs (capacity 25-30)
- 1 Seminar Hall (capacity 100)
- 1 Conference Room (capacity 20)

### Teacher Assignments
- Complete mappings of teachers to subjects and sections
- Based on real faculty expertise and availability
- Covers all subjects across all batches

---

## 🔧 Troubleshooting

### Script Won't Run
```bash
# Make sure you're in the right directory
cd django-backend/backend

# Check if Django is properly set up
python manage.py check

# Run the script
python scripts/populate_data.py
```

### Permission Errors
```bash
# On Unix/Linux/Mac, make scripts executable
chmod +x scripts/*.py

# Then run with python
python scripts/populate_data.py
```

### Database Errors
```bash
# Run migrations first
python manage.py migrate

# Then run the script
python scripts/populate_data.py
```

---

## 📝 Notes

- All scripts include detailed progress output
- Scrips are idemptotent (safe to run multiple times)
- Always run from the `django-backend/backend` directory
- Scripts will create missing data and skip existing records
- Use `cleanup_timetable.py` between timetable generations
- Use `cleanup_all.py` only for complete fresh starts
