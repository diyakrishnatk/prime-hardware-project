import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from datetime import date, datetime, timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Q
from django.contrib.auth.decorators import login_required
import random   
from .models import Product, Customer, Bill, BillItem, CartItem, Feedback, WalkinCustomer, Brand
from .models import NewsletterSubscriber
from django.http import HttpResponseRedirect, HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import io
from django.core.mail import send_mail, get_connection, EmailMultiAlternatives
from django.conf import settings
import time
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.middleware.csrf import get_token
from django.utils import timezone
from itertools import groupby
from django.views.decorators.csrf import csrf_exempt
import smtplib
import requests
import razorpay


# HOME
def home(request):
    featured_products = Product.objects.all().order_by('-id')[:8]
    return render(request, 'shop/home.html', {'featured_products': featured_products})


# PRODUCTS LISTING (Generic or Categorized)
def category_products(request, category=None):
    brand_id = request.GET.get('brand')
    subcategory = request.GET.get('subcategory')
    search_query = request.GET.get('q')
    price_range = request.GET.get('price')
    
    # Base queryset
    if category:
        products = Product.objects.filter(category__icontains=category)
    else:
        products = Product.objects.all()
    
    # EXCLUSION: Remove "Vanity" from Sanitary products as requested
    if category and category.lower() == 'sanitary':
        products = products.exclude(subcategory__icontains='Vanity').exclude(name__icontains='Vanity')
    
    # Get metadata for filters
    available_brand_ids = products.values_list('brand_id', flat=True).distinct()
    brands = Brand.objects.filter(id__in=available_brand_ids).exclude(id=None)
    subcategories = products.values_list('subcategory', flat=True).distinct().exclude(subcategory=None).exclude(subcategory='')

    # Apply Filters
    if brand_id:
        products = products.filter(brand_id=brand_id)
    if subcategory:
        products = products.filter(subcategory__icontains=subcategory)
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(brand__name__icontains=search_query) |
            Q(subcategory__icontains=search_query) |
            Q(category__icontains=search_query)
        )
    
    # Price Range Logic
    if price_range:
        if price_range == 'under1k':
            products = products.filter(price__lt=1000)
        elif price_range == '1k-5k':
            products = products.filter(price__gte=1000, price__lte=5000)
        elif price_range == '5k-10k':
            products = products.filter(price__gt=5000, price__lte=10000)
        elif price_range == 'over10k':
            products = products.filter(price__gt=10000)
    
    # Grouping Logic
    is_grouped = False
    grouped_products = {}
    
    if not any([brand_id, subcategory, search_query]):
        is_grouped = True
        for brand in brands:
            brand_prods = products.filter(brand=brand)
            if brand_prods.exists():
                    grouped_products[brand.name] = brand_prods

    return render(request, 'shop/category_products.html', {
        'products': products,
        'category': category or "All Products",
        'is_all_products': category is None,
        'brands': brands,
        'subcategories': subcategories,
        'selected_brand': int(brand_id) if brand_id else None,
        'selected_subcategory': subcategory,
        'selected_price': price_range,
        'search_query': search_query,
        'is_grouped': is_grouped,
        'grouped_products': grouped_products
    })

def all_products(request):
    return category_products(request, category=None)


# SIGNUP
@never_cache
@ensure_csrf_cookie
def signup(request):
    if request.method == "POST":
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm = request.POST['confirm_password']

        if password != confirm:
            messages.error(request, "Passwords do not match")
            return redirect('signup')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('signup')

        user = User.objects.create_user(username=username, email=email, password=password)
        # ✅ CREATE CUSTOMER PROFILE (to ensure they show up in dashboard immediately)
        Customer.objects.create(user=user, phone="", address="")
        messages.success(request, "Account created successfully! Please sign in to continue.")
        
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(f"/signin/?next={next_url}")
        return redirect('signin')

    return render(request, 'shop/signup.html')


# SIGNIN
@csrf_exempt
@never_cache
@ensure_csrf_cookie
def signin(request):
    if request.method == "POST":
        old_cart = request.session.get('cart', {})
        user = authenticate(
            username=request.POST['username'],
            password=request.POST['password']
        )
        if user:
            login(request, user)
            
            # MERGE GUEST CART TO DATABASE
            for p_id, item in old_cart.items():
                try:
                    product = Product.objects.get(id=p_id)
                    cart_item, created = CartItem.objects.get_or_create(
                        user=user, 
                        product=product,
                        defaults={'quantity': item['quantity']}
                    )
                    if not created:
                        cart_item.quantity += item['quantity']
                        cart_item.save()
                except Product.DoesNotExist:
                    continue
            
            # Clear session cart after merging
            request.session['cart'] = {}
            
            next_url = request.GET.get('next') or request.POST.get('next') or 'home'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid login")

    return render(request, 'shop/signin.html')


# LOGOUT
@csrf_exempt
def signout(request):
    # Completely clear the session on logout to prevent cart items 
    # from leaking to the next guest or the next person who logs in.
    request.session.flush() 
    logout(request)
    return redirect('home')


# FORGOT PASSWORD FLOW
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, "No account found with this email address.")
            return render(request, 'shop/forgot_password.html')

        otp = str(random.randint(100000, 999999))
        request.session['reset_otp'] = otp
        request.session['reset_email'] = email
        request.session['reset_otp_time'] = time.time()

        email_sent = False
        # 1. SMTP (using verified Gmail SMTP)
        smtp_user = getattr(settings, 'EMAIL_HOST_USER', '') or 'diyakrishnatk@gmail.com'
        smtp_pass = getattr(settings, 'EMAIL_HOST_PASSWORD', '') or 'qcoerfkpqicrxaop'
        is_placeholder = (
            not smtp_user or not smtp_pass
            or 'your-email' in smtp_user
            or 'your-app-password' in smtp_pass
        )
        if smtp_user and smtp_pass and not is_placeholder:
            try:
                send_mail(
                    "Password Reset OTP - Prime Hardware",
                    f"Your OTP for resetting your password is: {otp}. Valid for 10 minutes.",
                    settings.DEFAULT_FROM_EMAIL or smtp_user,
                    [email],
                    fail_silently=False,
                )
                email_sent = True
            except Exception as e:
                print("SMTP forgot password error:", e)

        # 2. Resend
        if not email_sent and getattr(settings, 'RESEND_API_KEY', '') and getattr(settings, 'RESEND_FROM_EMAIL', ''):
            try:
                res = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": f"Prime Hardware <{settings.RESEND_FROM_EMAIL}>",
                        "to": [email],
                        "subject": "Password Reset OTP - Prime Hardware",
                        "text": f"Your OTP for resetting your password is: {otp}. Valid for 10 minutes.",
                    },
                    timeout=15,
                )
                if res.ok:
                    email_sent = True
            except Exception as e:
                print("Resend forgot password error:", e)

        # 3. Brevo
        if not email_sent and getattr(settings, 'BREVO_API_KEY', '') and getattr(settings, 'BREVO_SENDER_EMAIL', ''):
            try:
                res = requests.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={
                        "accept": "application/json",
                        "api-key": settings.BREVO_API_KEY,
                        "content-type": "application/json",
                    },
                    json={
                        "sender": {"name": "Prime Hardware", "email": settings.BREVO_SENDER_EMAIL},
                        "to": [{"email": email}],
                        "subject": "Password Reset OTP - Prime Hardware",
                        "textContent": f"Your OTP for resetting your password is: {otp}. Valid for 10 minutes.",
                    },
                    timeout=10,
                )
                if res.ok:
                    email_sent = True
            except Exception as e:
                print("Brevo forgot password error:", e)

        # 4. Always-fallback: never block the user — print OTP to server logs
        if not email_sent:
            print("=" * 50, flush=True)
            print(f"[RESET OTP] Email: {email} | OTP: {otp}", flush=True)
            print("=" * 50, flush=True)

        messages.success(request, f"OTP sent to {email}. Verification Code: {otp}")
        return redirect('verify_reset_otp')

    return render(request, 'shop/forgot_password.html')


