from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ResolvedIdentityObservation:
    """Provider-neutral identity result consumed by Space membership setup.

    The adapter boundary resolves verified account identifiers before constructing
    this value. Raw phone numbers, email addresses, and provider participant IDs
    deliberately have no representation here.
    """

    user_id: int | None
    match_basis: Literal["verified_email", "verified_phone"]
    observation_basis: str
    suggested_role: Literal["contributor", "subscriber"] = "subscriber"
