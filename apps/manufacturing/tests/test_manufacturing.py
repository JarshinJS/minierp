import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from core.exceptions import DomainError
from apps.products.models import Product, Category, UnitOfMeasure
from apps.inventory import services as inventory_services
from apps.manufacturing.models import (
    BoM, BOMComponent, BOMOperation, WorkCenter,
    ManufacturingOrder, MOComponent, WorkOrder,
    MOStatus, WorkOrderStatus
)
from apps.manufacturing import services as manufacturing_services
from apps.manufacturing import selectors as manufacturing_selectors

User = get_user_model()

@pytest.fixture
def manufacturing_setup(db):
    category = Category.objects.create(name="Electronics")
    
    # Finished product
    finished_product = Product.objects.create(
        name="Assembled Robot",
        sku="ROB-001",
        category=category,
        cost_price=Decimal("100.00"),
        selling_price=Decimal("250.00"),
        unit_of_measure=UnitOfMeasure.PCS,
        is_active=True
    )
    
    # Raw materials
    component_1 = Product.objects.create(
        name="Microcontroller Board",
        sku="COMP-MCU",
        category=category,
        cost_price=Decimal("30.00"),
        selling_price=Decimal("50.00"),
        unit_of_measure=UnitOfMeasure.PCS,
        is_active=True
    )
    component_2 = Product.objects.create(
        name="Servo Motor",
        sku="COMP-SRV",
        category=category,
        cost_price=Decimal("15.00"),
        selling_price=Decimal("25.00"),
        unit_of_measure=UnitOfMeasure.PCS,
        is_active=True
    )
    
    # Work centers
    wc_assembly = manufacturing_services.create_work_center(
        name="Assembly Station A",
        code="WC-ASM-A",
        cost_per_hour=Decimal("20.00")
    )
    wc_testing = manufacturing_services.create_work_center(
        name="Testing & QA",
        code="WC-QA",
        cost_per_hour=Decimal("30.00")
    )
    
    user = User.objects.create_user(
        email="factory_mgr@example.com",
        password="password",
        full_name="Factory Manager",
        role="INVENTORY_USER"
    )
    
    return {
        "finished_product": finished_product,
        "component_1": component_1,
        "component_2": component_2,
        "wc_assembly": wc_assembly,
        "wc_testing": wc_testing,
        "user": user
    }


@pytest.mark.django_db
class TestWorkCenterServices:
    def test_create_work_center_success(self):
        wc = manufacturing_services.create_work_center("Paint Shop", "WC-PAINT", Decimal("25.50"))
        assert wc.name == "Paint Shop"
        assert wc.code == "WC-PAINT"
        assert wc.cost_per_hour == Decimal("25.50")
        assert wc.is_active is True

    def test_create_work_center_validations(self):
        with pytest.raises(DomainError) as exc:
            manufacturing_services.create_work_center(" ", "WC-CODE")
        assert "Work center name cannot be empty." in str(exc.value)

        with pytest.raises(DomainError) as exc:
            manufacturing_services.create_work_center("Name", " ")
        assert "Work center code cannot be empty." in str(exc.value)

        manufacturing_services.create_work_center("Name A", "WC-A")
        with pytest.raises(DomainError) as exc:
            manufacturing_services.create_work_center("Name B", "WC-A")
        assert "already exists" in str(exc.value)

        with pytest.raises(DomainError) as exc:
            manufacturing_services.create_work_center("Name A", "WC-B")
        assert "already exists" in str(exc.value)

    def test_update_work_center_success(self):
        wc = manufacturing_services.create_work_center("Old Name", "WC-OLD", Decimal("10.00"))
        updated = manufacturing_services.update_work_center(wc, name="New Name", cost_per_hour=Decimal("12.50"))
        assert updated.name == "New Name"
        assert updated.cost_per_hour == Decimal("12.50")
        assert updated.code == "WC-OLD"

    def test_update_work_center_validations(self):
        wc1 = manufacturing_services.create_work_center("WC One", "WC-1")
        wc2 = manufacturing_services.create_work_center("WC Two", "WC-2")

        with pytest.raises(DomainError) as exc:
            manufacturing_services.update_work_center(wc1, code="WC-2")
        assert "already exists" in str(exc.value)

        with pytest.raises(DomainError) as exc:
            manufacturing_services.update_work_center(wc1, name="WC Two")
        assert "already exists" in str(exc.value)

        with pytest.raises(DomainError) as exc:
            manufacturing_services.update_work_center(wc1, cost_per_hour=Decimal("-5.00"))
        assert "Cost per hour cannot be negative" in str(exc.value)


