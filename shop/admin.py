from django.contrib import admin
from .models import Product, Customer, Bill, BillItem, NewsletterSubscriber, Brand, WalkinCustomer

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'brand',
        'price',
        'stock',
        'is_offer',
        'offer_percent'
    )

    list_editable = (
        'is_offer',
        'offer_percent'
    )

    list_filter = ('is_offer',)

# ---------- CUSTOMER ----------
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'address')


# ---------- BILL ITEMS INLINE ----------
class BillItemInline(admin.TabularInline):
    model = BillItem
    extra = 1


# ---------- BILL ----------
@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'total_amount',
        'payment_status',
        'order_status',
        'created_at'
    )

    list_editable = ('order_status',)
    inlines = [BillItemInline]


# ---------- NEWSLETTER ----------
@admin.register(NewsletterSubscriber)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('email', 'subscribed_at')