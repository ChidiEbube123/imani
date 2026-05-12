from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.citizen_register, name='citizen_register'),
    path('login/', views.citizen_login, name='citizen_login'),
    path('logout/', views.citizen_logout, name='citizen_logout'),
    path('dashboard/', views.citizen_dashboard, name='citizen_dashboard'),
    path('profile/', views.citizen_profile, name='citizen_profile'),
    path('projects/', views.public_project_list, name='public_project_list'),
    path('projects/<int:pk>/', views.public_project_detail, name='public_project_detail'),
    path('projects/<int:project_id>/submit/', views.citizen_upload, name='citizen_upload'),
]
