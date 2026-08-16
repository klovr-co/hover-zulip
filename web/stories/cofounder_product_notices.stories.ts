import type {Meta, StoryObj} from "@storybook/html";

import render_message_sent_banner from "../templates/compose_banner/message_sent_banner.hbs";
import render_upload_banner from "../templates/compose_banner/upload_banner.hbs";
import render_modal_banner from "../templates/modal_banner/modal_banner.hbs";
import render_mark_as_read_disabled_banner from "../templates/unread_banner/mark_as_read_disabled_banner.hbs";
import render_cannot_deactivate_group_banner from "../templates/user_group_settings/cannot_deactivate_group_banner.hbs";

type NoticeArgs = Record<string, never>;

function render_message_sent_notice(): HTMLElement {
    const host = globalThis.document.createElement("section");
    host.className = "cf-theme storybook-notice-story";
    host.innerHTML = render_message_sent_banner({
        action_button_text: "View message",
        banner_text: "Your message was sent.",
        classname: "sent_scroll_to_view",
        link_msg_id: 42,
    });

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-notice-story__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");

    const restore = globalThis.document.createElement("button");
    restore.type = "button";
    restore.className = "cf-button cf-button--secondary storybook-product-notice__restore hide";
    restore.textContent = "Restore message notice";
    restore.hidden = true;
    host.append(feedback, restore);

    const notice = host.querySelector<HTMLElement>(".cf-notice");
    const hide_notice = (outcome: string): void => {
        if (notice) {
            notice.hidden = true;
            notice.classList.add("hide");
        }
        feedback.textContent = outcome;
        restore.hidden = false;
        restore.classList.remove("hide");
        restore.focus();
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        if (event.target.closest(".storybook-product-notice__restore")) {
            if (notice) {
                notice.hidden = false;
                notice.classList.remove("hide");
            }
            restore.hidden = true;
            restore.classList.add("hide");
            feedback.textContent = "Message sent notice restored.";
            notice?.querySelector<HTMLButtonElement>(".cf-notice__action")?.focus();
            return;
        }
        if (event.target.closest(".cf-notice__close")) {
            hide_notice("Message sent notice dismissed.");
            return;
        }
        const action = event.target.closest<HTMLButtonElement>(".cf-notice__action");
        if (action) {
            hide_notice(`Message ${action.dataset["messageId"] ?? "42"} selected.`);
        }
    });

    return host;
}

function render_upload_progress_notice(): HTMLElement {
    const filename = "product-brief.pdf";
    const host = globalThis.document.createElement("section");
    host.className = "cf-theme storybook-notice-story";
    host.innerHTML = render_upload_banner({
        banner_text: `Uploading ${filename}…`,
        banner_type: "info",
        cancel_button_label: `Cancel upload of ${filename}`,
        file_id: "product-brief",
        hide_button_label: `Hide upload progress for ${filename}`,
        is_upload_process_tracker: true,
        progress_label: `Upload progress for ${filename}`,
    });

    const progress = host.querySelector<HTMLElement>(".moving_bar");
    progress?.style.setProperty("width", "42%");
    progress?.setAttribute("aria-valuenow", "42");

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-notice-story__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");

    const restore = globalThis.document.createElement("button");
    restore.type = "button";
    restore.className = "cf-button cf-button--secondary storybook-product-notice__restore hide";
    restore.textContent = "Restore upload notice";
    restore.hidden = true;
    host.append(feedback, restore);

    const notice = host.querySelector<HTMLElement>(".upload_banner");
    const hide_notice = (outcome: string): void => {
        notice?.classList.add("hide");
        if (notice) {
            notice.hidden = true;
        }
        feedback.textContent = outcome;
        restore.hidden = false;
        restore.classList.remove("hide");
        restore.focus();
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        if (event.target.closest(".storybook-product-notice__restore")) {
            if (notice) {
                notice.hidden = false;
                notice.classList.remove("hide");
            }
            restore.hidden = true;
            restore.classList.add("hide");
            feedback.textContent = "Upload notice restored at 42 percent.";
            notice?.querySelector<HTMLButtonElement>(".upload_banner_cancel_button")?.focus();
            return;
        }
        if (event.target.closest(".upload_banner_cancel_button")) {
            hide_notice(`Upload of ${filename} canceled.`);
            return;
        }
        if (event.target.closest(".cf-notice__close")) {
            hide_notice(`Upload progress for ${filename} hidden.`);
        }
    });

    return host;
}

