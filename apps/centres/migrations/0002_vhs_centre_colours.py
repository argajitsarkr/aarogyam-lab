"""Repaint the three centres.

`seed_centres` only fills in centres that do not exist yet, so changing its
defaults does nothing to a database that already has them. This carries the new
colours to the server.

Only the three seeded short codes are touched, and only if they still hold the
old default colour - a colour someone has since chosen in the Centres page is
left alone.
"""
from django.db import migrations

OLD_TO_NEW = {
    "ARP": ("#0f766e", "#7B2D56"),  # plum - white text, 8.9:1
    "RRM": ("#7c3aed", "#D6303A"),  # red  - white text, 4.8:1
    "BHY": ("#ea580c", "#F4873A"),  # orange - near-black text, 7.9:1
}


def repaint(apps, schema_editor):
    Centre = apps.get_model("centres", "Centre")
    for code, (old, new) in OLD_TO_NEW.items():
        Centre.objects.filter(short_code=code, colour__iexact=old).update(colour=new)


def unpaint(apps, schema_editor):
    Centre = apps.get_model("centres", "Centre")
    for code, (old, new) in OLD_TO_NEW.items():
        Centre.objects.filter(short_code=code, colour__iexact=new).update(colour=old)


class Migration(migrations.Migration):
    dependencies = [("centres", "0001_initial")]
    operations = [migrations.RunPython(repaint, unpaint)]
