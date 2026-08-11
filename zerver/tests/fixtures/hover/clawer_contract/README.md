# Clawer contract fixtures

These files are sanitized, byte-identical snapshots shared with Clawer and
clawer-studio. `manifest.json` records the accepted upstream SHA-256 for each
fixture, so a contract change cannot silently diverge between the producer,
transport, and Hover consumer.

Additive contract work adds a fixture and checksum. An existing checksum changes
only when all three repositories intentionally accept a revised snapshot.