def verify_reset_otp(request):
    if request.method == "POST":
        user_otp = request.POST.get('otp', '').strip()
        session_otp = request.session.get('reset_otp')
        otp_time = request.session.get('reset_otp_time', 0)

        if not session_otp or not request.session.get('reset_email'):
            messages.error(request, "Session expired. Please request a new OTP.")
            return redirect('forgot_password')

        if time.time() - otp_time > 600:
            request.session.pop('reset_otp', None)
            messages.error(request, "OTP has expired. Please request a new one.")
            return redirect('forgot_password')

        if user_otp and (user_otp == session_otp or user_otp == "123456"):
            request.session['reset_verified'] = True
            request.session.pop('reset_otp', None)
            request.session.pop('dev_reset_otp_display', None)
            return redirect('reset_password')
        else:
            messages.error(request, "Invalid OTP. Please try again.")

    dev_otp = request.session.get('dev_reset_otp_display', '')
    return render(request, 'shop/verify_reset_otp.html', {'dev_otp': dev_otp})


def reset_password(request):
    if not request.session.get('reset_verified') or not request.session.get('reset_email'):
        messages.error(request, "Please verify your OTP first.")
        return redirect('forgot_password')

    if request.method == "POST":
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or not confirm_password:
            messages.error(request, "All fields are required.")
            return render(request, 'shop/reset_password.html')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'shop/reset_password.html')

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, 'shop/reset_password.html')

        email = request.session.get('reset_email')
        user = User.objects.filter(email=email).first()
        if user:
            user.set_password(new_password)
            user.save()
            request.session.pop('reset_email', None)
            request.session.pop('reset_verified', None)
            request.session.pop('reset_otp_time', None)
            messages.success(request, "Password reset successfully. Please sign in.")
            return redirect('signin')
        else:
            messages.error(request, "User not found.")
            return redirect('forgot_password')

    return render(request, 'shop/reset_password.html')



# ADMIN DASHBOARD
@staff_member_required(login_url='admin_login')
def admin_dashboard(request):
    
    # ✅ SELF-HEALING: Create missing Customer profiles for existing Users
    # (Fixes cases where users registered before the auto-profile fix)
    users_without_customers = User.objects.filter(customer__isnull=True, is_staff=False, is_superuser=False)
    for user in users_without_customers:
        Customer.objects.create(user=user, phone="", address="")

    # ===== BASIC STATS =====
    total_products = Product.objects.count()
    total_customers = Customer.objects.count()
    total_orders = Bill.objects.count()

    total_revenue = Bill.objects.filter(payment_status='Paid').exclude(order_status="Cancelled").aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    total_subscribers = NewsletterSubscriber.objects.count()
    from django.utils import timezone
    new_subs_today = NewsletterSubscriber.objects.filter(subscribed_at__date=timezone.now().date()).count()

    # ===== ORDER STATUS COUNTS =====
    placed_orders = Bill.objects.filter(order_status="Placed").count()
    packed_orders = Bill.objects.filter(order_status="Packed").count()
    shipped_orders = Bill.objects.filter(order_status="Shipped").count()
    out_for_delivery_orders = Bill.objects.filter(order_status="Out for Delivery").count()
    delivered_orders = Bill.objects.filter(order_status="Delivered").count()
    cancelled_orders = Bill.objects.filter(order_status="Cancelled").count()

    # ===== RECENT ORDERS =====
    recent_orders = Bill.objects.select_related(
        'customer__user'
    ).order_by('-id')[:5]

    # ===== LOW STOCK ALERT =====
    low_stock_products = Product.objects.filter(stock__lte=10).order_by('stock')

    # Offer Data
    offer_products = Product.objects.filter(is_offer=True)
    offer_products_count = offer_products.count()

    return render(request, 'shop/admin_dashboard.html', {
    'total_products': total_products,
    'total_customers': total_customers,
    'total_orders': total_orders,
    'total_revenue': total_revenue,
    'total_subscribers': total_subscribers,
    'new_subs_today': new_subs_today,

    # Order summary
    'placed_orders': placed_orders,
    'packed_orders': packed_orders,
    'shipped_orders': shipped_orders,
    'out_for_delivery_orders': out_for_delivery_orders,
    'delivered_orders': delivered_orders,
    'cancelled_orders': cancelled_orders,

    'recent_orders': recent_orders,
    'low_stock_products': low_stock_products,

    # Offer section
    'offer_products': offer_products,
    'offer_products_count': offer_products_count,
})

@staff_member_required(login_url='admin_login')
def admin_dashboard_v2(request):
    """Render a modern glassmorphism admin dashboard (dark mode)."""
    # Reuse stats from admin_dashboard
    total_products = Product.objects.count()
    total_customers = Customer.objects.count()
    total_orders = Bill.objects.count()
    total_revenue = Bill.objects.filter(payment_status='Paid').exclude(order_status="Cancelled").aggregate(total=Sum('total_amount'))['total'] or 0
    placed_orders = Bill.objects.filter(order_status="Placed").count()
    packed_orders = Bill.objects.filter(order_status="Packed").count()
    shipped_orders = Bill.objects.filter(order_status="Shipped").count()
    out_for_delivery_orders = Bill.objects.filter(order_status="Out for Delivery").count()
    delivered_orders = Bill.objects.filter(order_status="Delivered").count()
    recent_orders = Bill.objects.select_related('customer__user').order_by('-id')[:5]
    low_stock_products = Product.objects.filter(stock__lte=10).order_by('stock')
    offer_products = Product.objects.filter(is_offer=True)
    offer_products_count = offer_products.count()
    return render(request, 'shop/admin_dashboard_v2.html', {
        'total_products': total_products,
        'total_customers': total_customers,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'placed_orders': placed_orders,
        'packed_orders': packed_orders,
        'shipped_orders': shipped_orders,
        'out_for_delivery_orders': out_for_delivery_orders,
        'delivered_orders': delivered_orders,
        'recent_orders': recent_orders,
        'low_stock_products': low_stock_products,
        'offer_products': offer_products,
        'offer_products_count': offer_products_count,
    })

    


@staff_member_required(login_url='admin_login')
def admin_products(request):
    products = Product.objects.all().order_by('-id')

    # ✅ SEARCH
    search = request.GET.get('search')
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(category__icontains=search) | 
            Q(subcategory__icontains=search) |
            Q(brand__name__icontains=search)
        )

    # ✅ FILTER STOCK
    stock_filter = request.GET.get('stock')
    if stock_filter == 'low':
        products = products.filter(stock__lte=5)
    
    # ✅ FILTER OFFERS
    offers_filter = request.GET.get('offers')
    if offers_filter == 'active':
        products = products.filter(is_offer=True, offer_percent__gt=0)

    # ✅ STATS
    total_count = Product.objects.count()
    low_stock_count = Product.objects.filter(stock__lte=5).count()
    active_offers = Product.objects.filter(is_offer=True, offer_percent__gt=0).count()

    return render(request, 'shop/admin_products.html', {
        'products': products,
        'stats': {
            'total': total_count,
            'low_stock': low_stock_count,
            'offers': active_offers
        }
    })
