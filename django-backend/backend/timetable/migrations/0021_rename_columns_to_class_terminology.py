# Generated manually to rename columns using raw SQL

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('timetable', '0020_alter_batch_name_alter_subject_batch'),
    ]

    operations = [
        migrations.RunSQL(
            # Forward SQL: rename columns
            sql="""
            ALTER TABLE timetable_scheduleconfig RENAME COLUMN lesson_duration TO class_duration;
            ALTER TABLE timetable_config RENAME COLUMN lesson_duration TO class_duration;
            ALTER TABLE timetable_teacher RENAME COLUMN max_lessons_per_day TO max_classes_per_day;
            """,
            # Reverse SQL: rename columns back
            reverse_sql="""
            ALTER TABLE timetable_scheduleconfig RENAME COLUMN class_duration TO lesson_duration;
            ALTER TABLE timetable_config RENAME COLUMN class_duration TO lesson_duration;
            ALTER TABLE timetable_teacher RENAME COLUMN max_classes_per_day TO max_lessons_per_day;
            """
        ),
    ]
