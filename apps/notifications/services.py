import logging
# pyrefly: ignore [missing-import]
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
# pyrefly: ignore [missing-import]
from django.template.loader import render_to_string
# pyrefly: ignore [missing-import]
from django.utils.html import strip_tags    

logger = logging.getLogger(__name__)

def _send_email(subject, template_name, context, recipient_list):
    if not recipient_list or not any(recipient_list):
        logger.warning(f"No recipients provided for email: {subject}")
        return

    try:
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    except Exception as e:
        logger.error(f"Failed to send email '{subject}' to {recipient_list}: {e}")


def send_order_confirmation(order):
    if not order.customer_email:
        logger.warning(f"Order {order.order_number} has no customer_email. Skipping confirmation.")
        return

    subject = f"Order Confirmation: {order.order_number}"
    context = {
        "order": order,
    }
    _send_email(subject, "emails/order_confirmation.html", context, [order.customer_email])


def send_order_status_update(order):
    if not order.customer_email:
        logger.warning(f"Order {order.order_number} has no customer_email. Skipping status update.")
        return

    subject = f"Order Status Update: {order.order_number}"
    context = {
        "order": order,
    }
    _send_email(subject, "emails/order_status_update.html", context, [order.customer_email])


def send_delivery_dispatched(delivery_note):
    order = delivery_note.sales_order
    if not order.customer_email:
        logger.warning(f"Delivery {delivery_note.delivery_number} has no customer_email. Skipping dispatch notification.")
        return

    subject = f"Delivery Dispatched: {delivery_note.delivery_number}"
    context = {
        "delivery_note": delivery_note,
        "order": order,
    }
    _send_email(subject, "emails/delivery_dispatched.html", context, [order.customer_email])


def send_low_stock_alert(product):
    if not settings.INTERNAL_ALERT_EMAILS:
        logger.warning(f"No INTERNAL_ALERT_EMAILS configured. Skipping low stock alert for {product.sku}.")
        return

    subject = f"Low Stock Alert: {product.sku} ({product.name})"
    context = {
        "product": product,
    }
    _send_email(subject, "emails/low_stock_alert.html", context, settings.INTERNAL_ALERT_EMAILS)


def send_purchase_order_notification(order):
    if not order.vendor.email:
        logger.warning(f"Purchase Order {order.order_number} has no vendor email. Skipping notification.")
        return

    subject = f"Purchase Order: {order.order_number}"
    context = {
        "order": order,
    }
    _send_email(subject, "emails/purchase_order_notification.html", context, [order.vendor.email])