@pytest.mark.django_db
class TestBOMServices:
    def test_create_bom_success(self, manufacturing_setup):
        prod = manufacturing_setup["finished_product"]
        c1 = manufacturing_setup["component_1"]
        c2 = manufacturing_setup["component_2"]
        wc1 = manufacturing_setup["wc_assembly"]
        wc2 = manufacturing_setup["wc_testing"]
        
        components = [
            {"component_id": c1.id, "quantity": 1, "uom": "PCS", "sequence": 10},
            {"component_id": c2.id, "quantity": 4, "uom": "PCS", "sequence": 20}
        ]
        operations = [
            {"work_center_id": wc1.id, "name": "Assemble frame", "duration_minutes": 30, "sequence": 10},
            {"work_center_id": wc2.id, "name": "Quality check", "duration_minutes": 15, "sequence": 20}
        ]
        
        bom = manufacturing_services.create_bom(
            name="Robot BOM V1",
            reference="BOM-ROB-01",
            product=prod,
            product_qty=Decimal("1.00"),
            notes="Standard assembly recipe",
            components=components,
            operations=operations
        )
        
        assert bom.name == "Robot BOM V1"
        assert bom.reference == "BOM-ROB-01"
        assert bom.product == prod
        assert bom.product_qty == Decimal("1.00")
        assert bom.components.count() == 2
        assert bom.operations.count() == 2
        
        # Verify sequence order
        comps = list(bom.components.order_by("sequence"))
        assert comps[0].component == c1
        assert comps[0].quantity == Decimal("1.0000")
        assert comps[1].component == c2
        assert comps[1].quantity == Decimal("4.0000")

    def test_create_bom_validations(self, manufacturing_setup):
        prod = manufacturing_setup["finished_product"]
        
        with pytest.raises(DomainError) as exc:
            manufacturing_services.create_bom("", "BOM-1", prod)
        assert "BOM name cannot be empty" in str(exc.value)

        with pytest.raises(DomainError) as exc:
            manufacturing_services.create_bom("BOM Name", "", prod)
        assert "BOM reference cannot be empty" in str(exc.value)

        # Duplicate reference
        manufacturing_services.create_bom("BOM One", "BOM-REF", prod)
        with pytest.raises(DomainError) as exc:
            manufacturing_services.create_bom("BOM Two", "BOM-REF", prod)
        assert "already exists" in str(exc.value)

        # Invalid qty
        with pytest.raises(DomainError) as exc:
            manufacturing_services.create_bom("BOM One", "BOM-REF2", prod, product_qty=Decimal("-1.0"))
        assert "quantity must be positive" in str(exc.value)

    def test_update_bom_success(self, manufacturing_setup):
        prod = manufacturing_setup["finished_product"]
        c1 = manufacturing_setup["component_1"]
        wc1 = manufacturing_setup["wc_assembly"]
        
        bom = manufacturing_services.create_bom(
            name="Robot BOM V1",
            reference="BOM-ROB-01",
            product=prod,
            components=[{"component_id": c1.id, "quantity": 1}],
            operations=[{"work_center_id": wc1.id, "name": "Assemble", "duration_minutes": 30}]
        )
        
        # Update name and replace components/operations
        c2 = manufacturing_setup["component_2"]
        wc2 = manufacturing_setup["wc_testing"]
        updated = manufacturing_services.update_bom(
            bom,
            name="Robot BOM V2",
            components=[{"component_id": c2.id, "quantity": 10}],
            operations=[{"work_center_id": wc2.id, "name": "QA", "duration_minutes": 10}]
        )
        
        assert updated.name == "Robot BOM V2"
        assert updated.components.count() == 1
        assert updated.components.first().component == c2
        assert updated.components.first().quantity == Decimal("10.0000")
        assert updated.operations.count() == 1
        assert updated.operations.first().work_center == wc2

    def test_deactivate_bom(self, manufacturing_setup):
        prod = manufacturing_setup["finished_product"]
        bom = manufacturing_services.create_bom("Robot BOM", "BOM-ROB", prod)
        assert bom.is_active is True
        
        deactivated = manufacturing_services.deactivate_bom(bom)
        assert deactivated.is_active is False
        
        with pytest.raises(DomainError) as exc:
            manufacturing_services.deactivate_bom(bom)
        assert "already inactive" in str(exc.value)


