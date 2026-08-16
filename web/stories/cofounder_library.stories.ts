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

function button_specimen(label: string, button: string): string {
    return `<li class="storybook-state-specimen">${button}<span class="storybook-state-specimen__caption">${label}</span></li>`;
}

function field_specimen(label: string, field: string): string {
    return `<li class="storybook-field-specimen">${field}<span class="storybook-state-specimen__caption">${label}</span></li>`;
}

function status_specimen(label: string, status: string): string {
    return `<li class="storybook-state-specimen">${status}<span class="storybook-state-specimen__caption">${label}</span></li>`;
}

export const Buttons: Story = {
    render: () => `
        <section class="cf-theme storybook-component storybook-foundation-buttons" aria-label="Button specimens">
            <ul class="storybook-state-grid storybook-button-grid">
                ${button_specimen("Primary", render_button({label: "Save controls", variant: "primary"}))}
                ${button_specimen("Icon and label", render_button({icon: "activity", label: "View activity", variant: "secondary"}))}
                ${button_specimen("Compact ghost", render_button({compact: true, label: "Reset", variant: "ghost"}))}
                ${button_specimen("Danger", render_button({label: "Delete", variant: "danger"}))}
                ${button_specimen("Success", render_button({label: "Complete", variant: "success"}))}
                ${button_specimen("Loading", render_button({"aria-busy": "true", icon: "clock", label: "Saving…", variant: "primary"}))}
                ${button_specimen("Disabled", render_button({disabled: true, label: "Unavailable", variant: "secondary"}))}
                ${button_specimen("Icon only", render_button({"aria-label": "Add item", icon: "plus", variant: "secondary"}))}
            </ul>
        </section>
    `,
};

export const Fields: Story = {
    render: () => `
        <section class="cf-theme storybook-component storybook-foundation-fields" aria-label="Text field specimens">
            <ul class="storybook-state-grid storybook-field-grid">
                ${field_specimen(
                    "Default",
                    render_text_field({
                        id: "display-name",
                        label: "Display name",
                        placeholder: "Ada Lovelace",
                    }),
                )}
                ${field_specimen(
                    "Required with help",
                    render_text_field({
                        hint: "Shown to everyone in the workspace.",
                        id: "workspace-name",
                        label: "Workspace name",
                        placeholder: "Acme Studio",
                        required: true,
                    }),
                )}
                ${field_specimen(
                    "Invalid",
                    render_text_field({
                        error: "Enter a valid project name.",
                        id: "project-name",
                        label: "Project name",
                        value: "Q2 /",
                    }),
                )}
                ${field_specimen(
                    "Disabled",
                    render_text_field({
                        disabled: true,
                        id: "managed-name",
                        label: "Managed workspace",
                        value: "Locked by policy",
                    }),
                )}
            </ul>
        </section>
    `,
};

export const Statuses: Story = {
    render: () => `
        <section class="cf-theme storybook-component storybook-foundation-statuses" aria-label="Status specimens">
            <ul class="storybook-state-grid storybook-status-grid">
                ${status_specimen("Neutral", render_status({label: "Approval required"}))}
                ${status_specimen("Accent with icon", render_status({icon: "activity", label: "In progress", tone: "accent"}))}
                ${status_specimen(
                    "Contextual label",
                    render_status({
                        "aria-label": "Release status: Completed",
                        icon: "check",
                        label: "Completed",
                        tone: "success",
                    }),
                )}
                ${status_specimen("Warning", render_status({icon: "clock", label: "Needs attention", tone: "warning"}))}
                ${status_specimen("Danger", render_status({icon: "warning", label: "Blocked", tone: "danger"}))}
            </ul>
        </section>
    `,
};

export const Surfaces: Story = {
    render: () => render_surface_example(),
};
