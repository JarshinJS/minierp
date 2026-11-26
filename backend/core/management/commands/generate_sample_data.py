import datetime
from decimal import Decimal
import random

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.products.models import Category, Product, ProcurementType
from apps.manufacturing.models import BoM, BOMComponent
from apps.inventory.services import post_ledger_entry
from apps.sales import services as sales_services
from apps.purchase import services as purchase_services
from apps.purchase.models import Vendor
from apps.manufacturing import services as mfg_services
from apps.foreign_trade.models import TradeCustomer, TradeSupplier, Country, Currency
from apps.foreign_trade import services as ft_services
from apps.delivery import services as delivery_services

User = get_user_model()

class Command(BaseCommand):
    help = "Generates a large set of sample data across all modules to make the system look active and realistic."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Starting dynamic data generation...")
        
        # Ensure User
        user, _ = User.objects.get_or_create(
            email="admin@erp.com",
            defaults={"is_staff": True, "is_superuser": True, "role": "ADMIN"}
        )
        if _:
            user.set_password("password")
            user.save()

        # 1. Base Setup (Categories, Products)
        cat_fg, _ = Category.objects.get_or_create(name="Finished Goods")
        cat_rm, _ = Category.objects.get_or_create(name="Raw Materials")

        legs, _ = Product.objects.get_or_create(
            sku="RM-LEGS",
            defaults={"name": "Wooden Legs", "category": cat_rm, "cost_price": Decimal("5.00"), "selling_price": Decimal("0.00"), "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True}
        )
        top, _ = Product.objects.get_or_create(
            sku="RM-TOP",
            defaults={"name": "Wooden Top", "category": cat_rm, "cost_price": Decimal("25.00"), "selling_price": Decimal("0.00"), "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True}
        )
        screws, _ = Product.objects.get_or_create(
            sku="RM-SCRW",
            defaults={"name": "Screws", "category": cat_rm, "cost_price": Decimal("0.10"), "selling_price": Decimal("0.00"), "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True}
        )
        paint, _ = Product.objects.get_or_create(
            sku="RM-PNT",
            defaults={"name": "Paint", "category": cat_rm, "cost_price": Decimal("12.00"), "selling_price": Decimal("0.00"), "procurement_type": ProcurementType.PURCHASE, "procure_on_demand": True}
        )

        table, _ = Product.objects.get_or_create(
            sku="FG-DTBL",
            defaults={"name": "Dining Table", "category": cat_fg, "cost_price": Decimal("80.00"), "selling_price": Decimal("250.00"), "procurement_type": ProcurementType.MANUFACTURING, "procure_on_demand": True}
        )
        
        bom, created = BoM.objects.get_or_create(product=table)
        if created:
            BOMComponent.objects.create(bom=bom, component=legs, quantity=4)
            BOMComponent.objects.create(bom=bom, component=top, quantity=1)
            BOMComponent.objects.create(bom=bom, component=screws, quantity=16)
            BOMComponent.objects.create(bom=bom, component=paint, quantity=1)
            table.default_bom = bom
            table.save()

        # Seed initial inventory for RM
        for rm in [legs, top, screws, paint]:
            if rm.on_hand_qty < 1000:
                post_ledger_entry(product=rm, entry_type="RECEIPT", quantity=Decimal("1000.00"), reference="INITIAL-STOCK")

        # 2. Purchase Orders
        vendor, _ = Vendor.objects.get_or_create(name="Wood & Supplies Co", defaults={"code": "VEN-001"})
        
        for i in range(5):
            po = purchase_services.create_order(
                vendor=vendor,
                created_by=user,
                lines_data=[
                    {"product": top, "quantity": Decimal(random.randint(50, 200)), "unit_price": top.cost_price},
                    {"product": legs, "quantity": Decimal(random.randint(200, 500)), "unit_price": legs.cost_price}
                ]
            )
            if i > 1:
                purchase_services.confirm_order(po)
            if i > 2:
                purchase_services.receive_order(po)

        # 3. Sales Orders
        customers = ["Acme Corp", "Globex Inc", "Stark Industries", "Wayne Enterprises", "Initech"]
        for i in range(8):
            customer_name = random.choice(customers)
            qty = Decimal(random.randint(5, 50))
            so = sales_services.create_order(
                customer_name=customer_name,
                created_by=user,
                lines_data=[{"product": table, "quantity": qty, "unit_price": table.selling_price}]
            )
            if i > 2:
                sales_services.confirm_order(so)
            if i > 5:
                # Need to manufacture it first to deliver
                try:
                    sales_services.deliver_order(so)
                except Exception:
                    pass # May fail if not enough stock, which is fine, generates demand

        # 4. Foreign Trade Data
        in_country, _ = Country.objects.get_or_create(code="IN", defaults={"name": "India"})
        us_country, _ = Country.objects.get_or_create(code="US", defaults={"name": "United States"})
        usd, _ = Currency.objects.get_or_create(code="USD", defaults={"name": "US Dollar", "symbol": "$"})
        
        tc, _ = TradeCustomer.objects.get_or_create(name="Global Importers LLC", defaults={"country": us_country, "email": "contact@globalimporters.com"})
        ts, _ = TradeSupplier.objects.get_or_create(name="China Wood Exports", defaults={"country": in_country, "email": "sales@chinawood.com"})

        for i in range(3):
            # Export Order
            exo = ft_services.create_export_order(
                customer=tc, country=us_country, currency=usd,
                lines_data=[{"description": "Premium Dining Tables", "quantity": Decimal("100"), "unit_price": Decimal("250.00")}],
                created_by=user
            )
            if i > 0:
                ft_services.confirm_export_order(exo, user)
            if i > 1:
                ft_services.ship_export_order(exo, {"carrier": "Maersk", "tracking_number": f"TRK-{i}999", "vessel_name": "Evergreen"}, user)
                
            # Import Order
            imo = ft_services.create_import_order(
                supplier=ts, country=in_country, currency=usd,
                lines_data=[{"description": "Bulk Wooden Logs", "quantity": Decimal("500"), "unit_price": Decimal("5.00")}],
                created_by=user
            )
            if i > 0:
                ft_services.confirm_import_order(imo, user)

        self.stdout.write(self.style.SUCCESS("Successfully generated dynamic sample data!"))