@pytest.mark.django_db
class TestBOMSelectors:
    def test_selectors(self, manufacturing_setup):
        prod = manufacturing_setup["finished_product"]
        c1 = manufacturing_setup["component_1"] # cost = 30.00
        c2 = manufacturing_setup["component_2"] # cost = 15.00
        wc1 = manufacturing_setup["wc_assembly"]
        
        bom = manufacturing_services.create_bom(
            name="Selectors Test BOM",
            reference="BOM-SEL",
            product=prod,
            components=[
                {"component_id": c1.id, "quantity": 2},
                {"component_id": c2.id, "quantity": 3}
            ],
            operations=[
                {"work_center_id": wc1.id, "name": "Op 1", "duration_minutes": 45},
                {"work_center_id": wc1.id, "name": "Op 2", "duration_minutes": 15}
            ]
        )
        
        # Test get_bom_cost
        # Cost = 30.00 * 2 + 15.00 * 3 = 60.00 + 45.00 = 105.00
        cost = manufacturing_selectors.get_bom_cost(bom)
        assert cost == Decimal("105.00")
        
        # Test get_bom_operation_time
        op_time = manufacturing_selectors.get_bom_operation_time(bom)
        assert op_time == Decimal("60.00")
        
        # Test get_bom
        fetched = manufacturing_selectors.get_bom(bom.pk)
        assert fetched == bom
        
        # Test get_boms
        boms_qs = manufacturing_selectors.get_boms(search="SEL")
        assert bom in boms_qs


