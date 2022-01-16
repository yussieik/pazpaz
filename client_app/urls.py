from django.urls import path
from . import views

urlpatterns = [
    path("new_client", views.add_client, name='new_client')]
