import logging
from dataclasses import dataclass
from functools import cached_property

import stripe
from django.db import connection, models
from django.db.models import JSONField
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from pkg_resources import resource_string

from tickets.utils import format_price

logger = logging.getLogger("kompassi")

STRIPE_PAYMENT_WALL_ORIGIN = "checkout.stripe.com"
STRIPE_STATUSES = [
    ("open", _("Open")),  # status, Newly created session
    ("complete", _("Complete")),  # status, Complete, payment maybe in progress
    ("expired", _("Expired")),  # status, nothing more will happen
    # ("unpaid", _("Unpaid")), # payment_status
    ("paid", _("Paid")),  # payment_status
]


@dataclass
class PaymentsByPaymentMethod:
    provider: str

    num_new: int = 0
    num_ok: int = 0
    num_fail: int = 0
    num_delayed: int = 0

    @property
    def num_total(self):
        return self.num_new + self.num_ok + self.num_fail + self.num_delayed


@dataclass
class OrdersByPaymentStatus:
    new: int
    fail: int
    ok_after_fail: int
    ok_without_fail: int

    QUERY = resource_string(__name__, "queries/orders_by_payment_status.sql").decode("utf-8")

    @cached_property
    def total(self):
        return self.new + self.fail + self.ok_after_fail + self.ok_without_fail

    @property
    def new_percentage(self):
        return self.new / self.total * 100 if self.total else 0

    @property
    def fail_percentage(self):
        return self.fail / self.total * 100 if self.total else 0

    @property
    def ok_after_fail_percentage(self):
        return self.ok_after_fail / self.total * 100 if self.total else 0

    @property
    def ok_without_fail_percentage(self):
        return self.ok_without_fail / self.total * 100 if self.total else 0