@pytest.mark.django_db
class TestManufacturingOrderWorkflow:
    def test_mo_lifecycle(self, manufacturing_setup):
        prod = manufacturing_setup["finished_product"]
        c1 = manufacturing_setup["component_1"]
        c2 = manufacturing_setup["component_2"]
        wc1 = manufacturing_setup["wc_assembly"]
        
        # Create BOM: 1 run produces 2 robots, consuming 2 microcontroller boards and 4 servo motors
        bom = manufacturing_services.create_bom(
            name="Robot BOM",
            reference="BOM-ROB",
            product=prod,
            product_qty=Decimal("2.00"),
            components=[
                {"component_id": c1.id, "quantity": 2},
                {"component_id": c2.id, "quantity": 4}
            ],
            operations=[
                {"work_center_id": wc1.id, "name": "Assemble Robot", "duration_minutes": 20}
            ]
        )
        
        # 1. Create MO in DRAFT status
        mo = manufacturing_services.create_mo(
            product=prod,
            qty_to_produce=Decimal("4.00"),
            bom=bom,
            scheduled_date="2026-06-25",
            notes="First batch"
        )
        assert mo.status == MOStatus.DRAFT
        assert mo.qty_produced == Decimal("0.00")
        assert mo.reference.startswith("MO-")
        assert mo.components.count() == 0
        assert mo.work_orders.count() == 0
        
        # 2. Confirm MO
        # Scaling is qty_to_produce / bom.product_qty = 4 / 2 = 2x
        # Components required: c1 = 2 * 2 = 4, c2 = 4 * 2 = 8
        mo = manufacturing_services.confirm_mo(mo)
        assert mo.status == MOStatus.CONFIRMED
        assert mo.components.count() == 2
        assert mo.work_orders.count() == 1
        
        comp_mcu = mo.components.get(product=c1)
        assert comp_mcu.qty_required == Decimal("4.0000")
        assert comp_mcu.qty_consumed == Decimal("0.0000")
        
        comp_srv = mo.components.get(product=c2)
        assert comp_srv.qty_required == Decimal("8.0000")
        
        wo = mo.work_orders.first()
        assert wo.work_center == wc1
        assert wo.duration_expected == Decimal("20.00")
        assert wo.status == WorkOrderStatus.PENDING
        
        # 3. Start MO
        mo = manufacturing_services.start_mo(mo)
        assert mo.status == MOStatus.IN_PROGRESS
        
        # Verify first work order is auto-started
        wo.refresh_from_db()
        assert wo.status == WorkOrderStatus.IN_PROGRESS
        
        # Let's complete the work order
        manufacturing_services.complete_work_order(wo, duration_actual=Decimal("22.5"))
        wo.refresh_from_db()
        assert wo.status == WorkOrderStatus.DONE
        assert wo.duration_actual == Decimal("22.50")
        
        # 4. Produce MO (partial production)
        # Receive component stock so we can consume it
        inventory_services.receive_stock(c1, Decimal("10.00"), reference="Purchase")
        inventory_services.receive_stock(c2, Decimal("20.00"), reference="Purchase")
        
        # Produce 2 robot units out of 4 (ratio = 2/4 = 0.5)
        # Consumes: c1 = 4 * 0.5 = 2, c2 = 8 * 0.5 = 4
        mo = manufacturing_services.produce_mo(mo, Decimal("2.00"))
        assert mo.status == MOStatus.IN_PROGRESS
        assert mo.qty_produced == Decimal("2.00")
        
        prod.refresh_from_db()
        c1.refresh_from_db()
        c2.refresh_from_db()
        assert prod.on_hand_qty == Decimal("2.00") # Finished good received
        
        comp_mcu.refresh_from_db()
        comp_srv.refresh_from_db()
        assert comp_mcu.qty_consumed == Decimal("2.0000")
        assert comp_srv.qty_consumed == Decimal("4.0000")
        assert c1.on_hand_qty == Decimal("8.00")
        assert c2.on_hand_qty == Decimal("16.00")
        
        # 5. Produce remainder
        mo = manufacturing_services.produce_mo(mo, Decimal("2.00"))
        assert mo.status == MOStatus.DONE
        assert mo.qty_produced == Decimal("4.00")
        
        prod.refresh_from_db()
        c1.refresh_from_db()
        c2.refresh_from_db()
        assert prod.on_hand_qty == Decimal("4.00")
        
        comp_mcu.refresh_from_db()
        comp_srv.refresh_from_db()
        assert comp_mcu.qty_consumed == Decimal("4.0000")
        assert comp_srv.qty_consumed == Decimal("8.0000")
        assert c1.on_hand_qty == Decimal("6.00")
        assert c2.on_hand_qty == Decimal("12.00")

    def test_cancel_mo(self, manufacturing_setup):
        prod = manufacturing_setup["finished_product"]
        mo = manufacturing_services.create_mo(product=prod, qty_to_produce=10)
        
        # Cancel draft is OK
        mo = manufacturing_services.cancel_mo(mo)
        assert mo.status == MOStatus.CANCELLED
        
        # Cannot cancel cancelled MO
        with pytest.raises(DomainError) as exc:
            manufacturing_services.cancel_mo(mo)
        assert "already" in str(exc.value)
        
        # Cancel confirmed is OK
        mo2 = manufacturing_services.create_mo(product=prod, qty_to_produce=5)
        mo2 = manufacturing_services.confirm_mo(mo2)
        mo2 = manufacturing_services.cancel_mo(mo2)
        assert mo2.status == MOStatus.CANCELLED
        
        # Cannot cancel In Progress
        mo3 = manufacturing_services.create_mo(product=prod, qty_to_produce=5)
        mo3 = manufacturing_services.confirm_mo(mo3)
        mo3 = manufacturing_services.start_mo(mo3)
        with pytest.raises(DomainError) as exc:
            manufacturing_services.cancel_mo(mo3)
        assert "Cannot cancel an In Progress MO" in str(exc.value)


