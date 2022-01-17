from django.shortcuts import render, redirect
from .models import Client, Record
from .forms import ClientForm, RecordForm


def index(request):
    context = {'Title': 'Index', 'Clients': Client.objects.all()}

    return render(request, 'client/index.html', context)


# Create your views here.

def get_client(request, id):
    client = Client.objects.get(id=id)
    records = client.record_patient.all()
    context = {'client': client, 'records': records}
    return render(request, 'client/client.html', context)


def add_client(request):
    context = {'Title': 'New Client'}

    if request.method == 'POST':
        form = ClientForm(request.POST)

        if form.is_valid():

            form.save()

            first_name = form.cleaned_data['f_name']
            last_name = form.cleaned_data['l_name']
            age = form.cleaned_data['age']
            phone = form.cleaned_data['phone']
            description = form.cleaned_data['description']
            context['formInfo'] = [first_name, last_name, age, phone, description]
            return render(request, 'client/new_client.html', context)
        else:
            print("---ERRORS---", form.errors)
            context['form'] = form
            return render(request, 'client/new_client.html', context)
    else:
        context['form'] = ClientForm()
        return render(request, 'client/new_client.html', context)


def add_record(request):
    context = {'Title': 'Add record'}
    if request.method == 'POST':
        form = RecordForm(request.POST)

        if form.is_valid():

            form.save()

            client = form.cleaned_data['client']
            description = form.cleaned_data['description']
            context['formInfo'] = [client, description]
            return render(request, 'client/add_record.html', context)
        else:
            print("---ERRORS---", form.errors)
            context['form'] = form
            return render(request, 'client/add_record.html', context)
    else:
        context['form'] = RecordForm()
        return render(request, 'client/add_record.html', context)
