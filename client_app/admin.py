from django.contrib import admin
from .models import Client, Record, Treatment

# Register your models here.
admin.site.register(Client)
admin.site.register(Record)
admin.site.register(Treatment)


