from decimal import Decimal

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model 
from django.db import models
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from subscriptions.models import Subscription
from billing.models import Invoice, Payment

User = get_user_model()


@login_required
def dashboard(request):

    today = timezone.localdate()

    # ==================================
    # CUSTOMER DASHBOARD
    # ==================================

    if request.user.role == 'CUSTOMER' and not request.user.is_superuser:

        subscriptions = Subscription.objects.filter(
            customer=request.user
        )

        invoices = Invoice.objects.filter(
            customer=request.user
        )

        payments = Payment.objects.filter(
            invoice__customer=request.user
        )

        context = {

            'customer_dashboard': True,

            'total_subscriptions': subscriptions.count(),

            'active_subscriptions': subscriptions.filter(
                status='ACTIVE'
            ).count(),

            'paused_subscriptions': subscriptions.filter(
                status='PAUSED'
            ).count(),

            'total_invoices': invoices.count(),

            'pending_invoices': invoices.filter(
                status__in=['CONFIRMED', 'PARTIAL']
            ).count(),

            'overdue_invoices': invoices.filter(
                due_date__lt=today,
                amount_paid__lt=models.F('total_amount')
            ).exclude(
                status__in=['PAID', 'CANCELLED']
            ).count(),

            'total_paid': payments.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00'),

            'total_due': sum(
                (invoice.balance_due for invoice in invoices),
                Decimal('0.00')
            ),

            'recent_payments': payments.select_related(
                'invoice'
            ).order_by('-payment_date')[:5],

            'recent_invoices': invoices.order_by(
                '-created_at'
            )[:5],

        }

        return render(
            request,
            'dashboard.html',
            context
        )

    # ==================================
    # ADMIN AND STAFF DASHBOARD
    # ==================================

    if request.user.role not in ['ADMIN', 'STAFF'] and not request.user.is_superuser:

        return render(
            request,
            'dashboard.html',
            {
                'error': 'You do not have permission to access this dashboard.'
            }
        )

    subscriptions = Subscription.objects.all()

    invoices = Invoice.objects.all()

    payments = Payment.objects.all()

    # ==================================
    # REVENUE
    # ==================================

    total_revenue = payments.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    current_month_revenue = payments.filter(
        payment_date__year=today.year,
        payment_date__month=today.month
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # ==================================
    # SUBSCRIPTION STATISTICS
    # ==================================

    total_subscriptions = subscriptions.count()

    active_subscriptions = subscriptions.filter(
        status='ACTIVE'
    ).count()

    paused_subscriptions = subscriptions.filter(
        status='PAUSED'
    ).count()

    closed_subscriptions = subscriptions.filter(
        status='CLOSED'
    ).count()

    draft_subscriptions = subscriptions.filter(
        status='DRAFT'
    ).count()

    # ==================================
    # CUSTOMER STATISTICS
    # ==================================

    total_customers = User.objects.filter(
        role='CUSTOMER'
    ).count()

    total_staff = User.objects.filter(
        role='STAFF'
    ).count()

    # ==================================
    # INVOICE STATISTICS
    # ==================================

    total_invoices = invoices.exclude(
        status='CANCELLED'
    ).count()

    paid_invoices = invoices.filter(
        status='PAID'
    ).count()

    pending_invoices = invoices.filter(
        status__in=['CONFIRMED', 'PARTIAL']
    ).count()

    overdue_invoices = invoices.filter(
        due_date__lt=today,
        total_amount__gt=models.F('amount_paid')
    ).exclude(
        status__in=['PAID', 'CANCELLED']
    )

    overdue_count = overdue_invoices.count()

    total_outstanding = invoices.exclude(
        status__in=['PAID', 'CANCELLED']
    ).aggregate(
        total=Sum('total_amount') - Sum('amount_paid')
    )['total'] or Decimal('0.00')

    # ==================================
    # MONTHLY REVENUE
    # ==================================

    monthly_revenue = list(
        payments.annotate(
            month=TruncMonth('payment_date')
        ).values(
            'month'
        ).annotate(
            revenue=Sum('amount')
        ).order_by('month')
    )

    # ==================================
    # SUBSCRIPTION STATUS SUMMARY
    # ==================================

    subscription_summary = subscriptions.values(
        'status'
    ).annotate(
        count=Count('id')
    ).order_by('status')

    # ==================================
    # RECENT PAYMENTS
    # ==================================

    recent_payments = payments.select_related(
        'invoice',
        'invoice__customer'
    ).order_by('-payment_date')[:5]

    # ==================================
    # RECENT INVOICES
    # ==================================

    recent_invoices = invoices.select_related(
        'customer',
        'subscription'
    ).order_by('-created_at')[:5]

    # ==================================
    # DASHBOARD CONTEXT
    # ==================================

    context = {

        'customer_dashboard': False,

        'total_revenue': total_revenue,

        'current_month_revenue': current_month_revenue,

        'total_subscriptions': total_subscriptions,

        'active_subscriptions': active_subscriptions,

        'paused_subscriptions': paused_subscriptions,

        'closed_subscriptions': closed_subscriptions,

        'draft_subscriptions': draft_subscriptions,

        'total_customers': total_customers,

        'total_staff': total_staff,

        'total_invoices': total_invoices,

        'paid_invoices': paid_invoices,

        'pending_invoices': pending_invoices,

        'overdue_count': overdue_count,

        'total_outstanding': total_outstanding,

        'monthly_revenue': monthly_revenue,

        'subscription_summary': subscription_summary,

        'recent_payments': recent_payments,

        'recent_invoices': recent_invoices,

    }

    return render(
        request,
        'dashboard.html',
        context
    )