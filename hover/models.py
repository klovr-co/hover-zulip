from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import CASCADE, RESTRICT, SET_NULL, Q
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
            raise ValidationError(
                {"space": "Space administrators must share the Space organization."}
            )
        if self.user_id is not None and self.realm_id != self.user.realm_id:
            raise ValidationError(
                {"user": "Space administrators must share the Space organization."}
            )
        if self.added_by_id is not None and self.realm_id != self.added_by.realm_id:
            raise ValidationError(
                {"added_by": "Space administrators must share the actor organization."}
            )


observation_basis_validator = RegexValidator(
    regex=r"^obs_[0-9a-f]{32}$",
    message="Observation bases must be opaque observation IDs.",
)


class SpaceMembership(models.Model):
    class Role(models.TextChoices):
        CONTRIBUTOR = "contributor", "Contributor"
        SUBSCRIBER = "subscriber", "Subscriber"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    space = models.ForeignKey(Space, on_delete=CASCADE, related_name="memberships")
    user = models.ForeignKey(UserProfile, on_delete=CASCADE, related_name="hover_space_memberships")
    role = models.TextField(choices=Role.choices)
    added_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="hover_space_memberships_added",
    )
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["space", "user"], name="hover_space_membership_unique_user"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.space_id is not None and self.realm_id != self.space.realm_id:
            raise ValidationError({"space": "Space memberships must share the Space organization."})
        if self.user_id is not None and self.realm_id != self.user.realm_id:
            raise ValidationError({"user": "Space memberships must share the user organization."})
        if self.added_by_id is not None and self.realm_id != self.added_by.realm_id:
            raise ValidationError(
                {"added_by": "Space memberships must share the actor organization."}
            )


class SpaceMembershipSuggestion(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pending review"
        CONFIRMED = "confirmed", "Confirmed"
        REMOVED = "removed", "Removed"

    class MatchBasis(models.TextChoices):
        VERIFIED_EMAIL = "verified_email", "Verified email"
        VERIFIED_PHONE = "verified_phone", "Verified phone"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    space = models.ForeignKey(Space, on_delete=CASCADE, related_name="membership_suggestions")
    user = models.ForeignKey(
        UserProfile, on_delete=CASCADE, related_name="hover_space_membership_suggestions"
    )
    suggested_role = models.TextField(choices=SpaceMembership.Role.choices)
    state = models.TextField(choices=State.choices, default=State.PENDING)
    match_basis = models.TextField(choices=MatchBasis.choices)
    observation_basis = models.CharField(max_length=36, validators=[observation_basis_validator])
    updated_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="hover_space_membership_suggestions_updated",
    )
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["space", "user"], name="hover_space_suggestion_unique_user"
            ),
            models.CheckConstraint(
                condition=Q(
                    match_basis__in=["verified_email", "verified_phone"],
                    observation_basis__startswith="obs_",
                ),
                name="hover_space_suggestion_observation_basis",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.space_id is not None and self.realm_id != self.space.realm_id:
            raise ValidationError({"space": "Suggestions must share the Space organization."})
        if self.user_id is not None and self.realm_id != self.user.realm_id:
            raise ValidationError({"user": "Suggestions must share the user organization."})
        if self.updated_by_id is not None and self.realm_id != self.updated_by.realm_id:
            raise ValidationError({"updated_by": "Suggestions must share the actor organization."})


provider_key_validator = RegexValidator(
    regex=r"^[a-z][a-z0-9_]{0,31}$",
    message="Provider keys must start with a letter and contain only lowercase letters, digits, and underscores.",
)
selector_type_validator = RegexValidator(
    regex=r"^[a-z][a-z0-9_]{0,63}$",
    message="Selector types must start with a letter and contain only lowercase letters, digits, and underscores.",
)
source_ref_validator = RegexValidator(
    regex=r"^src_[0-9a-f]{32}$",
    message="Source references must be opaque Studio source IDs.",
)


class ConnectedAccount(models.Model):
    MAX_DISPLAY_NAME_LENGTH = 100
    MAX_PROVIDER_NAME_LENGTH = 60

    class ApprovalState(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REVOKED = "revoked", "Revoked"

    class HealthStatus(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        HEALTHY = "healthy", "Healthy"
        DEGRADED = "degraded", "Degraded"
        UNAVAILABLE = "unavailable", "Unavailable"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_connected_accounts")
    provider_key = models.CharField(max_length=32, validators=[provider_key_validator])
    provider_name = models.CharField(max_length=MAX_PROVIDER_NAME_LENGTH)
    external_account_id = models.UUIDField()
    display_name = models.CharField(max_length=MAX_DISPLAY_NAME_LENGTH)
    created_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="created_hover_connected_accounts",
    )
    owner = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="owned_hover_connected_accounts",
    )
    approval_state = models.TextField(choices=ApprovalState.choices, default=ApprovalState.PENDING)
    health_status = models.TextField(choices=HealthStatus.choices, default=HealthStatus.UNKNOWN)
    health_checked_at = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["realm", "provider_key", "external_account_id"],
                name="hover_connected_account_unique_external_id",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.created_by_id is not None and self.created_by.realm_id != self.realm_id:
            raise ValidationError(
                {"created_by": "Connected Accounts and creators must share an organization."}
            )
        if self.owner_id is not None and self.owner.realm_id != self.realm_id:
            raise ValidationError(
                {"owner": "Connected Accounts and owners must share an organization."}
            )


class ConnectedAccountGrant(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    realm = models.ForeignKey(
        Realm, on_delete=CASCADE, related_name="hover_connected_account_grants"
    )
    account = models.ForeignKey(ConnectedAccount, on_delete=CASCADE, related_name="grants")
    user = models.ForeignKey(
        UserProfile, on_delete=CASCADE, related_name="hover_connected_account_grants"
    )
    created_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="created_hover_connected_account_grants",
    )
    state = models.TextField(choices=State.choices, default=State.ACTIVE)
    all_selectors = models.BooleanField(default=False)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "user"], name="hover_connected_account_grant_unique_user"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.account_id is not None and self.account.realm_id != self.realm_id:
            raise ValidationError({"account": "Grants and accounts must share an organization."})
        if self.user_id is not None and self.user.realm_id != self.realm_id:
            raise ValidationError({"user": "Grants and users must share an organization."})
        if self.created_by_id is not None and self.created_by.realm_id != self.realm_id:
            raise ValidationError(
                {"created_by": "Grants and their creators must share an organization."}
            )