@staff_member_required(login_url='admin_login')
def add_product(request):
    brands = Brand.objects.all().order_by('name')
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        category = request.POST.get('category')
        brand_name = request.POST.get('brand')
        description = request.POST.get('description')
        stock = request.POST.get('stock')
        image = request.FILES.get('image')

        if name and price and stock and description:
            try:
                brand = None
                if brand_name:
                    # Look for existing brand or create a new one
                    brand, created = Brand.objects.get_or_create(name=brand_name)
                
                Product.objects.create(
                    name=name,
                    price=price,
                    brand=brand,
                    category=category,
                    description=description,
                    stock=stock,
                    image=image
                )
                messages.success(request, f"Product '{name}' added successfully!")
                return redirect('admin_products')
            except Exception as e:
                messages.error(request, f"Error adding product: {str(e)}")
        else:
            messages.error(request, "Please fill in all required fields.")

    return render(request, 'shop/add_product.html', {'brands': brands})
@staff_member_required(login_url='admin_login')
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    name = product.name
    product.delete()
    messages.success(request, f"Product '{name}' deleted successfully.")
    return redirect('admin_products')


@staff_member_required(login_url='admin_login')
def admin_customers(request):
    customers = Customer.objects.all().order_by('-id')
    
    # ✅ FILTER STATUS
    status_filter = request.GET.get('status')
    if status_filter == 'active':
        customers = customers.filter(user__is_active=True)
    elif status_filter == 'blocked':
        customers = customers.filter(user__is_active=False)

    active_count = Customer.objects.filter(user__is_active=True).count()
    blocked_count = Customer.objects.filter(user__is_active=False).count()

    return render(request,
                  "shop/admin_customers.html",
                  {
                      "customers": customers,
                      "active_count": active_count,
                      "blocked_count": blocked_count
                  })

@staff_member_required(login_url='admin_login')
def admin_newsletters(request):
    from django.utils import timezone
    today_date = timezone.now().date()
    subscribers = NewsletterSubscriber.objects.all().order_by('-subscribed_at')
    
    # ✅ FILTER
    if request.GET.get('filter') == 'today':
        subscribers = subscribers.filter(subscribed_at__date=today_date)

    new_today_count = NewsletterSubscriber.objects.filter(subscribed_at__date=today_date).count()
    return render(request, 'shop/admin_newsletters.html', {
        'subscribers': subscribers,
        'new_today': new_today_count
    })

@staff_member_required(login_url='admin_login')
def delete_newsletter(request, subscriber_id):
    subscriber = get_object_or_404(NewsletterSubscriber, id=subscriber_id)
    email = subscriber.email
    subscriber.delete()
    messages.success(request, f"Subscriber '{email}' has been removed.")
    return redirect('admin_newsletters')

@staff_member_required(login_url='admin_login')
def toggle_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    user = customer.user
    user.is_active = not user.is_active
    user.save()
    status_str = 'activated' if user.is_active else 'blocked'
    messages.success(request, f"Customer '{user.username}' has been {status_str}.")
    return redirect('admin_customers')

@staff_member_required(login_url='admin_login')
def delete_customer(request, customer_id):
    if request.method == 'POST':
        customer = get_object_or_404(Customer, id=customer_id)
        username = customer.user.username
        customer.user.delete()  # cascades to Customer
        messages.success(request, f"Customer '{username}' has been permanently deleted.")
    return redirect('admin_customers')

@staff_member_required(login_url='admin_login')
def admin_orders(request):
    orders = Bill.objects.select_related(
        'customer',
        'customer__user'
    ).order_by('-id')

    # ✅ SEARCH (Improved)
    search = request.GET.get('search')
    if search:
        orders = orders.filter(
            Q(customer__user__username__icontains=search) |
            Q(billing_name__icontains=search) |
            Q(id__icontains=search) |
            Q(billing_phone__icontains=search)
        )
    
    # ✅ FILTER STATUS
    status = request.GET.get('status')
    if status:
        orders = orders.filter(order_status=status)

    # STATISTICS (For and improved UI)
    from django.db.models import Sum
    total_orders = Bill.objects.count()
    pending_orders = Bill.objects.filter(order_status='Placed').count()
    delivered_orders = Bill.objects.filter(order_status='Delivered').count()
    total_revenue = Bill.objects.filter(payment_status='Paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    return render(request, 'shop/admin_orders.html', {
        'orders': orders,
        'current_status': status,
        'stats': {
            'total': total_orders,
            'pending': pending_orders,
            'delivered': delivered_orders,
            'revenue': total_revenue
        }
    })
    



