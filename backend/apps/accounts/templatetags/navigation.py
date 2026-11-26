"""
Role-aware application navigation.

`render_sidebar` renders the sidebar; `nav_breadcrumbs` exposes the active
module/page so the top bar can show breadcrumbs. Both share `build_navigation`
so the role → module mapping is defined exactly once.
"""
from django import template
from django.urls import reverse, NoReverseMatch

from apps.accounts.models import UserRole
from core.templatetags.ui import render_icon

register = template.Library()

# key -> definition. `children` become an expandable group in the sidebar.
NAV_ITEMS = {
    "dashboard": {"name": "Dashboard", "icon": "dashboard", "url": "dashboard:home"},
    "products": {"name": "Products", "icon": "package", "url": "products:product_list", "prefix": "/products/"},
    "inventory": {"name": "Inventory", "icon": "warehouse", "url": "inventory:home", "prefix": "/inventory/"},
    "sales": {
        "name": "Sales", "icon": "cart", "prefix": "/sales/",
        "children": [
            ("Sales orders", "sales:sales_order_list"),
            ("Pipeline board", "sales:sales_order_kanban"),
        ],
    },
    "purchase": {
        "name": "Purchase", "icon": "bag", "prefix": "/purchase/",
        "children": [
            ("Purchase orders", "purchase:purchase_order_list"),
            ("Vendors", "purchase:vendor_list"),
        ],
    },
    "procurement": {"name": "Procurement", "icon": "clipboard", "url": "procurement:trigger_dashboard", "prefix": "/procurement/"},
    "manufacturing": {
        "name": "Manufacturing", "icon": "factory", "prefix": "/manufacturing/",
        "children": [
            ("Manufacturing orders", "manufacturing:mo_list"),
            ("Bills of materials", "manufacturing:bom_list"),
            ("Work centers", "manufacturing:workcenter_list"),
        ],
    },
    "delivery": {"name": "Delivery", "icon": "truck", "url": "delivery:list", "prefix": "/delivery/"},
    "foreign_trade": {
        "name": "Foreign Trade", "icon": "globe", "prefix": "/trade/",
        "children": [
            ("Export orders", "foreign_trade:export_order_list"),
            ("Import orders", "foreign_trade:import_order_list"),
            ("Shipments", "foreign_trade:shipment_list",
             ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "AUDITOR"]),
            ("Trade customers", "foreign_trade:customer_list", ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]),
            ("Trade suppliers", "foreign_trade:supplier_list", ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]),
        ],
    },
    "blockchain": {
        "name": "Blockchain", "icon": "shield", "prefix": "/blockchain/",
        "children": [
            ("Overview", "blockchain:dashboard"),
            ("Anchored documents", "blockchain:document_list"),
            ("Ledger audit", "blockchain:audit_log_list", ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "AUDITOR"]),
        ],
    },
    "reports": {"name": "Reports", "icon": "chart", "url": "reports:home", "prefix": "/reports/",
                # Mirrors ReportsHomeView.allowed_roles so the link never leads to a 403.
                "roles": ["ADMIN", "BUSINESS_OWNER", "ACCOUNTANT"]},
    "audit_logs": {"name": "Audit Logs", "icon": "history", "url": "audit_logs:list", "prefix": "/audit/"},
    "accounts": {"name": "Users & Roles", "icon": "users", "url": "accounts:user_list", "prefix": "/accounts/users/"},
}

NAV_SECTIONS = [
    ("Overview", ["dashboard"]),
    ("Operations", ["products", "inventory", "sales", "purchase", "procurement", "manufacturing", "delivery"]),
    ("Trade & Compliance", ["foreign_trade", "blockchain"]),
    ("Insights", ["reports", "audit_logs"]),
    ("Administration", ["accounts"]),
]

# Role → module access lives in accounts.permissions so views and APIs enforce
# the same mapping the sidebar displays.
from apps.accounts.permissions import MODULE_ACCESS as ROLE_PERMISSIONS  # noqa: E402


def _reverse(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def build_navigation(request):
    """Return a list of sections, each with the menu items visible to the user."""
    if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
        return []

    allowed = set(ROLE_PERMISSIONS.get(request.user.role, ["dashboard"]))
    path = request.path
    sections = []

    for section_name, keys in NAV_SECTIONS:
        items = []
        for key in keys:
            if key not in allowed:
                continue
            spec = NAV_ITEMS[key]
            if "roles" in spec and request.user.role not in spec["roles"]:
                continue
            children = []
            for child in spec.get("children", []):
                label, url_name = child[0], child[1]
                # Optional third element: roles allowed to see this sub-page (mirrors the view's allowed_roles).
                if len(child) > 2 and request.user.role not in child[2]:
                    continue
                url = _reverse(url_name)
                if url:
                    children.append({"name": label, "url": url, "is_active": path.startswith(url)})

            url = _reverse(spec["url"]) if "url" in spec else (children[0]["url"] if children else None)
            if not url:
                continue
            prefix = spec.get("prefix")
            is_active = path == url or (prefix and path.startswith(prefix)) or any(c["is_active"] for c in children)
            items.append({
                "key": key,
                "name": spec["name"],
                "url": url,
                "icon": render_icon(spec["icon"]),
                "children": children,
                "is_active": bool(is_active),
            })
        if items:
            sections.append({"name": section_name, "items": items})
    return sections


@register.inclusion_tag("accounts/sidebar_menu.html", takes_context=True)
def render_sidebar(context):
    request = context.get("request")
    sections = build_navigation(request)
    # `menu_items` kept for backwards compatibility with any template that used the flat list.
    menu_items = [item for section in sections for item in section["items"]]
    return {"sections": sections, "menu_items": menu_items, "request": request}


@register.simple_tag(takes_context=True)
def nav_breadcrumbs(context):
    """[{name, url}] for the active module and (if any) its active sub-page."""
    request = context.get("request")
    for section in build_navigation(request):
        for item in section["items"]:
            if item["is_active"]:
                crumbs = [{"name": item["name"], "url": item["url"]}]
                active_child = next((c for c in item["children"] if c["is_active"]), None)
                if active_child:
                    crumbs.append({"name": active_child["name"], "url": active_child["url"]})
                return crumbs
    return []
