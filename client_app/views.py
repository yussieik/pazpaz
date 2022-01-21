from django.shortcuts import render, redirect
from .models import Client, Record, Treatment
from .forms import ClientForm, RecordForm, TreatmentForm
from django.views.generic.list import ListView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404


def index(request):
    context = {'Title': 'Index', 'Clients': Client.objects.all().order_by('modified')}

    return render(request, 'client/index.html', context)


def handle_404(request, exception):
    return render(request, '404.html')


def get_client(request, id):
    client = Client.objects.get(id=id)
    record = client.record_patient
    context = {'client': client, 'record': record}
    return render(request, 'client/client.html', context)


def add_client(request):
    context = {'Title': 'New Client'}

    if request.method == 'POST':
        form_client = ClientForm(request.POST)
        form_record = RecordForm(request.POST)
        if form_client.is_valid() or form_record.is_valid():
            form_client = form_client.save(commit=False)
            form_record = form_record.save(commit=False)
            client = Client(name=form_client.name, age=form_client.age, phone=form_client.phone,
                            address=form_client.address)
            rec = Record(client=client, description=form_record.description)
            client.save()
            rec.save()
            return redirect('index')
        else:
            print("---ERRORS---", form_client.errors)
            print("---ERRORS---", form_record.errors)
            context['client_form'] = form_client
            context['record_form'] = form_record
            return render(request, 'client/new_client.html', context)
    else:
        context['client_form'] = ClientForm()
        context['record_form'] = RecordForm()
        return render(request, 'client/new_client.html', context)


def add_treatment(request, id):
    client = Client.objects.get(id=id)

    context = {'Title': 'New treatment', 'client': client}

    if request.method == 'POST':
        form = TreatmentForm(request.POST)
        form.client = client

        if form.is_valid():
            n_record = Treatment(client=client, description=form.cleaned_data['description'])
            n_record.save()
            # form.save()
            description = form.cleaned_data['description']
            context['formInfo'] = [client, description]
            return redirect(f'../../client/{client.id}')
        else:
            print("---ERRORS---", form.errors)
            context['form'] = form
            return render(request, 'client/add_treatment.html', context)
    else:
        context['form'] = RecordForm()
        return render(request, 'client/add_treatment.html', context)


def search_client(request):
    client = request.GET.get('client')

    payload = []
    if client:
        client_objs = Client.objects.filter(f_name__icontains=client)

        for client in client_objs:
            payload.append(client)

    return JsonResponse({'status': 200, 'data': payload})
