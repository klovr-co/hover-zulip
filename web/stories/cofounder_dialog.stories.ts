import type {Meta, StoryObj} from "@storybook/html";

import render_dialog from "../templates/dialog_widget.hbs";

type DialogArgs = {
    destructive: boolean;
    loading: boolean;
    subtitle: string;
    title: string;
};

function render_dialog_story(args: DialogArgs): string {
    const html = render_dialog({
        close_on_overlay_click: true,
        modal_content_html: `
            <p style="margin:0;color:var(--cf-text-secondary);">
                Review the details before continuing. This action updates the shared workspace.
            </p>
        `,
        modal_exit_button_text: "Cancel",
        modal_buttons_disabled: args.loading,
        modal_submit_button_busy: args.loading ? "true" : undefined,
        modal_submit_button_text: args.destructive ? "Delete workspace" : "Save changes",
        modal_submit_button_variant: args.destructive ? "danger" : "primary",
        modal_subtitle_html: args.subtitle,
        modal_title_text: args.title,
        modal_unique_id: "cofounder-dialog-story",
    });

    return html
        .replace(
            "micromodal cf-theme cf-dialog-root",
            "micromodal cf-theme cf-dialog-root modal--open",
        )
        .replace('aria-hidden="true"', 'aria-hidden="false"');
}

const meta = {
    title: "Cofounder/Components/Dialog",
    parameters: {layout: "fullscreen"},
    args: {
        destructive: false,
        loading: false,
        subtitle: "Changes are visible to everyone in this workspace.",
        title: "Workspace settings",
    },
    render: render_dialog_story,
} satisfies Meta<DialogArgs>;

export default meta;
type Story = StoryObj<DialogArgs>;

export const Default: Story = {};

export const Destructive: Story = {
    args: {
        destructive: true,
        subtitle: "This action cannot be undone.",
        title: "Delete workspace?",
    },
};

export const Loading: Story = {
    args: {
        loading: true,
        subtitle: "Keep this window open while changes are saved.",
        title: "Saving workspace settings",
    },
};
