from apps.accounts.models import UserRole
from apps.dashboard.widgets.widget_classes import (
    ProductWidget,
    InventoryWidget,
    SalesWidget,
    PurchaseWidget,
    ManufacturingWidget,
    ProcurementWidget,
    DeliveryWidget,
    ReportsWidget,
    AuditWidget,
    ForeignTradeWidget
)

WIDGETS = [
    ProductWidget(),
    InventoryWidget(),
    SalesWidget(),
    PurchaseWidget(),
    ManufacturingWidget(),
    ProcurementWidget(),
    DeliveryWidget(),
    ReportsWidget(),
    AuditWidget(),
    ForeignTradeWidget()
]

def get_allowed_widgets_for_user(user):
    """
    Returns a list of dicts containing widget details and data
    for widgets that the given user has permission to view.
    """
    allowed = []
    for widget in WIDGETS:
        # Admin and Business Owner always see all widgets. Other roles are matched against allowed_roles.
        if user.role in [UserRole.ADMIN, UserRole.BUSINESS_OWNER] or user.role in widget.allowed_roles:
            try:
                data = widget.get_data(user)
                allowed.append({
                    "title": widget.title,
                    "icon": widget.icon,
                    "data": data,
                    "class_name": widget.__class__.__name__
                })
            except Exception:
                # Shield dashboard loading from a single widget failure
                pass
    return allowed
