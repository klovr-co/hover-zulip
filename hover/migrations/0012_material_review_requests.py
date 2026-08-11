# Generated for Hover's material Review request workflow.

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hover", "0011_reply_review"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SourceParticipantBinding",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("participant_ref", models.CharField(max_length=39, validators=[django.core.validators.RegexValidator(message="Participant references must be opaque participant IDs.", regex="^person_[0-9a-f]{32}$")])),
                ("match_basis", models.TextField(choices=[("verified_email", "Verified email"), ("verified_phone", "Verified phone")])),
                ("observation_basis", models.CharField(max_length=36, validators=[django.core.validators.RegexValidator(message="Observation bases must be opaque observation IDs.", regex="^obs_[0-9a-f]{32}$")])),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                ("realm", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="zerver.realm")),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participant_bindings", to="hover.source")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hover_source_participant_bindings", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="DisputedDetail",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ambiguity_key", models.CharField(max_length=42, validators=[django.core.validators.RegexValidator(message="Ambiguity keys must be opaque ambiguity IDs.", regex="^ambiguity_[0-9a-f]{32}$")])),
                ("field_path", models.CharField(max_length=64, validators=[django.core.validators.RegexValidator(message="Disputed fields must be normalized top-level keys.", regex="^[a-z][a-z0-9_]{0,63}$")])),
                ("summary", models.CharField(max_length=500)),
                ("material", models.BooleanField()),
                ("state", models.TextField(choices=[("needs_review", "Needs review"), ("resolved", "Resolved")], default="needs_review")),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                ("generated_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="disputed_details", to="hover.generateditem")),
                ("realm", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="zerver.realm")),
                ("resolved_by_revision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name="resolved_disputed_details", to="hover.revision")),
            ],
        ),
        migrations.CreateModel(
            name="DisputedEvidenceLink",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField()),
                ("disputed_detail", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conflicting_evidence", to="hover.disputeddetail")),
                ("evidence_link", models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name="dispute_links", to="hover.evidencelink")),
                ("realm", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="zerver.realm")),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.CreateModel(
            name="ReviewRequest",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("state", models.TextField(choices=[("open", "Open"), ("resolved", "Resolved")], default="open")),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("disputed_detail", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="review_request", to="hover.disputeddetail")),
                ("message", models.OneToOneField(on_delete=django.db.models.deletion.RESTRICT, related_name="hover_review_request", to="zerver.message")),
                ("realm", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="zerver.realm")),
                ("resolved_by_revision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name="resolved_review_requests", to="hover.revision")),
            ],
        ),
        migrations.CreateModel(
            name="ReviewRequestTarget",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.TextField(choices=[("involved_teammate", "Involved teammate"), ("space_admin_fallback", "Space administrator fallback")])),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("realm", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="zerver.realm")),
                ("review_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="targets", to="hover.reviewrequest")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(model_name="sourceparticipantbinding", constraint=models.UniqueConstraint(fields=("source", "participant_ref"), name="hover_source_participant_unique_ref")),
        migrations.AddConstraint(model_name="disputeddetail", constraint=models.UniqueConstraint(fields=("generated_item", "ambiguity_key"), name="hover_disputed_detail_unique_ambiguity")),
        migrations.AddConstraint(model_name="disputeddetail", constraint=models.UniqueConstraint(fields=("generated_item", "field_path"), name="hover_disputed_detail_unique_field")),
        migrations.AddConstraint(model_name="disputeddetail", constraint=models.CheckConstraint(condition=models.Q(models.Q(("resolved_by_revision__isnull", True), ("state", "needs_review")), models.Q(("resolved_by_revision__isnull", False), ("state", "resolved")), _connector="OR"), name="hover_disputed_detail_resolution_matches_state")),
        migrations.AddConstraint(model_name="disputedevidencelink", constraint=models.UniqueConstraint(fields=("disputed_detail", "evidence_link"), name="hover_disputed_evidence_unique_link")),
        migrations.AddConstraint(model_name="disputedevidencelink", constraint=models.UniqueConstraint(fields=("disputed_detail", "position"), name="hover_disputed_evidence_unique_position")),
        migrations.AddConstraint(model_name="reviewrequest", constraint=models.CheckConstraint(condition=models.Q(models.Q(("resolved_at__isnull", True), ("resolved_by_revision__isnull", True), ("state", "open")), models.Q(("resolved_at__isnull", False), ("resolved_by_revision__isnull", False), ("state", "resolved")), _connector="OR"), name="hover_review_request_resolution_matches_state")),
        migrations.AddConstraint(model_name="reviewrequesttarget", constraint=models.UniqueConstraint(fields=("review_request", "user"), name="hover_review_request_unique_target")),
    ]
