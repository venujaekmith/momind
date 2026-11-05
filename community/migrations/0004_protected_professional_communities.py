import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
        ("community", "0003_community_ai_insight"),
    ]

    operations = [
        migrations.AddField(
            model_name="hospitalgroup",
            name="owner_doctor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="community_groups",
                to="accounts.doctorprofile",
            ),
        ),
        migrations.AddField(
            model_name="groupcomment",
            name="is_private",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="groupcomment",
            name="recipient",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="private_community_responses",
                to="accounts.user",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="hospitalgroup",
            name="community_group_has_owner",
        ),
        migrations.AddConstraint(
            model_name="hospitalgroup",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(hospital__isnull=False)
                    | models.Q(owner_midwife__isnull=False)
                    | models.Q(owner_doctor__isnull=False)
                ),
                name="community_group_has_owner",
            ),
        ),
    ]
