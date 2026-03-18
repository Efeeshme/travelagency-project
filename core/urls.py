from django.urls import path
from . import views

urlpatterns = [
    path("", views.mainlanding, name="mainlanding"),
    path("search/", views.landing, name="landing"),
]