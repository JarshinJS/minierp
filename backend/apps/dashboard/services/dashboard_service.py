from apps.dashboard.selectors import (
    get_recent_activity_queryset, serialize_recent_activity,
    get_ceo_kpis, get_erp_workflow_status, get_intelligence_alerts, get_manufacturing_progress
)
from apps.dashboard.services.widget_service import get_allowed_widgets_for_user
from apps.dashboard.services.alert_service import get_all_alerts

def get_dashboard_data_for_user(user):
    """
    Orchestrates retrieving all widgets, alerts, and recent activities
    tailored to the user's role and authorization.
    """
    from apps.accounts.permissions import can_access_module

    widgets = get_allowed_widgets_for_user(user)
    alerts = get_all_alerts()
    # Recent activity is audit-trail data: only entries from modules the user may open.
    activities = [
        serialize_recent_activity(activity)
        for activity in get_recent_activity_queryset(limit=50)
        if can_access_module(user, activity.module)
    ][:10]
    from apps.accounts.templatetags.navigation import ROLE_PERMISSIONS, NAV_ITEMS
    allowed_modules = [
        key for key in ROLE_PERMISSIONS.get(user.role, ["dashboard"])
        if user.role in NAV_ITEMS.get(key, {}).get("roles", [user.role])
    ]
    return {
        "allowed_modules": allowed_modules,
        "widgets": widgets,
        "alerts": alerts,
        "recent_activities": activities,
        "ceo_kpis": get_ceo_kpis(),
        "erp_workflow": get_erp_workflow_status(),
        "intelligence_alerts": [
            alert for alert in get_intelligence_alerts()
            if can_access_module(user, alert.get("module", "dashboard"))
        ],
        "manufacturing_progress": get_manufacturing_progress(),
    }
