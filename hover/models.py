from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import CASCADE, RESTRICT, SET_NULL, Q
from django.db.models.base import ModelBase
from django.db.models.functions import Lower
from django.utils.timezone import now as timezone_now
from typing_extensions import override

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

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.category.realm_id:
            raise ValidationError({"category": "Spaces and categories must share an organization."})
        created_by = self.created_by
        if created_by is not None and self.realm_id != created_by.realm_id:
            raise ValidationError({"created_by": "Spaces and creators must share an organization."})
        stream = self.stream
        if stream is not None and self.realm_id != stream.realm_id:
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

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.space.realm_id:
            raise ValidationError(
                {"space": "Space administrators must share the Space organization."}
            )
        if self.realm_id != self.user.realm_id:
            raise ValidationError(
                {"user": "Space administrators must share the Space organization."}
            )
        added_by = self.added_by
        if added_by is not None and self.realm_id != added_by.realm_id:
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
    personal_editions_enabled = models.BooleanField(default=False)
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

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.space.realm_id:
            raise ValidationError({"space": "Space memberships must share the Space organization."})
        if self.realm_id != self.user.realm_id:
            raise ValidationError({"user": "Space memberships must share the user organization."})
        added_by = self.added_by
        if added_by is not None and self.realm_id != added_by.realm_id:
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

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.space.realm_id:
            raise ValidationError({"space": "Suggestions must share the Space organization."})
        if self.realm_id != self.user.realm_id:
            raise ValidationError({"user": "Suggestions must share the user organization."})
        updated_by = self.updated_by
        if updated_by is not None and self.realm_id != updated_by.realm_id:
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
participant_ref_validator = RegexValidator(
    regex=r"^person_[0-9a-f]{32}$",
    message="Participant references must be opaque participant IDs.",
)
ambiguity_key_validator = RegexValidator(
    regex=r"^ambiguity_[0-9a-f]{32}$",
    message="Ambiguity keys must be opaque ambiguity IDs.",
)
field_path_validator = RegexValidator(
    regex=r"^[a-z][a-z0-9_]{0,63}$",
    message="Disputed fields must be normalized top-level keys.",
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

    class ConnectionKind(models.TextChoices):
        REMOTE_STUDIO = "remote_studio", "Remote Studio"
        NATIVE_INTEGRATION = "native_integration", "Native integration"

    class LinkState(models.TextChoices):
        NONE = "none", "Not linked"
        PENDING = "pending", "Pending"
        LINKED = "linked", "Linked"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_connected_accounts")
    provider_key = models.CharField(max_length=32, validators=[provider_key_validator])
    provider_name = models.CharField(max_length=MAX_PROVIDER_NAME_LENGTH)
    external_account_id = models.UUIDField()
    display_name = models.CharField(max_length=MAX_DISPLAY_NAME_LENGTH)
    connection_kind = models.TextField(
        choices=ConnectionKind.choices, default=ConnectionKind.REMOTE_STUDIO
    )
    incoming_webhook_bot = models.OneToOneField(
        UserProfile,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="hover_connected_account",
    )
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
    link_state = models.TextField(choices=LinkState.choices, default=LinkState.NONE)
    link_expires_at = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["realm", "provider_key", "external_account_id"],
                name="hover_connected_account_unique_external_id",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        created_by = self.created_by
        if created_by is not None and created_by.realm_id != self.realm_id:
            raise ValidationError(
                {"created_by": "Connected Accounts and creators must share an organization."}
            )
        owner = self.owner
        if owner is not None and owner.realm_id != self.realm_id:
            raise ValidationError(
                {"owner": "Connected Accounts and owners must share an organization."}
            )
        if self.connection_kind == self.ConnectionKind.REMOTE_STUDIO:
            if self.incoming_webhook_bot_id is not None:
                raise ValidationError(
                    {"incoming_webhook_bot": "Remote Studio accounts cannot use a local bot."}
                )
        elif self.connection_kind == self.ConnectionKind.NATIVE_INTEGRATION:
            bot = self.incoming_webhook_bot
            if bot is None or bot.realm_id != self.realm_id:
                raise ValidationError(
                    {"incoming_webhook_bot": "Native integration bots must share the organization."}
                )
            if (
                not bot.is_active
                or not bot.is_bot
                or bot.bot_type != UserProfile.INCOMING_WEBHOOK_BOT
            ):
                raise ValidationError(
                    {"incoming_webhook_bot": "Choose an active incoming webhook bot."}
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

    @override
    def clean(self) -> None:
        super().clean()
        if self.account.realm_id != self.realm_id:
            raise ValidationError({"account": "Grants and accounts must share an organization."})
        if self.user.realm_id != self.realm_id:
            raise ValidationError({"user": "Grants and users must share an organization."})
        created_by = self.created_by
        if created_by is not None and created_by.realm_id != self.realm_id:
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

    @override
    def clean(self) -> None:
        super().clean()
        if self.grant.realm_id != self.realm_id:
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
    provider_name = models.CharField(max_length=ConnectedAccount.MAX_PROVIDER_NAME_LENGTH)
    external_url = models.URLField(blank=True)
    supports_live_capture = models.BooleanField(default=False)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "external_ref"],
                name="hover_source_unique_account_external_ref",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.account.realm_id != self.realm_id:
            raise ValidationError({"account": "Sources and accounts must share an organization."})
        if self.external_url and not self.external_url.startswith("https://"):
            raise ValidationError({"external_url": "Source links must use HTTPS."})
        if (
            self.supports_live_capture
            and self.account.connection_kind != ConnectedAccount.ConnectionKind.NATIVE_INTEGRATION
        ):
            raise ValidationError(
                {"supports_live_capture": "Live capture requires a native integration account."}
            )


class SourceParticipantBinding(models.Model):
    """A durable result from verified identity resolution, never raw identity data."""

    class MatchBasis(models.TextChoices):
        VERIFIED_EMAIL = "verified_email", "Verified email"
        VERIFIED_PHONE = "verified_phone", "Verified phone"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    source = models.ForeignKey(Source, on_delete=CASCADE, related_name="participant_bindings")
    participant_ref = models.CharField(max_length=39, validators=[participant_ref_validator])
    user = models.ForeignKey(
        UserProfile, on_delete=CASCADE, related_name="hover_source_participant_bindings"
    )
    match_basis = models.TextField(choices=MatchBasis.choices)
    observation_basis = models.CharField(max_length=36, validators=[observation_basis_validator])
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "participant_ref"],
                name="hover_source_participant_unique_ref",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.source.realm_id or self.realm_id != self.user.realm_id:
            raise ValidationError("Participant bindings must share one organization.")
        if not self.user.is_active or self.user.is_bot or self.user.is_guest:
            raise ValidationError({"user": "Participant bindings require an active teammate."})


