from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from django.core.validators import MinValueValidator
from decimal import Decimal
from calendar import monthrange
from datetime import date


class SubscriptionPlan(models.Model):

    BILLING_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('YEARLY', 'Yearly'),
    ]

    name = models.CharField(max_length=150)

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='plans'
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    billing_interval = models.CharField(
        max_length=10,
        choices=BILLING_CHOICES,
        default='MONTHLY'
    )

    minimum_quantity = models.PositiveIntegerField(default=1)

    available_from = models.DateField()

    available_until = models.DateField(
        null=True,
        blank=True
    )

    auto_close = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if (
            self.available_from
            and self.available_until
            and self.available_until < self.available_from
        ):
            raise ValidationError(
                "Availability end date cannot be before start date."
            )

    def __str__(self):
        return self.name


class Subscription(models.Model):

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('QUOTATION', 'Quotation'),
        ('CONFIRMED', 'Confirmed'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('CLOSED', 'Closed'),
    ]

    subscription_number = models.CharField(
        max_length=30,
        unique=True,
        blank=True
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )

    start_date = models.DateField()

    expiry_date = models.DateField()

    payment_terms = models.CharField(
        max_length=100,
        default='Due on receipt'
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):

        if not self.subscription_number:
            self.subscription_number = (
                'SUB-' + get_random_string(12).upper()
            )

        super().save(*args, **kwargs)

    def clean(self):

        if self.start_date and self.expiry_date:
            if self.expiry_date <= self.start_date:
                raise ValidationError(
                    "Expiry date must be after start date."
                )

        if self.plan_id and self.start_date:
            if self.start_date < self.plan.available_from:
                raise ValidationError(
                    "This plan is not available yet."
                )

            if (
                self.plan.available_until
                and self.start_date > self.plan.available_until
            ):
                raise ValidationError(
                    "This plan is no longer available."
                )

    def __str__(self):
        return self.subscription_number


class SubscriptionLine(models.Model):

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='lines'
    )

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT
    )

    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    @property
    def tax_amount(self):
        return (
            self.subtotal * self.tax_rate / Decimal('100')
        )

    @property
    def total_amount(self):
        return self.subtotal + self.tax_amount

    def clean(self):

        if self.quantity and self.subscription_id:
            if self.quantity < self.subscription.plan.minimum_quantity:
                raise ValidationError(
                    "Quantity is below the plan's minimum quantity."
                )

        if self.variant_id and self.product_id:
            if self.variant.product_id != self.product_id:
                raise ValidationError(
                    "Selected variant does not belong to this product."
                )

    def __str__(self):
        return f"{self.subscription} - {self.product}"