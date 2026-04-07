from django.db import models
from django.contrib.auth.models import User

# ---------------- BRAND ----------------
class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)

    def __str__(self):
        return self.name


# ---------------- PRODUCT ----------------
class Product(models.Model):
    name = models.CharField(max_length=100)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.CharField(max_length=100, blank=True, null=True)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    image = models.ImageField(upload_to='images/', blank=True, null=True)
    stock = models.IntegerField(default=10)

    is_offer = models.BooleanField(default=False)
    offer_percent = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def get_offer_price(self):
        if self.is_offer and self.offer_percent > 0:
            discount = (self.price * self.offer_percent) / 100
            return self.price - discount
        return self.price

    def __str__(self):
        return self.name

# ---------------- CUSTOMER ----------------
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    location = models.CharField(max_length=200, blank=True, null=True)
    address = models.TextField()

    def __str__(self):
        return self.user.username

class WalkinCustomer(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# ---------------- BILL (ORDER) ----------------
class Bill(models.Model):

    STATUS_CHOICES = [
        ('Placed', 'Placed'),
        ('Packed', 'Packed'),
        ('Shipped', 'Shipped'),
        ('Out for Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    walkin_customer = models.ForeignKey(WalkinCustomer, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=20)
    
    is_walkin = models.BooleanField(default=False)

    # Billing Details
    billing_name = models.CharField(max_length=100, null=True, blank=True)
    billing_phone = models.CharField(max_length=15, null=True, blank=True)
    billing_email = models.EmailField(null=True, blank=True)
    billing_location = models.CharField(max_length=200, null=True, blank=True)
    billing_address = models.TextField(null=True, blank=True)

    order_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Placed"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill #{self.id} - {self.billing_name} ({'Walk-in' if self.is_walkin else 'Online'})"


# ---------------- BILL ITEMS ----------------
class BillItem(models.Model):
    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.product.name} ({self.bill.id})"


# ---------------- NEWSLETTER ----------------
class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


# ---------------- CART ----------------
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def subtotal(self):
        return self.quantity * self.product.get_offer_price()

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class Feedback(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating}*)"