class SpaceAttachment(models.Model):
    MAX_TIMEZONE_LENGTH = 64

    class State(models.TextChoices):
        PENDING_SYNC = "pending_sync", "Pending sync"
        ACTIVE = "active", "Active"
        DETACHED = "detached", "Detached with retained history"

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
    destination_topic = models.CharField(max_length=60, default="")
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
    detached_at = models.DateTimeField(blank=True, null=True)
    detached_by = models.ForeignKey(
        UserProfile,
        blank=True,
        null=True,
        on_delete=SET_NULL,
        related_name="hover_space_attachments_detached",
    )
    evidence_deleted_at = models.DateTimeField(blank=True, null=True)
    evidence_deleted_by = models.ForeignKey(
        UserProfile,
        blank=True,
        null=True,
        on_delete=SET_NULL,
        related_name="hover_space_attachment_evidence_deleted",
    )
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["space", "source"], name="hover_space_attachment_unique_source"
            ),
            models.UniqueConstraint(
                Lower("destination_topic"),
                "space",
                condition=~Q(destination_topic=""),
                name="hover_space_attachment_unique_topic",
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
            models.CheckConstraint(
                condition=(
                    Q(state="detached", detached_at__isnull=False)
                    | Q(state__in=["pending_sync", "active"], detached_at__isnull=True)
                ),
                name="hover_space_attachment_detachment_matches_state",
            ),
            models.CheckConstraint(
                condition=(
                    Q(evidence_deleted_at__isnull=True, evidence_deleted_by__isnull=True)
                    | Q(state="detached", evidence_deleted_at__isnull=False)
                ),
                name="hover_attachment_evidence_deletion_requires_detachment",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.space.realm_id != self.realm_id:
            raise ValidationError(
                {"space": "Space attachments and Spaces must share an organization."}
            )
        if self.source.realm_id != self.realm_id:
            raise ValidationError(
                {"source": "Space attachments and Sources must share an organization."}
            )
        attached_by = self.attached_by
        if attached_by is not None and attached_by.realm_id != self.realm_id:
            raise ValidationError(
                {"attached_by": "Space attachments and actors must share an organization."}
            )
        detached_by = self.detached_by
        if detached_by is not None and detached_by.realm_id != self.realm_id:
            raise ValidationError(
                {
                    "detached_by": "Space attachments and detaching actors must share an organization."
                }
            )
        evidence_deleted_by = self.evidence_deleted_by
        if self.evidence_deleted_at is None and evidence_deleted_by is not None:
            raise ValidationError(
                {"evidence_deleted_by": "Evidence deletion requires a deletion time."}
            )
        if self.evidence_deleted_at is not None and self.state != self.State.DETACHED:
            raise ValidationError(
                {"evidence_deleted_at": "Evidence may only be deleted after Source detachment."}
            )
        if evidence_deleted_by is not None and evidence_deleted_by.realm_id != self.realm_id:
            raise ValidationError(
                {
                    "evidence_deleted_by": (
                        "Space attachments and evidence-deleting actors must share one "
                        "organization."
                    )
                }
            )


class IntegrationRouteAssociation(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        DETACHED = "detached", "Detached"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    attachment = models.ForeignKey(
        SpaceAttachment, on_delete=RESTRICT, related_name="integration_routes"
    )
    bot = models.ForeignKey(
        UserProfile, on_delete=RESTRICT, related_name="hover_integration_routes"
    )
    stream = models.ForeignKey(Stream, on_delete=RESTRICT, related_name="hover_integration_routes")
    state = models.TextField(choices=State.choices, default=State.ACTIVE)
    configured_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="configured_hover_integration_routes",
    )
    live_since = models.DateTimeField(default=timezone_now)
    detached_at = models.DateTimeField(blank=True, null=True)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attachment"],
                condition=Q(state="active"),
                name="hover_route_unique_active_attachment",
            ),
            models.UniqueConstraint(
                fields=["bot"],
                condition=Q(state="active"),
                name="hover_route_unique_active_bot",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.attachment.realm_id != self.realm_id:
            raise ValidationError({"attachment": "Integration routes must share the organization."})
        if self.bot.realm_id != self.realm_id:
            raise ValidationError({"bot": "Integration routes must share the organization."})
        if self.stream.realm_id != self.realm_id:
            raise ValidationError({"stream": "Integration routes must share the organization."})
        configured_by = self.configured_by
        if configured_by is not None and configured_by.realm_id != self.realm_id:
            raise ValidationError(
                {"configured_by": "Integration routes and actors must share an organization."}
            )
        if self.attachment.space.stream_id != self.stream_id:
            raise ValidationError({"stream": "Use the attached Space destination."})
        if (
            not self.bot.is_active
            or not self.bot.is_bot
            or self.bot.bot_type != UserProfile.INCOMING_WEBHOOK_BOT
        ):
            raise ValidationError({"bot": "Choose an active incoming webhook bot."})
        source = self.attachment.source
        if (
            source.account.connection_kind != ConnectedAccount.ConnectionKind.NATIVE_INTEGRATION
            or source.account.incoming_webhook_bot_id != self.bot_id
            or not source.supports_live_capture
        ):
            raise ValidationError({"bot": "Use the bot configured for this native Source."})


class Connector(models.Model):
    """Hover's product-facing record for an inbound webhook identity."""

    MAX_PROVIDER_KEY_LENGTH = 80
    MAX_PROVIDER_NAME_LENGTH = 100
    MAX_NAME_LENGTH = 80
    MAX_TOPIC_LENGTH = 60

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"
        NEEDS_ATTENTION = "needs_attention", "Needs attention"

    class ReconciliationState(models.TextChoices):
        CANONICAL = "canonical", "Canonical"
        LEGACY = "legacy", "Configured in existing URL"
        AMBIGUOUS = "ambiguous", "Needs reconciliation"

    class HealthStatus(models.TextChoices):
        UNKNOWN = "unknown", "Waiting for first delivery"
        HEALTHY = "healthy", "Healthy"
        DEGRADED = "degraded", "Delivery failed"

    class LastDeliveryStatus(models.TextChoices):
        NEVER = "never", "Not yet delivered"
        SUCCESS = "success", "Delivered"
        FAILURE = "failure", "Delivery failed"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    bot = models.OneToOneField(UserProfile, on_delete=RESTRICT, related_name="hover_connector")
    provider_key = models.CharField(max_length=MAX_PROVIDER_KEY_LENGTH)
    provider_name = models.CharField(max_length=MAX_PROVIDER_NAME_LENGTH)
    name = models.CharField(max_length=MAX_NAME_LENGTH, blank=True)
    destination = models.ForeignKey(
        Stream,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="hover_connectors",
    )
    topic = models.CharField(max_length=MAX_TOPIC_LENGTH, blank=True)
    event_options = models.JSONField(default=list, blank=True)
    state = models.TextField(choices=State.choices, default=State.ACTIVE)
    reconciliation_state = models.TextField(
        choices=ReconciliationState.choices, default=ReconciliationState.CANONICAL
    )
    created_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="created_hover_connectors"
    )
    owner = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="owned_hover_connectors"
    )
    health_status = models.TextField(choices=HealthStatus.choices, default=HealthStatus.UNKNOWN)
    last_delivery_status = models.TextField(
        choices=LastDeliveryStatus.choices, default=LastDeliveryStatus.NEVER
    )
    last_successful_delivery = models.DateTimeField(null=True, blank=True)
    last_delivery_attempt = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    @override
    def clean(self) -> None:
        super().clean()
        if self.bot.realm_id != self.realm_id:
            raise ValidationError(
                {"bot": "Connectors and webhook identities must share an organization."}
            )
        destination = self.destination
        if destination is not None and destination.realm_id != self.realm_id:
            raise ValidationError(
                {"destination": "Connector destinations must share an organization."}
            )
        created_by = self.created_by
        if created_by is not None and created_by.realm_id != self.realm_id:
            raise ValidationError({"created_by": "Connector creators must share an organization."})
        owner = self.owner
        if owner is not None and owner.realm_id != self.realm_id:
            raise ValidationError({"owner": "Connector owners must share an organization."})


