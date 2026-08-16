import type {Meta, StoryObj} from "@storybook/html";

import render_icon_button from "../templates/cofounder/components/icon_button.hbs";

import {component_story} from "./story_utils.ts";

type IconButtonArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Icon button",
    parameters: {layout: "padded"},
} satisfies Meta<IconButtonArgs>;

export default meta;
type Story = StoryObj<IconButtonArgs>;

function button(icon: string, intent: string, label: string, squared = false): string {
    return render_icon_button({
        "aria-label": label,
        "data-tippy-content": label,
        disabled: false,
        hidden: false,
        icon,
        intent,
        omit_legacy_classes: true,
        squared,
    });
}

function specimen(label: string, control: string): string {
    return `
        <li class="storybook-state-specimen">
            ${control}
            <span>${label}</span>
        </li>
    `;
}

export const States: Story = {
    render: () =>
        component_story(`
            <ul class="storybook-state-grid" aria-label="Icon button intents and states">
                ${specimen("Neutral", button("edit", "neutral", "Edit"))}
                ${specimen("Brand", button("link-alt", "brand", "Copy link"))}
                ${specimen("Success", button("check", "success", "Approve"))}
                ${specimen("Warning", button("reset", "warning", "Reset"))}
                ${specimen("Danger", button("trash", "danger", "Delete"))}
                ${specimen("Square", button("more-vertical", "neutral", "More", true))}
                ${specimen(
                    "Disabled",
                    render_icon_button({
                        "aria-label": "Disabled",
                        disabled: true,
                        hidden: false,
                        icon: "follow",
                        intent: "neutral",
                        omit_legacy_classes: true,
                        squared: false,
                    }),
                )}
            </ul>
        `),
};
