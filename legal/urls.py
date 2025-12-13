from django.urls import path
from . import views

app_name = 'legal'

urlpatterns = [
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
]