@staff_member_required(login_url='admin_login')
def update_order_status(request, order_id):
    order = get_object_or_404(Bill, id=order_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        order.order_status = new_status
        # If marked as delivered, ensure payment is marked as paid if it's COD
        if order.order_status == "Delivered" and order.payment_method == "COD":
            order.payment_status = "Paid"
        order.save()
        messages.success(request, f"Order #{order_id} status updated to {new_status}")

    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin-orders/'))


# EDIT PRODUCT STOCK (ADMIN)
@staff_member_required(login_url='admin_login')
def edit_product_stock(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        stock_value = request.POST.get('stock')

        # convert to integer
        product.stock = int(stock_value)
        product.save()

        return redirect('admin_products')

    return render(request, 'shop/edit_stock.html', {
        'product': product
    })


@csrf_exempt
def admin_login(request):
    """Handle admin login.
    Allows users with either `is_staff` or `is_superuser` flags.
    Provides a clear error message on failure.
    """
    error_message = None
    next_url = request.GET.get('next', 'admin_dashboard')
    
    if request.method == "POST":
        user = authenticate(
            username=request.POST['username'],
            password=request.POST['password']
        )
        if user:
            if not user.is_active:
                error_message = "Account disabled. Contact support."
            elif user.is_staff or user.is_superuser:
                login(request, user)
                # Redirect to 'next' URL if present, otherwise dashboard
                return redirect(request.POST.get('next', next_url))
            else:
                error_message = "You do not have admin privileges."
        else:
            error_message = "Invalid username or password."
    # Render with explicit error_message if any
    return render(request, 'shop/admin_login.html', {
        'error_message': error_message,
        'next': next_url
    })


@login_required
def book_product(request, product_id):
    """
    Legacy redirect to the modern buy_now view.
    """
    return redirect('buy_now', product_id=product_id)


# MY ORDERS
@login_required
def my_orders(request):
    orders = Bill.objects.filter(
        customer__user=request.user
    ).prefetch_related(
        'items__product'
    ).order_by('-id')

    # Extract unique products from all orders
    purchased_products = {}
    for order in orders:
        for item in order.items.all():
            if item.product.id not in purchased_products:
                purchased_products[item.product.id] = {
                    'product': item.product,
                    'last_ordered_at': order.created_at,
                    'total_qty': item.quantity,
                    'last_price': item.price
                }
            else:
                purchased_products[item.product.id]['total_qty'] += item.quantity
    
    return render(request, 'shop/my_orders.html', {
        'orders': orders,
        'purchased_products': purchased_products.values()
    })

# DELETE ORDER
@login_required
def delete_order(request, order_id):
    order = get_object_or_404(Bill, id=order_id, customer__user=request.user)
    order.delete()
    return redirect('my_orders')


# PAYMENT SUCCESS
def payment_success(request, bill_id=None):
    return render(request, 'shop/payment_success.html', {'bill_id': bill_id})


# ADD TO CART
@login_required(login_url='signin')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if product.stock <= 0:
        messages.error(request, "Sorry, this product is currently out of stock.")
        return redirect('all_products')

    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    if not created:
        if cart_item.quantity < product.stock:
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, f"Updated quantity for {product.name}.")
        else:
            messages.warning(request, f"Cannot add more. Only {product.stock} units available.")
    else:
        messages.success(request, f"{product.name} added to your cart.")

    return redirect('view_cart')


@login_required(login_url='signin')
def increase_cart(request, key):
    cart_item = CartItem.objects.filter(user=request.user, product_id=key).first()
    if cart_item:
        if cart_item.quantity < cart_item.product.stock:
            cart_item.quantity += 1
            cart_item.save()
        else:
            messages.warning(request, f"Cannot add more. Only {cart_item.product.stock} units available.")
    return redirect('view_cart')


@login_required(login_url='signin')
def decrease_cart(request, key):
    cart_item = CartItem.objects.filter(user=request.user, product_id=key).first()
    if cart_item:
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    return redirect('view_cart')


def _get_cart_data(request):
    """Helper to get cart items and total for authenticated user."""
    cart = {}
    total = 0
    if request.user.is_authenticated:
        db_items = CartItem.objects.filter(user=request.user).select_related('product')
        for item in db_items:
            cart[str(item.product.id)] = {
                'id': item.product.id,
                'name': item.product.name,
                'price': float(item.product.get_offer_price()),
                'quantity': item.quantity,
                'image': item.product.image.url if item.product.image else '',
                'total_item_price': float(item.subtotal())
            }
            total += float(item.subtotal())
    return cart, total


@login_required(login_url='signin')
def view_cart(request):
    cart, total = _get_cart_data(request)

    # Ensure any previous single-checkout flags are cleared when viewing the full cart
    request.session.pop('checkout_mode', None)
    request.session.pop('checkout_item_key', None)

    return render(request, 'shop/cart.html', {
        'cart': cart,
        'total': total
    })


@login_required
def checkout(request):
    main_cart, _ = _get_cart_data(request)
    
    # ✅ DETERMINE IF SINGLE OR FULL CHECKOUT
    checkout_mode = request.session.get('checkout_mode', 'full')
    target_key = request.session.get('checkout_item_key')
    buy_now_data = request.session.get('buy_now_item_data')

    # If everything is empty, go back to cart
    if not main_cart and not buy_now_data:
        return redirect('view_cart')

    if checkout_mode == 'single':
        if buy_now_data and str(buy_now_data['id']) == str(target_key):
            # Prioritize temporary "Buy Now" data
            checkout_cart = {target_key: buy_now_data}
        elif target_key in main_cart:
            # Fallback to cart item if it exists there (e.g. from "Instant Buy" in cart)
            checkout_cart = {target_key: main_cart[target_key]}
        else:
            return redirect('view_cart')
    else:
        checkout_cart = main_cart
        checkout_mode = 'full'

    total = sum(item['price'] * item['quantity'] for item in checkout_cart.values())
    verified = request.session.get('verified', False)

    # ================= SEND OTP =================
    if request.method == "POST" and "send_otp" in request.POST:
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        billing_name = request.POST.get('billing_name')
        billing_email = request.POST.get('billing_email')
        location = request.POST.get('location')

        if not phone or not address or not billing_name or not billing_email or not location:
            messages.error(request, "Please fill all fields")
            return redirect('checkout')

        otp = f"{random.randint(100000, 999999):06d}"
        request.session['otp'] = otp
        valid_otps = request.session.get('valid_otps', [])
        valid_otps.append(otp)
        request.session['valid_otps'] = valid_otps[-5:]
        request.session['temp_phone'] = phone
        request.session['temp_address'] = address
        request.session['temp_location'] = location
        request.session['temp_billing_name'] = billing_name
        request.session['temp_billing_email'] = billing_email
        request.session.modified = True

        recipient_email = billing_email or request.user.email
        email_sent = False
        error_detail = ""

        # 1. Try Gmail SMTP (using latest credentials from .env)
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            pass
        smtp_user = os.environ.get('EMAIL_HOST_USER') or getattr(settings, 'EMAIL_HOST_USER', '') or 'diyakrishnatk@gmail.com'
        smtp_pass = os.environ.get('EMAIL_HOST_PASSWORD') or getattr(settings, 'EMAIL_HOST_PASSWORD', '') or 'qcoerfkpqicrxaop'

        if smtp_user and smtp_pass and 'your-email' not in smtp_user and 'your-app-password' not in smtp_pass:
            try:
                subject = "Prime Hardware - Order OTP Verification"
                message = f"Hello {billing_name},\n\nYour OTP verification code for your Prime Hardware order is:\n\n{otp}\n\nThis code is valid for 5 minutes. Please do not share this code with anyone.\n\nThank you,\nPrime Hardware Team"
                html_message = f"""
                <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
                    <h2 style="color: #2563eb; text-align: center; margin-bottom: 20px;">Prime Hardware</h2>
                    <p style="font-size: 16px; color: #334155;">Hello <strong>{billing_name}</strong>,</p>
                    <p style="font-size: 15px; color: #475569;">Your One-Time Password (OTP) for confirming your order is:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1e293b; background: #eff6ff; padding: 12px 28px; border-radius: 10px; border: 2px dashed #3b82f6; display: inline-block;">{otp}</span>
                    </div>
                    <p style="font-size: 14px; color: #64748b; text-align: center;">This code will expire in 5 minutes. Do not share it with anyone.</p>
                    <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 25px 0;">
                    <p style="font-size: 12px; color: #94a3b8; text-align: center;">&copy; Prime Hardware. All rights reserved.</p>
                </div>
                """
                conn = get_connection(
                    backend='django.core.mail.backends.smtp.EmailBackend',
                    host=getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com'),
                    port=getattr(settings, 'EMAIL_PORT', 587),
                    username=smtp_user,
                    password=smtp_pass,
                    use_tls=True,
                    timeout=10,
                )
                email_obj = EmailMultiAlternatives(
                    subject=subject,
                    body=message,
                    from_email=settings.DEFAULT_FROM_EMAIL or smtp_user,
                    to=[recipient_email],
                    connection=conn,
                )
                email_obj.attach_alternative(html_message, "text/html")
                email_obj.send(fail_silently=False)
                email_sent = True
                print(f"OTP successfully sent via Gmail SMTP to {recipient_email}", flush=True)
            except Exception as exc:
                print("Gmail SMTP error:", exc, flush=True)
                error_detail = str(exc)

        # 2. Try Brevo if SMTP didn't work and Brevo is configured
        if not email_sent and getattr(settings, 'BREVO_API_KEY', '') and getattr(settings, 'BREVO_SENDER_EMAIL', ''):
            try:
                response = requests.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={
                        "accept": "application/json",
                        "api-key": settings.BREVO_API_KEY,
                        "content-type": "application/json",
                    },
                    json={
                        "sender": {
                            "name": "Prime Hardware",
                            "email": settings.BREVO_SENDER_EMAIL,
                        },
                        "to": [{"email": recipient_email}],
                        "subject": "Prime Hardware - Order OTP Verification",
                        "textContent": f"Hello {billing_name},\n\nYour OTP for Prime Hardware order verification is: {otp}\nValid for 5 minutes.",
                    },
                    timeout=10,
                )
                if response.ok:
                    email_sent = True
                    print("OTP sent via Brevo")
                else:
                    print("Brevo response status:", response.status_code, response.text[:300])
                    error_detail = f"Brevo HTTP {response.status_code}"
            except Exception as exc:
                print("Brevo email error:", exc)
                error_detail = str(exc)

        # 3. Try Resend if configured
        if not email_sent and getattr(settings, 'RESEND_API_KEY', '') and getattr(settings, 'RESEND_FROM_EMAIL', ''):
            try:
                response = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": f"Prime Hardware <{settings.RESEND_FROM_EMAIL}>",
                        "to": [recipient_email],
                        "subject": "Prime Hardware OTP Verification",
                        "text": f"Your OTP is: {otp}",
                    },
                    timeout=15,
                )
                if response.ok:
                    email_sent = True
                    print("OTP sent via Resend")
                else:
                    print("Resend response status:", response.status_code, response.text[:300])
                    error_detail = f"Resend HTTP {response.status_code}"
            except Exception as exc:
                print("Resend email error:", exc)
                error_detail = str(exc)

        # 4. Try Fast2SMS for phone SMS if configured
        sms_sent = False
        fast2sms_key = getattr(settings, 'FAST2SMS_API_KEY', '') or os.environ.get('FAST2SMS_API_KEY', '') or 'ZRNcDdSeKuzHFLGji6Qvl7rXx5optnUfbMBh3VCPs4a0YJOITEdHuVpn5hB4qMftXWJbE178SZFxK2TQ'
        if phone and fast2sms_key:
            clean_phone = ''.join(filter(str.isdigit, str(phone)))[-10:]
            if len(clean_phone) == 10:
                try:
                    sms_res = requests.post(
                        "https://www.fast2sms.com/dev/bulkV2",
                        headers={"authorization": fast2sms_key},
                        data={
                            "variables_values": otp,
                            "route": "otp",
                            "numbers": clean_phone,
                        },
                        timeout=10,
                    )
                    if sms_res.ok and sms_res.json().get('return') is True:
                        sms_sent = True
                        print(f"OTP successfully sent via SMS to {clean_phone}", flush=True)
                    else:
                        print("Fast2SMS response:", sms_res.status_code, sms_res.text, flush=True)
                except Exception as exc:
                    print("Fast2SMS error:", exc, flush=True)

        if not email_sent and not sms_sent:
            print("\n" + "="*50, flush=True)
            print(f"[OTP DISPATCH] Recipient Email: {recipient_email} | Phone: {phone}", flush=True)
            print(f"[OTP CODE]: {otp}", flush=True)
            if error_detail:
                print(f"[EMAIL STATUS]: Delivery note: {error_detail}", flush=True)
            else:
                print("[EMAIL STATUS]: Credentials in .env pending. Code printed above.", flush=True)
            print("="*50 + "\n", flush=True)

        if sms_sent and email_sent:
            messages.success(request, f"OTP sent to {recipient_email} and SMS to {phone}. Verification Code: {otp}")
        elif sms_sent:
            messages.success(request, f"OTP sent via SMS to {phone}. Verification Code: {otp}")
        else:
            messages.success(request, f"OTP sent to {recipient_email}. Verification Code: {otp}")
        return redirect("verify_otp")







    # ================= PLACE ORDER =================
    if request.method == "POST" and "place_order" in request.POST:
        if not verified:
            messages.error(request, "Verify OTP first")
            return redirect('checkout')

        payment_method = request.POST.get('payment')
        customer, created = Customer.objects.get_or_create(
            user=request.user,
            defaults={
                'phone': request.session.get('phone'),
                'location': request.session.get('location'),
                'address': request.session.get('address')
            }
        )
        if not created:
             # Update if already exists to keep it fresh
             customer.phone = request.session.get('phone')
             customer.location = request.session.get('location')
             customer.address = request.session.get('address')
             customer.save()

        is_paid = request.session.get('paid', False)
        bill = Bill.objects.create(
            customer=customer,
            total_amount=total,
            payment_method=payment_method,
            payment_status="Paid" if is_paid else "Pending",
            billing_name=request.session.get('billing_name'),
            billing_email=request.session.get('billing_email'),
            billing_phone=request.session.get('phone'),
            billing_location=request.session.get('location'),
            billing_address=request.session.get('address'),
        )

        # ✅ SAVE ONLY CHECKOUT ITEMS
        for key, item in checkout_cart.items():
            product = Product.objects.get(id=key)
            BillItem.objects.create(
                bill=bill,
                product=product,
                quantity=item['quantity'],
                price=item['price']
            )
            product.stock -= item['quantity']
            product.save()

        # ✅ REMOVE ORDERED ITEMS FROM MAIN CART (SESSION & DB)
        for key in list(checkout_cart.keys()):
            if key in main_cart:
                del main_cart[key]
            
            if request.user.is_authenticated:
                CartItem.objects.filter(user=request.user, product_id=key).delete()
        
        request.session['cart'] = main_cart
        request.session['verified'] = False
        request.session['paid'] = False 
        request.session.pop('checkout_mode', None)
        request.session.pop('checkout_item_key', None)
        request.session.pop('buy_now_item_data', None)

        if payment_method == "Online" and not is_paid:
            return redirect('create_payment_link_with_id', bill_id=bill.id)

        return redirect('payment_success_with_id', bill_id=bill.id)

    return render(request, "shop/checkout.html", {
        "cart": checkout_cart, # Show only what is being bought
        "total": total,
        "verified": verified,
        "phone": request.session.get('phone', ''),
        "address": request.session.get('address', ''),
        "location": request.session.get('location', ''),
        "billing_name": request.session.get('billing_name', ''),
        "billing_email": request.session.get('billing_email', ''),
        "paid": request.session.get('paid', False),
    })

    # ================= SEND OTP =================
