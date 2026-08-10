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

    class ConnectionKind(models.TextChoices):
        REMOTE_STUDIO = "remote_studio", "Remote Studio"
        NATIVE_INTEGRATION = "native_integration", "Native integration"

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

    def clean(self) -> None:
        super().clean()
        if self.account_id is not None and self.account.realm_id != self.realm_id:
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
    detached_at = models.DateTimeField(null=True)
    detached_by = models.ForeignKey(
        UserProfile,
        null=True,
        on_delete=SET_NULL,
        related_name="hover_space_attachments_detached",
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
            models.CheckConstraint(
                condition=(
                    Q(state="detached", detached_at__isnull=False)
                    | Q(state__in=["pending_sync", "active"], detached_at__isnull=True)
                ),
                name="hover_space_attachment_detachment_matches_state",
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
        if self.detached_by_id is not None and self.detached_by.realm_id != self.realm_id:
            raise ValidationError(
                {
                    "detached_by": "Space attachments and detaching actors must share an organization."
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
    detached_at = models.DateTimeField(null=True)
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

    def clean(self) -> None:
        super().clean()
        if self.attachment_id is not None and self.attachment.realm_id != self.realm_id:
            raise ValidationError({"attachment": "Integration routes must share the organization."})
        if self.bot_id is not None and self.bot.realm_id != self.realm_id:
            raise ValidationError({"bot": "Integration routes must share the organization."})
        if self.stream_id is not None and self.stream.realm_id != self.realm_id:
            raise ValidationError({"stream": "Integration routes must share the organization."})
        if self.configured_by_id is not None and self.configured_by.realm_id != self.realm_id:
            raise ValidationError(
                {"configured_by": "Integration routes and actors must share an organization."}
            )
        if (
            self.attachment_id is not None
            and self.stream_id is not None
            and self.attachment.space.stream_id != self.stream_id
        ):
            raise ValidationError({"stream": "Use the attached Space destination."})
        if self.bot_id is not None and (
            not self.bot.is_active
            or not self.bot.is_bot
            or self.bot.bot_type != UserProfile.INCOMING_WEBHOOK_BOT
        ):
            raise ValidationError({"bot": "Choose an active incoming webhook bot."})
        if self.attachment_id is not None and self.bot_id is not None:
            source = self.attachment.source
            if (
                source.account.connection_kind != ConnectedAccount.ConnectionKind.NATIVE_INTEGRATION
                or source.account.incoming_webhook_bot_id != self.bot_id
                or not source.supports_live_capture
            ):
                raise ValidationError({"bot": "Use the bot configured for this native Source."})


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

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk is not None and self.versions.exists():
            raise ValidationError("Published Module definitions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.versions.exists():
            raise ValidationError("Published Module definitions cannot be deleted.")
        return super().delete(*args, **kwargs)


class ModuleVersion(models.Model):
    """An immutable published execution and presentation contract."""

    definition = models.ForeignKey(ModuleDefinition, on_delete=RESTRICT, related_name="versions")
    version = models.CharField(max_length=32)
    output_type = models.CharField(max_length=32)
    runtime_key = models.CharField(max_length=100)
    prompt_key = models.CharField(max_length=100)
    destination_topic = models.CharField(max_length=60)
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
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk is not None and ModuleVersion.objects.filter(pk=self.pk).exists():
            raise ValidationError("Published Module versions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("Published Module versions cannot be deleted.")

    def clean(self) -> None:
        super().clean()
        if (
            self.published_by_id is not None
            and self.published_by.realm_id != self.definition.realm_id
        ):
            raise ValidationError(
                {"published_by": "Module publishers must share the definition organization."}
            )


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

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk is not None and ModuleSourceRequirement.objects.filter(pk=self.pk).exists():
            raise ValidationError("Published Module requirements are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
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

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk is not None and ModuleSupportedTrigger.objects.filter(pk=self.pk).exists():
            raise ValidationError("Published Module triggers are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
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
                fields=["space", "version"],
                condition=Q(state__in=["configured", "enabled", "paused_detached"]),
                name="hover_module_installation_unique_current_version",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.space_id is not None and self.realm_id != self.space.realm_id:
            raise ValidationError(
                {"space": "Module installations must share the Space organization."}
            )
        if self.version_id is not None and self.realm_id != self.version.definition.realm_id:
            raise ValidationError(
                {"version": "Module installations must use an organization Module version."}
            )
        if self.configured_by_id is not None and self.realm_id != self.configured_by.realm_id:
            raise ValidationError(
                {"configured_by": "Module installations must share the actor organization."}
            )
        if self.disabled_by_id is not None and self.realm_id != self.disabled_by.realm_id:
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

    def clean(self) -> None:
        super().clean()
        if (
            self.requirement_id is not None
            and self.installation.version_id != self.requirement.version_id
        ):
            raise ValidationError(
                {"requirement": "The requirement must belong to the pinned version."}
            )
        if (
            self.attachment_id is not None
            and self.installation.space_id != self.attachment.space_id
        ):
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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["installation", "supported_trigger"],
                name="hover_module_installation_trigger_unique_kind",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.supported_trigger_id is not None
            and self.installation.version_id != self.supported_trigger.version_id
        ):
            raise ValidationError(
                {"supported_trigger": "The trigger must belong to the pinned version."}
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
