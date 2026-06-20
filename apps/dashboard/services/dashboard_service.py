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
    widgets = get_allowed_widgets_for_user(user)
    alerts = get_all_alerts()
    activities = [
        serialize_recent_activity(activity)
        for activity in get_recent_activity_queryset(limit=10)
    ]
    return {
        "widgets": widgets,
        "alerts": alerts,
        "recent_activities": activities,
        "ceo_kpis": get_ceo_kpis(),
        "erp_workflow": get_erp_workflow_status(),
        "intelligence_alerts": get_intelligence_alerts(),
        "manufacturing_progress": get_manufacturing_progress(),
    }