function render_modal_warning_notice(): HTMLElement {
    const host = globalThis.document.createElement("section");
    host.className = "cf-theme storybook-notice-story";
    host.innerHTML = render_modal_banner({
        banner_text: "Some participants are not subscribed to this channel.",
        banner_type: "warning",
        button_text: "Review participants",
        classname: "unsubscribed-participants-warning",
    });

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-notice-story__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");

    const restore = globalThis.document.createElement("button");
    restore.type = "button";
    restore.className = "cf-button cf-button--secondary storybook-product-notice__restore hide";
    restore.textContent = "Restore participant warning";
    restore.hidden = true;
    host.append(feedback, restore);

    const notice = host.querySelector<HTMLElement>(".cf-notice");
    const action = notice?.querySelector<HTMLButtonElement>(".cf-notice__action");

    const hide_notice = (outcome: string): void => {
        if (notice) {
            notice.hidden = true;
            notice.classList.add("hide");
        }
        feedback.textContent = outcome;
        restore.hidden = false;
        restore.classList.remove("hide");
        restore.focus();
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        if (event.target.closest(".storybook-product-notice__restore")) {
            if (notice) {
                notice.hidden = false;
                notice.classList.remove("hide");
            }
            restore.hidden = true;
            restore.classList.add("hide");
            feedback.textContent = "Participant warning restored.";
            action?.focus();
            return;
        }
        if (event.target.closest(".cf-notice__close")) {
            hide_notice("Participant subscription warning dismissed.");
            return;
        }
        if (event.target.closest(".cf-notice__action") && action) {
            if (action.getAttribute("aria-busy") === "true") {
                return;
            }
            action.setAttribute("aria-disabled", "true");
            action.setAttribute("aria-busy", "true");
            feedback.textContent = "Reviewing participants…";
            setTimeout(() => {
                action.setAttribute("aria-disabled", "false");
                action.setAttribute("aria-busy", "false");
                hide_notice("Participant review opened.");
            }, 250);
        }
    });

    return host;
}

function render_reading_state_notice(): HTMLElement {
    const host = globalThis.document.createElement("section");
    host.className = "cf-theme storybook-notice-story";
    host.innerHTML = render_mark_as_read_disabled_banner();

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-notice-story__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");

    const restore = globalThis.document.createElement("button");
    restore.type = "button";
    restore.className = "cf-button cf-button--secondary storybook-product-notice__restore hide";
    restore.textContent = "Restore reading-state notice";
    restore.hidden = true;
    host.append(feedback, restore);

    const notice = host.querySelector<HTMLElement>(".cf-notice");
    const mark_read = notice?.querySelector<HTMLButtonElement>(".mark-view-read");

    const hide_notice = (outcome: string): void => {
        if (notice) {
            notice.hidden = true;
            notice.classList.add("hide");
        }
        feedback.textContent = outcome;
        restore.hidden = false;
        restore.classList.remove("hide");
        restore.focus();
    };

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        if (event.target.closest(".storybook-product-notice__restore")) {
            if (notice) {
                notice.hidden = false;
                notice.classList.remove("hide");
            }
            restore.hidden = true;
            restore.classList.add("hide");
            feedback.textContent = "Reading-state notice restored.";
            mark_read?.focus();
            return;
        }
        if (event.target.closest(".mark-as-read-state-content a")) {
            event.preventDefault();
            feedback.textContent = "Reading preferences selected.";
            return;
        }
        if (event.target.closest(".cf-notice__close")) {
            hide_notice("Reading-state notice dismissed.");
            return;
        }
        if (event.target.closest(".mark-view-read")) {
            hide_notice("Messages in this view marked as read.");
        }
    });

    return host;
}

function render_permissions_error_notice(): HTMLElement {
    const host = globalThis.document.createElement("section");
    host.className = "cf-theme storybook-notice-story";
    host.innerHTML = render_cannot_deactivate_group_banner({group_used_for_permissions: true});

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-notice-story__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");

    const restore = globalThis.document.createElement("button");
    restore.type = "button";
    restore.className = "cf-button cf-button--secondary storybook-product-notice__restore hide";
    restore.textContent = "Return to permissions error";
    restore.hidden = true;
    host.append(feedback, restore);

    const notice = host.querySelector<HTMLElement>(".cf-notice");
    const permissions = notice?.querySelector<HTMLButtonElement>(".permissions-button");

    host.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        if (event.target.closest(".storybook-product-notice__restore")) {
            if (notice) {
                notice.hidden = false;
                notice.classList.remove("hide");
            }
            restore.hidden = true;
            restore.classList.add("hide");
            feedback.textContent = "Permissions error restored.";
            permissions?.focus();
            return;
        }
        if (event.target.closest(".permissions-button")) {
            if (notice) {
                notice.hidden = true;
                notice.classList.add("hide");
            }
            feedback.textContent = "Permissions panel selected.";
            restore.hidden = false;
            restore.classList.remove("hide");
            restore.focus();
        }
    });

    return host;
}

const meta = {
    title: "Cofounder/Patterns/Product Notices",
    parameters: {layout: "padded"},
} satisfies Meta<NoticeArgs>;

export default meta;
type Story = StoryObj<NoticeArgs>;

export const MessageSent: Story = {
    render: render_message_sent_notice,
};

export const UploadProgress: Story = {
    render: render_upload_progress_notice,
};

export const ModalWarning: Story = {
    render: render_modal_warning_notice,
};

export const ReadingState: Story = {
    render: render_reading_state_notice,
};

export const PermissionsError: Story = {
    render: render_permissions_error_notice,
};
