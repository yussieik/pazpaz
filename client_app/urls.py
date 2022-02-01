from django.urls import path
from . import views

urlpatterns = [
    path("index", views.index, name='index'),
    path("new_client", views.add_client, name='new_client'),
    path("client/add_treatment/<int:id>", views.add_treatment, name='new_treatment'),
    path("client/<int:id>", views.get_client, name='get_client'),
    path("search/", views.search_client, name='search_client'),
    path("client/update_client/<int:id>", views.update_client, name='update_client'),
    path("client/update_treatment/<int:c_id>/<int:t_id>", views.update_treat, name='update_treatment'),
    path("schedule/schedule_treatment", views.schedule_treatment, name='schedule_treatment'),
    path("client/remove_treatment/<int:part_id>", views.remove_treatment, name='remove_treatment'),
    path("schedule/remove_event/<int:event_id>", views.remove_event, name='remove_event'),
    path("schedule/update_event/<int:event_id>", views.update_event, name='update_event'),

]

handler404 = "client_app.views.handle_404"
