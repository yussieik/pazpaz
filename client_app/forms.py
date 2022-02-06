from django import forms
from .models import Client, Record, Treatment, Event
from django.forms import modelformset_factory


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'
        exclude = ['created', 'modified']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'textarea'}),
        }


class RecordForm(forms.ModelForm):
    class Meta:
        model = Record
        fields = '__all__'
        exclude = ['client', 'created', 'modified']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'textarea'}),
        }


class TreatmentForm(forms.ModelForm):
    class Meta:
        model = Treatment
        fields = '__all__'
        exclude = ['client', 'modified', 'created']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'textarea'}),
        }


class EventForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(EventForm, self).__init__(*args, **kwargs)
        self.fields['event_date'].localize = True
        self.fields['event_date'].widget.is_localized = True

    class Meta:
        model = Event
        fields = ['client', 'event_date']

        widgets = {
            'client': forms.Select(),
            'event_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'language': 'he'}),
        }

