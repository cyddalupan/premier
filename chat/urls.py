from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('webhook/', views.webhook_callback, name='webhook_callback'),
]