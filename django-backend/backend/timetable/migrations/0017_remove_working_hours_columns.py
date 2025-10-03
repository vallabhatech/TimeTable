from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('timetable', '0016_add_batch_sections'),
    ]

    operations = [
        # Drop legacy columns that are not in the Django model but exist in DB
        migrations.RunSQL(
            sql="ALTER TABLE timetable_scheduleconfig DROP COLUMN working_hours_start;",
            reverse_sql="ALTER TABLE timetable_scheduleconfig ADD COLUMN working_hours_start time NULL;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE timetable_scheduleconfig DROP COLUMN working_hours_end;",
            reverse_sql="ALTER TABLE timetable_scheduleconfig ADD COLUMN working_hours_end time NULL;",
        ),
    ]




