# Hover

Hover is an organizational intelligence feed that turns activity from external
conversations and systems into source-backed posts, updates, and follow-up work.

## Language

**Space**:
A flat organizational feed with members, human posts, and AI-generated updates.
Spaces may have a built-in or custom category.
_Avoid_: Channel, stream, workspace

**Connected Account**:
An organization-approved connection through which a teammate may be granted
access to specific external Sources. It names the connection without exposing
credentials, provider identifiers, or deployment topology.
_Avoid_: Login, credential, bot session

**Source**:
A provider-neutral external feed identity discovered through a Connected
Account. Provider-specific selectors, such as a WhatsApp Group, are adapter
details; Hover stores only an opaque Source reference and safe identifying
metadata.
_Avoid_: Chat ID, JID, phone number

**Space Attachment**:
The durable association between a Space and a Source. It records the actor and
an immutable, explicitly bounded history start in UTC for later ingestion.
_Avoid_: Import, sync run, all history

**Space Membership Suggestion**:
An internal, pending relationship inferred from an attached Source observation
after a verified email or phone mapping resolves to an active teammate in the
same organization. It grants no Space visibility or subscription until a Space
Administrator confirms it.
_Avoid_: External participant, invite, automatic member

**Space Membership**:
The single confirmed access relationship between an internal teammate and a
Space, with a Contributor or Subscriber role. During Setup, visibility remains
limited to Space Administrators; at launch, confirmed memberships become the
exact native subscription cohort.
_Avoid_: Connected Account grant, Source participant, channel guest

**AIMTO Events**:
The first Hover Space, used to prove the product through a real mixed feed of
human activity and source-backed AI updates.
_Avoid_: AIMTO app, AIMTO dashboard