class Pipeline(models.Model):
    """A scheduled Hover summary built from exactly one Space Topic."""

    MAX_NAME_LENGTH = 80
    MAX_INSTRUCTION_LENGTH = 2000
    MAX_TOPIC_LENGTH = 60

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        DRAFT = "draft", "Draft"
        PAUSED = "paused", "Paused"

    class InputAvailability(models.TextChoices):
        AVAILABLE = "available", "Available"
        TOPIC_UNAVAILABLE = "topic_unavailable", "Topic unavailable"

    class RunHealth(models.TextChoices):
        NOT_RUN = "not_run", "Not run yet"
        HEALTHY = "healthy", "Healthy"
        FAILED = "failed", "Run failed"

    class Cadence(models.TextChoices):
        DAILY = "daily", "Every day"
        WEEKDAYS = "weekdays", "Weekdays"
        WEEKLY = "weekly", "Every week"

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_pipelines")
    input_destination = models.ForeignKey(
        Stream,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="hover_pipeline_inputs",
    )
    input_topic = models.CharField(max_length=MAX_TOPIC_LENGTH, blank=True)
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    instruction = models.TextField(max_length=MAX_INSTRUCTION_LENGTH)
    cadence = models.TextField(choices=Cadence.choices, default=Cadence.DAILY)
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices, null=True, blank=True)
    local_time = models.TimeField()
    timezone = models.CharField(max_length=SpaceAttachment.MAX_TIMEZONE_LENGTH)
    output_destination = models.ForeignKey(
        Stream, on_delete=RESTRICT, related_name="hover_pipeline_outputs"
    )
    output_topic = models.CharField(max_length=MAX_TOPIC_LENGTH)
    state = models.TextField(choices=State.choices, default=State.ACTIVE)
    input_availability = models.TextField(
        choices=InputAvailability.choices, default=InputAvailability.AVAILABLE
    )
    run_health = models.TextField(choices=RunHealth.choices, default=RunHealth.NOT_RUN)
    input_cursor_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="created_hover_pipelines"
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(state__in=["active", "draft", "paused"]),
                name="hover_pipeline_lifecycle_state_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        input_destination__isnull=True,
                        state="draft",
                        input_availability="topic_unavailable",
                    )
                    | Q(input_destination__isnull=False) & ~Q(input_topic="")
                ),
                name="hover_pipeline_input_recoverable_or_resolved",
            ),
        ]
        indexes = [
            models.Index(
                "input_destination", Lower("input_topic"), name="hover_pipeline_input_topic"
            ),
            models.Index(
                "state", "input_availability", "local_time", name="hover_pipeline_schedule"
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.cadence == self.Cadence.WEEKLY and self.weekday is None:
            raise ValidationError({"weekday": "Weekly Pipelines require a weekday."})
        if self.cadence != self.Cadence.WEEKLY and self.weekday is not None:
            raise ValidationError({"weekday": "Only weekly Pipelines can specify a weekday."})
        input_destination = self.input_destination
        if input_destination is None:
            if (
                self.state != self.State.DRAFT
                or self.input_availability != self.InputAvailability.TOPIC_UNAVAILABLE
            ):
                raise ValidationError(
                    {
                        "input_destination": (
                            "Only recoverable draft Pipelines may omit an input Space."
                        )
                    }
                )
        elif input_destination.realm_id != self.realm_id:
            raise ValidationError(
                {"input_destination": "Pipeline inputs must stay in the organization."}
            )
        if input_destination is not None and not self.input_topic.strip():
            raise ValidationError({"input_topic": "Pipeline inputs require a Topic."})
        if self.output_destination.realm_id != self.realm_id:
            raise ValidationError(
                {"output_destination": "Pipeline outputs must stay in the organization."}
            )
        created_by = self.created_by
        if created_by is not None and created_by.realm_id != self.realm_id:
            raise ValidationError({"created_by": "Pipeline creators must share the organization."})


class PipelineRun(models.Model):
    """One deterministic, retry-safe closed input window for a Pipeline."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    pipeline = models.ForeignKey(Pipeline, on_delete=CASCADE, related_name="runs")
    request_key = models.CharField(max_length=64)
    input_first_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    input_last_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.TextField(choices=Status.choices, default=Status.PENDING)
    output_message = models.OneToOneField(
        Message, null=True, blank=True, on_delete=RESTRICT, related_name="hover_pipeline_run"
    )
    failure_code = models.CharField(max_length=64, blank=True)
    date_created = models.DateTimeField(default=timezone_now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline", "request_key"], name="hover_pipeline_run_unique_request"
            ),
        ]


class PipelineAuthoredMessage(models.Model):
    """Durable provenance used to exclude Pipeline output from future input."""

    message = models.OneToOneField(
        Message, on_delete=CASCADE, related_name="hover_pipeline_authorship"
    )
    pipeline = models.ForeignKey(Pipeline, on_delete=CASCADE, related_name="authored_messages")
    run = models.OneToOneField(PipelineRun, on_delete=CASCADE, related_name="authorship")
    date_created = models.DateTimeField(default=timezone_now)

    @override
    def clean(self) -> None:
        super().clean()
        if self.run.pipeline_id != self.pipeline_id:
            raise ValidationError({"run": "Authored messages must use a run from the Pipeline."})
        if self.message.realm_id != self.pipeline.realm_id:
            raise ValidationError(
                {"message": "Pipeline-authored messages must stay in the organization."}
            )


class IntegrationMessageProvenance(models.Model):
    message = models.OneToOneField(
        Message, on_delete=CASCADE, related_name="hover_source_provenance"
    )
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    association = models.ForeignKey(
        IntegrationRouteAssociation, on_delete=RESTRICT, related_name="message_provenance"
    )
    attachment = models.ForeignKey(
        SpaceAttachment, on_delete=RESTRICT, related_name="message_provenance"
    )
    source = models.ForeignKey(Source, on_delete=RESTRICT, related_name="message_provenance")
    captured_at = models.DateTimeField(default=timezone_now)
    provider_key = models.CharField(max_length=Source.MAX_PROVIDER_KEY_LENGTH)
    provider_name = models.CharField(max_length=ConnectedAccount.MAX_PROVIDER_NAME_LENGTH)
    source_type = models.CharField(max_length=Source.MAX_SOURCE_TYPE_LENGTH)
    display_name = models.CharField(max_length=Source.MAX_DISPLAY_NAME_LENGTH)
    external_url = models.URLField(blank=True)

    @override
    def clean(self) -> None:
        super().clean()
        related_realms = {
            self.message.realm_id,
            self.association.realm_id,
            self.attachment.realm_id,
            self.source.realm_id,
        }
        if related_realms != {self.realm_id}:
            raise ValidationError("Message provenance must share one organization.")
        if self.association.attachment_id != self.attachment_id:
            raise ValidationError({"attachment": "Provenance must use the route attachment."})
        if self.attachment.source_id != self.source_id:
            raise ValidationError({"source": "Provenance must use the attached Source."})
        if self.external_url and not self.external_url.startswith("https://"):
            raise ValidationError({"external_url": "Source links must use HTTPS."})


module_key_validator = RegexValidator(
    regex=r"^[a-z][a-z0-9_]{0,63}$",
    message="Module keys must start with a letter and contain only lowercase letters, digits, and underscores.",
)

MAX_PIPELINE_RUNTIME_SECONDS = 3600


class PipelineCreatorAssignment(models.Model):
    """An auditable grant of the realm-scoped Pipeline Creator capability."""

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="pipeline_creator_assignments")
    user = models.ForeignKey(
        UserProfile, on_delete=CASCADE, related_name="hover_pipeline_creator_assignments"
    )
    granted_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="granted_pipeline_creator_roles"
    )
    granted_at = models.DateTimeField(default=timezone_now)
    revoked_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="revoked_pipeline_creator_roles",
    )
    revoked_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["realm", "user"],
                condition=Q(revoked_at__isnull=True),
                name="hover_pipeline_creator_unique_active",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        user = self.user
        if user.realm_id != self.realm_id or user.is_bot or user.is_guest:
            raise ValidationError({"user": "Pipeline Creators must be human organization members."})
        for field_name in ("granted_by", "revoked_by"):
            actor = getattr(self, field_name)
            if actor is not None and actor.realm_id != self.realm_id:
                raise ValidationError({field_name: "Role actors must share the organization."})
        if self.revoked_at is None and self.revoked_by_id is not None:
            raise ValidationError({"revoked_by": "A revoking actor requires a revocation time."})


class ModuleDefinition(models.Model):
    """The stable, realm-scoped identity of a reusable Hover Module."""

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_module_definitions")
    stable_key = models.CharField(max_length=64, validators=[module_key_validator])
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=1024, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["realm", "stable_key"], name="hover_module_definition_unique_key"
            )
        ]

    @override
    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding and self.versions.exists():
            raise ValidationError("Published Module definitions are immutable.")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @override
    def delete(
        self, using: Any | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        if self.versions.exists():
            raise ValidationError("Published Module definitions cannot be deleted.")
        return super().delete(using=using, keep_parents=keep_parents)


class ModuleVersion(models.Model):
    """An immutable published execution and presentation contract."""

    definition = models.ForeignKey(ModuleDefinition, on_delete=RESTRICT, related_name="versions")
    version = models.CharField(max_length=32)
    output_type = models.CharField(max_length=32)
    runtime_key = models.CharField(max_length=100)
    prompt_key = models.CharField(max_length=100)
    input_contract = models.JSONField(default=dict)
    lookback_seconds = models.PositiveIntegerField(default=86400)
    integration_keys = models.JSONField(default=list)
    destination_topic = models.CharField(max_length=60)
    output_template = models.JSONField(default=dict)
    maximum_runtime_seconds = models.PositiveSmallIntegerField(default=300)
    is_sealed = models.BooleanField(default=True)
    navigation_icon = models.CharField(max_length=64, default="zulip-icon-sparkles")
    navigation_order = models.PositiveSmallIntegerField()
    content_hash = models.CharField(max_length=64)
    published_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="published_hover_module_versions"
    )
    published_at = models.DateTimeField(default=timezone_now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "version"], name="hover_module_version_unique_version"
            ),
            models.UniqueConstraint(
                fields=["definition", "content_hash"], name="hover_module_version_unique_hash"
            ),
            models.CheckConstraint(
                condition=Q(lookback_seconds__gte=1),
                name="hover_module_version_positive_lookback",
            ),
            models.CheckConstraint(
                condition=(
                    Q(maximum_runtime_seconds__gte=1)
                    & Q(maximum_runtime_seconds__lte=MAX_PIPELINE_RUNTIME_SECONDS)
                ),
                name="hover_module_version_runtime_under_cap",
            ),
        ]

    @override
    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            raise ValidationError("Published Module versions are immutable.")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @override
    def delete(
        self, using: Any | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        raise ValidationError("Published Module versions cannot be deleted.")

    @override
    def clean(self) -> None:
        super().clean()
        published_by = self.published_by
        if published_by is not None and published_by.realm_id != self.definition.realm_id:
            raise ValidationError(
                {"published_by": "Module publishers must share the definition organization."}
            )


class ModuleDraft(models.Model):
    """A private mutable authoring workspace for one future immutable version."""

    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_module_drafts")
    definition = models.ForeignKey(
        ModuleDefinition,
        null=True,
        on_delete=RESTRICT,
        related_name="drafts",
    )
    based_on_version = models.ForeignKey(
        ModuleVersion,
        null=True,
        on_delete=RESTRICT,
        related_name="successor_drafts",
    )
    published_version = models.OneToOneField(
        ModuleVersion,
        null=True,
        on_delete=RESTRICT,
        related_name="originating_draft",
    )
    author = models.ForeignKey(
        UserProfile,
        on_delete=RESTRICT,
        related_name="authored_hover_module_drafts",
    )
    stable_key = models.CharField(max_length=64, validators=[module_key_validator])
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=1024, default="")
    version = models.CharField(max_length=32)
    state = models.TextField(choices=State.choices, default=State.DRAFT)
    revision = models.PositiveIntegerField(default=1)
    output_type = models.CharField(max_length=32)
    runtime_key = models.CharField(max_length=100)
    prompt_key = models.CharField(max_length=100)
    input_contract = models.JSONField(default=dict)
    lookback_seconds = models.PositiveIntegerField(default=86400)
    integration_keys = models.JSONField(default=list)
    destination_topic = models.CharField(max_length=60)
    navigation_icon = models.CharField(max_length=64, default="zulip-icon-sparkles")
    navigation_order = models.PositiveSmallIntegerField(default=100)
    output_template = models.JSONField(default=dict)
    maximum_runtime_seconds = models.PositiveSmallIntegerField(default=300)
    requirements = models.JSONField(default=list)
    supported_triggers = models.JSONField(default=list)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["author", "based_on_version"],
                condition=Q(state="draft", based_on_version__isnull=False),
                name="hover_module_draft_unique_author_successor",
            ),
            models.UniqueConstraint(
                fields=["realm", "stable_key"],
                condition=Q(definition__isnull=True, state="draft"),
                name="hover_module_draft_unique_new_key",
            ),
            models.CheckConstraint(
                condition=Q(lookback_seconds__gte=1),
                name="hover_module_draft_positive_lookback",
            ),
            models.CheckConstraint(
                condition=(
                    Q(maximum_runtime_seconds__gte=1)
                    & Q(maximum_runtime_seconds__lte=MAX_PIPELINE_RUNTIME_SECONDS)
                ),
                name="hover_module_draft_runtime_under_cap",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state="draft", published_version__isnull=True)
                    | Q(state="published", published_version__isnull=False)
                ),
                name="hover_module_draft_publication_matches_state",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        related_realm_ids = {self.realm_id}
        if self.definition_id is not None:
            definition = self.definition
            assert definition is not None
            related_realm_ids.add(definition.realm_id)
        if self.based_on_version_id is not None:
            based_on_version = self.based_on_version
            assert based_on_version is not None
            related_realm_ids.add(based_on_version.definition.realm_id)
            if self.definition_id != based_on_version.definition_id:
                raise ValidationError(
                    {"based_on_version": "Successor drafts must use their base definition."}
                )
        if self.published_version_id is not None:
            published_version = self.published_version
            assert published_version is not None
            related_realm_ids.add(published_version.definition.realm_id)
        if self.author_id is not None:
            related_realm_ids.add(self.author.realm_id)
        if related_realm_ids != {self.realm_id}:
            raise ValidationError("Module drafts must share one organization.")


class ModuleDraftCollaborator(models.Model):
    draft = models.ForeignKey(ModuleDraft, on_delete=CASCADE, related_name="collaborators")
    user = models.ForeignKey(
        UserProfile, on_delete=CASCADE, related_name="collaborating_hover_module_drafts"
    )
    added_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="added_module_draft_collaborators"
    )
    date_added = models.DateTimeField(default=timezone_now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["draft", "user"], name="hover_module_draft_unique_collaborator"
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.user.realm_id != self.draft.realm_id:
            raise ValidationError({"user": "Draft collaborators must share the organization."})
        added_by = self.added_by
        if added_by is not None and added_by.realm_id != self.draft.realm_id:
            raise ValidationError({"added_by": "Collaborator actors must share the organization."})


class ModuleDefinitionArchive(models.Model):
    definition = models.OneToOneField(
        ModuleDefinition, on_delete=RESTRICT, related_name="archive_record"
    )
    archived_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="archived_module_definitions"
    )
    archived_at = models.DateTimeField(default=timezone_now)


class ModuleVersionArchive(models.Model):
    version = models.OneToOneField(ModuleVersion, on_delete=RESTRICT, related_name="archive_record")
    archived_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="archived_module_versions"
    )
    archived_at = models.DateTimeField(default=timezone_now)


class ModuleSourceRequirement(models.Model):
    version = models.ForeignKey(ModuleVersion, on_delete=RESTRICT, related_name="requirements")
    key = models.CharField(max_length=64, validators=[module_key_validator])
    capability = models.CharField(max_length=64, validators=[module_key_validator])
    minimum_count = models.PositiveSmallIntegerField(default=1)
    maximum_count = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "key"], name="hover_module_requirement_unique_key"
            ),
            models.CheckConstraint(
                condition=Q(minimum_count__gte=1) & Q(maximum_count__gte=models.F("minimum_count")),
                name="hover_module_requirement_valid_cardinality",
            ),
        ]

    @override
    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self._state.adding and self.version.is_sealed:
            raise ValidationError("Published Module requirements cannot be extended.")
        if not self._state.adding:
            raise ValidationError("Published Module requirements are immutable.")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @override
    def delete(
        self, using: Any | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        raise ValidationError("Published Module requirements cannot be deleted.")


class ModuleSupportedTrigger(models.Model):
    class Kind(models.TextChoices):
        MANUAL = "manual", "Manual"
        NEW_SOURCE = "new_source", "New Source"
        SCHEDULE = "schedule", "Schedule"

    version = models.ForeignKey(
        ModuleVersion, on_delete=RESTRICT, related_name="supported_triggers"
    )
    kind = models.TextField(choices=Kind.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "kind"], name="hover_module_supported_trigger_unique_kind"
            )
        ]

    @override
    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self._state.adding and self.version.is_sealed:
            raise ValidationError("Published Module triggers cannot be extended.")
        if not self._state.adding:
            raise ValidationError("Published Module triggers are immutable.")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @override
    def delete(
        self, using: Any | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        raise ValidationError("Published Module triggers cannot be deleted.")


class SourceCapability(models.Model):
    source = models.ForeignKey(Source, on_delete=CASCADE, related_name="capabilities")
    capability = models.CharField(max_length=64, validators=[module_key_validator])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "capability"], name="hover_source_capability_unique"
            )
        ]


class ModuleInstallation(models.Model):
    class State(models.TextChoices):
        CONFIGURED = "configured", "Configured"
        ENABLED = "enabled", "Enabled"
        DISABLED = "disabled", "Disabled"
        PAUSED_DETACHED = "paused_detached", "Paused after Source detach"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_module_installations")
    space = models.ForeignKey(Space, on_delete=CASCADE, related_name="module_installations")
    version = models.ForeignKey(ModuleVersion, on_delete=RESTRICT, related_name="installations")
    label = models.CharField(max_length=60, default="")
    summary_stream = models.OneToOneField(
        Stream,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="hover_summary_installation",
    )
    state = models.TextField(choices=State.choices)
    activation_timezone = models.CharField(max_length=SpaceAttachment.MAX_TIMEZONE_LENGTH)
    activated_at = models.DateTimeField(null=True)
    processing_start_at = models.DateTimeField(null=True)
    backfill_confirmed = models.BooleanField(default=False)
    policy_revision = models.PositiveIntegerField(default=1)
    policy_hash = models.CharField(max_length=64)
    configured_by = models.ForeignKey(
        UserProfile, null=True, on_delete=SET_NULL, related_name="configured_hover_modules"
    )
    disabled_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="disabled_hover_modules",
    )
    predecessor = models.OneToOneField(
        "self", null=True, on_delete=RESTRICT, related_name="successor"
    )
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(state="configured", activated_at__isnull=True)
                    | Q(state="disabled")
                    | Q(state__in=["enabled", "paused_detached"], activated_at__isnull=False)
                ),
                name="hover_module_installation_activation_matches_state",
            ),
            models.UniqueConstraint(
                Lower("label"),
                "space",
                condition=Q(state__in=["configured", "enabled", "paused_detached"]),
                name="hover_module_installation_unique_current_label",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.space.realm_id:
            raise ValidationError(
                {"space": "Module installations must share the Space organization."}
            )
        if self.realm_id != self.version.definition.realm_id:
            raise ValidationError(
                {"version": "Module installations must use an organization Module version."}
            )
        summary_stream = self.summary_stream
        if summary_stream is not None and self.realm_id != summary_stream.realm_id:
            raise ValidationError(
                {"summary_stream": "Summaries and native containers must share an organization."}
            )
        configured_by = self.configured_by
        if configured_by is not None and self.realm_id != configured_by.realm_id:
            raise ValidationError(
                {"configured_by": "Module installations must share the actor organization."}
            )
        disabled_by = self.disabled_by
        if disabled_by is not None and self.realm_id != disabled_by.realm_id:
            raise ValidationError(
                {"disabled_by": "Module installations must share the actor organization."}
            )


class ModuleInstallationBinding(models.Model):
    installation = models.ForeignKey(ModuleInstallation, on_delete=CASCADE, related_name="bindings")
    requirement = models.ForeignKey(ModuleSourceRequirement, on_delete=RESTRICT)
    attachment = models.ForeignKey(
        SpaceAttachment, on_delete=RESTRICT, related_name="module_bindings"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["installation", "requirement", "attachment"],
                name="hover_module_binding_unique_attachment",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.installation.version_id != self.requirement.version_id:
            raise ValidationError(
                {"requirement": "The requirement must belong to the pinned version."}
            )
        if self.installation.space_id != self.attachment.space_id:
            raise ValidationError(
                {"attachment": "The binding must use an attachment from its Space."}
            )


class ModuleInstallationTrigger(models.Model):
    class Cadence(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    installation = models.ForeignKey(ModuleInstallation, on_delete=CASCADE, related_name="triggers")
    supported_trigger = models.ForeignKey(ModuleSupportedTrigger, on_delete=RESTRICT)
    cadence = models.TextField(choices=Cadence.choices, null=True)
    local_time = models.TimeField(null=True)
    timezone = models.CharField(max_length=SpaceAttachment.MAX_TIMEZONE_LENGTH, default="")
    debounce_seconds = models.PositiveIntegerField(null=True)
    # Summary schedules use contiguous elapsed-UTC intervals.  These fields are
    # intentionally nullable because inherited non-Summary Modules retain their
    # daily/weekly wall-clock trigger contract.
    anchor_at = models.DateTimeField(null=True)
    interval_seconds = models.PositiveIntegerField(null=True)
    next_due_at = models.DateTimeField(null=True)
    lease_expires_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["installation", "supported_trigger"],
                name="hover_module_installation_trigger_unique_kind",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.installation.version_id != self.supported_trigger.version_id:
            raise ValidationError(
                {"supported_trigger": "The trigger must belong to the pinned version."}
            )


class SummaryTopicInput(models.Model):
    class Kind(models.TextChoices):
        REGULAR = "regular", "Regular"
        SOURCE = "source", "Source"

    installation = models.ForeignKey(
        ModuleInstallation, on_delete=CASCADE, related_name="summary_inputs"
    )
    stream = models.ForeignKey(Stream, on_delete=RESTRICT, related_name="hover_summary_inputs")
    topic_name = models.CharField(max_length=60)
    kind = models.TextField(choices=Kind.choices)
    source_attachment = models.ForeignKey(
        SpaceAttachment,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="summary_inputs",
    )
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["installation", "position"],
                name="hover_summary_input_unique_position",
            ),
            models.UniqueConstraint(
                Lower("topic_name"),
                "installation",
                "stream",
                name="hover_summary_input_unique_topic",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="source", source_attachment__isnull=False)
                    | Q(kind="regular", source_attachment__isnull=True)
                ),
                name="hover_summary_input_source_matches_kind",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        space = self.installation.space
        if self.stream_id != space.stream_id:
            raise ValidationError({"stream": "Summary inputs must belong to the parent Space."})
        attachment = self.source_attachment
        if attachment is not None and (
            attachment.space_id != space.id or attachment.destination_topic != self.topic_name
        ):
            raise ValidationError(
                {"source_attachment": "Source inputs must use their persisted destination topic."}
            )


class SummaryExecution(models.Model):
    """One immutable Summary generation attempt owned by Hover."""

    class Kind(models.TextChoices):
        MANUAL = "manual", "Manual"
        SCHEDULED = "scheduled", "Scheduled"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPATCHED = "dispatched", "Dispatched"
        SUCCEEDED = "succeeded", "Succeeded"
        NO_CHANGE = "no_change", "No change"
        FAILED = "failed", "Failed"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    installation = models.ForeignKey(
        ModuleInstallation, on_delete=RESTRICT, related_name="summary_executions"
    )
    kind = models.TextField(choices=Kind.choices)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    policy_revision = models.PositiveIntegerField()
    policy_hash = models.CharField(max_length=64)
    status = models.TextField(choices=Status.choices, default=Status.PENDING)
    request_hash = models.CharField(max_length=64, default="")
    snapshot_hash = models.CharField(max_length=64, default="")
    result_hash = models.CharField(max_length=64, default="")
    callback_token_hash = models.CharField(max_length=64, default="")
    requester = models.ForeignKey(
        UserProfile,
        null=True,
        blank=True,
        on_delete=SET_NULL,
        related_name="requested_summary_executions",
    )
    manual_request_id = models.CharField(max_length=64, null=True, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=64, default="")
    result = models.JSONField(default=dict)
    eligible_message_count = models.PositiveIntegerField(default=0)
    snapshot_message_count = models.PositiveSmallIntegerField(default=0)
    published_item = models.OneToOneField(
        "GeneratedItem",
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="summary_execution",
    )
    date_created = models.DateTimeField(default=timezone_now)
    dispatched_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    published_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["date_created", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(window_end__gt=models.F("window_start")),
                name="hover_summary_execution_valid_window",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="manual", manual_request_id__isnull=False, scheduled_for__isnull=True)
                    | Q(
                        kind="scheduled",
                        manual_request_id__isnull=True,
                        scheduled_for__isnull=False,
                    )
                ),
                name="hover_summary_execution_identity_matches_kind",
            ),
            models.UniqueConstraint(
                fields=["installation", "manual_request_id"],
                condition=Q(kind="manual", manual_request_id__isnull=False),
                name="hover_summary_execution_unique_manual_request",
            ),
            models.UniqueConstraint(
                fields=["installation", "scheduled_for"],
                condition=Q(kind="scheduled", scheduled_for__isnull=False),
                name="hover_summary_execution_unique_occurrence",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        requester = self.requester
        if requester is not None and requester.realm_id != self.installation.realm_id:
            raise ValidationError(
                {"requester": "Summary executions and requesters must share an organization."}
            )
        if self.kind == self.Kind.MANUAL and self.requester_id is None:
            raise ValidationError({"requester": "Manual Summary executions require a requester."})
        published_item = self.published_item
        if published_item is not None and published_item.installation_id != self.installation_id:
            raise ValidationError(
                {"published_item": "Published editions must belong to the same Summary."}
            )


class SummaryExecutionInput(models.Model):
    """Generation-time topic identity for an execution, including no-change runs."""

    execution = models.ForeignKey(
        SummaryExecution, on_delete=CASCADE, related_name="input_snapshots"
    )
    stream = models.ForeignKey(Stream, on_delete=RESTRICT)
    topic_name = models.CharField(max_length=60)
    kind = models.TextField(choices=SummaryTopicInput.Kind.choices)
    source_attachment = models.ForeignKey(
        SpaceAttachment, null=True, blank=True, on_delete=RESTRICT
    )
    provider_name = models.CharField(
        max_length=ConnectedAccount.MAX_PROVIDER_NAME_LENGTH, default=""
    )
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "position"],
                name="hover_summary_execution_input_unique_position",
            ),
            models.UniqueConstraint(
                Lower("topic_name"),
                "execution",
                "stream",
                name="hover_summary_execution_input_unique_topic",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="source", source_attachment__isnull=False)
                    | Q(kind="regular", source_attachment__isnull=True)
                ),
                name="hover_summary_execution_input_source_matches_kind",
            ),
        ]


class SummaryExecutionMessage(models.Model):
    """Frozen message text and sender metadata sent to the generator."""

    execution = models.ForeignKey(
        SummaryExecution, on_delete=CASCADE, related_name="message_snapshots"
    )
    input = models.ForeignKey(
        SummaryExecutionInput, on_delete=CASCADE, related_name="message_snapshots"
    )
    message = models.ForeignKey(
        Message, on_delete=RESTRICT, related_name="hover_summary_execution_snapshots"
    )
    frozen_content = models.TextField()
    frozen_rendered_content = models.TextField()
    content_digest = models.CharField(max_length=64)
    sender_label = models.CharField(max_length=100)
    sent_at = models.DateTimeField()
    position = models.PositiveSmallIntegerField()
    citation_token = models.CharField(max_length=32)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "position"],
                name="hover_summary_execution_message_unique_position",
            ),
            models.UniqueConstraint(
                fields=["execution", "message"],
                name="hover_summary_execution_message_unique_native",
            ),
            models.UniqueConstraint(
                fields=["execution", "citation_token"],
                name="hover_summary_execution_message_unique_token",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.input.execution_id != self.execution_id:
            raise ValidationError({"input": "Execution messages must use their own input."})
        if self.message.realm_id != self.execution.installation.realm_id:
            raise ValidationError(
                {"message": "Execution messages must share the Summary organization."}
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
        blank=True,
        on_delete=RESTRICT,
        related_name="generated_items",
    )
    installation = models.ForeignKey(
        ModuleInstallation,
        null=True,
        blank=True,
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
    # `payload` is the immutable publication-time interpretation. Human Reviews
    # update this separate projection so the original wording and evidence stay
    # available for comparison.
    reviewed_payload = models.JSONField(default=dict)
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
            models.UniqueConstraint(
                fields=["installation", "publication_id"],
                condition=Q(installation__isnull=False, publication_id__isnull=False),
                name="hover_generated_item_unique_installation_publication",
            ),
            models.UniqueConstraint(
                fields=["installation", "idempotency_key"],
                condition=Q(installation__isnull=False, idempotency_key__isnull=False),
                name="hover_generated_item_unique_installation_idempotency",
            ),
            models.CheckConstraint(
                condition=(
                    Q(attachment__isnull=False, installation__isnull=True)
                    | Q(attachment__isnull=True, installation__isnull=False)
                ),
                name="hover_generated_item_exactly_one_owner",
            ),
        ]

    @override
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
        installation = self.installation
        if installation is not None and self.realm_id != installation.realm_id:
            raise ValidationError(
                {"installation": "Generated items and Summaries must share an organization."}
            )
        if attachment is not None and installation is not None:
            raise ValidationError(
                "Generated items must belong to either a Source or a Summary, not both."
            )


class GeneratedInputSnapshot(models.Model):
    """The exact topic boundary used to produce one Summary edition."""

    generated_item = models.ForeignKey(
        GeneratedItem, on_delete=CASCADE, related_name="input_snapshots"
    )
    stream = models.ForeignKey(Stream, on_delete=RESTRICT)
    topic_name = models.CharField(max_length=60)
    kind = models.TextField(choices=SummaryTopicInput.Kind.choices)
    source_attachment = models.ForeignKey(
        SpaceAttachment, null=True, blank=True, on_delete=RESTRICT
    )
    provider_name = models.CharField(
        max_length=ConnectedAccount.MAX_PROVIDER_NAME_LENGTH, default=""
    )
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["generated_item", "position"],
                name="hover_generated_input_unique_position",
            ),
            models.UniqueConstraint(
                Lower("topic_name"),
                "generated_item",
                "stream",
                name="hover_generated_input_unique_topic",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="source", source_attachment__isnull=False)
                    | Q(kind="regular", source_attachment__isnull=True)
                ),
                name="hover_generated_input_source_matches_kind",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        installation = self.generated_item.installation
        if installation is None:
            raise ValidationError({"generated_item": "Only Summary editions have input snapshots."})
        if self.stream_id != installation.space.stream_id:
            raise ValidationError({"stream": "Snapshot inputs must belong to the parent Space."})
        attachment = self.source_attachment
        if attachment is not None and (
            attachment.space_id != installation.space_id
            or attachment.destination_topic.casefold() != self.topic_name.casefold()
        ):
            raise ValidationError(
                {"source_attachment": "Snapshot Sources must belong to the Summary input topic."}
            )


class PersonalEdition(models.Model):
    """One immutable Clawer personal-edition publication owned by one teammate."""

    class Edition(models.TextChoices):
        MORNING = "morning", "Morning Daily Brief"
        END_OF_DAY = "end_of_day", "End-of-Day Roundup"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_personal_editions")
    user = models.ForeignKey(
        UserProfile, on_delete=RESTRICT, related_name="hover_personal_editions"
    )
    account = models.ForeignKey(
        ConnectedAccount, on_delete=RESTRICT, related_name="personal_editions"
    )
    teammate_ref = models.CharField(max_length=39, validators=[participant_ref_validator])
    publication_id = models.TextField()
    idempotency_key = models.TextField()
    publication_envelope_hash = models.CharField(max_length=64)
    source_ref = models.CharField(max_length=36, validators=[source_ref_validator])
    edition = models.TextField(choices=Edition.choices)
    payload = models.JSONField()
    evidence_refs = models.JSONField(default=list)
    covered_start_at = models.DateTimeField()
    covered_end_at = models.DateTimeField()
    producing_version = models.TextField()
    generated_at = models.DateTimeField()
    published_at = models.DateTimeField()
    date_created = models.DateTimeField(default=timezone_now)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "edition", "-covered_end_at"],
                name="hover_edition_user_latest",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "publication_id"],
                name="hover_edition_unique_publication",
            ),
            models.UniqueConstraint(
                fields=["account", "idempotency_key"],
                name="hover_edition_unique_idempotency",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.user.realm_id or self.realm_id != self.account.realm_id:
            raise ValidationError(
                "Personal editions, users, and accounts must share an organization."
            )


class PersonalEditionSyncState(models.Model):
    """Cursor state for one verified Personal Edition target and Connected Account."""

    realm = models.ForeignKey(
        Realm, on_delete=CASCADE, related_name="hover_personal_edition_sync_states"
    )
    user = models.ForeignKey(
        UserProfile, on_delete=CASCADE, related_name="hover_personal_edition_sync_states"
    )
    account = models.ForeignKey(
        ConnectedAccount, on_delete=CASCADE, related_name="personal_edition_sync_states"
    )
    teammate_ref = models.CharField(max_length=39, validators=[participant_ref_validator])
    start_at = models.DateTimeField()
    cursor = models.TextField(default="")
    last_sync_at = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=64, default="")
    sync_failures = models.PositiveIntegerField(default=0)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "user", "teammate_ref"],
                name="hover_edition_sync_unique_target",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.user.realm_id or self.realm_id != self.account.realm_id:
            raise ValidationError(
                "Personal edition sync state must remain inside one organization."
            )


class ParticipantSelectorReconciliation(models.Model):
    """Durable account-scoped outbox for Studio participant authorization."""

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        LEASED = "leased", "Leased"
        BACKOFF = "backoff", "Backoff"
        CURRENT = "current", "Current"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    account = models.OneToOneField(
        ConnectedAccount,
        on_delete=CASCADE,
        related_name="participant_selector_reconciliation",
    )
    state = models.TextField(choices=State.choices, default=State.PENDING)
    generation = models.PositiveBigIntegerField(default=1)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone_now)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    last_reconciled_at = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["state", "next_attempt_at"],
                name="hover_participant_reconcile_due",
            ),
            models.Index(
                fields=["state", "lease_expires_at"],
                name="hover_participant_lease_due",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.account.realm_id:
            raise ValidationError("Participant reconciliation must share the account organization.")


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
        blank=True,
        on_delete=RESTRICT,
        related_name="evidence_links",
    )
    citation_message = models.ForeignKey(
        Message,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="hover_evidence_citations",
    )
    evidence_ref = models.TextField(default="", blank=True)
    position = models.PositiveIntegerField()
    provider_key = models.TextField(blank=True)
    provider_name = models.TextField(blank=True)
    display_name = models.TextField(blank=True)
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
            models.CheckConstraint(
                condition=(
                    Q(citation_message__isnull=False, source__isnull=True, evidence_ref="")
                    | Q(citation_message__isnull=True, source__isnull=False) & ~Q(evidence_ref="")
                ),
                name="hover_evidence_link_exactly_one_kind",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.generated_item.realm_id:
            raise ValidationError(
                {"generated_item": "Evidence links and generated items must share an organization."}
            )
        source = self.source
        if source is not None and self.realm_id != source.realm_id:
            raise ValidationError(
                {"source": "Evidence links and Sources must share an organization."}
            )
        citation = self.citation_message
        if citation is not None:
            if any(
                [
                    self.evidence_ref,
                    self.provider_key,
                    self.provider_name,
                    self.display_name,
                    self.url,
                ]
            ):
                raise ValidationError("Native citations cannot contain external Source metadata.")
            if citation.realm_id != self.realm_id or not citation.is_channel_message:
                raise ValidationError(
                    {
                        "citation_message": (
                            "Citations must be channel messages in the generated item's organization."
                        )
                    }
                )
            if self.generated_item.installation_id is None:
                raise ValidationError(
                    {"citation_message": "Native citations may only belong to Summary editions."}
                )
            if not self.generated_item.input_snapshots.filter(
                stream_id=citation.recipient.type_id,
                topic_name__iexact=citation.topic_name(),
            ).exists():
                raise ValidationError(
                    {"citation_message": "Citations must belong to a generation-time input."}
                )
        if source is not None and citation is not None:
            raise ValidationError(
                "Evidence must use either an external Source or a native citation."
            )
        if source is not None and not all(
            [self.evidence_ref, self.provider_key, self.provider_name, self.display_name]
        ):
            raise ValidationError("External evidence must include its Source metadata.")


class Response(models.Model):
    class ResponseType(models.TextChoices):
        REPLY = "reply", "Reply"
        REVIEW = "review", "Review"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    generated_item = models.ForeignKey(GeneratedItem, on_delete=CASCADE, related_name="responses")
    message = models.OneToOneField(Message, on_delete=CASCADE, related_name="hover_response")
    response_type = models.TextField(choices=ResponseType.choices)
    clarification_required = models.BooleanField(default=False)
    date_created = models.DateTimeField(default=timezone_now)

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.generated_item.realm_id or self.realm_id != self.message.realm_id:
            raise ValidationError(
                "Responses, generated items, and messages must share an organization."
            )
        if self.generated_item.message.recipient_id != self.message.recipient_id:
            raise ValidationError("Responses must be sent beneath their generated root.")
        if self.generated_item.message.topic_name() != self.message.topic_name():
            raise ValidationError("Responses must be sent beneath their generated root.")


class Revision(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    generated_item = models.ForeignKey(GeneratedItem, on_delete=CASCADE, related_name="revisions")
    response = models.OneToOneField(Response, on_delete=RESTRICT, related_name="revision")
    actor = models.ForeignKey(UserProfile, on_delete=RESTRICT, related_name="hover_revisions")
    field_path = models.TextField()
    previous_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    reason = models.TextField(default="")
    date_created = models.DateTimeField(default=timezone_now)

    class Meta:
        ordering = ["date_created", "id"]

    @override
    def clean(self) -> None:
        super().clean()
        if (
            self.realm_id != self.generated_item.realm_id
            or self.realm_id != self.response.realm_id
            or self.realm_id != self.actor.realm_id
        ):
            raise ValidationError("Revisions and their related records must share an organization.")
        if self.response.generated_item_id != self.generated_item_id:
            raise ValidationError("A revision must belong to its originating Review.")
        if self.response.response_type != Response.ResponseType.REVIEW:
            raise ValidationError("Only a Review can originate a revision.")


class DisputedDetail(models.Model):
    class State(models.TextChoices):
        NEEDS_REVIEW = "needs_review", "Needs review"
        RESOLVED = "resolved", "Resolved"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    generated_item = models.ForeignKey(
        GeneratedItem, on_delete=CASCADE, related_name="disputed_details"
    )
    ambiguity_key = models.CharField(max_length=42, validators=[ambiguity_key_validator])
    field_path = models.CharField(max_length=64, validators=[field_path_validator])
    summary = models.CharField(max_length=500)
    material = models.BooleanField()
    state = models.TextField(choices=State.choices, default=State.NEEDS_REVIEW)
    resolved_by_revision = models.ForeignKey(
        Revision,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="resolved_disputed_details",
    )
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["generated_item", "ambiguity_key"],
                name="hover_disputed_detail_unique_ambiguity",
            ),
            models.UniqueConstraint(
                fields=["generated_item", "field_path"],
                name="hover_disputed_detail_unique_field",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state="needs_review", resolved_by_revision__isnull=True)
                    | Q(state="resolved", resolved_by_revision__isnull=False)
                ),
                name="hover_disputed_detail_resolution_matches_state",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.generated_item.realm_id:
            raise ValidationError("Disputed details must share the generated item organization.")
        revision = self.resolved_by_revision
        if revision is not None and (
            revision.realm_id != self.realm_id
            or revision.generated_item_id != self.generated_item_id
            or revision.field_path != self.field_path
        ):
            raise ValidationError(
                {"resolved_by_revision": "Use a matching field Revision from this generated item."}
            )


class DisputedEvidenceLink(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    disputed_detail = models.ForeignKey(
        DisputedDetail, on_delete=CASCADE, related_name="conflicting_evidence"
    )
    evidence_link = models.ForeignKey(
        EvidenceLink, on_delete=RESTRICT, related_name="dispute_links"
    )
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["disputed_detail", "evidence_link"],
                name="hover_disputed_evidence_unique_link",
            ),
            models.UniqueConstraint(
                fields=["disputed_detail", "position"],
                name="hover_disputed_evidence_unique_position",
            ),
        ]

    @override
    def clean(self) -> None:
        super().clean()
        if (
            self.realm_id != self.disputed_detail.realm_id
            or self.realm_id != self.evidence_link.realm_id
            or self.disputed_detail.generated_item_id != self.evidence_link.generated_item_id
        ):
            raise ValidationError("Conflicting evidence must belong to its generated item.")


class ReviewRequest(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    disputed_detail = models.OneToOneField(
        DisputedDetail, on_delete=CASCADE, related_name="review_request"
    )
    message = models.OneToOneField(Message, on_delete=RESTRICT, related_name="hover_review_request")
    state = models.TextField(choices=State.choices, default=State.OPEN)
    resolved_by_revision = models.ForeignKey(
        Revision,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="resolved_review_requests",
    )
    date_created = models.DateTimeField(default=timezone_now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(state="open", resolved_by_revision__isnull=True, resolved_at__isnull=True)
                    | Q(
                        state="resolved",
                        resolved_by_revision__isnull=False,
                        resolved_at__isnull=False,
                    )
                ),
                name="hover_review_request_resolution_matches_state",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        detail = self.disputed_detail
        if (
            not detail.material
            or self.realm_id != detail.realm_id
            or self.realm_id != self.message.realm_id
            or detail.generated_item.message.recipient_id != self.message.recipient_id
            or detail.generated_item.message.topic_name() != self.message.topic_name()
        ):
            raise ValidationError("Review requests must belong beneath a material dispute root.")
        if self.resolved_by_revision_id != detail.resolved_by_revision_id:
            raise ValidationError("Review request and disputed detail resolution must match.")


class ReviewRequestTarget(models.Model):
    class Reason(models.TextChoices):
        INVOLVED_TEAMMATE = "involved_teammate", "Involved teammate"
        SPACE_ADMIN_FALLBACK = "space_admin_fallback", "Space administrator fallback"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    review_request = models.ForeignKey(ReviewRequest, on_delete=CASCADE, related_name="targets")
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)
    reason = models.TextField(choices=Reason.choices)
    date_created = models.DateTimeField(default=timezone_now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["review_request", "user"],
                name="hover_review_request_unique_target",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        detail = self.review_request.disputed_detail
        attachment = detail.generated_item.attachment
        if (
            self.realm_id != self.review_request.realm_id
            or self.realm_id != self.user.realm_id
            or attachment is None
            or not self.user.is_active
            or self.user.is_bot
            or self.user.is_guest
            or not SpaceMembership.objects.filter(space=attachment.space, user=self.user).exists()
        ):
            raise ValidationError("Review request targets must be confirmed active Space members.")


person_ref_validator = RegexValidator(
    regex=r"^person_[0-9a-f]{32}$",
    message="Proposed assignees must use opaque person references.",
)


class SuggestedAction(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        NOT_ACTION = "not_action", "Not an action"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_suggested_actions")
    space = models.ForeignKey(Space, on_delete=CASCADE, related_name="suggested_actions")
    generated_item = models.OneToOneField(
        GeneratedItem, on_delete=RESTRICT, related_name="suggested_action"
    )
    state = models.TextField(choices=State.choices, default=State.PENDING)
    wording = models.TextField()
    proposed_assignee_ref = models.CharField(
        max_length=39, blank=True, validators=[person_ref_validator]
    )
    proposed_assignee_display_name = models.CharField(max_length=200, blank=True)
    assignee = models.ForeignKey(
        UserProfile,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="hover_assigned_suggested_actions",
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    version = models.PositiveIntegerField(default=1)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["space", "state"], name="hover_action_space_state")]

    @override
    def clean(self) -> None:
        super().clean()
        item = self.generated_item
        attachment = item.attachment
        stream = self.space.stream
        if (
            self.realm_id != self.space.realm_id
            or self.realm_id != item.realm_id
            or self.space.state != Space.State.LAUNCHED
            or item.output_type != GeneratedItem.OutputType.SUGGESTED_ACTION
            or attachment is None
            or attachment.space_id != self.space_id
            or stream is None
            or item.message.recipient_id != stream.recipient_id
        ):
            raise ValidationError(
                "Suggested Actions must belong to their launched Space publication."
            )
        assignee = self.assignee
        if assignee is not None and (
            assignee.realm_id != self.realm_id
            or not assignee.is_active
            or assignee.is_guest
            or assignee.is_bot
            or not SpaceMembership.objects.filter(space=self.space, user=assignee).exists()
        ):
            raise ValidationError({"assignee": "Assignees must be active confirmed Space members."})


class SuggestedActionTransition(models.Model):
    class Kind(models.TextChoices):
        APPROVE = "approve", "Approve"
        NOT_ACTION = "not_action", "Not an action"
        RESTORE = "restore", "Restore"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    action = models.ForeignKey(SuggestedAction, on_delete=RESTRICT, related_name="transitions")
    request_id = models.UUIDField()
    kind = models.TextField(choices=Kind.choices)
    from_state = models.TextField(choices=SuggestedAction.State.choices)
    to_state = models.TextField(choices=SuggestedAction.State.choices)
    actor = models.ForeignKey(
        UserProfile, on_delete=RESTRICT, related_name="hover_action_transitions"
    )
    reason = models.TextField(default="")
    before_wording = models.TextField()
    after_wording = models.TextField()
    before_assignee_id = models.PositiveIntegerField(null=True)
    after_assignee_id = models.PositiveIntegerField(null=True)
    before_due_date = models.DateField(null=True)
    after_due_date = models.DateField(null=True)
    todo = models.OneToOneField(
        "Todo", null=True, blank=True, on_delete=RESTRICT, related_name="approval_transition"
    )
    date_created = models.DateTimeField(default=timezone_now)

    class Meta:
        ordering = ["date_created", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["action", "request_id"], name="hover_action_transition_unique_request"
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="approve", from_state="pending", to_state="approved")
                    | Q(kind="not_action", from_state="pending", to_state="not_action")
                    | Q(kind="restore", from_state="not_action", to_state="pending")
                ),
                name="hover_action_transition_legal_state",
            ),
        ]

    @override
    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValidationError("Suggested Action transitions are append-only.")
        super().save(*args, **kwargs)

    @override
    def delete(
        self, using: Any | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        raise ValidationError("Suggested Action transitions are append-only.")

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.action.realm_id or self.actor.realm_id != self.realm_id:
            raise ValidationError(
                "Suggested Action transitions and actors must share one organization."
            )
        if len(self.reason) > 1000 or (self.kind != self.Kind.NOT_ACTION and self.reason):
            raise ValidationError({"reason": "Only a dismissal may include a short reason."})
        todo = self.todo
        if self.kind == self.Kind.APPROVE:
            if todo is None or todo.suggested_action_id != self.action_id:
                raise ValidationError({"todo": "Approval transitions must link their Todo."})
        elif todo is not None:
            raise ValidationError({"todo": "Only approval transitions may create a Todo."})


class Todo(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    realm = models.ForeignKey(Realm, on_delete=CASCADE, related_name="hover_todos")
    space = models.ForeignKey(Space, on_delete=CASCADE, related_name="todos")
    suggested_action = models.OneToOneField(
        SuggestedAction, on_delete=RESTRICT, related_name="todo"
    )
    state = models.TextField(choices=State.choices, default=State.ACTIVE)
    wording = models.TextField()
    assignee = models.ForeignKey(
        UserProfile, null=True, blank=True, on_delete=RESTRICT, related_name="hover_todos"
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(
        UserProfile, on_delete=RESTRICT, related_name="hover_created_todos"
    )
    version = models.PositiveIntegerField(default=1)
    date_created = models.DateTimeField(default=timezone_now)
    date_updated = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["space", "state"], name="hover_todo_space_state")]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(state="active", completed_at__isnull=True)
                    | Q(state="completed", completed_at__isnull=False)
                ),
                name="hover_todo_completion_matches_state",
            )
        ]

    @override
    def clean(self) -> None:
        super().clean()
        action = self.suggested_action
        if (
            self.realm_id != self.space.realm_id
            or self.realm_id != action.realm_id
            or self.space_id != action.space_id
            or self.created_by.realm_id != self.realm_id
        ):
            raise ValidationError(
                "Todos must belong to their Suggested Action organization and Space."
            )
        assignee = self.assignee
        if assignee is not None and (
            assignee.realm_id != self.realm_id
            or not assignee.is_active
            or assignee.is_guest
            or assignee.is_bot
            or not SpaceMembership.objects.filter(space=self.space, user=assignee).exists()
        ):
            raise ValidationError(
                {"assignee": "Todo assignees must be active confirmed Space members."}
            )


class TodoEvent(models.Model):
    class Kind(models.TextChoices):
        APPROVED = "approved", "Approved"
        ASSIGNED = "assigned", "Assigned"
        REASSIGNED = "reassigned", "Reassigned"
        COMPLETED = "completed", "Completed"
        REOPENED = "reopened", "Reopened"

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    todo = models.ForeignKey(Todo, on_delete=RESTRICT, related_name="events")
    transition = models.OneToOneField(
        SuggestedActionTransition,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="todo_event",
    )
    request_id = models.UUIDField()
    kind = models.TextField(choices=Kind.choices)
    actor = models.ForeignKey(UserProfile, on_delete=RESTRICT, related_name="hover_todo_events")
    previous_state = models.TextField(blank=True)
    new_state = models.TextField(choices=Todo.State.choices)
    previous_assignee = models.ForeignKey(
        UserProfile,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="+",
    )
    new_assignee = models.ForeignKey(
        UserProfile,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="+",
    )
    reason = models.TextField(default="")
    notification_message = models.OneToOneField(
        Message,
        null=True,
        blank=True,
        on_delete=RESTRICT,
        related_name="hover_todo_notification",
    )
    version = models.PositiveIntegerField(default=1)
    date_created = models.DateTimeField(default=timezone_now)

    class Meta:
        ordering = ["date_created", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["todo", "request_id"], name="hover_todo_event_unique_request"
            ),
            models.UniqueConstraint(
                fields=["todo", "version"], name="hover_todo_event_unique_version"
            ),
        ]

    @override
    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValidationError("Todo events are append-only.")
        super().save(*args, **kwargs)

    @override
    def delete(
        self, using: Any | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        raise ValidationError("Todo events are append-only.")

    @override
    def clean(self) -> None:
        super().clean()
        if self.realm_id != self.todo.realm_id or self.realm_id != self.actor.realm_id:
            raise ValidationError("Todo events and actors must share one organization.")
        transition = self.transition
        if self.kind == self.Kind.APPROVED:
            if (
                transition is None
                or self.realm_id != transition.realm_id
                or transition.todo_id != self.todo_id
                or transition.action_id != self.todo.suggested_action_id
            ):
                raise ValidationError(
                    "Todo approval events must belong to their approval transition."
                )
        elif transition is not None:
            raise ValidationError(
                {"transition": "Only approval events link an approval transition."}
            )
        for assignee in (self.previous_assignee, self.new_assignee):
            if assignee is not None and assignee.realm_id != self.realm_id:
                raise ValidationError("Todo event assignees must share one organization.")
