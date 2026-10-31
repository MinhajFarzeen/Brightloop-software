from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import get_random_string
from decimal import Decimal


# ==================================
# 1. QUOTATION TEMPLATE
# ==================================

class QuotationTemplate(models.Model):

    name = models.CharField(max_length=150)

    plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan',
        on_delete=models.PROTECT
    )

    validity_days = models.PositiveIntegerField(default=30)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class QuotationTemplateLine(models.Model):

    template = models.ForeignKey(
        QuotationTemplate,
        on_delete=models.CASCADE,
        related_name='lines'
    )

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT
    )

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def __str__(self):
        return self.product.name


# ==================================
# 2. QUOTATION
# ==================================

class Quotation(models.Model):

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('CONFIRMED', 'Confirmed'),
        ('CONVERTED', 'Converted'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]

    quotation_number = models.CharField(
        max_length=30,
        unique=True,
        blank=True
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='quotations'
    )

    template = models.ForeignKey(
        QuotationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan',
        on_delete=models.PROTECT
    )

    quotation_date = models.DateField(
        default=timezone.localdate
    )

    valid_until = models.DateField()

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )

    converted_subscription = models.OneToOneField(
        'subscriptions.Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_quotation'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        if not self.quotation_number:
            self.quotation_number = (
                'QUO-' + get_random_string(12).upper()
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.quotation_number


class QuotationLine(models.Model):

    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name='lines'
    )

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    @property
    def subtotal(self):
        return self.quantity * self.unit_price


# ==================================
# 3. TAX
# ==================================

class Tax(models.Model):

    name = models.CharField(max_length=100)

    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


# ==================================
# 4. DISCOUNT
# ==================================

class Discount(models.Model):

    DISCOUNT_TYPES = [
        ('FIXED', 'Fixed Amount'),
        ('PERCENTAGE', 'Percentage'),
    ]

    name = models.CharField(max_length=150)

    discount_type = models.CharField(
        max_length=15,
        choices=DISCOUNT_TYPES
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    minimum_purchase = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    minimum_quantity = models.PositiveIntegerField(default=1)

    start_date = models.DateField()

    end_date = models.DateField()

    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    times_used = models.PositiveIntegerField(default=0)

    products = models.ManyToManyField(
        'products.Product',
        blank=True
    )

    is_active = models.BooleanField(default=True)

    def clean(self):

        if self.value <= 0:
            raise ValidationError(
                "Discount value must be greater than zero."
            )

        if self.discount_type == 'PERCENTAGE' and self.value > 100:
            raise ValidationError(
                "Percentage discount cannot exceed 100."
            )

        if self.end_date < self.start_date:
            raise ValidationError(
                "End date cannot be before start date."
            )

    def is_valid(self, subtotal, quantity, today=None):

        today = today or timezone.localdate()

        if not self.is_active:
            return False

        if today < self.start_date or today > self.end_date:
            return False

        if subtotal < self.minimum_purchase:
            return False

        if quantity < self.minimum_quantity:
            return False

        if (
            self.usage_limit is not None
            and self.times_used >= self.usage_limit
        ):
            return False

        return True

    def __str__(self):
        return self.name


# ==================================
# 5. INVOICE
# ==================================

class Invoice(models.Model):

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('CONFIRMED', 'Confirmed'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
    ]

    invoice_number = models.CharField(
        max_length=30,
        unique=True,
        blank=True
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='invoices'
    )

    subscription = models.ForeignKey(
        'subscriptions.Subscription',
        on_delete=models.PROTECT,
        related_name='invoices'
    )

    invoice_date = models.DateField(
        default=timezone.localdate
    )

    due_date = models.DateField()

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )

    discount = models.ForeignKey(
        Discount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        if not self.invoice_number:
            self.invoice_number = (
                'INV-' + get_random_string(12).upper()
            )

        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return max(
            self.total_amount - self.amount_paid,
            Decimal('0.00')
        )

    @property
    def is_overdue(self):
        return (
            self.status not in ['PAID', 'CANCELLED']
            and self.due_date < timezone.localdate()
            and self.balance_due > 0
        )

    def __str__(self):
        return self.invoice_number


class InvoiceLine(models.Model):

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines'
    )

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT
    )

    description = models.CharField(max_length=200)

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def tax_amount(self):
        return (
            self.subtotal
            * self.tax_rate
            / Decimal('100')
        )

    @property
    def total_amount(self):
        return self.subtotal + self.tax_amount


# ==================================
# 6. PAYMENT
# ==================================

class Payment(models.Model):

    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('UPI', 'UPI'),
        ('BANK', 'Bank Transfer'),
        ('OTHER', 'Other'),
    ]

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payments'
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHODS
    )

    payment_date = models.DateField(
        default=timezone.localdate
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True
    )

    note = models.TextField(blank=True)

    def __str__(self):
        return f"Payment for {self.invoice.invoice_number}"