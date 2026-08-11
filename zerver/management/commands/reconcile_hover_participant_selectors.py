from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from hover.clawer_sync import get_clawer_sync
from hover.participant_selector_reconciliation import (
    due_participant_reconciliation_ids,
    reconcile_participant_selector_row,
    schedule_all_participant_selector_reconciliations,
    schedule_participant_selector_reconciliation,
)
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = "Reconcile Hover's opaque participant selector grants into Studio."

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--account-id", type=int)
        parser.add_argument("--repair-all", action="store_true")
        parser.add_argument("--limit", type=int, default=100)

    @override
    def handle(self, *args: object, **options: object) -> None:
        limit = options["limit"]
        assert isinstance(limit, int)
        if limit < 1 or limit > 1_000:
            raise CommandError("--limit must be between 1 and 1000")
        account_id = options.get("account_id")
        if account_id is not None:
            assert isinstance(account_id, int)
            schedule_participant_selector_reconciliation(account_id)
        elif options["repair_all"]:
            schedule_all_participant_selector_reconciliations()

        adapter = get_clawer_sync()
        failures = 0
        row_ids = due_participant_reconciliation_ids(
            limit=1 if account_id is not None else limit,
            account_id=account_id,
        )
        for row_id in row_ids:
            result = reconcile_participant_selector_row(
                reconciliation_id=row_id,
                clawer_sync=adapter,
            )
            if result.success and result.current:
                self.stdout.write(
                    f"account={result.account_id} participant_count={result.participant_count}"
                )
            elif result.success:
                self.stdout.write(f"account={result.account_id} state=pending")
            else:
                failures += 1
                self.stderr.write(f"account={result.account_id} error={result.error_code}")
        if failures:
            raise CommandError(f"{failures} participant selector reconciliations failed")
