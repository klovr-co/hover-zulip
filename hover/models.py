from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CASCADE, Q, RESTRICT, SET_NULL
from django.db.models.functions import Lower
from django.utils.timezone import now as timezone_now

from zerver.models.channel_folders import ChannelFolder
from zerver.models.messages import Message
from zerver.models.realms import Realm
from zerver.models.streams import Stream
from zerver.models.users import UserProfile


class Space(models.Model):
    MAX_NAME_LENGTH = 60
    MAX_DESCRIPTION_LENGTH = 1024

    class State(models.TextChoices):
        SETUP = "setup", "Setup"
        LAUNCHED = "launched", "Launched"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    description = models.CharField(max_length=MAX_DESCRIPTION_LENGTH, default="")
    state = models.TextField(choices=State.choices, default=State.SETUP)
    category = models.ForeignKey(ChannelFolder, on_delete=RESTRICT, related_name="hover_spaces")
    created_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="created_hover_spaces"
    )
    stream = models.OneToOneField(
        Stream,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="hover_space",
    )
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "realm", name="hover_space_unique_name_in_realm"
            ),
            models.CheckConstraint(
                condition=(
                    Q(state="setup", stream__isnull=True)
                    | Q(state="launched", stream__isnull=False)
                ),
                name="hover_space_state_requires_stream",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.category_id is not None and self.realm_id != self.category.realm_id:
            raise ValidationError({"category": "Spaces and categories must share an organization."})
        if self.created_by_id is not None and self.realm_id != self.created_by.realm_id:
            raise ValidationError({"created_by": "Spaces and creators must share an organization."})
        if self.stream_id is not None and self.realm_id != self.stream.realm_id:
            raise ValidationError({"stream": "Spaces and channels must share an organization."})


class SpaceAdministrator(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    space = models.ForeignKey(Space, on_delete=CASCADE, related_name="administrator_assignments")
    user = models.ForeignKey(
        UserProfile, on_delete=CASCADE, related_name="hover_space_administrator_assignments"
    )
    added_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="hover_space_administrator_assignments_added",
    )
    date_created = models.DateTimeField(default=timezone_now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["space", "user"], name="hover_space_administrator_unique_user"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.space_id is not None and self.realm_id != self.space.realm_id:
            raise ValidationError({"space": "Space administrators must share the Space organization."})
        if self.user_id is not None and self.realm_id != self.user.realm_id:
            raise ValidationError({"user": "Space administrators must share the Space organization."})
        if self.added_by_id is not None and self.realm_id != self.added_by.realm_id:
            raise ValidationError({"added_by": "Space administrators must share the actor organization."})


class GeneratedItem(models.Model):
    class OutputType(models.TextChoices):
        FEED_UPDATE = "feed_update", "Feed update"
        DIGEST = "digest", "Digest"
        SUGGESTED_ACTION = "suggested_action", "Suggested action"
        PROGRESS_UPDATE = "progress_update", "Progress update"
        DECISION = "decision", "Decision"
        ANALYSIS = "analysis", "Analysis"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    message = models.OneToOneField(Message, on_delete=CASCADE, related_name="hover_generated_item")
    output_type = models.TextField(choices=OutputType.choices)
    module_key = models.TextField()
    module_name = models.TextField()
    module_version = models.TextField()
    source_summary = models.TextField()

    def clean(self) -> None:
        super().clean()
        if self.message_id is not None and self.realm_id != self.message.realm_id:
            raise ValidationError({"message": "Generated items and messages must share an organization."})


class EvidenceLink(models.Model):
    generated_item = models.ForeignKey(
        GeneratedItem, on_delete=CASCADE, related_name="evidence_links"
    )
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    position = models.PositiveIntegerField()
    provider_key = models.TextField()
    provider_name = models.TextField()
    display_name = models.TextField()
    url = models.URLField(blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["generated_item", "position"], name="hover_evidence_link_unique_position"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.generated_item_id is not None and self.realm_id != self.generated_item.realm_id:
            raise ValidationError(
                {"generated_item": "Evidence links and generated items must share an organization."}
            )
