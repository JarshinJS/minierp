from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("module", models.CharField(db_index=True, max_length=64)),
                ("record_type", models.CharField(db_index=True, max_length=64)),
                ("record_id", models.UUIDField(db_index=True)),
                ("action", models.CharField(choices=[("created", "Created"), ("updated", "Updated"), ("deleted", "Deleted"), ("status_changed", "Status Changed"), ("price_changed", "Price Changed"), ("stock_adjusted", "Stock Adjusted"), ("auto_created", "Auto Created")], db_index=True, max_length=32)),
                ("field_changed", models.CharField(blank=True, max_length=128)),
                ("old_value", models.TextField(blank=True)),
                ("new_value", models.TextField(blank=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-timestamp", "-created_at"],
                "indexes": [
                    models.Index(fields=["module", "action", "timestamp"], name="audit_logs_mo_act_ti_4d7a9c_idx"),
                    models.Index(fields=["record_type", "record_id"], name="audit_logs_recor_4c8d77_idx"),
                ],
            },
        ),
    ]