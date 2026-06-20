from django import template
from django.urls import reverse, NoReverseMatch
from apps.accounts.models import UserRole

register = template.Library()

@register.inclusion_tag("accounts/sidebar_menu.html", takes_context=True)
def render_sidebar(context):
    request = context.get("request")
    if not request or not request.user or not request.user.is_authenticated:
        return {"menu_items": []}

    user = request.user
    role = user.role
    
    # Menu structure: (name, url_name, icon_svg_path)
    all_items = {
        "dashboard": {
            "name": "Dashboard",
            "url": "accounts:dashboard_home",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>',
        },
        "accounts": {
            "name": "User Management",
            "url": "accounts:user_list",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/></svg>',
        },
        "products": {
            "name": "Products",
            "url": "products:product_list",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>',
        },
        "inventory": {
            "name": "Inventory",
            "url": "#",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/></svg>',
        },
        "sales": {
            "name": "Sales",
            "url": "sales:sales_order_list",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        },
        "purchase": {
            "name": "Purchase",
            "url": "purchase:purchase_order_list",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"/></svg>',
        },
        "manufacturing": {
            "name": "Manufacturing",
            "url": "manufacturing:mo_list",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/></svg>',
        },
        "procurement": {
            "name": "Procurement",
            "url": "#",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>',
        },
        "audit_logs": {
            "name": "Audit Logs",
            "url": "audit_logs:list",
            "icon": '<svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>',
        }
    }

    # Role permission mappings: dynamic navigation based on roles
    role_permissions = {
        UserRole.ADMIN: ["dashboard", "accounts", "products", "inventory", "sales", "purchase", "manufacturing", "procurement", "audit_logs"],
        UserRole.BUSINESS_OWNER: ["dashboard", "accounts", "products", "inventory", "sales", "purchase", "manufacturing", "procurement", "audit_logs"],
        UserRole.SALES_USER: ["dashboard", "sales", "products"],
        UserRole.PURCHASE_USER: ["dashboard", "purchase", "products", "procurement"],
        UserRole.MANUFACTURING_USER: ["dashboard", "manufacturing", "inventory"],
        UserRole.INVENTORY_MANAGER: ["dashboard", "inventory", "products", "procurement"],
    }

    allowed_keys = role_permissions.get(role, ["dashboard"])
    menu_items = []
    
    current_path = request.path

    for key in allowed_keys:
        if key in all_items:
            item = all_items[key]
            # Resolve url name if possible, else keep '#'
            url_target = "#"
            is_active = False
            if item["url"] != "#":
                try:
                    url_target = reverse(item["url"])
                    # Check if active
                    if current_path == url_target or (url_target != "/" and current_path.startswith(url_target)):
                        is_active = True
                except NoReverseMatch:
                    pass
            
            menu_items.append({
                "name": item["name"],
                "url": url_target,
                "icon": item["icon"],
                "is_active": is_active
            })

    return {
        "menu_items": menu_items,
        "request": request,
    }
