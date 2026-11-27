"""
Account approval workflow.

Existing accounts are kept working: the column is added with default APPROVED
(filling every current row), then the default is switched to PENDING so that only
accounts created from now on start unapproved. Review existing self-registered
accounts afterwards (see docs/deployment.md, "Signup approval").
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

STATUS_CHOICES = [
    ("PENDING", "Pending approval"),
    ("APPROVED", "Approved"),
    ("REJECTED", "Rejected"),
    ("SUSPENDED", "Suspended"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_role"),
    ]

    operations = [
        # 1. Existing rows -> APPROVED.
        migrations.AddField(
            model_name="user",
            name="account_status",
            field=models.CharField(choices=STATUS_CHOICES, db_index=True, default="APPROVED", max_length=20),
        ),
        # 2. New rows -> PENDING.
        migrations.AlterField(
            model_name="user",
            name="account_status",
            field=models.CharField(choices=STATUS_CHOICES, db_index=True, default="PENDING", max_length=20),
        ),
        migrations.AddField(
            model_name="user",
            name="status_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="status_changed_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="status_note",
            field=models.CharField(blank=True, help_text="Reason for rejection/suspension", max_length=500),
        ),
    ]
