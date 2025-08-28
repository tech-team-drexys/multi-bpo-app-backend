# apps/dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.backend_status, name='backend_status'),
]