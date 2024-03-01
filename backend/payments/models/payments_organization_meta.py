from datetime import UTC, datetime
from uuid import uuid4

from django.db import models

META_DEFAULTS = dict(
    checkout_password="SAIPPUAKAUPPIAS",
    checkout_merchant="375917",
    # No common dev secrets for Stripe. You have to create your own account and get secret from https://dashboard.stripe.com/apikeys
    # Personal nonverified account is enough for testing
    stripe_api_secret="",
    # Dev webhook key you can get from 'stripe listen --forward-to localhost:8000/payments/stripe/callbacks/success'
    # or create public URL webhook https://dashboard.stripe.com/test/webhooks
    stripe_webhook_secret="",
)


class PaymentsOrganizationMeta(models.Model):
    organization = models.OneToOneField("core.Organization", on_delete=models.CASCADE, primary_key=True)
    checkout_password = models.CharField(max_length=255)
    checkout_merchant = models.CharField(max_length=255)
    stripe_api_secret = models.CharField(max_length=255)
    stripe_webhook_secret = models.CharField(max_length=255)

    @classmethod
    def get_or_create_dummy(cls, organization=None):
        """
        Creates a POM with Checkout test merchant. Suitable for development, but try to use it in production and you'll get 500 ISE.
        """
        from core.models import Organization

        if organization is None:
            organization, uwused = Organization.get_or_create_dummy()

        return cls.objects.get_or_create(
            organization=organization,
            defaults=META_DEFAULTS,
        )

    def get_checkout_params(self, method="POST", t=None):
        if t is None:
            t = datetime.now(UTC)

        return {
            "checkout-account": self.checkout_merchant,
            "checkout-algorithm": "sha256",
            "checkout-method": method,
            "checkout-nonce": str(uuid4()),
            "checkout-timestamp": t.isoformat(),
        }
