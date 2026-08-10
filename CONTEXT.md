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

**AIMTO Events**:
The first Hover Space, used to prove the product through a real mixed feed of
human activity and source-backed AI updates.
_Avoid_: AIMTO app, AIMTO dashboard
