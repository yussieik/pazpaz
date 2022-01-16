from django.shortcuts import render, redirect
from .models import Client, Record
from .forms import ClientForm, RecordForm


# Create your views here.
def add_client(request):
    context = {'Title': 'New Client', 'form': ClientForm}
    return render(request, 'client/new_client.html', context)
