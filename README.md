
# 🗓️ Automated Timetable Generation System

A web-based academic timetable generation platform built with **Next.js** frontend and **Django REST Framework** backend. The system uses constraint-based algorithms to generate conflict-free academic schedules.

---

## 🚀 Key Features

### 🔄 Timetable Generation

* Multiple scheduling algorithms (Final Universal Scheduler, Enhanced Scheduler, Working Scheduler)
* Constraint-based optimization
* Support for theory and practical subjects
* Batch and section-based scheduling

### 📋 Constraint Management

* 19 academic and infrastructure constraints
* Real-time constraint validation
* Conflict detection and resolution
* Room allocation optimization

### 🏫 Academic Features

* Teacher-subject assignments with section specificity
* Department-based data isolation
* Batch and semester management
* Classroom and lab allocation

### 📤 Export & Accessibility

* PDF export functionality using jsPDF
* Responsive web interface
* User role management (Admin, Teacher, Student)

---

## 🧮 Algorithm Implementation

The system implements a **Deterministic Constraint-Based Algorithm** with controlled randomization:

### Key Characteristics:

* **Deterministic Core**: Same input always produces identical output for consistent scheduling
* **Constraint-Based Foundation**: All 19 academic constraints are strictly enforced
* **Controlled Randomization**: Random elements only when explicitly regenerating timetables
* **Predictable Results**: Ensures consistent timetables for same academic configuration

### Algorithm Components:

#### Final Universal Scheduler

* Deterministic constraint-based scheduling
* Enhanced room allocation with priority-based selection
* Gap filling for compact scheduling
* Section-based scheduling support

#### Enhanced Scheduler

* Advanced constraint validation
* Teacher unavailability handling
* Cross-semester conflict detection

#### Working Scheduler

* Basic conflict resolution
* Teacher and room constraint enforcement

#### Constraint Enforced Scheduler

* Systematic constraint validation
* Iterative conflict resolution

---

## ⚙️ Constraint System

The system enforces **19 constraints**:

#### Academic & Scheduling

1. **Subject Frequency** - Correct number of classes per week based on credits
2. **Practical Blocks** - 3-hour consecutive blocks for practical subjects
3. **Teacher Conflicts** - No teacher double-booking
4. **Room Conflicts** - No room double-booking
5. **Friday Time Limits** - Classes must not exceed 12:00/1:00 PM with practical, 11:00 AM without practical
6. **Minimum Daily Classes** - No day has only practical or only one class
7. **Thesis Day Constraint** - Wednesday is exclusively reserved for Thesis subjects for final year students
8. **Compact Scheduling** - Classes wrap up quickly while respecting Friday constraints
9. **Cross Semester Conflicts** - Prevents scheduling conflicts across batches
10. **Teacher Assignments** - Intelligent teacher assignment matching
11. **Friday Aware Scheduling** - Monday-Thursday scheduling considers Friday limits proactively
12. **Working Hours** - All classes are within 8:00 AM to 3:00 PM
13. **Same Lab Rule** - All 3 blocks of practical subjects must use the same lab
14. **Practicals in Labs** - Practical subjects must be scheduled only in laboratory rooms
15. **Room Consistency** - Enhanced room consistency for theory/practical separation
16. **Same Theory Subject Distribution** - Max 1 class per day, distributed across 5 weekdays
17. **Breaks Between Classes** - Minimal breaks, only when needed
18. **Teacher Breaks** - After 2 consecutive theory classes, teacher must have a break
19. **Teacher Unavailability** - Teachers cannot be scheduled during their unavailable periods

✅ **All 19 constraints have been successfully implemented and tested with real academic data from Software Engineering Department, including real faculty members, actual course structures, and comprehensive constraint validation.**

---

## 🛠️ Tech Stack

### Frontend

* **Next.js 15.1.4**
* **React 19.1.0**
* **Tailwind CSS 3.4.1**
* **Axios 1.7.9** for API communication
* **MUI Icons 7.0.1**, **React Icons 5.4.0**, and **Lucide React 0.487.0** for UI elements
* **jsPDF 3.0.1** and **jspdf-autotable 5.0.2** for PDF exports

### Backend

* **Django 4.2.7** with Django REST Framework 3.14.0
* **JWT** authentication via djangorestframework-simplejwt 5.3.0
* **SQLite** database

### Development Tools

* **ESLint 9** for code quality
* **Turbopack** for faster development builds

---

## 📦 Getting Started

### Prerequisites

* Python 3.8+
* Node.js 16+

### Setup Instructions

1. **Clone the repository**

```bash
git clone <repository-url>
cd timetable-generation
```

2. **Install Backend Dependencies**

```bash
cd django-backend/backend
pip install -r requirements.txt
```

3. **Install Frontend Dependencies**

```bash
cd frontend
npm install
```

4. **Set Environment Variables**

   * Create `.env` files for both backend and frontend
   * Configure Firebase service account credentials
   * Set Django secret key and database settings

5. **Run the Application**

```bash
# Start both backend and frontend concurrently
npm start

# Or start individually:
npm run start:backend
npm run start:frontend
```

---

## 🏗️ Project Structure

```
timetable-generation/
├── django-backend/          # Django backend application
│   ├── backend/            # Django project settings
│   ├── timetable/          # Main timetable app
│   │   ├── algorithms/     # Scheduling algorithms
│   │   ├── models.py       # Data models
│   │   ├── views.py        # API views
│   │   └── urls.py         # URL routing
│   ├── users/              # User management app
│   └── requirements.txt    # Python dependencies
├── frontend/               # Next.js frontend application
│   ├── pages/             # Application pages
│   │   ├── components/    # React components
│   │   └── utils/         # Utility functions
│   ├── styles/            # CSS and styling
│   └── package.json       # Node.js dependencies
└── package.json           # Root package.json with scripts
```

---

## 🔧 Development Notes

* Modular architecture with separation between UI, API, and scheduling logic
* Enhanced constraint validator and resolver for complex scheduling requirements
* Supports multiple user roles and department-based access controls
* Firebase integration for user authentication
* Celery integration for background task processing

---

## 🎯 Use Case

This system automates the creation of academic timetables for educational institutions, handling complex scheduling constraints while ensuring conflict-free schedules. It's designed for **colleges, universities, and institutions** looking to streamline their timetable generation process.


