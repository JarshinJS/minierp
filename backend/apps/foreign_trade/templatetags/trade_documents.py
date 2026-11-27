from django import template

from apps.foreign_trade.documents import download_url

register = template.Library()


@register.simple_tag(takes_context=True)
def document_download_url(context, document):
    """Signed, short-lived download URL for the current user (empty if none)."""
    request = context.get("request")
    if request is None or not document.file:
        return ""
    return download_url(document, request.user) or ""
