import re

from django import forms
from django.contrib.auth.forms import (
    UserCreationForm,
    AuthenticationForm
)

from .models import User


class RegisterForm(UserCreationForm):

    email = forms.EmailField(required=True)

    phone = forms.CharField(required=False)

    company_name = forms.CharField(required=False)

    class Meta:
        model = User

        fields = [
            'username',
            'email',
            'phone',
            'company_name',
            'password1',
            'password2'
        ]

    def clean_email(self):
        email = self.cleaned_data['email'].lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "This email is already registered."
            )

        return email

    def clean_password1(self):
        password = self.cleaned_data['password1']

        if len(password) <= 8:
            raise forms.ValidationError(
                "Password must contain more than 8 characters."
            )

        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError(
                "Password must contain an uppercase letter."
            )

        if not re.search(r'[a-z]', password):
            raise forms.ValidationError(
                "Password must contain a lowercase letter."
            )

        if not re.search(r'[^A-Za-z0-9]', password):
            raise forms.ValidationError(
                "Password must contain a special character."
            )

        return password


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={'placeholder': 'Username'}
        )
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Password'}
        )
    )