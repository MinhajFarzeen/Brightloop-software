from calendar import monthrange
from datetime import date, timedelta

from django import forms
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import SubscriptionPlan, Subscription, SubscriptionLine
from products.models import Product, ProductVariant
from accounts.views import staff_required, admin_required

User = get_user_model()


# -----------------------------
# SUBSCRIPTION PLAN FORM
# -----------------------------

class PlanForm(forms.ModelForm):

    class Meta:
        model = SubscriptionPlan

        fields = [
            'name',
            'product',
            'price',
            'billing_interval',
            'minimum_quantity',
            'available_from',
            'available_until',
            'auto_close',
            'is_active'
        ]

        widgets = {
            'available_from': forms.DateInput(
                attrs={'type': 'date'}
            ),
            'available_until': forms.DateInput(
                attrs={'type': 'date'}
            ),
        }


# -----------------------------
# SUBSCRIPTION FORM
# -----------------------------

class SubscriptionForm(forms.ModelForm):

    quantity = forms.IntegerField(
        min_value=1,
        initial=1
    )

    variant = forms.ModelChoiceField(
        queryset=ProductVariant.objects.none(),
        required=False
    )

    class Meta:
        model = Subscription

        fields = [
            'customer',
            'plan',
            'start_date',
            'expiry_date',
            'payment_terms'
        ]

        widgets = {
            'start_date': forms.DateInput(
                attrs={'type': 'date'}
            ),
            'expiry_date': forms.DateInput(
                attrs={'type': 'date'}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):

        super().__init__(*args, **kwargs)

        self.user = user

        self.fields['plan'].queryset = (
            SubscriptionPlan.objects.filter(
                is_active=True
            ).select_related('product')
        )

        self.fields['variant'].queryset = (
            ProductVariant.objects.select_related('product')
        )

        if user and user.role == 'CUSTOMER':
            self.fields.pop('customer')

        else:
            self.fields['customer'].queryset = User.objects.filter(
                role='CUSTOMER'
            )

    def clean(self):

        cleaned_data = super().clean()

        plan = cleaned_data.get('plan')
        start_date = cleaned_data.get('start_date')
        expiry_date = cleaned_data.get('expiry_date')
        quantity = cleaned_data.get('quantity')
        variant = cleaned_data.get('variant')

        if start_date and expiry_date:
            if expiry_date <= start_date:
                self.add_error(
                    'expiry_date',
                    'Expiry date must be after start date.'
                )

        if plan and start_date:

            if start_date < plan.available_from:
                self.add_error(
                    'start_date',
                    'This plan is not available yet.'
                )

            if (
                plan.available_until
                and start_date > plan.available_until
            ):
                self.add_error(
                    'start_date',
                    'This plan is no longer available.'
                )

        if plan and quantity:
            if quantity < plan.minimum_quantity:
                self.add_error(
                    'quantity',
                    f'Minimum quantity is {plan.minimum_quantity}.'
                )

        if plan and variant:
            if variant.product_id != plan.product_id:
                self.add_error(
                    'variant',
                    'This variant does not belong to the selected plan product.'
                )

        return cleaned_data


# -----------------------------
# PLAN MANAGEMENT
# -----------------------------

@staff_required
def plan_list(request):

    plans = SubscriptionPlan.objects.select_related(
        'product'
    ).order_by('name')

    return render(
        request,
        'plans.html',
        {'plans': plans}
    )


@admin_required
def add_plan(request):

    if request.method == 'POST':

        form = PlanForm(request.POST)

        if form.is_valid():
            plan = form.save(commit=False)

            try:
                plan.full_clean()
                plan.save()

                messages.success(
                    request,
                    'Subscription plan created successfully!'
                )

                return redirect('plans')

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = PlanForm()

    return render(
        request,
        'plans.html',
        {
            'form': form,
            'action': 'Add Plan'
        }
    )


@admin_required
def edit_plan(request, plan_id):

    plan = get_object_or_404(
        SubscriptionPlan,
        id=plan_id
    )

    if request.method == 'POST':

        form = PlanForm(
            request.POST,
            instance=plan
        )

        if form.is_valid():

            try:
                updated_plan = form.save(commit=False)
                updated_plan.full_clean()
                updated_plan.save()

                messages.success(
                    request,
                    'Plan updated successfully!'
                )

                return redirect('plans')

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = PlanForm(instance=plan)

    return render(
        request,
        'plans.html',
        {
            'form': form,
            'action': 'Edit Plan',
            'plan': plan
        }
    )


@admin_required
@require_POST
def delete_plan(request, plan_id):

    plan = get_object_or_404(
        SubscriptionPlan,
        id=plan_id
    )

    if plan.subscriptions.exists():
        messages.error(
            request,
            'Cannot delete a plan that has subscriptions.'
        )
    else:
        plan.delete()

        messages.success(
            request,
            'Plan deleted successfully!'
        )

    return redirect('plans')


# -----------------------------
# SUBSCRIPTION MANAGEMENT
# -----------------------------

def subscription_list(request):

    if not request.user.is_authenticated:
        return redirect('login')

    # Automatically close expired subscriptions
    # only when their associated plan has auto_close enabled.

    today = timezone.localdate()

    Subscription.objects.filter(
        status='ACTIVE',
        expiry_date__lt=today,
        plan__auto_close=True
    ).update(status='CLOSED')

    if request.user.role == 'CUSTOMER':
        subscriptions = Subscription.objects.filter(
            customer=request.user
        )
    elif (
        request.user.role in ['ADMIN', 'STAFF']
        or request.user.is_superuser
    ):
        subscriptions = Subscription.objects.all()
    else:
        subscriptions = Subscription.objects.none()

    subscriptions = subscriptions.select_related(
        'customer',
        'plan',
        'plan__product'
    ).prefetch_related('lines').order_by('-created_at')

    return render(
        request,
        'subscriptions.html',
        {'subscriptions': subscriptions}
    )


@login_required
def create_subscription(request):

    if request.user.role not in [
        'ADMIN', 'STAFF', 'CUSTOMER'
    ] and not request.user.is_superuser:

        return redirect('dashboard')

    if request.method == 'POST':

        form = SubscriptionForm(
            request.POST,
            user=request.user
        )

        if form.is_valid():

            with transaction.atomic():

                subscription = form.save(commit=False)

                if request.user.role == 'CUSTOMER':
                    subscription.customer = request.user

                subscription.status = 'DRAFT'

                try:
                    subscription.full_clean()
                    subscription.save()

                    plan = subscription.plan
                    variant = form.cleaned_data['variant']
                    quantity = form.cleaned_data['quantity']

                    unit_price = plan.price

                    if variant:
                        unit_price += variant.additional_price

                    SubscriptionLine.objects.create(
                        subscription=subscription,
                        product=plan.product,
                        variant=variant,
                        quantity=quantity,
                        unit_price=unit_price
                    )

                    messages.success(
                        request,
                        'Subscription created successfully!'
                    )

                    return redirect('subscriptions')

                except ValidationError as error:
                    form.add_error(None, error)

    else:
        form = SubscriptionForm(user=request.user)

    return render(
        request,
        'subscriptions.html',
        {
            'form': form,
            'action': 'Create Subscription'
        }
    )


@login_required
def subscription_detail(request, subscription_id):

    subscription = get_object_or_404(
        Subscription.objects.select_related(
            'customer',
            'plan',
            'plan__product'
        ).prefetch_related('lines'),
        id=subscription_id
    )

    if (
        request.user.role == 'CUSTOMER'
        and subscription.customer != request.user
    ):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if request.user.role not in [
        'ADMIN', 'STAFF', 'CUSTOMER'
    ] and not request.user.is_superuser:

        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    return render(
        request,
        'subscriptions.html',
        {
            'subscription': subscription,
            'detail_view': True
        }
    )


# -----------------------------
# SUBSCRIPTION STATUS CHANGES
# -----------------------------

STATUS_TRANSITIONS = {
    'DRAFT': ['QUOTATION'],
    'QUOTATION': ['CONFIRMED', 'CLOSED'],
    'CONFIRMED': ['ACTIVE', 'CLOSED'],
    'ACTIVE': ['PAUSED', 'CLOSED'],
    'PAUSED': ['ACTIVE', 'CLOSED'],
    'CLOSED': [],
}


@login_required
@require_POST
def change_subscription_status(request, subscription_id):

    subscription = get_object_or_404(
        Subscription,
        id=subscription_id
    )

    if (
        request.user.role == 'CUSTOMER'
        and subscription.customer != request.user
    ):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if (
        request.user.role not in ['ADMIN', 'STAFF']
        and not request.user.is_superuser
    ):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    new_status = request.POST.get('status')

    allowed_statuses = STATUS_TRANSITIONS.get(
        subscription.status,
        []
    )

    if new_status not in allowed_statuses:

        messages.error(
            request,
            'Invalid subscription status change.'
        )

    else:

        if new_status == 'ACTIVE':
            if subscription.expiry_date < timezone.localdate():
                messages.error(
                    request,
                    'An expired subscription cannot be activated.'
                )
                return redirect(
                    'subscription_detail',
                    subscription_id=subscription.id
                )

        subscription.status = new_status
        subscription.save()

        messages.success(
            request,
            f'Subscription status changed to {new_status}.'
        )

    return redirect(
        'subscription_detail',
        subscription_id=subscription.id
    )


# -----------------------------
# SUBSCRIPTION RENEWAL
# -----------------------------

def add_billing_period(start_date, interval):

    if interval == 'DAILY':
        return start_date + timedelta(days=1)

    if interval == 'WEEKLY':
        return start_date + timedelta(weeks=1)

    if interval == 'MONTHLY':

        month = start_date.month + 1
        year = start_date.year

        if month > 12:
            month = 1
            year += 1

        day = min(
            start_date.day,
            monthrange(year, month)[1]
        )

        return date(year, month, day)

    if interval == 'YEARLY':

        year = start_date.year + 1

        day = min(
            start_date.day,
            monthrange(year, start_date.month)[1]
        )

        return date(year, start_date.month, day)

    return start_date


@login_required
@require_POST
def renew_subscription(request, subscription_id):

    subscription = get_object_or_404(
        Subscription,
        id=subscription_id
    )

    if (
        request.user.role == 'CUSTOMER'
        and subscription.customer != request.user
    ):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if (
        request.user.role not in ['ADMIN', 'STAFF']
        and not request.user.is_superuser
    ):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if subscription.status not in ['ACTIVE', 'CLOSED']:

        messages.error(
            request,
            'Only active or closed subscriptions can be renewed.'
        )

    else:

        today = timezone.localdate()

        renewal_start = max(
            subscription.expiry_date,
            today
        )

        new_expiry = add_billing_period(
            renewal_start,
            subscription.plan.billing_interval
        )

        subscription.expiry_date = new_expiry
        subscription.status = 'ACTIVE'

        subscription.save()

        messages.success(
            request,
            'Subscription renewed successfully!'
        )

    return redirect(
        'subscription_detail',
        subscription_id=subscription.id
    )

# Create your views here.