class StripePayment(models.Model):
    """
    Stripe online payments

    See https://stripe.com/docs/api/checkout/sessions/create
    """

    organization = models.ForeignKey("core.Organization", on_delete=models.CASCADE)
    event = models.ForeignKey("core.Event", on_delete=models.CASCADE, blank=True, null=True)

    # Fields sent in Create Payment request
    transaction_id = models.TextField(primary_key=True, default="", editable=False)
    reference = models.TextField(editable=False)
    price_cents = models.IntegerField(editable=False)
    items = JSONField(editable=False)
    customer = JSONField(editable=False)

    # Fields extracted from redirect or callback
    provider = models.TextField(editable=False, blank=True)
    status = models.CharField(
        default="new",
        editable=False,
        choices=STRIPE_STATUSES,
        max_length=max(len(status) for (status, _) in STRIPE_STATUSES),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if self.event:
            self.organization = self.event.organization

        return super().save(*args, **kwargs)

    @classmethod
    def from_order(cls, order):
        items = [
            {
                "price_data": {
                    "product_data": {
                        "name": order_product.product.name,
                        "description": order_product.product.description,
                    },
                    "unit_amount": order_product.product.price_cents,
                    "currency": "eur",
                },
                "quantity": order_product.count,
            }
            for order_product in order.order_product_set.all()
            if order_product.count > 0
        ]

        customer = {
            "email": order.customer.email,
        }

        return cls(
            event=order.event,
            reference=order.reference_number,
            price_cents=order.price_cents,
            items=items,
            customer=customer,
        )

    @classmethod
    def from_membership_fee_payment(cls, membership_fee_payment):
        term = membership_fee_payment.term
        organization = term.organization
        person = membership_fee_payment.member.person

        items = [
            {
                "price_data": {
                    "product_data": {
                        "name": "Jäsenmaksu",
                        "description": f"Jäsenmaksu kaudelle {term.title}",
                    },
                    "unit_amount": term.membership_fee_cents,
                    "currency": "eur",
                },
                "quantity": 1,
            }
        ]
        if term.entrance_fee_cents and membership_fee_payment.payment_type == "membership_fee_with_entrance_fee":
            items.append(
                {
                    "price_data": {
                        "product_data": {
                            "name": "Liittymismaksu",
                            "description": "Liittymismaksu",
                        },
                        "unit_amount": term.entrance_fee_cents,
                        "currency": "eur",
                    },
                    "quantity": 1,
                }
            )

        customer = {
            "email": person.email,
        }

        return cls(
            organization=organization,
            reference=membership_fee_payment.reference_number,
            price_cents=membership_fee_payment.amount_cents,
            items=items,
            customer=customer,
        )

    @property
    def meta(self):
        return self.organization.payments_organization_meta

    @property
    def tickets_order(self):
        """
        Old webshop order for this payment, or None if this payment was not from the old webshop
        """
        if not hasattr(self, "_tickets_order"):
            from tickets.models import Order

            self._tickets_order = Order.objects.filter(reference_number=self.reference).first()

        return self._tickets_order

    @property
    def membership_fee_payment(self):
        if not hasattr(self, "_membership_fee_payment"):
            from membership.models import MembershipFeePayment

            self._membership_fee_payment = MembershipFeePayment.objects.filter(reference_number=self.reference).first()

        return self._membership_fee_payment

    def setup_webhook(self, request):
        if self.meta.stripe_api_secret == "":
            raise ValueError(f"Event {self.event} doesn't have Stripe credentials, please change this in admin")

        stripe.api_key = self.meta.stripe_api_secret
        response = stripe.WebhookEndpoint.create(
            enabled_events=["checkout.session.async_payment_succeeded", "payment_intent.succeeded"],
            url=request.build_absolute_uri(reverse("payments_stripe_webhook")),
        )
        # logger.debug("create webhook response %r", response)
        self.meta.stripe_webhook_secret = response["secret"]
        self.meta.save()

    def perform_create_payment_request(self, request):
        if self.meta.stripe_api_secret == "":
            raise ValueError(f"Event {self.event} doesn't have Stripe credentials, please change this in admin")

        # TODO: move maybe to PaymentsOrganizationMeta so this is executed only once when secret is changed
        self.setup_webhook(request)

        # TODO: more unique ref to success/cancel URLs (but we get transaction id only after sending the request)
        stripe.api_key = self.meta.stripe_api_secret
        result = stripe.checkout.Session.create(
            success_url=request.build_absolute_uri(reverse("payments_stripe_success_view")) + "/" + self.reference,
            cancel_url=request.build_absolute_uri(reverse("payments_stripe_cancel_view")) + "/" + self.reference,
            line_items=self.items,
            client_reference_id=self.reference,
            mode="payment",
            currency="eur",
            customer_email=self.customer["email"],
        )
        # logger.debug("stripe.create response %r", result)

        self.transaction_id = result["id"]
        self.status = result["status"]
        self.save()

        # Make it look like Checkout response
        result["href"] = result["url"]

        return result

    def process_stripe_payment(self, result):
        self.provider = ",".join(result["payment_method_types"])
        self.status = result["status"]
        if result["payment_status"] == "paid":
            self.status = "paid"
        self.save()

        if self.tickets_order:
            if self.status == "paid" and not self.tickets_order.is_paid:
                self.tickets_order.confirm_payment()
        elif self.membership_fee_payment and self.status == "paid" and not self.membership_fee_payment.is_paid:
            self.membership_fee_payment.confirm_payment(payment_method="stripe")

    def process_stripe_webhook(self, request):
        result = request["data"]["object"]
        # logger.debug("stripe webhook %r", result)
        self.process_stripe_payment(result)

    def process_stripe_response(self):
        # Stripe success response doesn't contain any data of the payment itself
        # We have to poll for current status (or ignore and trust webhooks)
        stripe.api_key = self.meta.stripe_api_secret
        result = stripe.checkout.Session.retrieve(self.transaction_id)
        # logger.debug("stripe session retrieve %r", result)
        self.process_stripe_payment(result)

    def admin_get_customer_email(self):
        try:
            return self.customer["email"]
        except (IndexError, KeyError, ValueError):
            return None

    admin_get_customer_email.short_description = "Customer E-mail"

    def admin_get_formatted_amount(self):
        if self.price_cents is None:
            return None

        return format_price(self.price_cents)

    admin_get_formatted_amount.short_description = "Amount"
    admin_get_formatted_amount.admin_order_field = "price_cents"

    def get_redirect(self):
        if self.tickets_order:
            match self.tickets_order.event.tickets_event_meta.tickets_view_version:
                case "v1":
                    if self.status in ["ok", "pending", "delayed"]:
                        return redirect("tickets_thanks_view", self.tickets_order.event.slug)
                    else:
                        return redirect("tickets_confirm_view", self.tickets_order.event.slug)
                case "v1.5":
                    # XXX named tickets_welcome_view for historical reasons
                    # but it actually shows the order confirmation view
                    return redirect("tickets_welcome_view", self.tickets_order.event.slug)
                case unsupported_version:
                    raise NotImplementedError(unsupported_version)

        elif self.membership_fee_payment:
            return redirect("core_organization_view", self.membership_fee_payment.term.organization.slug)
        else:
            raise NotImplementedError(f"Received payment without handler: {self.transaction_id}")

    @classmethod
    def get_payments_by_payment_method(cls, event):
        results: dict[str, PaymentsByPaymentMethod] = dict()

        for payment in cls.objects.filter(event=event):
            result = results.setdefault(payment.provider, PaymentsByPaymentMethod(provider=payment.provider))

            if payment.status == "open":
                result.num_new += 1
            elif payment.status == "paid":
                result.num_ok += 1
            elif payment.status == "expired":
                result.num_fail += 1
            elif payment.status == "complete":
                result.num_delayed += 1
            else:
                raise NotImplementedError(payment.status)

        total_row = PaymentsByPaymentMethod(provider="Total")
        for result in results.values():
            total_row.num_new += result.num_new
            total_row.num_ok += result.num_ok
            total_row.num_fail += result.num_fail
            total_row.num_delayed += result.num_delayed

        results_sorted = sorted(results.values(), key=lambda result: result.num_total, reverse=True)
        results_sorted.append(total_row)

        return results_sorted

    @classmethod
    def get_orders_by_payment_status(cls, event):
        with connection.cursor() as cursor:
            cursor.execute(OrdersByPaymentStatus.QUERY, [event.id])
            (one_row,) = cursor.fetchall()

        return OrdersByPaymentStatus(*one_row)
