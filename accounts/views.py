from functools import wraps

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.forms import (
    PasswordResetForm,
    SetPasswordForm
)
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetConfirmView
)

from .forms import RegisterForm, LoginForm
from .models import User


def register(request):

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(
                request,
                "Account created successfully!"
            )

            return redirect('dashboard')

    else:
        form = RegisterForm()

    return render(
        request,
        'register.html',
        {'form': form}
    )


def user_login(request):

    if request.method == 'POST':
        form = LoginForm(
            request,
            data=request.POST
        )

        if form.is_valid():
            user = form.get_user()
            login(request, user)

            return redirect('dashboard')

    else:
        form = LoginForm(request)

    return render(
        request,
        'login.html',
        {'form': form}
    )


@login_required
def user_logout(request):

    if request.method == 'POST':
        logout(request)
        return redirect('login')

    return redirect('dashboard')


def admin_required(view_func):

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        if not (
            request.user.is_superuser
            or request.user.role == 'ADMIN'
        ):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper


def staff_required(view_func):

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        if not (
    request.user.is_superuser
    or request.user.role in ['ADMIN', 'STAFF']
):
    raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper


@admin_required
def create_staff(request):

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            staff = form.save(commit=False)
            staff.role = 'STAFF'
            staff.save()

            messages.success(
                request,
                "Staff account created successfully!"
            )

            return redirect('dashboard')

    else:
        form = RegisterForm()

    return render(
        request,
        'register.html',
        {'form': form}
    )