from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    QuotationTemplate,
    QuotationTemplateLine,
    Quotation,
    QuotationLine,
    Tax,
    Discount,
    Invoice,
    InvoiceLine,
    Payment
)

from subscriptions.models import (
    Subscription,
    SubscriptionLine
)

from subscriptions.views import add_billing_period
from accounts.views import staff_required, admin_required

User = get_user_model()

CENT = Decimal('0.01')


def money(value):
    return Decimal(value).quantize(
        CENT,
        rounding=ROUND_HALF_UP
    )


# ==========================================
# 1. FORMS
# ==========================================

class QuotationForm(forms.ModelForm):

    class Meta:
        model = Quotation

        fields = [
            'customer',
            'template',
            'plan',
            'quotation_date',
            'valid_until'
        ]

        widgets = {
            'quotation_date': forms.DateInput(
                attrs={'type': 'date'}
            ),
            'valid_until': forms.DateInput(
                attrs={'type': 'date'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['customer'].queryset = User.objects.filter(
            role='CUSTOMER'
        )


class PaymentForm(forms.ModelForm):

    class Meta:
        model = Payment

        fields = [
            'amount',
            'payment_method',
            'payment_date',
            'reference_number',
            'note'
        ]

        widgets = {
            'payment_date': forms.DateInput(
                attrs={'type': 'date'}
            )
        }


# ==========================================
# 2. QUOTATION TEMPLATE MANAGEMENT
# ==========================================

@admin_required
def create_quotation_template(request):

    if request.method == 'POST':

        name = request.POST.get('name')
        plan_id = request.POST.get('plan')
        validity = request.POST.get('validity_days', 30)

        try:
            plan = Subscription.objects.none()
            from subscriptions.models import SubscriptionPlan

            plan = get_object_or_404(
                SubscriptionPlan,
                id=plan_id
            )

            validity = int(validity)

            if validity < 1:
                raise ValueError

            template = QuotationTemplate.objects.create(
                name=name,
                plan=plan,
                validity_days=validity
            )

            QuotationTemplateLine.objects.create(
                template=template,
                product=plan.product,
                quantity=plan.minimum_quantity,
                unit_price=plan.price
            )

            messages.success(
                request,
                'Quotation template created successfully!'
            )

            return redirect('quotation_templates')

        except (ValueError, TypeError):
            messages.error(
                request,
                'Please enter valid template details.'
            )

    templates = QuotationTemplate.objects.select_related(
        'plan',
        'plan__product'
    )

    from subscriptions.models import SubscriptionPlan

    plans = SubscriptionPlan.objects.filter(
        is_active=True
    )

    return render(
        request,
        'quotations.html',
        {
            'templates': templates,
            'plans': plans,
            'template_form': True
        }
    )


@staff_required
def quotation_template_list(request):

    templates = QuotationTemplate.objects.select_related(
        'plan',
        'plan__product'
    ).prefetch_related('lines')

    return render(
        request,
        'quotations.html',
        {'templates': templates}
    )


# ==========================================
# 3. CREATE QUOTATION
# ==========================================

@staff_required
def create_quotation(request):

    if request.method == 'POST':

        form = QuotationForm(request.POST)

        if form.is_valid():

            quotation = form.save(commit=False)

            template = quotation.template

            if template:
                quotation.plan = template.plan

                quotation.valid_until = (
                    quotation.quotation_date
                    + timedelta(days=template.validity_days)
                )

            if quotation.valid_until < quotation.quotation_date:
                form.add_error(
                    'valid_until',
                    'Validity date cannot be before quotation date.'
                )

            else:

                with transaction.atomic():

                    quotation.save()

                    if template:
                        for line in template.lines.all():

                            QuotationLine.objects.create(
                                quotation=quotation,
                                product=line.product,
                                quantity=line.quantity,
                                unit_price=line.unit_price
                            )

                    messages.success(
                        request,
                        'Quotation created successfully!'
                    )

                    return redirect('quotations')

    else:
        form = QuotationForm()

    return render(
        request,
        'quotations.html',
        {
            'form': form,
            'action': 'Create Quotation'
        }
    )


@staff_required
def quotation_list(request):

    quotations = Quotation.objects.select_related(
        'customer',
        'plan'
    ).prefetch_related('lines').order_by('-created_at')

    return render(
        request,
        'quotations.html',
        {'quotations': quotations}
    )


# ==========================================
# 4. CONFIRM QUOTATION
# ==========================================

@staff_required
@require_POST
def confirm_quotation(request, quotation_id):

    quotation = get_object_or_404(
        Quotation,
        id=quotation_id
    )

    if quotation.status != 'DRAFT' and quotation.status != 'SENT':

        messages.error(
            request,
            'This quotation cannot be confirmed.'
        )

    elif quotation.valid_until < timezone.localdate():

        quotation.status = 'EXPIRED'
        quotation.save()

        messages.error(
            request,
            'This quotation has expired.'
        )

    else:

        quotation.status = 'CONFIRMED'
        quotation.save()

        messages.success(
            request,
            'Quotation confirmed successfully!'
        )

    return redirect('quotations')


# ==========================================
# 5. CONVERT QUOTATION INTO SUBSCRIPTION
# ==========================================

@staff_required
@require_POST
def convert_quotation(request, quotation_id):

    quotation = get_object_or_404(
        Quotation.objects.select_related(
            'customer',
            'plan'
        ).prefetch_related('lines'),
        id=quotation_id
    )

    if quotation.status != 'CONFIRMED':

        messages.error(
            request,
            'Only confirmed quotations can be converted.'
        )

        return redirect('quotations')

    if quotation.valid_until < timezone.localdate():

        quotation.status = 'EXPIRED'
        quotation.save()

        messages.error(
            request,
            'This quotation has expired.'
        )

        return redirect('quotations')

    if not quotation.lines.exists():

        messages.error(
            request,
            'Quotation must contain at least one product.'
        )

        return redirect('quotations')

    from subscriptions.views import add_billing_period

    with transaction.atomic():

        quotation = Quotation.objects.select_for_update().get(
            id=quotation_id
        )

        if quotation.status != 'CONFIRMED':
            messages.error(
                request,
                'This quotation has already been processed.'
            )
            return redirect('quotations')

        today = timezone.localdate()

        expiry = add_billing_period(
            today,
            quotation.plan.billing_interval
        )

        subscription = Subscription.objects.create(
            customer=quotation.customer,
            plan=quotation.plan,
            start_date=today,
            expiry_date=expiry,
            payment_terms='Due on receipt',
            status='CONFIRMED'
        )

        for line in quotation.lines.all():

            SubscriptionLine.objects.create(
                subscription=subscription,
                product=line.product,
                quantity=line.quantity,
                unit_price=line.unit_price
            )

        quotation.status = 'CONVERTED'
        quotation.converted_subscription = subscription

        quotation.save()

    messages.success(
        request,
        'Quotation converted into subscription successfully!'
    )

    return redirect('subscriptions')


# ==========================================
# 6. TAX MANAGEMENT
# ==========================================

@admin_required
def add_tax(request):

    if request.method == 'POST':

        name = request.POST.get('name')
        rate = request.POST.get('rate')

        try:

            rate = Decimal(rate)

            if not name.strip() or rate < 0 or rate > 100:
                raise ValueError

            Tax.objects.create(
                name=name.strip(),
                rate=rate
            )

            messages.success(
                request,
                'Tax created successfully!'
            )

            return redirect('taxes')

        except (ValueError, TypeError, ArithmeticError):
            messages.error(
                request,
                'Enter a valid tax name and rate between 0 and 100.'
            )

    taxes = Tax.objects.all()

    return render(
        request,
        'invoices.html',
        {
            'taxes': taxes,
            'tax_form': True
        }
    )


@staff_required
def tax_list(request):

    taxes = Tax.objects.all()

    return render(
        request,
        'invoices.html',
        {'taxes': taxes}
    )


# ==========================================
# 7. DISCOUNT MANAGEMENT
# ==========================================

@admin_required
def add_discount(request):

    if request.method == 'POST':

        try:

            discount = Discount(
                name=request.POST.get('name'),
                discount_type=request.POST.get('discount_type'),
                value=Decimal(request.POST.get('value')),
                minimum_purchase=Decimal(
                    request.POST.get('minimum_purchase', '0')
                ),
                minimum_quantity=int(
                    request.POST.get('minimum_quantity', '1')
                ),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                usage_limit=(
                    int(request.POST['usage_limit'])
                    if request.POST.get('usage_limit')
                    else None
                )
            )

            discount.full_clean()
            discount.save()

            product_ids = request.POST.getlist('products')
            discount.products.set(
                product_ids
            )

            messages.success(
                request,
                'Discount created successfully!'
            )

            return redirect('discounts')

        except (
            ValueError,
            TypeError,
            ValidationError
        ):
            messages.error(
                request,
                'Please enter valid discount details.'
            )

    discounts = Discount.objects.prefetch_related('products')
    products = __import__(
        'products.models',
        fromlist=['Product']
    ).Product.objects.filter(is_active=True)

    return render(
        request,
        'invoices.html',
        {
            'discounts': discounts,
            'products': products,
            'discount_form': True
        }
    )


@staff_required
def discount_list(request):

    discounts = Discount.objects.prefetch_related('products')

    return render(
        request,
        'invoices.html',
        {'discounts': discounts}
    )


# ==========================================
# 8. CALCULATE DISCOUNT
# ==========================================

def calculate_discount(discount, subtotal, quantity):

    if not discount:
        return Decimal('0.00')

    if not discount.is_valid(subtotal, quantity):
        return Decimal('0.00')

    if discount.discount_type == 'FIXED':

        amount = discount.value

    else:

        amount = (
            subtotal * discount.value / Decimal('100')
        )

    return min(
        money(amount),
        money(subtotal)
    )


# ==========================================
# 9. GENERATE INVOICE
# ==========================================

@staff_required
@require_POST
def generate_invoice(request, subscription_id):

    subscription = get_object_or_404(
        Subscription.objects.select_related(
            'customer',
            'plan'
        ).prefetch_related('lines'),
        id=subscription_id
    )

    today = timezone.localdate()

    if subscription.status != 'ACTIVE':

        messages.error(
            request,
            'Invoices can only be generated for active subscriptions.'
        )

        return redirect('subscriptions')

    if subscription.expiry_date < today:

        messages.error(
            request,
            'This subscription has expired.'
        )

        return redirect('subscriptions')

    with transaction.atomic():

        existing = Invoice.objects.filter(
            subscription=subscription,
            invoice_date=today
        ).exists()

        if existing:

            messages.warning(
                request,
                'An invoice has already been generated today.'
            )

            return redirect('invoices')

        lines = list(subscription.lines.all())

        if not lines:

            messages.error(
                request,
                'This subscription has no product lines.'
            )

            return redirect('subscriptions')

        invoice = Invoice.objects.create(
            customer=subscription.customer,
            subscription=subscription,
            invoice_date=today,
            due_date=today + timedelta(days=7),
            status='DRAFT'
        )

        subtotal = Decimal('0.00')
        tax_amount = Decimal('0.00')
        total_quantity = 0

        tax = Tax.objects.filter(
            is_active=True
        ).first()

        tax_rate = tax.rate if tax else Decimal('0.00')

        for line in lines:

            invoice_line = InvoiceLine.objects.create(
                invoice=invoice,
                product=line.product,
                description=line.product.name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate=tax_rate
            )

            subtotal += invoice_line.subtotal
            tax_amount += invoice_line.tax_amount
            total_quantity += line.quantity

        subtotal = money(subtotal)
        tax_amount = money(tax_amount)

        discount = Discount.objects.filter(
            is_active=True
        ).order_by('value').first()

        discount_amount = calculate_discount(
            discount,
            subtotal,
            total_quantity
        )

        # Use the discount only when it applies to
        # at least one of the subscription's products.
        if discount and discount.products.exists():

            product_ids = {
                line.product_id for line in lines
            }

            if not discount.products.filter(
                id__in=product_ids
            ).exists():

                discount = None
                discount_amount = Decimal('0.00')

        total = money(
            subtotal + tax_amount - discount_amount
        )

        invoice.subtotal = subtotal
        invoice.tax_amount = tax_amount
        invoice.discount = discount
        invoice.discount_amount = discount_amount
        invoice.total_amount = total

        invoice.save()

        if discount_amount > 0:
            discount.times_used += 1
            discount.save(update_fields=['times_used'])

    messages.success(
        request,
        'Invoice generated successfully!'
    )

    return redirect('invoices')


# ==========================================
# 10. RECURRING INVOICE GENERATION
# ==========================================

@staff_required
@require_POST
def generate_recurring_invoices(request):

    today = timezone.localdate()

    subscriptions = Subscription.objects.filter(
        status='ACTIVE',
        start_date__lte=today,
        expiry_date__gte=today
    ).select_related('plan', 'customer')

    generated = 0

    for subscription in subscriptions:

        last_invoice = Invoice.objects.filter(
            subscription=subscription
        ).exclude(
            status='CANCELLED'
        ).order_by('-invoice_date').first()

        if last_invoice:

            next_due = add_billing_period(
                last_invoice.invoice_date,
                subscription.plan.billing_interval
            )

        else:

            next_due = subscription.start_date

        if next_due > today:
            continue

        # Reuse the same invoice-generation logic.
        # Only one invoice per subscription per billing date.

        from django.test import RequestFactory

        factory = RequestFactory()

        fake_request = factory.post(
            f'/billing/generate/{subscription.id}/'
        )

        fake_request.user = request.user

        # Generate using a shared helper would be preferable
        # in a larger production system. This endpoint uses
        # the same public invoice-generation view.

        existing = Invoice.objects.filter(
            subscription=subscription,
            invoice_date=today
        ).exists()

        if existing:
            continue

        # Generate the invoice for this subscription.
        # This function is defined below.

        create_invoice_for_subscription(
            subscription,
            today
        )

        generated += 1

    messages.success(
        request,
        f'{generated} recurring invoices generated.'
    )

    return redirect('invoices')


def create_invoice_for_subscription(subscription, today):

    if Invoice.objects.filter(
        subscription=subscription,
        invoice_date=today
    ).exists():
        return None

    lines = list(subscription.lines.all())

    if not lines:
        return None

    with transaction.atomic():

        invoice = Invoice.objects.create(
            customer=subscription.customer,
            subscription=subscription,
            invoice_date=today,
            due_date=today + timedelta(days=7),
            status='CONFIRMED'
        )

        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')
        quantity = 0

        tax = Tax.objects.filter(
            is_active=True
        ).first()

        rate = tax.rate if tax else Decimal('0.00')

        for line in lines:

            invoice_line = InvoiceLine.objects.create(
                invoice=invoice,
                product=line.product,
                description=line.product.name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate=rate
            )

            subtotal += invoice_line.subtotal
            tax_total += invoice_line.tax_amount
            quantity += line.quantity

        subtotal = money(subtotal)
        tax_total = money(tax_total)

        discount = Discount.objects.filter(
            is_active=True
        ).order_by('value').first()

        discount_amount = calculate_discount(
            discount,
            subtotal,
            quantity
        )

        if discount and discount.products.exists():

            product_ids = {
                line.product_id for line in lines
            }

            if not discount.products.filter(
                id__in=product_ids
            ).exists():

                discount = None
                discount_amount = Decimal('0.00')

        invoice.subtotal = subtotal
        invoice.tax_amount = tax_total
        invoice.discount = discount
        invoice.discount_amount = discount_amount

        invoice.total_amount = money(
            subtotal + tax_total - discount_amount
        )

        invoice.save()

        if discount_amount > 0:
            discount.times_used += 1
            discount.save(update_fields=['times_used'])

    return invoice


# ==========================================
# 11. INVOICE MANAGEMENT
# ==========================================

@login_required
def invoice_list(request):

    if request.user.role == 'CUSTOMER':

        invoices = Invoice.objects.filter(
            customer=request.user
        )

    elif (
        request.user.role in ['ADMIN', 'STAFF']
        or request.user.is_superuser
    ):

        invoices = Invoice.objects.all()

    else:

        invoices = Invoice.objects.none()

    invoices = invoices.select_related(
        'customer',
        'subscription'
    ).prefetch_related(
        'lines',
        'payments'
    ).order_by('-created_at')

    return render(
        request,
        'invoices.html',
        {'invoices': invoices}
    )


@staff_required
@require_POST
def confirm_invoice(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if invoice.status != 'DRAFT':

        messages.error(
            request,
            'Only draft invoices can be confirmed.'
        )

    else:

        invoice.status = 'CONFIRMED'
        invoice.save()

        messages.success(
            request,
            'Invoice confirmed successfully!'
        )

    return redirect('invoices')


# ==========================================
# 12. RECORD PAYMENT
# ==========================================

@staff_required
@require_POST
def record_payment(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    form = PaymentForm(request.POST)

    if form.is_valid():

        with transaction.atomic():

            invoice = Invoice.objects.select_for_update().get(
                id=invoice_id
            )

            if invoice.status in ['DRAFT', 'CANCELLED']:

                messages.error(
                    request,
                    'This invoice cannot receive payments.'
                )

                return redirect('invoices')

            payment = form.save(commit=False)

            if payment.amount <= 0 or payment.amount > invoice.balance_due:

                messages.error(
                    request,
                    'Payment amount exceeds the outstanding balance.'
                )

                return redirect('invoices')

            payment.invoice = invoice
            payment.save()

            invoice.amount_paid += payment.amount

            if invoice.amount_paid >= invoice.total_amount:
                invoice.status = 'PAID'

            elif invoice.amount_paid > 0:
                invoice.status = 'PARTIAL'

            invoice.save(
                update_fields=['amount_paid', 'status']
            )

        messages.success(
            request,
            'Payment recorded successfully!'

        )

    else:

        messages.error(
            request,
            'Please enter valid payment details.'
        )

    return redirect('invoices')


# ==========================================
# 13. CANCEL INVOICE
# ==========================================

@staff_required
@require_POST
def cancel_invoice(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if invoice.amount_paid > 0:

        messages.error(
            request,
            'An invoice with recorded payments cannot be cancelled.'
        )

    elif invoice.status == 'PAID':

        messages.error(
            request,
            'Paid invoices cannot be cancelled.'
        )

    else:

        invoice.status = 'CANCELLED'
        invoice.save()

        messages.success(
            request,
            'Invoice cancelled successfully!'
        )

    return redirect('invoices')