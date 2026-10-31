from django.urls import path
from . import views

urlpatterns = [

    # Subscription plans
    path(
        'plans/',
        views.plan_list,
        name='plans'
    ),

    path(
        'plans/add/',
        views.add_plan,
        name='add_plan'
    ),

    path(
        'plans/edit/<int:plan_id>/',
        views.edit_plan,
        name='edit_plan'
    ),

    path(
        'plans/delete/<int:plan_id>/',
        views.delete_plan,
        name='delete_plan'
    ),

    # Subscriptions
    path(
        '',
        views.subscription_list,
        name='subscriptions'
    ),

    path(
        'create/',
        views.create_subscription,
        name='create_subscription'
    ),

    path(
        '<int:subscription_id>/',
        views.subscription_detail,
        name='subscription_detail'
    ),

    path(
        '<int:subscription_id>/change-status/',
        views.change_subscription_status,
        name='change_subscription_status'
    ),

    path(
        '<int:subscription_id>/renew/',
        views.renew_subscription,
        name='renew_subscription'
    ),
]