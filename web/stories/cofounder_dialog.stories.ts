import type {Meta, StoryObj} from "@storybook/html";

import render_dialog from "../templates/dialog_widget.hbs";

type DialogArgs = {
    destructive: boolean;
    loading: boolean;
    subtitle: string;
    title: string;
};

function render_dialog_story(args: DialogArgs): HTMLElement {
    const html = render_dialog({
        close_on_overlay_click: true,
        modal_content_html: args.loading
            ? `
            <p style="margin:0;color:var(--cf-text-secondary);">
                Saving your changes to the shared workspace now.
            </p>
        `
            : `
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

    const container = globalThis.document.createElement("div");
    container.innerHTML = html
        .replace(
            "micromodal cf-theme cf-dialog-root",
            "micromodal cf-theme cf-dialog-root storybook-dialog-story modal--open",
        )
        .replace('aria-hidden="true"', 'aria-hidden="false"');

    const dialog = container.firstElementChild;
    if (!(dialog instanceof HTMLElement)) {
        throw new TypeError("The Cofounder dialog story did not render a dialog root.");
    }
    const rendered_dialog = dialog;

    const close_button = rendered_dialog.querySelector<HTMLButtonElement>(".cf-dialog__close");
    const exit_button = rendered_dialog.querySelector<HTMLButtonElement>(".cf-dialog__exit");
    const submit_button = rendered_dialog.querySelector<HTMLButtonElement>(".cf-dialog__submit");
    const overlay = rendered_dialog.querySelector<HTMLElement>(".cf-dialog-backdrop");

    function close_dialog(): void {
        rendered_dialog.classList.remove("modal--open");
        rendered_dialog.setAttribute("aria-hidden", "true");
        rendered_dialog.hidden = true;
    }

    close_button?.addEventListener("click", close_dialog);
    exit_button?.addEventListener("click", close_dialog);
    if (!args.loading) {
        submit_button?.addEventListener("click", close_dialog);
    }
    overlay?.addEventListener("click", (event) => {
        if (event.target === overlay) {
            close_dialog();
        }
    });
    rendered_dialog.addEventListener("keydown", (event) => {
        if (event.key === "Tab") {
            const focusable_buttons = [
                ...rendered_dialog.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"),
            ];
            const first_button = focusable_buttons[0];
            const last_button = focusable_buttons.at(-1);

            if (event.shiftKey && globalThis.document.activeElement === first_button) {
                event.preventDefault();
                last_button?.focus();
            } else if (!event.shiftKey && globalThis.document.activeElement === last_button) {
                event.preventDefault();
                first_button?.focus();
            }
        } else if (event.key === "Escape") {
            close_dialog();
        }
    });
    setTimeout(() => close_button?.focus(), 0);

    return rendered_dialog;
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
        subtitle: "Your changes should be ready in a few seconds.",
        title: "Saving workspace settings",
    },
};
