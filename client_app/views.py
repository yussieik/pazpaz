from django.shortcuts import render, redirect
from .models import Client, Record
from .forms import ClientForm, RecordForm
from django.views.generic.list import ListView
from django.http import JsonResponse

def index(request):
    context = {'Title': 'Index', 'Clients': Client.objects.all().order_by('modified')}

    return render(request, 'client/index.html', context)


def handle_404(request, exception):
    return render(request, '404.html')


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
            # first_name = form.cleaned_data['f_name']
            # last_name = form.cleaned_data['l_name']
            # age = form.cleaned_data['age']
            # phone = form.cleaned_data['phone']
            # description = form.cleaned_data['description']
            # context['formInfo'] = [first_name, last_name, age, phone, description]
            # return render(request, 'client/new_client.html', context)
            return redirect('index')
        else:
            print("---ERRORS---", form.errors)
            context['form'] = form
            return render(request, 'client/new_client.html', context)
    else:
        context['form'] = ClientForm()
        return render(request, 'client/new_client.html', context)


def add_record(request, id):
    client = Client.objects.get(id=id)

    context = {'Title': 'Add record', 'client': client}

    if request.method == 'POST':
        form = RecordForm(request.POST)
        form.client = client

        if form.is_valid():
            n_record = Record(client = client, description = form.cleaned_data['description'])
            n_record.save()
            # form.save()
            description = form.cleaned_data['description']
            context['formInfo'] = [client, description]
            return redirect(f'../../client/{client.id}')
        else:
            print("---ERRORS---", form.errors)
            context['form'] = form
            return render(request, 'client/add_record.html', context)
    else:
        context['form'] = RecordForm()
        return render(request, 'client/add_record.html', context)


def search_client(request):
    client = request.GET.get('client')

    payload = []
    if client:
        client_objs = Client.objects.filter(f_name__icontains=client)

        for client in client_objs:
            payload.append(client)

    return JsonResponse({'status': 200, 'data': payload})