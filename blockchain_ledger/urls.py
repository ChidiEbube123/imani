from django.urls import path
from . import views

urlpatterns = [
    path('', views.ledger_view, name='ledger_view'),
    path('api/status/', views.chain_status, name='chain_status'),
    path('api/block/<int:index>/', views.block_detail, name='block_detail'),
]
