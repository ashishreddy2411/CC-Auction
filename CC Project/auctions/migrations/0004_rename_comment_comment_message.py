# Generated by Django 3.2.5 on 2022-06-16 06:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auctions', '0003_auction_current_bid'),
    ]

    operations = [
        migrations.RenameField(
            model_name='comment',
            old_name='comment',
            new_name='message',
        ),
    ]