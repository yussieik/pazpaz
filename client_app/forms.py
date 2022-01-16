from django import forms
from .models import Client, Record
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
        exclude = ['created', 'modified']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'textarea'}),
        }


