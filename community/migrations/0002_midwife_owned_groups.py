import django.db.models.deletion
from django.db import migrations, models


def promote_midwife_members(apps, schema_editor):
    GroupMember = apps.get_model("community", "GroupMember")
    GroupMember.objects.filter(user__role="MIDWIFE").update(role="MIDWIFE")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
        ("community", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hospitalgroup",
            name="hospital",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="groups",
                to="accounts.hospitalprofile",
            ),
        ),
        migrations.AddField(
            model_name="hospitalgroup",
            name="owner_midwife",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="community_groups",
                to="accounts.midwifeprofile",
            ),
        ),
        migrations.AlterField(
            model_name="groupmember",
            name="role",
            field=models.CharField(
                choices=[
                    ("PATIENT", "Patient"),
                    ("DOCTOR", "Doctor"),
                    ("MIDWIFE", "Midwife"),
                    ("NURSE", "Nurse"),
                    ("ADMIN", "Admin"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(promote_midwife_members, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="hospitalgroup",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(hospital__isnull=False)
                    | models.Q(owner_midwife__isnull=False)
                ),
                name="community_group_has_owner",
            ),
        ),
    ]
