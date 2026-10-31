from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django import forms

from .models import Product, ProductVariant
from accounts.views import staff_required


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product

        fields = [
            'name',
            'product_type',
            'sales_price',
            'cost_price',
            'notes',
            'is_active'
        ]


class VariantForm(forms.ModelForm):

    class Meta:
        model = ProductVariant

        fields = [
            'name',
            'additional_price'
        ]


@staff_required
def product_list(request):

    products = Product.objects.prefetch_related(
        'variants'
    ).order_by('name')

    return render(
        request,
        'products.html',
        {'products': products}
    )


@staff_required
def add_product(request):

    if request.method == 'POST':

        form = ProductForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Product added successfully!'
            )

            return redirect('products')

    else:
        form = ProductForm()

    return render(
        request,
        'products.html',
        {
            'form': form,
            'action': 'Add'
        }
    )


@staff_required
def edit_product(request, product_id):

    product = get_object_or_404(
        Product,
        id=product_id
    )

    if request.method == 'POST':

        form = ProductForm(
            request.POST,
            instance=product
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Product updated successfully!'
            )

            return redirect('products')

    else:
        form = ProductForm(instance=product)

    return render(
        request,
        'products.html',
        {
            'form': form,
            'action': 'Edit',
            'product': product
        }
    )


@staff_required
def delete_product(request, product_id):

    product = get_object_or_404(
        Product,
        id=product_id
    )

    if request.method == 'POST':
        product.delete()

        messages.success(
            request,
            'Product deleted successfully!'
        )

    return redirect('products')


@staff_required
def add_variant(request, product_id):

    product = get_object_or_404(
        Product,
        id=product_id
    )

    if request.method == 'POST':

        form = VariantForm(request.POST)

        if form.is_valid():

            variant = form.save(commit=False)
            variant.product = product
            variant.save()

            messages.success(
                request,
                'Variant added successfully!'
            )

            return redirect('products')

    else:
        form = VariantForm()

    return render(
        request,
        'products.html',
        {
            'form': form,
            'product': product,
            'action': 'Add Variant'
        }
    )