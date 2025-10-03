# Generated manually to rename ClassGroup lesson fields to class fields

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('timetable', '0021_rename_columns_to_class_terminology'),
    ]

    operations = [
        migrations.RenameField(
            model_name='classgroup',
            old_name='min_lessons',
            new_name='min_classes',
        ),
        migrations.RenameField(
            model_name='classgroup',
            old_name='max_lessons',
            new_name='max_classes',
        ),
    ]
