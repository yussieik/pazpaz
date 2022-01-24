from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField

time = timezone.localtime(timezone.now())

# Create your models here.

class Client(models.Model):
    name = models.CharField('שם', max_length=200)
    age = models.IntegerField('גיל')
    phone = PhoneNumberField('מספר טלפון', region='IL')

    address = models.CharField('כתובת', max_length=255)

    created = models.DateTimeField(editable=False)
    modified = models.DateTimeField()

    def get_fields(self):
        return {field.name: field.value_to_string(self) for field in Client._meta.fields if
                field.name not in ['id', 'created', 'modified']}

    def save(self, *args, **kwargs):
        if not self.id:
            self.created = timezone.localtime(time).strftime("%Y-%m-%d %H:%M:%S")

        self.modified = timezone.localtime(time).strftime("%Y-%m-%d %H:%M:%S")

        return super(Client, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}, {self.age}"


class Record(models.Model):
    client = models.OneToOneField(Client, verbose_name="מטופל", on_delete=models.CASCADE, related_name='record_patient')

    description = models.TextField('תיאור')

    created = models.DateTimeField(editable=False)
    modified = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.id:
            self.created = timezone.localtime(time).strftime("%Y-%m-%d %H:%M:%S")
        self.modified = timezone.localtime(time).strftime("%Y-%m-%d %H:%M:%S")
        return super(Record, self).save(*args, **kwargs)

    def __str__(self):
        return f"תיק  {self.id} : {self.description}"


class Treatment(models.Model):

    class Meta:
        ordering = ('modified',)

    client = models.ForeignKey(Client, on_delete=models.DO_NOTHING, related_name='treatments')
    description = models.TextField('תיאור')

    created = models.DateTimeField(editable=False)
    modified = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.id:
            self.created = timezone.localtime(time).strftime("%Y-%m-%d %H:%M:%S")
        self.modified = timezone.localtime(time).strftime("%Y-%m-%d %H:%M:%S")
        return super(Treatment, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.modified}, {self.description}"