@pytest.mark.django_db
class TestManufacturingOrderSelectors:
    def test_selectors(self, manufacturing_setup):
        prod = manufacturing_setup["finished_product"]
        mo = manufacturing_services.create_mo(product=prod, qty_to_produce=5)
        
        mo_list = manufacturing_selectors.get_manufacturing_orders(status=MOStatus.DRAFT)
        assert mo in mo_list
        
        fetched = manufacturing_selectors.get_manufacturing_order(mo.pk)
        assert fetched == mo


@pytest.mark.django_db
class TestManufacturingAPI:
    def test_workcenter_endpoints(self, manufacturing_setup):
        client = APIClient()
        client.force_login(manufacturing_setup["user"])
        
        # List
        url = reverse("manufacturing:api_workcenter-list")
        res = client.get(url)
        assert res.status_code == status.HTTP_200_OK
        
        # Create
        data = {
            "name": "Testing Station B",
            "code": "WC-TEST-B",
            "cost_per_hour": "15.00"
        }
        res = client.post(url, data)
        assert res.status_code == status.HTTP_201_CREATED
        assert WorkCenter.objects.filter(code="WC-TEST-B").exists()

    def test_bom_endpoints(self, manufacturing_setup):
        client = APIClient()
        client.force_login(manufacturing_setup["user"])
        
        # List
        url = reverse("manufacturing:api_bom-list")
        res = client.get(url)
        assert res.status_code == status.HTTP_200_OK
        
        # Create
        data = {
            "name": "BOM API Robot",
            "reference": "BOM-API-ROB",
            "product": manufacturing_setup["finished_product"].id,
            "product_qty": "1.00",
            "notes": "API note"
        }
        res = client.post(url, data)
        assert res.status_code == status.HTTP_201_CREATED
        bom_id = res.data["id"]
        
        # Cost action
        cost_url = reverse("manufacturing:api_bom-cost", args=[bom_id])
        res = client.get(cost_url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["total_cost"] == "0.00"

    def test_mo_endpoints(self, manufacturing_setup):
        client = APIClient()
        client.force_login(manufacturing_setup["user"])
        
        prod = manufacturing_setup["finished_product"]
        c1 = manufacturing_setup["component_1"]
        wc1 = manufacturing_setup["wc_assembly"]
        
        bom = manufacturing_services.create_bom(
            name="Robot BOM",
            reference="BOM-ROB",
            product=prod,
            components=[{"component_id": c1.id, "quantity": 1}],
            operations=[{"work_center_id": wc1.id, "name": "Op", "duration_minutes": 10}]
        )
        
        # Create MO
        url = reverse("manufacturing:api_mo-list")
        data = {
            "product": prod.id,
            "qty_to_produce": "5.00",
            "bom": bom.id,
            "scheduled_date": "2026-07-01",
            "notes": "API MO"
        }
        res = client.post(url, data)
        assert res.status_code == status.HTTP_201_CREATED
        mo_id = res.data["id"]
        
        # Action: Confirm
        confirm_url = reverse("manufacturing:api_mo-confirm", args=[mo_id])
        res = client.post(confirm_url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == MOStatus.CONFIRMED
        
        # Action: Start
        start_url = reverse("manufacturing:api_mo-start", args=[mo_id])
        res = client.post(start_url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == MOStatus.IN_PROGRESS
        
        # Action: Produce (must receive stock first)
        inventory_services.receive_stock(c1, Decimal("10.00"), reference="Stocking")
        
        produce_url = reverse("manufacturing:api_mo-produce", args=[mo_id])
        res = client.post(produce_url, {"qty_produced": "2.00"})
        assert res.status_code == status.HTTP_200_OK
        assert res.data["qty_produced"] == "2.00"
        
        # Action: Cancel (In progress cannot cancel)
        cancel_url = reverse("manufacturing:api_mo-cancel", args=[mo_id])
        res = client.post(cancel_url)
        assert res.status_code == status.HTTP_400_BAD_REQUEST
