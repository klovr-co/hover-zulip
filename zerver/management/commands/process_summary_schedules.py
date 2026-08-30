from typing import Any

from django.core.management.base import BaseCommand
from typing_extensions import override

from hover.actions_summary_executions import (
    do_publish_summary_execution,
    prepare_due_summary_executions,
    retry_stale_scheduled_dispatches,
)
from hover.models import SummaryExecution
from hover.summary_dispatch import get_summary_dispatcher
from zerver.lib.exceptions import JsonableError


class Command(BaseCommand):
    help = "Dispatch due Hover Summary intervals and recover stale dispatches."

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        dispatcher = get_summary_dispatcher()
        dispatches = [
            *retry_stale_scheduled_dispatches(),
            *prepare_due_summary_executions(),
        ]
        for dispatch in dispatches:
            execution = dispatch.execution
            if execution.status == SummaryExecution.Status.NO_CHANGE:
                do_publish_summary_execution(execution=execution)
                continue
            try:
                dispatcher.dispatch(
                    realm_uuid=execution.installation.realm.uuid,
                    dispatch=dispatch,
                )
            except JsonableError:
                # The immutable dispatched execution remains recoverable.  A
                # later minute rotates only its callback bearer and resends the
                # same request hash.
                continue
