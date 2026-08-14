import type {Meta, StoryObj} from "@storybook/html";

import render_button from "../templates/cofounder/components/button.hbs";
import render_status from "../templates/cofounder/components/status.hbs";
import render_text_field from "../templates/cofounder/components/text_field.hbs";

import render_surface_example from "./templates/cofounder_surface_example.hbs";

type LibraryArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Foundations",
    parameters: {layout: "padded"},
} satisfies Meta<LibraryArgs>;

export default meta;
type Story = StoryObj<LibraryArgs>;

export const Buttons: Story = {
    render: () => `
        <div class="cf-theme" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:16px;">
            ${render_button({label: "Save controls", variant: "primary"})}
            ${render_button({label: "View details", variant: "secondary"})}
            ${render_button({label: "Reset", variant: "ghost"})}
            ${render_button({label: "Delete", variant: "danger"})}
            ${render_button({label: "Saved", variant: "success"})}
            ${render_button({disabled: true, label: "Unavailable", variant: "primary"})}
            ${render_button({"aria-label": "Add item", icon: "plus", variant: "secondary"})}
        </div>
    `,
};

export const Fields: Story = {
    render: () => `
        <div class="cf-theme" style="display:grid;gap:16px;width:320px;padding:16px;">
            ${render_text_field({
                hint: "Shown to everyone in the workspace.",
                id: "workspace-name",
                label: "Workspace name",
                placeholder: "Acme Studio",
                required: true,
            })}
            ${render_text_field({
                error: "Enter a valid project name.",
                id: "project-name",
                label: "Project name",
                value: "Q2 /",
            })}
        </div>
    `,
};

export const Statuses: Story = {
    render: () => `
        <div class="cf-theme" style="display:flex;flex-wrap:wrap;gap:8px;padding:16px;">
            ${render_status({label: "Approval required"})}
            ${render_status({label: "In progress", tone: "accent"})}
            ${render_status({label: "Completed", tone: "success"})}
            ${render_status({label: "Needs attention", tone: "warning"})}
            ${render_status({label: "Blocked", tone: "danger"})}
        </div>
    `,
};

export const Surfaces: Story = {
    render: () => render_surface_example(),
};
