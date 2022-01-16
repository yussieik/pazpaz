from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField


# Create your models here.

class Client(models.Model):
    f_name = models.CharField(max_length=200)
    l_name = models.CharField(max_length=200)
    age = models.IntegerField()
    phone = PhoneNumberField(region='IL')

    description = models.TextField()

    created = models.DateTimeField(editable=False)
    modified = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.id:
            self.created = timezone.now()
        self.modified = timezone.now()
        return super(Client, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.f_name} {self.l_name}, {self.age}"


class Record(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='record_patient')

    description = models.TextField()

    created = models.DateTimeField(editable=False)
    modified = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.id:
            self.created = timezone.now()
        self.modified = timezone.now()
        return super(Record, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.id}, {self.client.f_name} {self.client.l_name}"

