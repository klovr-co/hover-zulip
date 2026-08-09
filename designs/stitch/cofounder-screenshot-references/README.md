# Cofounder desktop screenshot references

These screenshots were captured from the local Zulip development realm as
`desdemona@zulip.com` at a 1422 × 1024 CSS-pixel viewport with a 2× device
scale. The PNGs are consequently 2844 × 2048 pixels, while preserving the
requested 1422px desktop layout.

Upload the relevant image to its corresponding Stitch screen, or use it to
create a new screen when the interaction is not already represented in the
project. Keep the image at its native dimensions.

| File | UI state | Suggested Stitch screen / use |
| --- | --- | --- |
| `01-channel-conversation.png` | Active channel topic with messages and reactions | Core conversation screen |
| `02-inbox.png` | Inbox empty state | Inbox view |
| `03-recent-conversations.png` | Recent-conversations list | Recent conversations view |
| `04-settings-profile.png` | Personal profile settings modal | Settings: Profile |
| `05-settings-preferences.png` | Personal preferences settings modal | Settings: Preferences |
| `06-settings-notifications.png` | Personal notification controls | Settings: Notifications |
| `07-settings-organization.png` | Organization profile settings modal | Settings: Organization |
| `08-search-results.png` | Search results with a matching message | Search results |
| `09-create-channel.png` | Create-channel dialog | Create channel flow |
| `10-channel-settings.png` | Channel settings modal | Channel settings |
| `11-composer-expanded.png` | Expanded rich-message composer | Composer / drafting state |
| `12-user-card-popover.png` | Participant context menu and user summary | User profile / message-author actions |

The desktop-notification prompt shown by a local development browser was
removed from every final capture so it does not become part of the design
reference.

## Focused crops

The `focused/` subdirectory contains one non-destructive crop per image above.
Each crop isolates the central interaction: message content, settings form,
channel form, composer, or user popover. Use these smaller images for Stitch
screens that should redesign the active surface rather than the full Zulip
application frame. The parent directory retains the original full desktop
captures for layout context.
