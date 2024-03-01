"""
For changes between v1 and v1.5, see
https://outline.con2.fi/doc/ticket-sales-1cFCJvcZxc
"""

from csp.decorators import csp_update
from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from core.utils import initialize_form
from payments.models.checkout_payment import CHECKOUT_PAYMENT_WALL_ORIGIN, CheckoutPayment
from payments.models.stripe_payment import STRIPE_PAYMENT_WALL_ORIGIN, StripePayment

from ..forms import CustomerForm, OrderProductForm
from ..helpers import tickets_event_required
from .tickets_v1_views import clear_order, get_order, set_order, tickets_welcome_view


@tickets_event_required
@require_http_methods(["GET", "HEAD", "POST"])
def tickets_router_view(request, event, *args, **kwargs):
    if event.tickets_event_meta.tickets_view_version == "v1.5":
        return tickets_view(request, event, *args, **kwargs)
    else:
        return tickets_welcome_view(request, event.slug, *args, **kwargs)


@csp_update(FORM_ACTION=CHECKOUT_PAYMENT_WALL_ORIGIN + " " + STRIPE_PAYMENT_WALL_ORIGIN)
def tickets_view(request, event):
    order = get_order(request, event)
    if order.is_confirmed:
        return tickets_confirmed_view(request, event, order)

    code = request.GET.get("code", "")

    with transaction.atomic():
        # TODO handle serialization_failure
        cursor = connection.cursor()
        cursor.execute("set transaction isolation level serializable")

        order_product_forms = OrderProductForm.get_for_order(request, order, code=code)
        customer_form = initialize_form(CustomerForm, request, order=order)

        vars = dict(
            customer_form=customer_form,
            event=event,
            form=order_product_forms,  # for historical reasons this needs to be called "form"
            order=order,
        )

        if request.method != "POST":
            return render(request, "v1.5/tickets_view.pug", vars)

        # if we are here, the user is trying to confirm the order

        if not customer_form.is_valid() or not all(form.is_valid() for form in order_product_forms):
            messages.error(request, _("Please check the form."))
            return render(request, "v1.5/tickets_view.pug", vars)

        order_products = [form.save(commit=False) for form in order_product_forms]
        if sum(op.count for op in order_products) == 0:
            messages.error(request, _("Please select at least one product."))
            return render(request, "v1.5/tickets_view.pug", vars)

        # TODO as OrderProductForm sets max_value, this should not be necessary
        if any(op.product.amount_available < op.count for op in order_products):
            messages.error(
                request,
                _(
                    "We're sorry to inform you that a product you have selected "
                    "is not available in the quantity you have requested."
                ),
            )
            return render(request, "v1.5/tickets_view.pug", vars)

        order.save()
        set_order(request, event, order)

        customer = customer_form.save(commit=False)
        customer.order = order
        customer.save()

        for op in order_products:
            op.order = order
            op.save()

        order.confirm_order()

        # TODO: option to select which payment to use
        if True:
            payment = CheckoutPayment.from_order(order)
        else:
            payment = StripePayment.from_order(order)
        payment.save()

    # does an API call to Paytrail so we need to do it after the transaction
    result = payment.perform_create_payment_request(request)
    return redirect(result["href"])


def tickets_confirmed_view(request, event, order):
    """
    Note that this "view" is not mounted in an URL config but rather delegated to from
    tickets_view when the order is confirmed.

    This view can only be entered when there is a confirmed order in the session.

    If that order is paid, this view will present the user a thank you message.

    If that order is not paid, this view will present the user a message saying so, and
    a button to complete the payment.
    """
    if not order.is_confirmed:
        raise ValueError("order must be confirmed")

    vars = dict(
        event=event,
        order=order,
        products=order.order_product_set.all(),  # for fuck's sake, why is this called products in the template
    )

    if request.method == "POST":
        match request.POST.get("action"):
            case "new-order":
                clear_order(request, event)
                return redirect("tickets_welcome_view", event.slug)
            case "cancel-order":
                if order.is_paid:
                    messages.error(
                        request,
                        _(
                            "The order is paid and cannot be canceled here. "
                            "Please contact us if you need to cancel it."
                        ),
                    )
                else:
                    order.cancel(send_email=False)
                    return redirect("tickets_welcome_view", event.slug)
            case "pay-order":
                if order.is_paid:
                    messages.error(request, _("This order has already been paid."))
                else:
                    # TODO: Get correct option from somewhere
                    if True:
                        payment = CheckoutPayment.from_order(order)
                    else:
                        payment = StripePayment.from_order(order)
                    payment.save()

                    # does an API call to Paytrail so we need to do it after the transaction
                    result = payment.perform_create_payment_request(request)
                    return redirect(result["href"])
            case _:
                messages.error(request, _("Please check the form."))

    return render(request, "v1.5/tickets_confirmed_view.pug", vars)
