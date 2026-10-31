from django.urls import path
from . import views

urlpatterns = [

    # Quotation templates
    path(
        'quotation-templates/',
        views.quotation_template_list,
        name='quotation_templates'
    ),

    path(
        'quotation-templates/add/',
        views.create_quotation_template,
        name='create_quotation_template'
    ),

    # Quotations
    path(
        'quotations/',
        views.quotation_list,
        name='quotations'
    ),

    path(
        'quotations/create/',
        views.create_quotation,
        name='create_quotation'
    ),

    path(
        'quotations/<int:quotation_id>/confirm/',
        views.confirm_quotation,
        name='confirm_quotation'
    ),

    path(
        'quotations/<int:quotation_id>/convert/',
        views.convert_quotation,
        name='convert_quotation'
    ),

    # Taxes
    path(
        'taxes/',
        views.tax_list,
        name='taxes'
    ),

    path(
        'taxes/add/',
        views.add_tax,
        name='add_tax'
    ),

    # Discounts
    path(
        'discounts/',
        views.discount_list,
        name='discounts'
    ),

    path(
        'discounts/add/',
        views.add_discount,
        name='add_discount'
    ),

    # Invoices
    path(
        'invoices/',
        views.invoice_list,
        name='invoices'
    ),

    path(
        'generate/<int:subscription_id>/',
        views.generate_invoice,
        name='generate_invoice'
    ),

    path(
        'generate-recurring/',
        views.generate_recurring_invoices,
        name='generate_recurring_invoices'
    ),

    path(
        'invoices/<int:invoice_id>/confirm/',
        views.confirm_invoice,
        name='confirm_invoice'
    ),

    path(
        'invoices/<int:invoice_id>/payment/',
        views.record_payment,
        name='record_payment'
    ),

    path(
        'invoices/<int:invoice_id>/cancel/',
        views.cancel_invoice,
        name='cancel_invoice'
    ),
]