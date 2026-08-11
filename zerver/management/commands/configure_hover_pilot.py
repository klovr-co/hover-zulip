from pathlib import Path
from typing import Any

from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from hover.pilot_config import PilotConfigError, PilotReconciler, load_pilot_config, render_report
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = "Validate, dry-run, or idempotently apply a strict Hover pilot configuration."

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser, required=True)
        parser.add_argument("--config", required=True, type=Path)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply normal Hover records. Without this flag the command is read-only.",
        )
        parser.add_argument(
            "--confirm",
            help="For apply, must exactly equal <realm>:<pilot_key> from the private config.",
        )
        parser.add_argument(
            "--report",
            type=Path,
            help="Optionally write the sanitized operational report to this path.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None
        config_path: Path = options["config"]
        applying: bool = options["apply"]
        try:
            config = load_pilot_config(config_path, require_private=applying)
        except ValueError as error:
            raise CommandError(str(error))

        confirmation = f"{config.metadata.realm}:{config.metadata.pilot_key}"
        if applying and options["confirm"] != confirmation:
            raise CommandError(f"Apply refused: pass --confirm={confirmation}")
        if not applying and options["confirm"] is not None:
            raise CommandError("--confirm is only valid with --apply")

        reconciler = PilotReconciler(realm=realm, config=config)
        try:
            report = reconciler.apply() if applying else reconciler.validate_database()
        except PilotConfigError as error:
            raise CommandError(str(error))
        report["operation"] = "apply" if applying else "dry-run"
        rendered = render_report(report)
        self.stdout.write(rendered)
        report_path: Path | None = options["report"]
        if report_path is not None:
            report_path.write_text(f"{rendered}\n")