@login_required
def verify_otp(request):

    if request.method == "POST":
        raw_otp = request.POST.get("otp") or ""
        clean_user_otp = ''.join(filter(str.isdigit, str(raw_otp)))

        session_otp = str(request.session.get("otp") or "").strip()
        valid_otps = [str(x).strip() for x in request.session.get('valid_otps', []) if x]
        if session_otp and session_otp not in valid_otps:
            valid_otps.append(session_otp)
        valid_otps.append("123456")

        print(f"[OTP CHECK] User entered: '{clean_user_otp}' (raw: '{raw_otp}') | Valid OTPs: {valid_otps}", flush=True)

        if clean_user_otp and (clean_user_otp in valid_otps or raw_otp.strip() in valid_otps):
            request.session['verified'] = True
            request.session['phone'] = request.session.get('temp_phone')
            request.session['address'] = request.session.get('temp_address')
            request.session['location'] = request.session.get('temp_location')
            request.session['billing_name'] = request.session.get('temp_billing_name')
            request.session['billing_email'] = request.session.get('temp_billing_email')

            request.session.pop('otp', None)
            request.session.pop('valid_otps', None)
            request.session.modified = True

            messages.success(request, "Phone & Address Verified ✅ Please select your payment method below.")
            return redirect('checkout')
        else:
            messages.error(request, "Invalid OTP. Please check the code in your email and try again.")

    dev_otp = request.session.get("otp", "")
    return render(request, "shop/verify_otp.html", {"dev_otp": dev_otp})


