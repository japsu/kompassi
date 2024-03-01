import json
import logging

import stripe
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_list_or_404, get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from payments.models.stripe_payment import StripePayment

from .helpers import valid_checkout_signature_required

logger = logging.getLogger("kompassi")

# Checkout / Paytrail


@valid_checkout_signature_required
def payments_checkout_success_view(request, payment):
    """
    https://checkoutfinland.github.io/psp-api/#/?id=redirect-and-callback-url-parameters
    """
    payment.process_checkout_response(request.GET)

    if payment.status == "ok":
        messages.success(request, _("Payment successful. Thank you for your order!"))
    elif payment.status in ["pending", "delayed"]:
        messages.warning(
            request,
            _(
                "The order was successful, but we are still waiting for final confirmation of payment from the payment processor. "
                "You will receive your e-tickets once we have received the confirmation. This may take up to three banking days."
            ),
        )
    else:
        logger.warning(
            "Success callback called with non-successful status %s. This should not happen idk?", payment.status
        )
        messages.error(request, _("The payment was not completed. Please try again."))

    return payment.get_redirect()


@valid_checkout_signature_required
def payments_checkout_cancel_view(request, payment):
    payment.process_checkout_response(request.GET)

    messages.error(request, _("The payment was not completed. Please try again."))
    return payment.get_redirect()


@valid_checkout_signature_required
def payments_checkout_success_callback(request, payment):
    payment.process_checkout_response(request.GET)
    return HttpResponse("")


@valid_checkout_signature_required
def payments_checkout_cancel_callback(request, payment):
    payment.process_checkout_response(request.GET)
    return HttpResponse("")


# Stripe


def payments_stripe_success_view(request, reference):
    # If multiple payment tries then we can have multiple references
    payments = get_list_or_404(StripePayment, reference=reference)
    payment = payments[-1]
    payment.process_stripe_response()

    if payment.status == "paid":
        messages.success(request, _("Payment successful. Thank you for your order!"))
    elif payment.status == "complete":
        messages.warning(
            request,
            _(
                "The order was successful, but we are still waiting for final confirmation of payment from the payment processor. "
                "You will receive your e-tickets once we have received the confirmation. This may take up to three banking days."
            ),
        )
    else:
        logger.warning(
            "Success callback called with non-successful status %s. This should not happen idk?", payment.status
        )
        messages.error(request, _("The payment was not completed. Please try again."))

    return payment.get_redirect()


def payments_stripe_cancel_view(request, reference):
    # If multiple payment tries then we can have multiple references
    payments = get_list_or_404(StripePayment, reference=reference)
    payment = payments[-1]
    payment.process_stripe_response()

    messages.error(request, _("The payment was not completed. Please try again."))
    return payment.get_redirect()


@csrf_exempt
def payments_stripe_webhook(request):
    # Parse manually first to verify type and get Payment with ID so we can get webhook secret
    data = json.load(request.body)

    # TODO: maybe also need to handle payment_intent.succeeded
    if data["type"] != "checkout.session.async_payment_succeeded":
        return HttpResponse("")

    payment = get_object_or_404(StripePayment, transaction_id=data["data"]["object"]["id"])

    # Verify signature
    # https://stripe.com/docs/webhooks#verify-official-libraries
    event = None
    signature = request.headers["Stripe-Signature"]
    try:
        event = stripe.Webhook.construct_event(request.body, signature, payment.meta.stripe_webhook_secret)
    except ValueError as e:
        # Invalid payload
        logger.warning(f"Error parsing Stripe payload: {str(e)}")
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError as e:
        # Invalid signature
        logger.warning(f"Error verifying Stripe webhook signature: {str(e)}")
        return HttpResponse(status=400)

    # logger.debug("stripe webhook %r", event)

    payment.process_stripe_webhook(event)
    return HttpResponse("")
