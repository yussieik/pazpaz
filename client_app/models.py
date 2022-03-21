from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from colorfield.fields import ColorField
import pytz
from _datetime import datetime


def get_localtime(utctime):
    utc = utctime.replace(tzinfo=pytz.UTC)
    localtz = utc.astimezone(timezone.get_current_timezone())
    return localtz


time = get_localtime(datetime.now())


# Create your models here.

class Client(models.Model):
    name = models.CharField('שם', max_length=200)
    age = models.IntegerField('גיל')
    phone = PhoneNumberField('מספר טלפון', region='IL')

    COLOR_PALETTE = [
        ('#FFFFFF', 'white', ),
        ('#000000', 'black', ),
    ]

    color = ColorField(samples=COLOR_PALETTE, default='#FF0000')

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
        return f"{self.name}"


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
    description = models.TextField('תיאור הבעיה', blank=True)
    process = models.TextField('הטיפול הניתן', blank=True)
    notice = models.TextField('הערות', blank=True)

    created = models.DateTimeField(editable=True)
    modified = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.id:
            if not self.created:
                self.created = timezone.localtime(time).strftime("%Y-%m-%d %H:%M:%S")
        self.modified = timezone.localtime(time).strftime("%Y-%m-%d %H:%M:%S")
        return super(Treatment, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.modified}, {self.description}"

class Event(models.Model):
    client = models.ForeignKey(Client, verbose_name='מטופל', on_delete=models.CASCADE, related_name='events')
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, related_name='treatment')
    event_date = models.DateTimeField(verbose_name='תאריך')
    done = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.client} + {self.event_date}"

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        if not self.id:
            self.treatment = Treatment.objects.create(client=self.client, created=self.event_date)
            super(Event, self).save(force_insert=False, force_update=False, *args, **kwargs)
        super(Event, self).save(force_insert=False, force_update=False, *args, **kwargs)