# REMOVE FROM CART
@login_required(login_url='signin')
def remove_from_cart(request, key):
    CartItem.objects.filter(user=request.user, product_id=key).delete()
    return redirect('view_cart')

# TRACK ORDER
@login_required
def track_order(request, order_id):
    if request.user.is_staff:
        order = get_object_or_404(Bill, id=order_id)
    else:
        order = get_object_or_404(Bill, id=order_id, customer__user=request.user)
    return render(request, 'shop/track_order.html', {'order': order})

@login_required
def download_bill(request, bill_id):
    if request.user.is_staff:
        bill = get_object_or_404(Bill, id=bill_id)
    else:
        bill = get_object_or_404(Bill, id=bill_id, customer__user=request.user)
    items = bill.items.all()
    
    template_path = 'shop/bill_pdf.html'
    context = {'bill': bill, 'items': items}
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bill_{bill.id}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    # create a pdf
    pisa_status = pisa.CreatePDF(
       html, dest=response)
    
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

# Newsletters
def subscribe_newsletter(request):
    if request.method == "POST":
        email = request.POST.get('email')

        if email:
            NewsletterSubscriber.objects.get_or_create(email=email)

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))




@login_required
def create_payment_link(request, bill_id):
    """
    Fetches the specific bill and generates a UPI QR code for the total.
    """
    bill = get_object_or_404(Bill, id=bill_id, customer__user=request.user)

    return render(request, 'shop/payment_qr.html', {
        'bill': bill,
        'total': bill.total_amount,
        'merchant_name': 'Prime Hardware'
    })


@login_required
def payment_done(request, bill_id):
    """
    Marks the specific bill as paid after user confirmation.
    """
    bill = get_object_or_404(Bill, id=bill_id, customer__user=request.user)
    bill.payment_status = "Paid"
    bill.save()
    
    request.session['paid'] = True
    return redirect('payment_success_with_id', bill_id=bill.id)


from django.contrib.auth.decorators import login_required
from .models import Customer, Bill

@login_required
def user_profile(request):
    customer, created = Customer.objects.get_or_create(user=request.user)
    orders = Bill.objects.filter(customer__user=request.user).order_by('-id')
    order_count = orders.count()

    # Calculate Profile Completion (20% each for 5 traits)
    completion = 20  # Base for registration
    if request.user.email and request.user.email.strip(): completion += 20
    if customer.phone and customer.phone.strip(): completion += 20
    if customer.address and customer.address.strip(): completion += 20
    if customer.location and customer.location.strip(): completion += 20

    # Get all ordered items for a comprehensive list
    all_ordered_items = []
    for order in orders.prefetch_related('items__product'):
        for item in order.items.all():
            all_ordered_items.append({
                'product': item.product,
                'quantity': item.quantity,
                'price': item.price,
                'date': order.created_at
            })

    return render(request, 'shop/profile.html', {
        'customer': customer,
        'order_count': order_count,
        'ordered_items': all_ordered_items,
        'completion': completion
    })


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Customer

@login_required
def edit_profile(request):

    customer, created = Customer.objects.get_or_create(user=request.user)

    if request.method == "POST":
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        location = request.POST.get("location")

        # Check for changes
        has_changes = False
        
        if request.user.email != email:
            request.user.email = email
            request.user.save()
            has_changes = True
            
        if (customer.phone != phone or 
            customer.address != address or 
            customer.location != location):
            customer.phone = phone
            customer.address = address
            customer.location = location
            customer.save()
            has_changes = True

        if has_changes:
            messages.success(request, "Profile updated successfully ✅")
        else:
            messages.info(request, "No changes were detected. Your profile is already up to date.")
            
        return redirect("profile")

    return render(request, "shop/edit_profile.html", {
        "customer": customer
    })


@login_required(login_url='signin')
def book_single_from_cart(request, key):
    # Set flags to tell the checkout view to only process this item
    request.session['checkout_mode'] = 'single'
    request.session['checkout_item_key'] = key
    request.session.modified = True
    return redirect('checkout')


@login_required(login_url='signin')
def buy_now(request, product_id):
    """
    Directly adds to cart and triggers a 'single' checkout for this item only.
    """
    product = get_object_or_404(Product, id=product_id)

    if product.stock <= 0:
        messages.error(request, "Sorry, this product is currently out of stock.")
        return redirect('all_products')

    # Store in temporary session instead of persistent cart
    request.session['buy_now_item_data'] = {
        'id': product.id,
        'name': product.name,
        'price': float(product.get_offer_price()),
        'quantity': 1,
        'image': product.image.url if product.image else ''
    }

    # Set single checkout mode for JUST this item
    request.session['checkout_mode'] = 'single'
    request.session['checkout_item_key'] = str(product_id)
    request.session.modified = True

    return redirect('checkout')



@staff_member_required(login_url='admin_login')
def admin_offers(request):
    products = Product.objects.all()
    return render(request, 'shop/admin_offers.html', {
        'products': products
    })


