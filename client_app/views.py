from django.shortcuts import render, redirect
from .models import Client, Record, Treatment, Event
from .forms import ClientForm, RecordForm, TreatmentForm, EventForm
from django.http import JsonResponse
from datetime import datetime


def index(request):
    context = {'Title': 'Index', 'Clients': Client.objects.all()}

    return render(request, 'client/index.html', context)


def schedule_treatment(request):
    today = datetime.today()
    events = Event.objects.filter(event_date__gte=today).order_by('event_date')
    events_divided = {}
    for event in events:
        event_d = event.event_date.strftime("%Y/%m/%d")
        if event_d in events_divided:
            events_divided[event_d].append(event)
        else:
            events_divided[event_d] = [event]
    context = {'Title': 'Scheduler', 'events': events, 'events_divided': events_divided, 'today': today.strftime("%Y/%m/%d")}

    if request.method == 'POST':
        form_event = EventForm(request.POST)
        if form_event.is_valid():
            form_event.save()
            return redirect('index')
        else:
            print("---ERRORS---", form_event.errors)
            context['event_form'] = form_event
            return render(request, 'schedule/schedule_treatment.html', context)
    else:
        context['event_form'] = EventForm()
        return render(request, 'schedule/schedule_treatment.html', context)


def get_client(request, id):
    client = Client.objects.get(id=id)
    record = client.record_patient
    context = {'Title': 'Client', 'client': client, 'record': record,
               'treatments': client.treatments.all().order_by('-created')}
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

            description = form.cleaned_data['description']
            process = form.cleaned_data['process']
            notice = form.cleaned_data['notice']
            n_treat = Treatment(client=client, description=description, process=process, notice=notice)
            n_treat.save()
            context['formInfo'] = [client, description, process, notice]
            return redirect(f'../../client/{client.id}')
        else:
            print("---ERRORS---", form.errors)
            context['form'] = form
            return render(request, 'client/add_treatment.html', context)
    else:
        context['form'] = TreatmentForm()
        return render(request, 'client/add_treatment.html', context)


def update_client(request, id):
    client = Client.objects.get(id=id)
    record = Record.objects.get(client_id=client.id)
    form_client = ClientForm(request.POST or None, instance=client)
    form_record = RecordForm(request.POST or None, instance=record)
    context = {'Title': 'Update Client', 'client': client, 'record': record, 'client_form': form_client,
               'record_form': form_record}

    if request.method == 'POST':
        if form_client.is_valid() and form_record.is_valid():
            form_client.save()
            form_record.save()
            print('Success')
            return redirect(f'../../client/{client.id}')
        else:
            print("---ERRORS---", form_client.errors)
    else:
        return render(request, 'client/update_client.html', context)


def update_treat(request, c_id, t_id):
    client = Client.objects.get(id=c_id)
    treatment = client.treatments.get(id=t_id)
    form_treat = TreatmentForm(request.POST or None, instance=treatment)
    context = {'Title': 'Update treatment', 'form': form_treat, 'client': client, 'treatment': treatment}

    if request.method == 'POST':
        if form_treat.is_valid():
            form_treat.save()
            print('Success')
            return redirect(f'../../../client/{client.id}')
        else:
            print("---ERRORS---", form_treat.errors)
    else:
        return render(request, 'client/update_treatment.html', context)


def update_event(request, event_id):
    event = Event.objects.get(id=event_id)
    form_event = EventForm(request.POST or None, instance=event)

    if request.method == 'POST':
        if form_event.is_valid():
            form_event.save()
            print('Success')
            return schedule_treatment(request)
        else:
            print("---ERRORS---", form_event.errors)
    else:
        return schedule_treatment(request)


def remove_treatment(request, part_id):
    treatment_obj = Treatment.objects.get(id=part_id)
    client = treatment_obj.client
    treatment_obj.delete()
    return get_client(request, client.id)


def remove_event(request, event_id):
    event_obj = Event.objects.get(id=event_id)
    event_obj.delete()
    return schedule_treatment(request)


def search_client(request):
    client = request.GET.get('client')

    payload = []
    if client:
        client_objs = Client.objects.filter(f_name__icontains=client)

        for client in client_objs:
            payload.append(client)

    return JsonResponse({'status': 200, 'data': payload})


def handle_404(request, exception):
    return render(request, '404.html')