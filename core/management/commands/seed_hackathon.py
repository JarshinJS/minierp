from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.products.models import Category, Product, ProcurementType
from apps.manufacturing.models import BoM, BOMComponent
from apps.inventory.services import post_ledger_entry  # bypassing high level for init


User = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with Hackathon Demo Scenario data"

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Hackathon Demo Seeding...")
        
        # 1. Ensure Admin User exists for tracking logs
        user, created = User.objects.get_or_create(
            email="admin@erp.com",
            defaults={"is_staff": True, "is_superuser": True, "role": "ADMIN"}
        )
        if created:
            user.set_password("password")
            user.save()
        
        # 2. Categories
        cat_fg, _ = Category.objects.get_or_create(name="Finished Goods")
        cat_rm, _ = Category.objects.get_or_create(name="Raw Materials")

        # 3. Components (Raw Materials)
        legs, _ = Product.objects.get_or_create(
            sku="RM-LEGS",
            defaults={
                "name": "Wooden Legs", "category": cat_rm, "cost_price": Decimal("5.00"), "selling_price": Decimal("0.00"),
                "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True
            }
        )
        top, _ = Product.objects.get_or_create(
            sku="RM-TOP",
            defaults={
                "name": "Wooden Top", "category": cat_rm, "cost_price": Decimal("25.00"), "selling_price": Decimal("0.00"),
                "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True
            }
        )
        screws, _ = Product.objects.get_or_create(
            sku="RM-SCRW",
            defaults={
                "name": "Screws", "category": cat_rm, "cost_price": Decimal("0.10"), "selling_price": Decimal("0.00"),
                "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True
            }
        )
        paint, _ = Product.objects.get_or_create(
            sku="RM-PNT",
            defaults={
                "name": "Paint", "category": cat_rm, "cost_price": Decimal("12.00"), "selling_price": Decimal("0.00"),
                "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True
            }
        )

        # 4. Finished Goods
        table1, _ = Product.objects.get_or_create(
            sku="FG-WTBL",
            defaults={
                "name": "Wooden Table", "category": cat_fg, "cost_price": Decimal("50.00"), "selling_price": Decimal("150.00"),
                "procurement_type": ProcurementType.MANUFACTURING, "procure_on_demand": True
            }
        )
        dining_table, _ = Product.objects.get_or_create(
            sku="FG-DTBL",
            defaults={
                "name": "Dining Table", "category": cat_fg, "cost_price": Decimal("80.00"), "selling_price": Decimal("250.00"),
                "procurement_type": ProcurementType.MANUFACTURING, "procure_on_demand": True,
            }
        )
        chair, _ = Product.objects.get_or_create(
            sku="FG-CHR",
            defaults={
                "name": "Office Chair", "category": cat_fg, "cost_price": Decimal("35.00"), "selling_price": Decimal("100.00"),
                "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True
            }
        )

        # 5. Create BOM for Dining Table
        bom, created = BoM.objects.get_or_create(product=dining_table)
        if created:
            BOMComponent.objects.create(bom=bom, component=legs, quantity=4)
            BOMComponent.objects.create(bom=bom, component=top, quantity=1)
            BOMComponent.objects.create(bom=bom, component=screws, quantity=16)
            BOMComponent.objects.create(bom=bom, component=paint, quantity=1)
        
        # Link default BOM
        dining_table.default_bom = bom
        dining_table.save()

        # 6. Set initial stock to 5 for Dining Table
        if dining_table.on_hand_qty == 0:
            dining_table.on_hand_qty = Decimal("5.00")
            dining_table.save()
            post_ledger_entry(
                product=dining_table,
                entry_type="RECEIPT",
                quantity=Decimal("5.00"),
                reference="SEED-001"
            )
            
        # Give some stock to components so it can manufacture at least some
        # (Actually the demo says "System Automatically Creates Manufacturing Order, Consumes Components". 
        # For that to work, components need some initial stock or it will trigger purchasing)
        for comp in [legs, top, screws, paint]:
            if comp.on_hand_qty == 0:
                qty = Decimal("100.00")
                comp.on_hand_qty = qty
                comp.save()
                post_ledger_entry(
                    product=comp,
                    entry_type="RECEIPT",
                    quantity=qty,
                    reference="SEED-001"
                )

        self.stdout.write(self.style.SUCCESS("Successfully seeded the Hackathon Demo Data!"))
        self.stdout.write("To test the scenario:")
        self.stdout.write("1. Create a Sales Order for 20 'Dining Table'")
        self.stdout.write("2. Observe available stock is 5, shortage is 15.")
        self.stdout.write("3. Confirming Sales Order automatically triggers a Manufacturing Order for 15.")
        self.stdout.write("4. Complete the Manufacturing Order to produce the goods.")
        self.stdout.write("5. Finally, deliver the Sales Order.")
