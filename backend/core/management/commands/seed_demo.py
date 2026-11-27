"""
Deterministic demo dataset for screenshots, local demos and the Playwright suite.

    python manage.py seed_demo                                   # add demo data (idempotent)
    python manage.py seed_demo --reset --settings=config.settings.e2e   # wipe + reseed (e2e only)

Everything goes through the service layer, so the data obeys the same rules as
the app: stock receipts write ledger entries, confirming an order reserves stock.
"""
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts import services as account_services
from apps.accounts.models import AccountStatus, User, UserRole
from apps.inventory import services as inventory_services
from apps.products import services as product_services
from apps.products.models import Category, Product
from apps.purchase import services as purchase_services
from apps.purchase.models import Vendor
from apps.sales import services as sales_services
from apps.sales.models import SalesOrder

# Public, documented demo credentials. Only ever used on local/e2e databases.
DEMO_PASSWORD = "Demo-pass-2026!"
DEMO_DOMAIN = "demo.minierp.dev"

DEMO_USERS = [
    # (local part, full name, role)
    ("admin", "Asha Admin", UserRole.ADMIN),
    ("owner", "Omar Owner", UserRole.BUSINESS_OWNER),
    ("sales", "Sara Sales", UserRole.SALES_USER),
    ("purchase", "Paul Purchase", UserRole.PURCHASE_USER),
    ("inventory", "Ines Inventory", UserRole.INVENTORY_MANAGER),
    ("accountant", "Arjun Accountant", UserRole.ACCOUNTANT),
    ("trade", "Tara Trade", UserRole.TRADE_MANAGER),
    ("auditor", "Ali Auditor", UserRole.AUDITOR),
]
PENDING_USER = ("pending", "Priya Pending")

CATEGORIES = ["Finished Goods", "Raw Materials", "Hardware"]

# sku, name, category, unit, cost, price, opening stock
PRODUCTS = [
    ("FG-DTBL", "Teak Dining Table", "Finished Goods", "PCS", "8200", "18500", 14),
    ("FG-CHR", "Oak Dining Chair", "Finished Goods", "PCS", "1900", "4200", 48),
    ("FG-SOFA", "Three-Seater Sofa", "Finished Goods", "PCS", "15500", "32000", 4),
    ("FG-BED", "Queen Bed Frame", "Finished Goods", "PCS", "11000", "24500", 0),
    ("FG-DESK", "Study Desk", "Finished Goods", "PCS", "4300", "9800", 22),
    ("RM-TEAK", "Teak Plank 2m", "Raw Materials", "PCS", "2100", "0", 160),
    ("RM-OAK", "Oak Plank 2m", "Raw Materials", "PCS", "1750", "0", 3),
    ("RM-FOAM", "Upholstery Foam", "Raw Materials", "M", "380", "0", 85),
    ("HW-SCRW", "Wood Screws (box)", "Hardware", "BOX", "120", "0", 240),
    ("HW-HNGE", "Brass Hinges", "Hardware", "PCS", "65", "0", 0),
]

# customer, [(sku, qty)], confirm?
SALES_ORDERS = [
    ("Lotus Interiors", [("FG-DTBL", 2), ("FG-CHR", 12)], True),
    ("Coastal Homes", [("FG-SOFA", 1)], True),
    ("Greenleaf Cafe", [("FG-CHR", 20), ("FG-DESK", 2)], False),
]


class Command(BaseCommand):
    help = "Create the deterministic demo dataset (users per role, catalogue, stock, orders)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Flush the database first. Only allowed with config.settings.e2e.",
        )

    def handle(self, *args, reset=False, **options):
        if reset:
            if not getattr(settings, "E2E", False):
                raise CommandError("--reset wipes the database; it only runs with --settings=config.settings.e2e.")
            call_command("flush", interactive=False, verbosity=0)

        with transaction.atomic():
            users = self._users()
            products = self._catalogue()
            self._orders(users["sales"], products)
            self._purchase(users["purchase"], products)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Sign in as e.g. admin@{DEMO_DOMAIN} / {DEMO_PASSWORD}"
        ))

    def _users(self):
        users = {}
        for local, name, role in DEMO_USERS:
            email = f"{local}@{DEMO_DOMAIN}"
            user = User.objects.filter(email=email).first() or account_services.create_user(
                email=email, password=DEMO_PASSWORD, full_name=name, role=role,
                is_staff=role == UserRole.ADMIN, is_superuser=role == UserRole.ADMIN,
            )
            users[local] = user
        local, name = PENDING_USER
        if not User.objects.filter(email=f"{local}@{DEMO_DOMAIN}").exists():
            account_services.create_user(
                email=f"{local}@{DEMO_DOMAIN}", password=DEMO_PASSWORD, full_name=name,
                account_status=AccountStatus.PENDING,
            )
        return users

    def _catalogue(self):
        categories = {name: Category.objects.get_or_create(name=name)[0] for name in CATEGORIES}
        products = {}
        for sku, name, category, unit, cost, price, opening in PRODUCTS:
            product = Product.objects.filter(sku=sku).first()
            if product is None:
                product = product_services.create_product(
                    name=name, sku=sku, category=categories[category], unit_of_measure=unit,
                    cost_price=Decimal(cost), selling_price=Decimal(price),
                )
                if opening:
                    inventory_services.receive_stock(product, Decimal(opening), "Opening balance")
            products[sku] = product
        return products

    def _orders(self, sales_user, products):
        if SalesOrder.objects.exists():
            return
        for customer, lines, confirm in SALES_ORDERS:
            order = sales_services.create_order(
                customer, sales_user,
                [{"product": products[sku], "quantity": Decimal(q), "unit_price": products[sku].selling_price}
                 for sku, q in lines],
            )
            if confirm:
                sales_services.confirm_order(order)

    def _purchase(self, purchase_user, products):
        vendor, created = Vendor.objects.get_or_create(
            code="V-TEAK", defaults={"name": "Malabar Timber Co.", "email": "orders@malabar-timber.example"},
        )
        if created:
            purchase_services.create_order(
                vendor, purchase_user,
                [{"product": products["RM-OAK"], "quantity": Decimal("40"), "unit_price": Decimal("1750")}],
            )
