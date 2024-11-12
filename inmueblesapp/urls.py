from django.urls import path
from inmueblesapp.views import hello

urlpatterns = [
    path('', hello),
]