class ConnectedAccountGrantSelector(models.Model):
    MAX_DISPLAY_NAME_LENGTH = 100
    MAX_SOURCE_REF_LENGTH = 36

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    grant = models.ForeignKey(ConnectedAccountGrant, on_delete=CASCADE, related_name="selectors")
    selector_type = models.CharField(max_length=64, validators=[selector_type_validator])
    source_ref = models.CharField(
        max_length=MAX_SOURCE_REF_LENGTH, validators=[source_ref_validator]
    )
    display_name = models.CharField(max_length=MAX_DISPLAY_NAME_LENGTH)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["grant", "selector_type", "source_ref"],
                name="hover_connected_account_grant_unique_selector",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.grant_id is not None and self.grant.realm_id != self.realm_id:
            raise ValidationError({"grant": "Grant selectors must share the grant organization."})


class Source(models.Model):
    MAX_ADAPTER_KEY_LENGTH = 32
    MAX_PROVIDER_KEY_LENGTH = 32
    MAX_SOURCE_TYPE_LENGTH = 64
    MAX_DISPLAY_NAME_LENGTH = 100

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_sources")
    account = models.ForeignKey(ConnectedAccount, on_delete=RESTRICT, related_name="sources")
    adapter_key = models.CharField(max_length=MAX_ADAPTER_KEY_LENGTH)
    provider_key = models.CharField(
        max_length=MAX_PROVIDER_KEY_LENGTH, validators=[provider_key_validator]
    )
    source_type = models.CharField(
        max_length=MAX_SOURCE_TYPE_LENGTH, validators=[selector_type_validator]
    )
    external_ref = models.CharField(
        max_length=ConnectedAccountGrantSelector.MAX_SOURCE_REF_LENGTH,
        validators=[source_ref_validator],
    )
    display_name = models.CharField(max_length=MAX_DISPLAY_NAME_LENGTH)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "external_ref"],
                name="hover_source_unique_account_external_ref",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.account_id is not None and self.account.realm_id != self.realm_id:
            raise ValidationError({"account": "Sources and accounts must share an organization."})


