from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Auction


@receiver(pre_save, sender=Auction)
def close_auction(sender, instance, **kwargs):
    if instance.end_date and instance.end_date <= timezone.now():
        print("Auction closed", instance.title)
        print(timezone.now())
        instance.closed = True