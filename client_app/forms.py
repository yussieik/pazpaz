from django import forms
from .models import Client, Record, Treatment
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