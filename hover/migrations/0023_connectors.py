import re
from typing import Any

import django.db.models.deletion
import django.utils.timezone
from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

PROVIDER_NAMES = {
    "airbrake": "Airbrake",
    "alertmanager": "Alertmanager",
    "bitbucket": "Bitbucket",
    "circleci": "CircleCI",
    "gitea": "Gitea",
    "github": "GitHub",
    "githubsponsors": "GitHub Sponsors",
    "gitlab": "GitLab",
    "grafana": "Grafana",
    "jira": "Jira",
    "json": "JSON",
    "linear": "Linear",
    "newrelic": "New Relic",
    "pagerduty": "PagerDuty",
    "posthog": "PostHog",
    "sentry": "Sentry",
    "slack": "Slack",
    "slack_incoming": "Slack-compatible webhook",
    "stripe": "Stripe",
    "trello": "Trello",
    "zendesk": "Zendesk",
}


def infer_provider(bot: Any, bot_config_data_model: type[Any]) -> tuple[str, str] | None:
    configured_provider = (
        bot_config_data_model.objects.filter(bot_profile_id=bot.id, key="integration_id")
        .values_list("value", flat=True)
        .first()
    )
    if configured_provider:
        provider_name = PROVIDER_NAMES.get(
            configured_provider,
            configured_provider.replace("_", " ").title(),
        )
        return configured_provider, provider_name

    normalized_name = re.sub(r"\s+(bot|connector|webhook)$", "", bot.full_name.strip().lower())
    for provider_key, provider_name in PROVIDER_NAMES.items():
        if normalized_name in {provider_key.replace("_", " "), provider_name.lower()}:
            return provider_key, provider_name
    return None


def backfill_connectors(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    BotConfigData = apps.get_model("zerver", "BotConfigData")
    Connector = apps.get_model("hover", "Connector")
    Subscription = apps.get_model("zerver", "Subscription")
    UserProfile = apps.get_model("zerver", "UserProfile")
    for bot in UserProfile.objects.filter(is_active=True, is_bot=True, bot_type=2):
        provider = infer_provider(bot, BotConfigData)
        destination_ids = list(
            Subscription.objects.filter(
                user_profile_id=bot.id,
                active=True,
                recipient__type=2,
            ).values_list("recipient__type_id", flat=True)
        )
        destination_id = destination_ids[0] if len(destination_ids) == 1 else None
        confident = provider is not None and destination_id is not None
        provider_key, provider_name = provider or ("legacy", "Legacy webhook")
        Connector.objects.get_or_create(
            bot_id=bot.id,
            defaults={
                "realm_id": bot.realm_id,
                "provider_key": provider_key,
                "provider_name": provider_name,
                "destination_id": destination_id,
                "state": "active" if confident else "needs_attention",
                "reconciliation_state": "legacy" if confident else "ambiguous",
                "created_by_id": bot.bot_owner_id,
                "owner_id": bot.bot_owner_id,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("hover", "0022_summary_executions"),
        ("zerver", "0798_remove_userprofile_recipient_and_personal_recipients"),
    ]

    operations = [
        migrations.CreateModel(
            name="Connector",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("provider_key", models.CharField(max_length=80)),
                ("provider_name", models.CharField(max_length=100)),
                ("topic", models.CharField(blank=True, max_length=60)),
                ("event_options", models.JSONField(blank=True, default=list)),
                (
                    "state",
                    models.TextField(
                        choices=[
                            ("active", "Active"),
                            ("disabled", "Disabled"),
                            ("needs_attention", "Needs attention"),
                        ],
                        default="active",
                    ),
                ),
                (
                    "reconciliation_state",
                    models.TextField(
                        choices=[
                            ("canonical", "Canonical"),
                            ("legacy", "Configured in existing URL"),
                            ("ambiguous", "Needs reconciliation"),
                        ],
                        default="canonical",
                    ),
                ),
                (
                    "health_status",
                    models.TextField(
                        choices=[
                            ("unknown", "Waiting for first delivery"),
                            ("healthy", "Healthy"),
                            ("degraded", "Delivery failed"),
                        ],
                        default="unknown",
                    ),
                ),
                (
                    "last_delivery_status",
                    models.TextField(
                        choices=[
                            ("never", "Not yet delivered"),
                            ("success", "Delivered"),
                            ("failure", "Delivery failed"),
                        ],
                        default="never",
                    ),
                ),
                ("last_successful_delivery", models.DateTimeField(blank=True, null=True)),
                ("last_delivery_attempt", models.DateTimeField(blank=True, null=True)),
                ("date_created", models.DateTimeField(default=django.utils.timezone.now)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                (
                    "bot",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="hover_connector",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_hover_connectors",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "destination",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="hover_connectors",
                        to="zerver.stream",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="owned_hover_connectors",
                        to="zerver.userprofile",
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill_connectors, migrations.RunPython.noop),
    ]
