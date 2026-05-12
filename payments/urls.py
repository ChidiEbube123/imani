from django.urls import path
from . import views

urlpatterns = [
    path('', views.payment_list, name='payment_list'),
    path('<int:pk>/', views.payment_detail, name='payment_detail'),
    path('<int:pk>/approve/', views.approve_payment, name='approve_payment'),
    path('api/stats/', views.payment_stats_api, name='payment_stats_api'),
]
