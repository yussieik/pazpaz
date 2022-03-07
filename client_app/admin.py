from django.contrib import admin
from .models import Client, Record, Treatment, Event

# Register your models here.
admin.site.register(Client)
admin.site.register(Record)
admin.site.register(Treatment)
admin.site.register(Event)

