from django.urls import path
from . import views

urlpatterns = [
    path("index", views.index, name='index'),
    path("new_client", views.add_client, name='new_client'),
    path("new_record", views.add_record, name='new_record'),
    path("client/<int:id>", views.get_client, name='get_client')
    ]
