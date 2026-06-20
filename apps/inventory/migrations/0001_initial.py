from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockLedger",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("movement_type", models.CharField(choices=[("purchase_receipt", "Purchase Receipt"), ("sale_delivery", "Sale Delivery"), ("mo_consumption", "MO Consumption"), ("mo_production", "MO Production"), ("adjustment", "Adjustment")], db_index=True, max_length=32)),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=12)),
                ("direction", models.CharField(choices=[("in", "In"), ("out", "Out")], db_index=True, max_length=3)),
                ("reference_type", models.CharField(blank=True, db_index=True, max_length=64)),
                ("reference_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_ledger_entries", to="products.product")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["product", "created_at"], name="inventory_s_product_2f6f08_idx"),
                    models.Index(fields=["movement_type", "direction"], name="inventory_s_movemen_8f0e8c_idx"),
                ],
            },
        ),
    ]