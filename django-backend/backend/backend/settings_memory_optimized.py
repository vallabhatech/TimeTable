"""
Memory-Optimized Production Settings for Render
Preserves ALL algorithm functionality while optimizing memory usage
"""

from .settings import *
import os
import gc

# Production environment detection
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = ['*']

# Python runtime optimizations for memory efficiency
# These settings optimize the Python interpreter itself

# Garbage Collection Optimization
gc.set_threshold(700, 10, 10)  # More aggressive GC for memory efficiency

# Django memory optimizations
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25MB (reasonable for timetable data)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Database connection optimization
DATABASES['default'].update({
    'CONN_MAX_AGE': 120,  # Keep connections alive longer to reduce overhead
    'OPTIONS': {
        'timeout': 30,
        'check_same_thread': False,  # For SQLite
    }
})

# Template system optimization
TEMPLATES[0]['OPTIONS']['context_processors'] = [
    'django.template.context_processors.debug',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
]

# Remove debug toolbar from production
if not DEBUG:
    INSTALLED_APPS = [app for app in INSTALLED_APPS if 'debug_toolbar' not in app]
    MIDDLEWARE = [m for m in MIDDLEWARE if 'debug_toolbar' not in m]

# Optimized logging for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'timetable': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Session optimization
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 3600  # 1 hour

# Cache configuration (memory-friendly)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'timetable-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,  # Limit cache entries
            'CULL_FREQUENCY': 4,  # Remove 1/4 of entries when MAX_ENTRIES reached
        }
    }
}

# Enhanced CORS settings for production
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://localhost:3000",
    "https://whimsical-tapioca-45ba52.netlify.app",
    "https://frontend-livid-five-15.vercel.app",
]

# Add production frontend URL from environment
FRONTEND_URL = os.environ.get('FRONTEND_URL')
if FRONTEND_URL:
    CORS_ALLOWED_ORIGINS.append(FRONTEND_URL)

# CORS optimization
CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours

# Security optimizations
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

# Memory-optimized timetable algorithm settings
TIMETABLE_MEMORY_SETTINGS = {
    'ENABLE_MEMORY_LOGGING': True,
    'MEMORY_WARNING_THRESHOLD_MB': 350,
    'MEMORY_CRITICAL_THRESHOLD_MB': 450,
    'FORCE_GC_EVERY_N_ITERATIONS': 5,
    'USE_MEMORY_OPTIMIZED_OPERATIONS': True,
}

# Enhanced constraint resolver settings (preserves all functionality)
ENHANCED_RESOLVER_SETTINGS = {
    'MAX_ITERATIONS': 30,  # Your original setting preserved
    'ENABLE_ALL_STRATEGIES': True,  # All resolution strategies enabled
    'ENABLE_ROOM_OPTIMIZATION': True,  # Room allocation optimization enabled
    'ENABLE_MEMORY_MONITORING': True,  # Memory monitoring enabled
    'AGGRESSIVE_GC': True,  # Garbage collection between iterations
}

# Custom middleware for memory monitoring (optional)
if DEBUG:
    MIDDLEWARE += ['timetable.middleware.MemoryMonitoringMiddleware']

# Production static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Additional static files directories
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
