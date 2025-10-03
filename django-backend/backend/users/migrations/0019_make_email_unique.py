# Generated manually to make email field unique

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_remove_user_role_user_firebase_uid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(blank=True, max_length=254, unique=True, verbose_name='email address'),
        ),
    ]
