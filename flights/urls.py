from django.urls import path
from .views import search_flights

urlpatterns = [
    path("search/", search_flights, name="search_flights"),
]