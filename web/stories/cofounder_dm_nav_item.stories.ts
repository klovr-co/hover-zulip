import type {Meta, StoryObj} from "@storybook/html";

import render_dm_section_header from "../templates/cofounder/components/dm_section_header.hbs";
import render_more_pms from "../templates/more_pms.hbs";
import render_pm_list_item from "../templates/pm_list_item.hbs";

import {component_story} from "./story_utils.ts";

type DmNavItemArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Direct-message navigation item",
    parameters: {layout: "padded"},
} satisfies Meta<DmNavItemArgs>;

export default meta;
type Story = StoryObj<DmNavItemArgs>;

function conversation({
    has_unread_mention = false,
    is_active = false,
    is_bot = false,
    is_current_user = false,
    is_group = false,
    is_zero = false,
    name,
    presence = "user-circle-offline",
    unread,
}: {
    has_unread_mention?: boolean;
    is_active?: boolean;
    is_bot?: boolean;
    is_current_user?: boolean;
    is_group?: boolean;
    is_zero?: boolean;
    name: string;
    presence?: string;
    unread: number;
}): string {
    const user_ids_string = is_group ? "8,9,10" : `${7 + unread}`;
    return render_pm_list_item({
        has_unread_mention,
        is_active,
        is_bot,
        is_current_user,
        is_group,
        is_zero,
        recipients: name,
        status_emoji_info: undefined,
        unread,
        url: `#narrow/dm/${user_ids_string}`,
        user_circle_class: is_group ? undefined : presence,
        user_ids_string,
    });
}

function render_states(): HTMLElement {
    const container = globalThis.document.createElement("div");
    container.innerHTML = component_story(`
            <nav aria-label="Direct messages" style="width: 280px">
                ${render_dm_section_header({
                    custom_classes: "zoomed-out",
                    has_filter: false,
                    has_toggle: true,
                    id: "direct-messages-section-header",
                    is_modal: false,
                    title: "Direct messages",
                })}
                <ul class="dm-list" style="display: grid; gap: 2px; margin: 2px 0 0; padding: 0; list-style: none">
                    ${conversation({is_active: true, name: "Alex Lee", presence: "user-circle-active", unread: 2})}
                    ${conversation({has_unread_mention: true, name: "Jamie Morris", presence: "user-circle-idle", unread: 4})}
                    ${conversation({is_group: true, name: "Design review group", unread: 7})}
                    ${conversation({is_bot: true, name: "Release", unread: 1})}
                    ${conversation({is_current_user: true, is_zero: true, name: "Maxine", unread: 0})}
                    ${render_more_pms({more_conversations_unread_count: 8})}
                </ul>
            </nav>
        `);

    const component = container.firstElementChild;
    if (!(component instanceof HTMLElement)) {
        throw new TypeError("The direct-message navigation story did not render.");
    }

    const toggle = component.querySelector<HTMLButtonElement>(
        "#toggle-direct-messages-section-icon",
    );
    const list = component.querySelector<HTMLElement>(".dm-list");
    toggle?.addEventListener("click", () => {
        const expanded = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(expanded));
        toggle.setAttribute(
            "aria-label",
            expanded ? "Collapse direct messages" : "Expand direct messages",
        );
        toggle.classList.toggle("rotate-icon-down", expanded);
        toggle.classList.toggle("rotate-icon-right", !expanded);
        if (list) {
            list.hidden = !expanded;
            list.style.display = expanded ? "grid" : "none";
        }
    });

    return component;
}

export const States: Story = {
    render: render_states,
};
