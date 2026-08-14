import type {Meta, StoryObj} from "@storybook/html";

import render_icon_button from "../templates/components/icon_button.hbs";

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
        squared,
    });
}

export const States: Story = {
    render: () =>
        component_story(`
            <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center">
                ${button("edit", "neutral", "Edit")}
                ${button("link-alt", "brand", "Copy link")}
                ${button("check", "success", "Approve")}
                ${button("reset", "warning", "Reset")}
                ${button("trash", "danger", "Delete")}
                ${button("more-vertical", "neutral", "More", true)}
                ${render_icon_button({
                    "aria-label": "Disabled",
                    disabled: true,
                    hidden: false,
                    icon: "follow",
                    intent: "neutral",
                    squared: false,
                })}
            </div>
        `),
};
