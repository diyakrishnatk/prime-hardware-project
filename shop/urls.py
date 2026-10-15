from django.urls import path
from . import views

urlpatterns = [

    # HOME
    path('', views.home, name='home'),

    # CATEGORY & PRODUCT
    path('products/', views.all_products, name='all_products'),
    path('category/<str:category>/', views.category_products, name='category_products'),
    path('book/<int:product_id>/', views.book_product, name='book_product'),

    # CART
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('remove-from-cart/<str:key>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/increase/<str:key>/', views.increase_cart, name='increase_cart'),
    path('cart/decrease/<str:key>/', views.decrease_cart, name='decrease_cart'),
    path('checkout/', views.checkout, name='checkout'),
     
    # ORDERS
    path('my-orders/', views.my_orders, name='my_orders'),
    path('delete-order/<int:order_id>/', views.delete_order, name='delete_order'),
    path('download-bill/<int:bill_id>/', views.download_bill, name='download_bill'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-success/<int:bill_id>/', views.payment_success, name='payment_success_with_id'),

    # AUTH
    path('signup/', views.signup, name='signup'),
    path('signin/', views.signin, name='signin'),
    path('logout/', views.signout, name='logout'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-reset-otp/', views.verify_reset_otp, name='verify_reset_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),

    # ADMIN
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    path('admin-product-stock/<int:product_id>/',
    views.edit_product_stock,
    name='edit_product_stock'),
    
    #TRACKING
    path('track-order/<int:order_id>/', views.track_order, name='track_order'),



    path('admin-products/', views.admin_products, name='admin_products'),
    path('admin-add-product/', views.add_product, name='add_product'),
    path('admin-delete-product/<int:product_id>/', views.delete_product, name='delete_product'),
    path('admin-customers/', views.admin_customers, name='admin_customers'),

    # ⭐ ADD THESE TWO
    path('toggle-customer/<int:customer_id>/',
     views.toggle_customer,
     name='toggle_customer'),

    path('delete-customer/<int:customer_id>/',
     views.delete_customer,
     name='delete_customer'),
    path('admin-orders/', views.admin_orders, name='admin_orders'),
    path('update-order/<int:order_id>/', views.update_order_status, name='update_order_status'),

    # Newsletters
    path('subscribe/', views.subscribe_newsletter, name='subscribe_newsletter'),
    path('admin-newsletters/', views.admin_newsletters, name='admin_newsletters'),
    path('admin-delete-newsletter/<int:subscriber_id>/', views.delete_newsletter, name='delete_newsletter'),


    path('pay/<int:bill_id>/', views.create_payment_link, name='create_payment_link_with_id'),
    # path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-done/<int:bill_id>/', views.payment_done, name='payment_done'),

    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('profile/', views.user_profile, name='profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('book-cart/<str:key>/', views.book_single_from_cart, name='book_single_from_cart'),   
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),
    path('admin-offers/', views.admin_offers, name='admin_offers'),
    path('toggle-offer/<int:product_id>/', views.toggle_offer, name='toggle_offer'), 
    
    path('product-feedback/<int:product_id>/', views.product_feedback, name='product_feedback'),
    path('admin-feedback/', views.admin_feedback, name='admin_feedback'),
    path('admin-walkin-customers/', views.admin_walkin_customers, name='admin_walkin_customers'),
    path('admin-add-walkin/', views.add_walkin_customer, name='add_walkin_customer'),
    path('admin-walkin-order/<int:customer_id>/', views.admin_walkin_order, name='admin_walkin_order'),
    path('admin-walkin-success/<int:bill_id>/', views.admin_walkin_success, name='admin_walkin_success'),
    path('admin-delete-walkin/<int:customer_id>/', views.delete_walkin_customer, name='delete_walkin_customer'),
    path('admin-sales-report/', views.admin_sales_report, name='admin_sales_report'),
    path('admin-products-report/', views.admin_products_report, name='admin_products_report'),
    path('admin-orders-report/', views.admin_orders_report, name='admin_orders_report'),
    path('admin-customers-report/', views.admin_customers_report, name='admin_customers_report'),
    path('admin-walkin-report/', views.admin_walkin_report, name='admin_walkin_report'),
    path('admin-clear-orders/', views.admin_clear_orders, name='admin_clear_orders'),
    path('admin-clear-walkins/', views.admin_clear_walkins, name='admin_clear_walkins'),
    path('admin-clear-customers/', views.admin_clear_customers, name='admin_clear_customers'),
    path('admin-clear-newsletters/', views.admin_clear_newsletters, name='admin_clear_newsletters'),
]