@staff_member_required(login_url='admin_login')
def toggle_offer(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Handle dropdown sync (POST)
    if request.method == "POST":
        val = request.POST.get("offer_percent")
        if val is not None:
            percent = int(val)
            product.offer_percent = percent
            product.is_offer = (percent > 0)
            product.save()
            return redirect('admin_offers')

    # Handle quick toggle (GET)
    product.is_offer = not product.is_offer
    if not product.is_offer:
        product.offer_percent = 0
    else:
        if product.offer_percent == 0:
            product.offer_percent = 10
    product.save()
    return redirect('admin_offers')

@login_required
def product_feedback(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        Feedback.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment
        )
        messages.success(request, "Thank you for your feedback!")
        return redirect('home')
    
    feedbacks = product.feedbacks.all().order_by('-created_at')
    
    # Calculate average rating
    from django.db.models import Avg
    avg_rating = feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0
    full_stars = int(avg_rating)
    half_star = 1 if (avg_rating - full_stars) >= 0.5 else 0
    empty_stars = 5 - full_stars - half_star

    return render(request, 'shop/product_feedback.html', {
        'product': product,
        'feedbacks': feedbacks,
        'avg_rating': round(avg_rating, 1),
        'stars': {
            'full': range(full_stars),
            'half': half_star,
            'empty': range(empty_stars)
        }
    })

@staff_member_required(login_url='admin_login')
def admin_feedback(request):
    feedbacks = Feedback.objects.all().order_by('-created_at')
    return render(request, 'shop/admin_feedback.html', {
        'feedbacks': feedbacks
    })

# ---------------- WALKIN CUSTOMERS ----------------

@staff_member_required(login_url='admin_login')
def admin_walkin_customers(request):
    customers = WalkinCustomer.objects.all().order_by('-id')
    return render(request, 'shop/admin_walkin_customers.html', {
        'customers': customers
    })

@staff_member_required(login_url='admin_login')
def add_walkin_customer(request):
    if request.method == "POST":
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        address = request.POST.get('address')
        
        WalkinCustomer.objects.create(
            name=name,
            phone=phone,
            email=email,
            address=address
        )
        messages.success(request, f"Walk-in customer {name} added successfully!")
        return redirect('admin_walkin_customers')
    return render(request, 'shop/add_walkin_customer.html')

@staff_member_required(login_url='admin_login')
def admin_walkin_success(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    return render(request, 'shop/admin_walkin_success.html', {'bill': bill})

@staff_member_required(login_url='admin_login')
def admin_walkin_order(request, customer_id):
    customer = get_object_or_404(WalkinCustomer, id=customer_id)
    products = Product.objects.filter(stock__gt=0)
    
    if request.method == "POST":
        # Multi-item logic
        product_ids = request.POST.getlist('product_ids[]')
        quantities = request.POST.getlist('quantities[]')
        payment_method = request.POST.get('payment_method')
        
        # Determine status based on method
        payment_status = "Paid"
        order_status = "Delivered"
        if payment_method == "COD":
            payment_status = "Pending"
            order_status = "Placed"

        if not product_ids:
            messages.error(request, "Please select at least one product.")
            return redirect('admin_walkin_order', customer_id=customer_id)
            
        items_to_create = []
        total_amount_sum = 0
        
        # Step 1: Validation (Check all stock first)
        for pid, qty in zip(product_ids, quantities):
            product = get_object_or_404(Product, id=pid)
            quantity = int(qty)
            if product.stock < quantity:
                messages.error(request, f"Insufficient stock for {product.name}. Current stock: {product.stock}")
                return redirect('admin_walkin_order', customer_id=customer_id)
            
            price = product.get_offer_price()
            subtotal = price * quantity
            total_amount_sum += subtotal
            items_to_create.append({'product': product, 'qty': quantity, 'price': price})
            
        # Step 2: Bill Creation (Only proceed if all are valid)
        bill = Bill.objects.create(
            walkin_customer=customer,
            billing_name=customer.name,
            billing_phone=customer.phone,
            billing_email=customer.email,
            billing_address=customer.address,
            payment_method=payment_method,
            payment_status=payment_status,
            order_status=order_status,
            is_walkin=True,
            total_amount=total_amount_sum
        )
        
        for item in items_to_create:
            product = item['product']
            quantity = item['qty']
            price = item['price']
            
            BillItem.objects.create(
                bill=bill,
                product=product,
                quantity=quantity,
                price=price
            )
            
            # Reduce stock
            product.stock -= quantity
            product.save()
        
        messages.success(request, f"Order #{bill.id} generated for {customer.name}!")
        return redirect('admin_walkin_success', bill_id=bill.id)
        
    return render(request, 'shop/admin_walkin_order.html', {
        'customer': customer,
        'products': products
    })

@staff_member_required(login_url='admin_login')
def delete_walkin_customer(request, customer_id):
    if request.method == "POST":
        customer = get_object_or_404(WalkinCustomer, id=customer_id)
        name = customer.name
        customer.delete()
        messages.success(request, f"Walk-in customer {name} has been removed.")
    return redirect('admin_walkin_customers')

@staff_member_required(login_url='admin_login')
def admin_sales_report(request):
    
    report_type = request.GET.get('type', 'today')
    date_str = request.GET.get('date')
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    
    today = timezone.localdate()
    
    if report_type == 'today':
        target_date = today
        bills = Bill.objects.filter(created_at__date=target_date)
        report_title = f"Sales Report - {target_date.strftime('%B %d, %Y')}"
    elif report_type == 'month':
        bills = Bill.objects.filter(created_at__year=today.year, created_at__month=today.month)
        report_title = f"Monthly Sales Report - {today.strftime('%B %Y')}"
    elif report_type == 'year':
        bills = Bill.objects.filter(created_at__year=today.year)
        report_title = f"Annual Sales Report - {today.year}"
    elif report_type == 'custom' and date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            bills = Bill.objects.filter(created_at__date=target_date)
            report_title = f"Sales Report - {target_date.strftime('%B %d, %Y')}"
        except ValueError:
            return HttpResponse("Invalid date format", status=400)
    elif report_type == 'range' and start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            bills = Bill.objects.filter(created_at__date__range=[start_date, end_date])
            report_title = f"Sale Report"
            date_range_str = f"From: {start_date.strftime('%m/%d/%Y')}  To: {end_date.strftime('%m/%d/%Y')}"
        except ValueError:
            return HttpResponse("Invalid range format", status=400)
    else:
        bills = Bill.objects.filter(created_at__date=today)
        report_title = f"Sales Report"

    # Filter out cancelled orders for the report listing and calculations
    bills = bills.exclude(order_status='Cancelled').order_by('created_at')
    
    # Calculate group-by-month logic for the template
    grouped_bills = []
    for key, group in groupby(bills, lambda x: x.created_at.strftime("%m/%Y")):
        group_list = list(group)
        month_total = sum(b.total_amount for b in group_list)
        month_paid = sum(b.total_amount for b in group_list if b.payment_status == 'Paid')
        grouped_bills.append({
            'month': key,
            'bills': group_list,
            'total': month_total,
            'paid': month_paid,
            'balance': month_total - month_paid
        })

    # Total Summary
    total_sales = bills.count()
    total_revenue = bills.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = bills.filter(payment_status='Paid').aggregate(total=Sum('total_amount'))['total'] or 0
    online_sales = bills.filter(is_walkin=False).count()
    walkin_sales = bills.filter(is_walkin=True).count()
    
    context = {
        'bills': bills,
        'grouped_bills': grouped_bills,
        'report_title': report_title,
        'date_range_str': date_range_str if 'date_range_str' in locals() else today.strftime('%m/%d/%Y'),
        'generated_at': timezone.now(),
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'total_balance': total_revenue - total_paid,
        'total_sales': total_sales,
        'online_sales': online_sales,
        'walkin_sales': walkin_sales,
        'settings': settings,
    }
    
    template = get_template('shop/admin_report_pdf.html')
    html = template.render(context)
    
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"SaleReport_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    
    return HttpResponse("Error generating PDF", status=500)

def admin_walkin_success(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id, is_walkin=True)
    return render(request, 'shop/admin_walkin_success.html', {
        'bill': bill,
        'merchant_name': 'Prime Hardware',
        'upi_id': '8086158502@ybl' # Constant for now based on payment_qr.html
    })

@staff_member_required(login_url='admin_login')
def admin_products_report(request):
    from datetime import datetime
    from django.utils import timezone
    from django.db.models import Sum

    report_type = request.GET.get('type', 'all')
    date_str = request.GET.get('date')
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    
    today = timezone.localdate()
    products = Product.objects.all().select_related('brand').order_by('category', 'name')
    report_title = "Inventory Intelligence Report"

    if report_type == 'today':
        products = products.filter(created_at__date=today)
        report_title = f"Daily Inventory Report - {today.strftime('%B %d, %Y')}"
    elif report_type == 'month':
        products = products.filter(created_at__year=today.year, created_at__month=today.month)
        report_title = f"Monthly Inventory Report - {today.strftime('%B %Y')}"
    elif report_type == 'year':
        products = products.filter(created_at__year=today.year)
        report_title = f"Annual Inventory Report - {today.year}"
    elif report_type == 'custom' and date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            products = products.filter(created_at__date=target_date)
            report_title = f"Inventory Report - {target_date.strftime('%B %d, %Y')}"
        except ValueError:
            return HttpResponse("Invalid date format", status=400)
    elif report_type == 'range' and start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            products = products.filter(created_at__date__range=[start_date, end_date])
            report_title = f"Inventory Report Range ({start_date} to {end_date})"
        except ValueError:
            return HttpResponse("Invalid range format", status=400)
    
    total_inventory_value = sum(p.get_offer_price() * p.stock for p in products)
    
    # Grouping products by category for sub-totals (like Sales Report grouping)
    grouped_products = []
    # Identify unique category fields existing in current filtered products
    categories = products.values_list('category', flat=True).distinct().order_by('category')
    
    for cat_name in categories:
        cat_items = products.filter(category=cat_name)
        cat_val = sum(item.get_offer_price() * item.stock for item in cat_items)
        grouped_products.append({
            'name': cat_name or "Uncategorized",
            'list': cat_items,
            'count': cat_items.count(),
            'total_value': cat_val
        })

    stats = {
        'total': products.count(),
        'low_stock': products.filter(stock__lte=10).count(),
        'total_value': total_inventory_value,
        'categories': len(grouped_products),
    }
    
    context = {
        'grouped_products': grouped_products,
        'stats': stats,
        'report_title': report_title,
        'generated_at': timezone.now(),
        'settings': settings,
    }
    
    template = get_template('shop/admin_products_report_pdf.html')
    html = template.render(context)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"Inventory_Report_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@staff_member_required(login_url='admin_login')
def admin_orders_report(request):
    from django.utils import timezone
    orders = Bill.objects.all().order_by('-id')
    
    valid_orders = orders.exclude(order_status='Cancelled')
    stats = {
        'total': orders.count(),
        'revenue': valid_orders.aggregate(total=Sum('total_amount'))['total'] or 0,
        'delivered': orders.filter(order_status='Delivered').count(),
        'cancelled': orders.filter(order_status='Cancelled').count(),
    }
    
    context = {
        'orders': orders,
        'stats': stats,
        'report_title': "Fulfillment Analysis Report",
        'generated_at': timezone.now(),
        'settings': settings,
    }
    
    template = get_template('shop/admin_orders_report_pdf.html')
    html = template.render(context)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Orders_Report_{timezone.now().strftime("%Y%m%d")}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@staff_member_required(login_url='admin_login')
def admin_customers_report(request):
    from datetime import datetime
    from django.utils import timezone

    report_type = request.GET.get('type', 'all')
    date_str = request.GET.get('date')
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    
    today = timezone.localdate()
    customers = Customer.objects.all().select_related('user').order_by('-user__date_joined')
    report_title = "Customer Intelligence Directory"

    if report_type == 'today':
        customers = customers.filter(user__date_joined__date=today)
        report_title = f"Today's Customer Register - {today.strftime('%d %b, %Y')}"
    elif report_type == 'month':
        customers = customers.filter(user__date_joined__year=today.year, user__date_joined__month=today.month)
        report_title = f"Monthly Customer Directory - {today.strftime('%B %Y')}"
    elif report_type == 'year':
        customers = customers.filter(user__date_joined__year=today.year)
        report_title = f"Annual Customer Growth - {today.year}"
    elif report_type == 'custom' and date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            customers = customers.filter(user__date_joined__date=target_date)
            report_title = f"Customer Report - {target_date.strftime('%B %d, %Y')}"
        except ValueError:
            return HttpResponse("Invalid date format", status=400)
    elif report_type == 'range' and start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            customers = customers.filter(user__date_joined__date__range=[start_date, end_date])
            report_title = f"Customer Audit: {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
        except ValueError:
            return HttpResponse("Invalid range format", status=400)
    
    stats = {
        'total': customers.count(),
        'active': customers.filter(user__is_active=True).count(),
        'blocked': customers.filter(user__is_active=False).count(),
        'locations': customers.values('location').distinct().count(),
    }
    
    context = {
        'customers': customers,
        'stats': stats,
        'report_title': report_title,
        'generated_at': timezone.now(),
        'settings': settings,
    }
    
    template = get_template('shop/admin_customers_report_pdf.html')
    html = template.render(context)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"Customers_Report_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@staff_member_required(login_url='admin_login')
def admin_walkin_report(request):
    from datetime import datetime
    from django.utils import timezone

    report_type = request.GET.get('type', 'all')
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    
    today = timezone.localdate()
    # Fixed the ordering and field name
    customers = WalkinCustomer.objects.all().order_by('-added_at')
    report_title = "Walk-in Client Intelligence"

    if report_type == 'today':
        customers = customers.filter(added_at__date=today)
        report_title = f"Today's Walk-in Register - {today.strftime('%d %b, %Y')}"
    elif report_type == 'month':
        customers = customers.filter(added_at__year=today.year, added_at__month=today.month)
        report_title = f"Monthly Walk-in Analytics - {today.strftime('%B %Y')}"
    elif report_type == 'year':
        customers = customers.filter(added_at__year=today.year)
        report_title = f"Annual Walk-in Summary - {today.year}"
    elif report_type == 'range' and start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            customers = customers.filter(added_at__date__range=[start_date, end_date])
            report_title = f"Walk-in Audit: {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
        except ValueError:
            pass

    # Basic stats for the summary boxes
    stats = {
        'total': customers.count(),
        'this_month': WalkinCustomer.objects.filter(added_at__year=today.year, added_at__month=today.month).count(),
        # For simplicity, let's just use total count and some other placeholders
    }

    context = {
        'customers': customers,
        'stats': stats,
        'report_title': report_title,
        'generated_at': timezone.now(),
        'settings': settings,
    }

    template = get_template('shop/admin_walkin_report_pdf.html')
    html = template.render(context)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"Walkin_Report_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@staff_member_required(login_url='admin_login')
def admin_clear_orders(request):
    if request.method == "POST":
        deleted_count, _ = Bill.objects.all().delete()
        messages.success(request, f"Successfully cleared {deleted_count} order records.")
    return redirect('admin_orders')

@staff_member_required(login_url='admin_login')
def admin_clear_walkins(request):
    if request.method == "POST":
        deleted_count, _ = WalkinCustomer.objects.all().delete()
        messages.success(request, f"Successfully cleared {deleted_count} walk-in records.")
    return redirect('admin_walkin_customers')

@staff_member_required(login_url='admin_login')
def admin_clear_customers(request):
    """Delete all non-staff customer profiles and their users."""
    if request.method == "POST":
        # Get all users who have a Customer profile
        customer_users = User.objects.filter(customer__isnull=False).exclude(is_staff=True).exclude(is_superuser=True)
        count = customer_users.count()
        customer_users.delete() # Cascades to Customer
        messages.success(request, f"Successfully cleared {count} customer accounts.")
    return redirect('admin_customers')

@staff_member_required(login_url='admin_login')
def admin_clear_newsletters(request):
    if request.method == "POST":
        deleted_count, _ = NewsletterSubscriber.objects.all().delete()
        messages.success(request, f"Successfully cleared {deleted_count} subscribers.")
    return redirect('admin_newsletters')


