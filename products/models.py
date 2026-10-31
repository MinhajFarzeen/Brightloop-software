from django.db import models


class Product(models.Model):
    PRODUCT_TYPES = [
        ('SOFTWARE', 'Software'),
        ('SERVICE', 'Service'),
        ('ADDON', 'Add-on'),
        ('OTHER', 'Other'),
    ]

    name = models.CharField(max_length=200)
    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPES,
        default='SOFTWARE'
    )
    sales_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def _str_(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    name = models.CharField(max_length=150)
    additional_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    @property
    def final_price(self):
        return self.product.sales_price + self.additional_price

    def _str_(self):
        return f"{self.product.name} - {self.name}"