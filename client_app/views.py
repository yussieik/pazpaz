from django.shortcuts import render, redirect
from .models import Client, Record
from .forms import ClientForm, RecordForm


# Create your views here.
def add_client(request):
    context = {'Title': 'New Client'}

    if request.method == 'POST':
        form = ClientForm(request.POST)

        if form.is_valid():

            client = form.save()

            first_name = form.cleaned_data['f_name']
            last_name = form.cleaned_data['l_name']
            age = form.cleaned_data['age']
            phone = form.cleaned_data['phone']
            context['formInfo'] = [first_name, last_name, age, phone]
            return render(request, 'client/new_client.html', context)
        else:
            print("---ERRORS---", form.errors)
            context['form'] = form
            return render(request, 'client/new_client.html', context)
    else:
        context['form'] = ClientForm()
        return render(request, 'client/new_client.html', context)
