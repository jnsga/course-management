# Generated manually for Issue #104
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='max_enrollments_per_user',
            field=models.IntegerField(
                default=0,
                help_text='Maximum number of courses in this subject a user can enroll in. 0 means unlimited.'
            ),
        ),
    ]
