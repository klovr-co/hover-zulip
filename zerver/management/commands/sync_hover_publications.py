from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from hover.clawer_sync import get_clawer_sync
from hover.models import Space, SpaceAttachment
from hover.publication_sync import PublicationSyncError, sync_space_attachment
from zerver.lib.management import ZulipBaseCommand
from zerver.models.users import UserProfile


class Command(ZulipBaseCommand):
    help = "Incrementally materialize validated Clawer publications into launched Hover Spaces."

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--attachment-id", type=int)
        parser.add_argument("--max-pages", type=int, default=20)

    @override
    def handle(self, *args: object, **options: object) -> None:
        assistant_email = str(settings.HOVER_ASSISTANT_EMAIL).strip()
        if not assistant_email:
            raise CommandError("HOVER_ASSISTANT_EMAIL is not configured")
        max_pages = int(options["max_pages"])
        if max_pages < 1 or max_pages > 100:
            raise CommandError("--max-pages must be between 1 and 100")

        attachments = SpaceAttachment.objects.filter(
            state=SpaceAttachment.State.ACTIVE,
            space__state=Space.State.LAUNCHED,
            space__stream__isnull=False,
        ).select_related("realm")
        attachment_id = options.get("attachment_id")
        if attachment_id is not None:
            attachments = attachments.filter(id=int(attachment_id))

        adapter = get_clawer_sync()
        failures = 0
        for attachment in attachments.order_by("id"):
            try:
                assistant = UserProfile.objects.get(
                    realm=attachment.realm,
                    delivery_email__iexact=assistant_email,
                    is_active=True,
                    is_bot=True,
                )
                for _page_number in range(max_pages):
                    result = sync_space_attachment(
                        attachment_id=attachment.id,
                        assistant=assistant,
                        clawer_sync=adapter,
                    )
                    self.stdout.write(
                        f"attachment={attachment.id} created={result.created} "
                        f"replayed={result.replayed}"
                    )
                    if not result.has_more:
                        break
                else:
                    raise PublicationSyncError("publication_page_limit_reached", retryable=True)
            except UserProfile.DoesNotExist:
                failures += 1
                self.stderr.write(f"attachment={attachment.id} error=hover_assistant_not_found")
            except PublicationSyncError as exc:
                failures += 1
                self.stderr.write(f"attachment={attachment.id} error={exc.error_code}")

        if failures:
            raise CommandError(f"{failures} Hover publication attachment syncs failed")
