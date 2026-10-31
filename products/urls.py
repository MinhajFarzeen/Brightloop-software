from django.urls import path
from . import views

urlpatterns = [

    path(
        '',
        views.product_list,
        name='products'
    ),

    path(
        'add/',
        views.add_product,
        name='add_product'
    ),

    path(
        'edit/<int:product_id>/',
        views.edit_product,
        name='edit_product'
    ),

    path(
        'delete/<int:product_id>/',
        views.delete_product,
        name='delete_product'
    ),

    path(
        '<int:product_id>/add-variant/',
        views.add_variant,
        name='add_variant'
    ),
]