class SpaceAttachment(models.Model):
    MAX_TIMEZONE_LENGTH = 64

    class State(models.TextChoices):
        PENDING_SYNC = "pending_sync", "Pending sync"
        ACTIVE = "active", "Active"

    class HistoryWindow(models.TextChoices):
        TODAY = "today", "Today"
        LAST_30_DAYS = "last_30_days", "Last 30 days"
        CUSTOM = "custom", "Custom start date"

    class PublicationSyncState(models.TextChoices):
        IDLE = "idle", "Idle"
        LEASED = "leased", "Leased"
        BACKOFF = "backoff", "Retry backoff"
        BLOCKED = "blocked", "Blocked"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_space_attachments")
    space = models.ForeignKey(Space, on_delete=CASCADE, related_name="attachments")
    source = models.ForeignKey(Source, on_delete=RESTRICT, related_name="space_attachments")
    state = models.TextField(choices=State.choices, default=State.PENDING_SYNC)
    history_window = models.TextField(choices=HistoryWindow.choices)
    history_timezone = models.CharField(max_length=MAX_TIMEZONE_LENGTH)
    history_start_at = models.DateTimeField()
    custom_start_date = models.DateField(null=True)
    publication_cursor = models.TextField(default="")
    last_publication_sync_at = models.DateTimeField(null=True)
    last_publication_sync_error = models.CharField(max_length=64, default="")
    publication_sync_failures = models.PositiveIntegerField(default=0)
    publication_sync_state = models.TextField(
        choices=PublicationSyncState.choices,
        default=PublicationSyncState.IDLE,
    )
    publication_sync_lease_token = models.UUIDField(null=True)
    publication_sync_lease_expires_at = models.DateTimeField(null=True)
    next_publication_sync_at = models.DateTimeField(default=timezone_now, null=True)
    attached_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="hover_space_attachments_added",
    )
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["space", "source"], name="hover_space_attachment_unique_source"
            ),
            models.CheckConstraint(
                condition=(
                    Q(history_window="custom", custom_start_date__isnull=False)
                    | Q(
                        history_window__in=["today", "last_30_days"], custom_start_date__isnull=True
                    )
                ),
                name="hover_space_attachment_custom_date_matches_window",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.space_id is not None and self.space.realm_id != self.realm_id:
            raise ValidationError(
                {"space": "Space attachments and Spaces must share an organization."}
            )
        if self.source_id is not None and self.source.realm_id != self.realm_id:
            raise ValidationError(
                {"source": "Space attachments and Sources must share an organization."}
            )
        if self.attached_by_id is not None and self.attached_by.realm_id != self.realm_id:
            raise ValidationError(
                {"attached_by": "Space attachments and actors must share an organization."}
            )


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
    attachment = models.ForeignKey(
        SpaceAttachment,
        null=True,
        on_delete=RESTRICT,
        related_name="generated_items",
    )
    publication_id = models.TextField(null=True)
    idempotency_key = models.TextField(null=True)
    publication_envelope_hash = models.CharField(max_length=64, default="")
    business_identity = models.TextField(default="")
    output_type = models.TextField(choices=OutputType.choices)
    module_key = models.TextField()
    module_name = models.TextField()
    module_version = models.TextField()
    source_summary = models.TextField()
    payload = models.JSONField(default=dict)
    importance = models.TextField(
        choices=[
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        default="normal",
    )
    run_reference = models.TextField(default="")
    covered_start_at = models.DateTimeField(null=True)
    covered_end_at = models.DateTimeField(null=True)
    occurred_at = models.DateTimeField(null=True)
    generated_at = models.DateTimeField(null=True)
    published_at = models.DateTimeField(null=True)
    lineage_key = models.TextField(null=True)
    parent_publication_id = models.TextField(null=True)
    material_change = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attachment", "publication_id"],
                condition=Q(attachment__isnull=False, publication_id__isnull=False),
                name="hover_generated_item_unique_attachment_publication",
            ),
            models.UniqueConstraint(
                fields=["attachment", "idempotency_key"],
                condition=Q(attachment__isnull=False, idempotency_key__isnull=False),
                name="hover_generated_item_unique_attachment_idempotency",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.message.realm_id:
            raise ValidationError(
                {"message": "Generated items and messages must share an organization."}
            )
        attachment = self.attachment
        if attachment is not None and self.realm_id != attachment.realm_id:
            raise ValidationError(
                {"attachment": "Generated items and attachments must share an organization."}
            )


class PublicationSyncAttempt(models.Model):
    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        ERROR = "error", "Error"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    attachment = models.ForeignKey(
        SpaceAttachment,
        on_delete=CASCADE,
        related_name="publication_sync_attempts",
    )
    outcome = models.TextField(choices=Outcome.choices)
    error_code = models.CharField(max_length=64, default="")
    retryable = models.BooleanField(default=False)
    publication_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    replayed_count = models.PositiveIntegerField(default=0)
    requested_cursor_hash = models.CharField(max_length=64, default="")
    returned_cursor_hash = models.CharField(max_length=64, default="")
    date_created = models.DateTimeField(default=timezone_now)


class EvidenceLink(models.Model):
    generated_item = models.ForeignKey(
        GeneratedItem, on_delete=CASCADE, related_name="evidence_links"
    )
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    source = models.ForeignKey(
        Source,
        null=True,
        on_delete=RESTRICT,
        related_name="evidence_links",
    )
    evidence_ref = models.TextField(default="")
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
            ),
            models.UniqueConstraint(
                fields=["generated_item", "evidence_ref"],
                condition=~Q(evidence_ref=""),
                name="hover_evidence_link_unique_ref",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.generated_item_id is not None and self.realm_id != self.generated_item.realm_id:
            raise ValidationError(
                {"generated_item": "Evidence links and generated items must share an organization."}
            )
        if self.source_id is not None and self.realm_id != self.source.realm_id:
            raise ValidationError(
                {"source": "Evidence links and Sources must share an organization."}
            )
