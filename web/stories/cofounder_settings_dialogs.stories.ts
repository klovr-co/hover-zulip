import type {Meta, StoryObj} from "@storybook/html";

import render_channel_list_item from "../templates/channel_list_item.hbs";
import render_dialog from "../templates/dialog_widget.hbs";
import render_source_results from "../templates/hover_source_discovery_results.hbs";
import render_space_setup from "../templates/hover_space_setup_modal.hbs";
import render_copy_email from "../templates/stream_settings/copy_email_address_modal.hbs";
import render_edit_folder from "../templates/stream_settings/edit_channel_folder_modal.hbs";

type DialogStoryContext = {
    dialog: HTMLElement;
    feedback: HTMLElement;
    submitButton: HTMLButtonElement | null;
};

function render_open_dialog(args: {
    content: string;
    id: string;
    initialFocus?: string;
    setup?: (context: DialogStoryContext) => void;
    submitLabel: string;
    title: string;
}): HTMLElement {
    const container = globalThis.document.createElement("div");
    container.innerHTML = render_dialog({
        close_on_overlay_click: true,
        id: args.id,
        modal_content_html: args.content,
        modal_exit_button_text: "Close",
        modal_submit_button_text: args.submitLabel,
        modal_submit_button_variant: "primary",
        modal_title_text: args.title,
        modal_unique_id: `${args.id}-story`,
    })
        .replace(
            "micromodal cf-theme cf-dialog-root",
            "micromodal cf-theme cf-dialog-root storybook-dialog-story storybook-settings-dialog modal--open",
        )
        .replace('aria-hidden="true"', 'aria-hidden="false"');

    const rendered_dialog = container.firstElementChild;
    if (!(rendered_dialog instanceof HTMLElement)) {
        throw new TypeError("The Cofounder settings dialog story did not render a dialog root.");
    }

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-settings-dialog__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    rendered_dialog.querySelector<HTMLElement>(".cf-dialog__body")?.append(feedback);

    const close_button = rendered_dialog.querySelector<HTMLButtonElement>(".cf-dialog__close");
    const exit_button = rendered_dialog.querySelector<HTMLButtonElement>(".cf-dialog__exit");
    const submit_button = rendered_dialog.querySelector<HTMLButtonElement>(".cf-dialog__submit");
    const overlay = rendered_dialog.querySelector<HTMLElement>(".cf-dialog-backdrop");

    const close_dialog = (): void => {
        rendered_dialog.classList.remove("modal--open");
        rendered_dialog.setAttribute("aria-hidden", "true");
        rendered_dialog.hidden = true;
    };

    close_button?.addEventListener("click", close_dialog);
    exit_button?.addEventListener("click", close_dialog);
    overlay?.addEventListener("click", (event) => {
        if (event.target === overlay) {
            close_dialog();
        }
    });
    rendered_dialog.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            close_dialog();
            return;
        }
        if (event.key !== "Tab") {
            return;
        }
        const focusable_buttons = [
            ...rendered_dialog.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"),
        ].filter((button) => button.getClientRects().length > 0);
        const first_button = focusable_buttons[0];
        const last_button = focusable_buttons.at(-1);
        if (event.shiftKey && globalThis.document.activeElement === first_button) {
            event.preventDefault();
            last_button?.focus();
        } else if (!event.shiftKey && globalThis.document.activeElement === last_button) {
            event.preventDefault();
            first_button?.focus();
        }
    });

    if (args.setup) {
        args.setup({dialog: rendered_dialog, feedback, submitButton: submit_button});
    } else {
        submit_button?.addEventListener("click", () => {
            feedback.textContent = `${args.submitLabel} requested.`;
        });
    }
    setTimeout(() => {
        const initial_focus = args.initialFocus
            ? rendered_dialog.querySelector<HTMLElement>(args.initialFocus)
            : close_button;
        initial_focus?.focus();
    }, 0);

    return rendered_dialog;
}

function setup_channel_email_dialog({dialog, feedback, submitButton}: DialogStoryContext): void {
    const sender_trigger = dialog.querySelector<HTMLButtonElement>(
        "#sender_channel_email_address_widget",
    );
    if (sender_trigger === null) {
        return;
    }
    const sender_value = sender_trigger.querySelector<HTMLElement>(".dropdown_widget_value");
    const sender_wrapper = sender_trigger.closest<HTMLElement>(
        ".dropdown_widget_with_label_wrapper",
    );
    const address_field = dialog.querySelector<HTMLElement>(".stream-email");
    const address_value = dialog.querySelector<HTMLElement>(".email-address");
    const copy_button = dialog.querySelector<HTMLButtonElement>(".copy-email-address");
    if (
        sender_value === null ||
        sender_wrapper === null ||
        address_field === null ||
        address_value === null ||
        copy_button === null
    ) {
        return;
    }

    let base_address = "design.4e2f7c@example.hover.app";
    const checkboxes = [...dialog.querySelectorAll<HTMLInputElement>(".tag-checkbox")];
    const update_address = (): string => {
        const separator = base_address.indexOf("@");
        const flags = checkboxes
            .filter((checkbox) => checkbox.checked)
            .map((checkbox) => `.${checkbox.id}`)
            .join("");
        const address = `${base_address.slice(0, separator)}${flags}${base_address.slice(separator)}`;
        address_value.textContent = address;
        copy_button.dataset["clipboardText"] = address;
        return address;
    };

    sender_wrapper.classList.add("storybook-settings-dialog__sender");
    const sender_menu = globalThis.document.createElement("div");
    sender_menu.id = "storybook-channel-email-sender-menu";
    sender_menu.className = "storybook-settings-dialog__sender-menu";
    sender_menu.setAttribute("role", "menu");
    sender_menu.setAttribute("aria-label", "Channel email sender");
    sender_menu.hidden = true;
    sender_trigger.setAttribute("aria-controls", sender_menu.id);
    sender_trigger.setAttribute("aria-expanded", "false");
    sender_trigger.setAttribute("aria-haspopup", "menu");

    const senders = ["Email Gateway bot", "You", "Design helper bot"] as const;
    const sender_options = senders.map((sender, index) => {
        const option = globalThis.document.createElement("button");
        option.type = "button";
        option.className = "storybook-settings-dialog__sender-option";
        option.setAttribute("role", "menuitemradio");
        option.setAttribute("aria-checked", String(index === 0));
        option.textContent = sender;
        sender_menu.append(option);
        return option;
    });
    sender_wrapper.append(sender_menu);

    const close_sender_menu = (restore_focus = false): void => {
        sender_menu.hidden = true;
        sender_trigger.setAttribute("aria-expanded", "false");
        if (restore_focus) {
            sender_trigger.focus();
        }
    };
    const select_sender = (option: HTMLButtonElement): void => {
        for (const candidate of sender_options) {
            candidate.setAttribute("aria-checked", String(candidate === option));
        }
        sender_value.textContent = option.textContent;
        sender_trigger.setAttribute("aria-label", `Sender: ${option.textContent}`);
        address_field.hidden = true;
        feedback.textContent = `${option.textContent} selected. Generate a new address to apply this sender.`;
        close_sender_menu(true);
    };

    sender_value.textContent = senders[0];
    sender_trigger.setAttribute("aria-label", `Sender: ${senders[0]}`);
    sender_trigger.addEventListener("click", () => {
        const opening = sender_menu.hidden;
        sender_menu.hidden = !opening;
        sender_trigger.setAttribute("aria-expanded", String(opening));
        if (opening) {
            sender_options[0]?.focus();
        }
    });
    sender_trigger.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            sender_menu.hidden = false;
            sender_trigger.setAttribute("aria-expanded", "true");
            sender_options[0]?.focus();
        }
    });
    for (const option of sender_options) {
        option.addEventListener("click", () => {
            select_sender(option);
        });
    }
    sender_menu.addEventListener("keydown", (event) => {
        const option =
            event.target instanceof Element
                ? event.target.closest<HTMLButtonElement>("[role='menuitemradio']")
                : null;
        if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            close_sender_menu(true);
            return;
        }
        if (option === null || !["ArrowDown", "ArrowUp"].includes(event.key)) {
            return;
        }
        event.preventDefault();
        const offset = event.key === "ArrowDown" ? 1 : -1;
        const next =
            sender_options[
                (sender_options.indexOf(option) + offset + sender_options.length) %
                    sender_options.length
            ];
        next?.focus();
    });
    dialog.addEventListener("click", (event) => {
        if (event.target instanceof Node && !sender_wrapper.contains(event.target)) {
            close_sender_menu();
        }
    });

    const default_checkbox = dialog.querySelector<HTMLInputElement>("#show-sender");
    if (default_checkbox) {
        default_checkbox.checked = true;
    }
    update_address();
    for (const checkbox of checkboxes) {
        checkbox.addEventListener("change", () => {
            update_address();
            const label = checkbox
                .closest<HTMLElement>(".cf-email-options__option")
                ?.querySelector<HTMLElement>(".cf-email-options__label")
                ?.textContent?.trim();
            feedback.textContent = `${label ?? "Email content"} ${checkbox.checked ? "included" : "excluded"}.`;
        });
    }
    copy_button.addEventListener("click", () => {
        const address = address_value.textContent ?? "";
        feedback.textContent = `Copy requested for ${address}.`;
    });
    submitButton?.addEventListener("click", () => {
        base_address = "design.9a73d1@example.hover.app";
        update_address();
        address_field.hidden = false;
        feedback.textContent = "Generated a new channel email address.";
        submitButton.focus();
    });
}

type StoryChannel = {
    color: string;
    invite_only: boolean;
    is_archived: boolean;
    is_web_public: boolean;
    name: string;
    stream_id: number;
};

function setup_channel_folder_dialog({dialog, feedback, submitButton}: DialogStoryContext): void {
    const list = dialog.querySelector<HTMLElement>(".folder-stream-list");
    const filter = dialog.querySelector<HTMLInputElement>(".stream-search");
    const clear_filter = dialog.querySelector<HTMLButtonElement>(".input-close-filter-button");
    const add_trigger = dialog.querySelector<HTMLButtonElement>("#add_channel_folder_widget");
    const add_button = dialog.querySelector<HTMLButtonElement>(".add-channel-button");
    const name_input = dialog.querySelector<HTMLInputElement>("#edit_channel_folder_name");
    const description_input = dialog.querySelector<HTMLTextAreaElement>(
        "#edit_channel_folder_description",
    );
    if (
        list === null ||
        filter === null ||
        add_trigger === null ||
        add_button === null ||
        name_input === null ||
        description_input === null ||
        submitButton === null
    ) {
        return;
    }
    const add_value = add_trigger.querySelector<HTMLElement>(".dropdown_widget_value");
    const add_wrapper = add_trigger.closest<HTMLElement>(".add_channel_folder_widget");
    if (add_value === null || add_wrapper === null) {
        return;
    }

    let channels: StoryChannel[] = [
        {
            color: "#3974d9",
            invite_only: false,
            is_archived: false,
            is_web_public: false,
            name: "Product planning",
            stream_id: 41,
        },
        {
            color: "#9b59b6",
            invite_only: true,
            is_archived: false,
            is_web_public: false,
            name: "Design reviews",
            stream_id: 42,
        },
        {
            color: "#2a9d72",
            invite_only: false,
            is_archived: false,
            is_web_public: true,
            name: "Launch coordination",
            stream_id: 43,
        },
    ];
    let candidates: StoryChannel[] = [
        {
            color: "#d97927",
            invite_only: false,
            is_archived: false,
            is_web_public: false,
            name: "Customer research",
            stream_id: 51,
        },
        {
            color: "#457b9d",
            invite_only: false,
            is_archived: false,
            is_web_public: false,
            name: "Support escalations",
            stream_id: 52,
        },
        {
            color: "#b04a5a",
            invite_only: true,
            is_archived: false,
            is_web_public: false,
            name: "Leadership notes",
            stream_id: 53,
        },
    ];
    let selected_candidate_id: number | undefined;

    const render_channels = (): void => {
        const query = filter.value.trim().toLocaleLowerCase();
        const visible_channels = channels.filter((channel) =>
            channel.name.toLocaleLowerCase().includes(query),
        );
        list.innerHTML = visible_channels
            .map((channel) =>
                render_channel_list_item({
                    can_manage_folder: true,
                    remove_channel_label: `Remove ${channel.name} from folder`,
                    stream: channel,
                    view_channel_label: `View details for ${channel.name}`,
                }),
            )
            .join("");
        if (visible_channels.length === 0) {
            const empty = globalThis.document.createElement("li");
            empty.className = "storybook-settings-dialog__empty-list";
            empty.textContent = query ? "No matching channels." : "No channels in this folder.";
            list.append(empty);
        }
    };

    list.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const row = event.target.closest<HTMLElement>(".stream-list-item");
        const stream_id = Number(row?.dataset["streamId"]);
        const channel = channels.find((candidate) => candidate.stream_id === stream_id);
        if (row === null || channel === undefined) {
            return;
        }
        if (event.target.closest(".remove-button")) {
            channels = channels.filter((candidate) => candidate !== channel);
            candidates = [...candidates, channel].toSorted((a, b) => a.name.localeCompare(b.name));
            render_channels();
            feedback.textContent = `${channel.name} removed from Product.`;
            filter.focus();
            return;
        }
        if (event.target.closest(".view-stream-card")) {
            feedback.textContent = `Channel details requested for ${channel.name}.`;
        }
    });

    filter.addEventListener("input", () => {
        render_channels();
        const visible_count = list.querySelectorAll(".stream-list-item").length;
        feedback.textContent = `${visible_count} ${visible_count === 1 ? "channel" : "channels"} shown.`;
    });
    clear_filter?.addEventListener("click", () => {
        filter.value = "";
        render_channels();
        feedback.textContent = `${channels.length} channels shown.`;
        filter.focus();
    });

    add_wrapper.classList.add("storybook-settings-dialog__menu-anchor");
    const channel_menu = globalThis.document.createElement("div");
    channel_menu.id = "storybook-channel-folder-menu";
    channel_menu.className = "storybook-settings-dialog__menu";
    channel_menu.setAttribute("role", "menu");
    channel_menu.setAttribute("aria-label", "Channels available to add");
    channel_menu.hidden = true;
    add_trigger.setAttribute("aria-controls", channel_menu.id);
    add_trigger.setAttribute("aria-expanded", "false");
    add_trigger.setAttribute("aria-haspopup", "menu");
    add_wrapper.append(channel_menu);

    const close_channel_menu = (restore_focus = false): void => {
        channel_menu.hidden = true;
        add_trigger.setAttribute("aria-expanded", "false");
        if (restore_focus) {
            add_trigger.focus();
        }
    };
    const select_candidate = (channel: StoryChannel): void => {
        selected_candidate_id = channel.stream_id;
        add_value.textContent = channel.name;
        add_trigger.setAttribute("aria-label", `Channel to add: ${channel.name}`);
        add_button.disabled = false;
        feedback.textContent = `${channel.name} selected to add.`;
        close_channel_menu(true);
    };
    const render_candidate_menu = (): void => {
        channel_menu.replaceChildren();
        for (const channel of candidates) {
            const option = globalThis.document.createElement("button");
            option.type = "button";
            option.className = "storybook-settings-dialog__menu-option";
            option.setAttribute("role", "menuitemradio");
            option.setAttribute(
                "aria-checked",
                String(channel.stream_id === selected_candidate_id),
            );
            option.textContent = channel.name;
            option.addEventListener("click", () => {
                select_candidate(channel);
            });
            channel_menu.append(option);
        }
    };
    add_trigger.addEventListener("click", () => {
        const opening = channel_menu.hidden;
        if (opening) {
            render_candidate_menu();
        }
        channel_menu.hidden = !opening;
        add_trigger.setAttribute("aria-expanded", String(opening));
        if (opening) {
            channel_menu.querySelector<HTMLButtonElement>("button")?.focus();
        }
    });
    add_trigger.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            render_candidate_menu();
            channel_menu.hidden = false;
            add_trigger.setAttribute("aria-expanded", "true");
            channel_menu.querySelector<HTMLButtonElement>("button")?.focus();
        }
    });
    channel_menu.addEventListener("keydown", (event) => {
        const options = [
            ...channel_menu.querySelectorAll<HTMLButtonElement>("[role='menuitemradio']"),
        ];
        const option =
            event.target instanceof Element
                ? event.target.closest<HTMLButtonElement>("[role='menuitemradio']")
                : null;
        if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            close_channel_menu(true);
            return;
        }
        if (option === null || !["ArrowDown", "ArrowUp"].includes(event.key)) {
            return;
        }
        event.preventDefault();
        const offset = event.key === "ArrowDown" ? 1 : -1;
        const next = options[(options.indexOf(option) + offset + options.length) % options.length];
        next?.focus();
    });
    dialog.addEventListener("click", (event) => {
        if (event.target instanceof Node && !add_wrapper.contains(event.target)) {
            close_channel_menu();
        }
    });
    add_button.addEventListener("click", () => {
        const channel = candidates.find(
            (candidate) => candidate.stream_id === selected_candidate_id,
        );
        if (channel === undefined) {
            return;
        }
        candidates = candidates.filter((candidate) => candidate !== channel);
        channels = [...channels, channel];
        selected_candidate_id = undefined;
        add_value.textContent = "Select a channel";
        add_trigger.setAttribute("aria-label", "Channel to add");
        add_button.disabled = true;
        filter.value = "";
        render_channels();
        feedback.textContent = `${channel.name} added to Product.`;
        add_trigger.focus();
    });

    let saved_name = name_input.value;
    let saved_description = description_input.value;
    const update_save_state = (): void => {
        const has_name = name_input.value.trim().length > 0;
        const changed =
            name_input.value !== saved_name || description_input.value !== saved_description;
        submitButton.disabled = !has_name || !changed;
        if (!has_name) {
            feedback.textContent = "Channel folder name is required.";
        }
    };
    name_input.addEventListener("input", update_save_state);
    description_input.addEventListener("input", update_save_state);
    submitButton.disabled = true;
    submitButton.addEventListener("click", () => {
        saved_name = name_input.value;
        saved_description = description_input.value;
        submitButton.disabled = true;
        feedback.textContent = `${saved_name.trim()} changes saved.`;
        name_input.focus();
    });

    render_channels();
}

function setup_space_setup_dialog({dialog, feedback, submitButton}: DialogStoryContext): void {
    const source_status = dialog.querySelector<HTMLElement>("#cf-source-discovery-status");
    const source_preview = dialog.querySelector<HTMLElement>("#cf-source-preview");
    const source_query = dialog.querySelector<HTMLInputElement>("#cf-source-query");
    const source_account = dialog.querySelector<HTMLSelectElement>("#cf-source-account");
    const history_window = dialog.querySelector<HTMLSelectElement>("#cf-source-history-window");
    const custom_date_field = dialog.querySelector<HTMLElement>("[data-cf-source-custom-date]");
    const custom_date = dialog.querySelector<HTMLInputElement>("#cf-source-custom-start-date");
    if (
        source_status === null ||
        source_preview === null ||
        source_query === null ||
        source_account === null ||
        history_window === null ||
        custom_date_field === null ||
        custom_date === null ||
        submitButton === null
    ) {
        return;
    }

    const source_rows = [...dialog.querySelectorAll<HTMLElement>(".cf-space-workbench__candidate")];
    let selected_source_ref: string | undefined;
    let selected_source_name: string | undefined;

    const source_details = (
        row: HTMLElement,
    ): {detail: string; input: HTMLInputElement; name: string} | undefined => {
        const input = row.querySelector<HTMLInputElement>("input[name='cf_source_candidate']");
        const name = row.querySelector<HTMLElement>(
            ":scope .cf-space-workbench__candidate-copy strong",
        );
        const detail = row.querySelector<HTMLElement>(
            ":scope .cf-space-workbench__candidate-copy small",
        );
        if (input === null || name === null || detail === null) {
            return undefined;
        }
        return {
            detail: detail.textContent?.trim() ?? "",
            input,
            name: name.textContent?.trim() ?? "Source",
        };
    };
    const update_attach_state = (): void => {
        const custom_date_missing = history_window.value === "custom" && custom_date.value === "";
        submitButton.disabled = selected_source_ref === undefined || custom_date_missing;
    };
    const reset_source_selection = (): void => {
        selected_source_ref = undefined;
        selected_source_name = undefined;
        for (const radio of dialog.querySelectorAll<HTMLInputElement>(
            "input[name='cf_source_candidate']",
        )) {
            radio.checked = false;
        }
        source_preview.classList.add("hide");
        source_preview.replaceChildren();
        update_attach_state();
    };
    const preview_source = (row: HTMLElement): void => {
        const details = source_details(row);
        if (details === undefined) {
            return;
        }
        selected_source_ref = details.input.value;
        selected_source_name = details.name;
        details.input.checked = true;
        const label = globalThis.document.createElement("span");
        label.className = "cf-space-workbench__preview-label";
        label.textContent = "Verified preview";
        const name = globalThis.document.createElement("strong");
        name.textContent = details.name;
        const detail = globalThis.document.createElement("small");
        detail.textContent = details.detail;
        source_preview.replaceChildren(label, name, detail);
        source_preview.classList.remove("hide");
        source_status.textContent = "Source identity verified.";
        feedback.textContent = `${details.name} is verified and ready to attach.`;
        update_attach_state();
    };
    const filter_sources = (): void => {
        const query = source_query.value.trim().toLocaleLowerCase();
        let visible_count = 0;
        let selected_is_visible = false;
        for (const row of source_rows) {
            const details = source_details(row);
            const visible = details?.name.toLocaleLowerCase().includes(query) ?? false;
            row.hidden = !visible;
            if (visible) {
                visible_count += 1;
                selected_is_visible ||= details?.input.value === selected_source_ref;
            }
        }
        if (!selected_is_visible && selected_source_ref !== undefined) {
            reset_source_selection();
        }
        source_status.textContent =
            visible_count === 0
                ? "No permitted Sources found."
                : `${visible_count} permitted ${visible_count === 1 ? "Source" : "Sources"} found. Choose one to preview.`;
        feedback.textContent =
            visible_count === 0
                ? "No permitted Sources match this search."
                : `${visible_count} ${visible_count === 1 ? "Source" : "Sources"} shown.`;
    };

    submitButton.disabled = true;
    source_status.textContent = "2 permitted Sources found. Choose one to preview.";
    dialog
        .querySelector<HTMLButtonElement>("[data-cf-space-action='search-source']")
        ?.addEventListener("click", filter_sources);
    source_query.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            filter_sources();
        }
    });
    source_account.addEventListener("change", () => {
        source_query.value = "";
        for (const row of source_rows) {
            row.hidden = false;
        }
        reset_source_selection();
        source_status.textContent = "2 permitted Sources found. Choose one to preview.";
        feedback.textContent = "Assigned account updated; Source selection reset.";
    });
    for (const row of source_rows) {
        row.querySelector<HTMLInputElement>("input[name='cf_source_candidate']")?.addEventListener(
            "change",
            () => {
                preview_source(row);
            },
        );
        row.querySelector<HTMLButtonElement>(
            "[data-cf-space-action='preview-source']",
        )?.addEventListener("click", () => {
            preview_source(row);
        });
    }
    dialog
        .querySelector<HTMLButtonElement>("[data-cf-space-action='more-sources']")
        ?.addEventListener("click", (event) => {
            const button = event.currentTarget;
            if (!(button instanceof HTMLButtonElement)) {
                return;
            }
            button.disabled = true;
            source_status.textContent = "All permitted Sources are shown.";
            feedback.textContent = "No additional permitted Sources in this preview.";
            source_query.focus();
        });
    const update_history_window = (): void => {
        const is_custom = history_window.value === "custom";
        custom_date_field.classList.toggle("hide", !is_custom);
        custom_date.required = is_custom;
        if (!is_custom) {
            custom_date.value = "";
        }
        feedback.textContent = `${history_window.selectedOptions[0]?.textContent?.trim() ?? "History"} history selected.`;
        update_attach_state();
    };
    history_window.addEventListener("change", update_history_window);
    custom_date.addEventListener("input", update_attach_state);
    submitButton.addEventListener("click", () => {
        if (selected_source_ref === undefined || selected_source_name === undefined) {
            return;
        }
        if (history_window.value === "custom" && !custom_date.checkValidity()) {
            feedback.textContent = "Choose a custom history start date.";
            custom_date.focus();
            return;
        }
        const history =
            history_window.value === "custom"
                ? `history starting ${custom_date.value}`
                : `${history_window.selectedOptions[0]?.textContent?.trim() ?? "bounded"} history`;
        feedback.textContent = `${selected_source_name} attached with ${history}.`;
        submitButton.disabled = true;
        source_query.focus();
    });

    for (const trigger of dialog.querySelectorAll<HTMLSelectElement>("[data-cf-module-trigger]")) {
        trigger.addEventListener("change", () => {
            const card = trigger.closest<HTMLElement>("[data-cf-module-card]");
            const schedule = card?.querySelector<HTMLElement>("[data-cf-module-schedule]");
            const debounce = card?.querySelector<HTMLElement>("[data-cf-module-debounce]");
            schedule?.classList.toggle("hide", trigger.value !== "schedule");
            debounce?.classList.toggle("hide", trigger.value !== "new_source");
            const module_name = card?.querySelector<HTMLElement>(
                ":scope .cf-space-workbench__row-copy strong",
            )?.textContent;
            feedback.textContent = `${module_name ?? "Module"} trigger set to ${trigger.selectedOptions[0]?.textContent?.trim() ?? trigger.value}.`;
        });
    }
    for (const checkbox of dialog.querySelectorAll<HTMLInputElement>(
        "[data-cf-module-attachment], [data-cf-module-backfill-confirm]",
    )) {
        checkbox.addEventListener("change", () => {
            const label = checkbox.closest("label")?.textContent?.trim() ?? "Module option";
            feedback.textContent = `${label} ${checkbox.checked ? "selected" : "cleared"}.`;
        });
    }
    dialog
        .querySelector<HTMLButtonElement>("[data-cf-space-action='install-module']")
        ?.addEventListener("click", (event) => {
            const button = event.currentTarget;
            if (!(button instanceof HTMLButtonElement)) {
                return;
            }
            const card = button.closest<HTMLElement>("[data-cf-module-card]");
            const module_name =
                card
                    ?.querySelector<HTMLElement>(":scope .cf-space-workbench__row-copy strong")
                    ?.textContent?.trim() ?? "Module";
            button.disabled = true;
            button.querySelector<HTMLElement>(".cf-button__label")!.textContent = "Enabled";
            feedback.textContent = `${module_name} enabled with the selected policy.`;
            card?.querySelector<HTMLSelectElement>("[data-cf-module-trigger]")?.focus();
        });
    dialog
        .querySelector<HTMLButtonElement>("[data-cf-space-action='disable-module']")
        ?.addEventListener("click", (event) => {
            const button = event.currentTarget;
            if (!(button instanceof HTMLButtonElement)) {
                return;
            }
            const row = button.closest<HTMLElement>(".cf-space-workbench__installed-row");
            const module_name =
                row
                    ?.querySelector<HTMLElement>(":scope .cf-space-workbench__row-copy strong")
                    ?.textContent?.trim() ?? "Module";
            row?.remove();
            feedback.textContent = `${module_name} disabled.`;
            const heading = dialog.querySelector<HTMLElement>("#cf-space-modules-heading");
            heading?.setAttribute("tabindex", "-1");
            heading?.focus();
        });

    const membership_panel = dialog.querySelector<HTMLElement>("#cf-space-membership-panel");
    const launch_button = membership_panel?.querySelector<HTMLButtonElement>(
        "[data-cf-space-action='launch-space']",
    );
    const update_launch_state = (): void => {
        if (
            membership_panel?.querySelector(
                ":scope [data-cf-membership-action='confirm-suggestion']",
            ) !== null
        ) {
            return;
        }
        const open_requirement = [
            ...dialog.querySelectorAll<HTMLElement>(":scope #cf-space-launch-requirements li"),
        ].find((item) => item.textContent?.includes("No pending teammate suggestions"));
        open_requirement?.setAttribute("data-state", "met");
        if (launch_button) {
            launch_button.disabled = false;
            launch_button.querySelector<HTMLElement>(".cf-button__label")!.textContent =
                "Run final check & launch";
        }
        const launch_heading = membership_panel?.querySelector<HTMLElement>(
            ":scope .cf-space-workbench__launch-copy strong",
        );
        if (launch_heading) {
            launch_heading.textContent = "Ready for final launch check";
        }
    };
    membership_panel?.addEventListener("change", (event) => {
        const select =
            event.target instanceof Element
                ? event.target.closest<HTMLSelectElement>("[data-cf-member-role]")
                : null;
        if (select === null) {
            return;
        }
        const name = select
            .closest<HTMLElement>("[data-cf-member-row]")
            ?.querySelector<HTMLElement>(
                ":scope .cf-space-workbench__row-copy strong",
            )?.textContent;
        feedback.textContent = `${name ?? "Teammate"} role changed to ${select.selectedOptions[0]?.textContent?.trim() ?? select.value}.`;
    });
    membership_panel?.addEventListener("click", (event) => {
        const button =
            event.target instanceof Element
                ? event.target.closest<HTMLButtonElement>("[data-cf-membership-action]")
                : null;
        if (button === null) {
            return;
        }
        const row = button.closest<HTMLElement>("[data-cf-member-row]");
        const name =
            row
                ?.querySelector<HTMLElement>(":scope .cf-space-workbench__row-copy strong")
                ?.textContent?.trim() ?? "Teammate";
        const action = button.dataset["cfMembershipAction"];
        if (action === "confirm-suggestion") {
            const detail = row?.querySelector<HTMLElement>(
                ":scope .cf-space-workbench__row-copy small",
            );
            if (detail) {
                detail.textContent = "Confirmed member";
            }
            button.remove();
            feedback.textContent = `${name} confirmed as a Space teammate.`;
            row?.querySelector<HTMLSelectElement>("[data-cf-member-role]")?.focus();
            update_launch_state();
            return;
        }
        if (action === "remove") {
            row?.remove();
            feedback.textContent = `${name} removed from the Space.`;
            const heading = membership_panel?.querySelector<HTMLElement>(
                "#cf-space-members-heading",
            );
            heading?.setAttribute("tabindex", "-1");
            heading?.focus();
            update_launch_state();
            return;
        }
        if (action === "promote") {
            const select = row?.querySelector<HTMLSelectElement>("[data-cf-member-role]");
            const role = globalThis.document.createElement("span");
            role.className = "cf-space-workbench__member-role";
            role.textContent = select?.selectedOptions[0]?.textContent?.trim() ?? "Member";
            select?.replaceWith(role);
            row?.querySelectorAll<HTMLButtonElement>("[data-cf-membership-action]").forEach(
                (action_button) => {
                    action_button.remove();
                },
            );
            const detail = row?.querySelector<HTMLElement>(
                ":scope .cf-space-workbench__row-copy small",
            );
            if (detail) {
                detail.textContent = "Space Admin";
            }
            feedback.textContent = `${name} promoted to Space Admin.`;
            role.setAttribute("tabindex", "-1");
            role.focus();
        }
    });
    const add_member_button = dialog.querySelector<HTMLButtonElement>(
        "[data-cf-space-action='add-member']",
    );
    add_member_button?.addEventListener("click", () => {
        const user = dialog.querySelector<HTMLSelectElement>("#cf-member-user");
        const role = dialog.querySelector<HTMLSelectElement>("#cf-member-role");
        const name = user?.selectedOptions[0]?.textContent?.trim() ?? "Selected teammate";
        feedback.textContent = `${name} added as ${role?.selectedOptions[0]?.textContent?.trim() ?? "Contributor"}.`;
        add_member_button.disabled = true;
        user?.focus();
    });
    launch_button?.addEventListener("click", () => {
        launch_button.disabled = true;
        launch_button.querySelector<HTMLElement>(".cf-button__label")!.textContent = "Launched";
        feedback.textContent = "Final launch check passed. Community launch is now live.";
        const heading = dialog.querySelector<HTMLElement>(
            ":scope .cf-space-workbench__identity h2",
        );
        heading?.setAttribute("tabindex", "-1");
        heading?.focus();
    });
}

const meta = {
    title: "Cofounder/Settings/Dialogs",
    parameters: {layout: "fullscreen"},
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const ChannelEmailAddress: Story = {
    render: () =>
        render_open_dialog({
            content: render_copy_email({
                email_address: "design.4e2f7c@example.hover.app",
                tags: [
                    {description: "The sender's email address", name: "show-sender"},
                    {
                        description: "Email footers (for example, signatures)",
                        name: "include-footer",
                    },
                    {description: "Quoted original email in replies", name: "include-quotes"},
                    {description: "Use HTML encoding", name: "prefer-html"},
                ],
            }),
            id: "copy_email_address_modal",
            setup: setup_channel_email_dialog,
            submitLabel: "Generate email address",
            title: "Generate channel email address",
        }),
};

export const ManageChannelFolder: Story = {
    render: () =>
        render_open_dialog({
            content: render_edit_folder({
                can_manage_folder: true,
                description: "Planning and delivery channels for the product team.",
                folder_id: 4,
                max_channel_folder_description_length: 200,
                max_channel_folder_name_length: 60,
                name: "Product",
            }),
            id: "edit_channel_folder",
            initialFocus: "#edit_channel_folder_name",
            setup: setup_channel_folder_dialog,
            submitLabel: "Save changes",
            title: "Manage channel folder",
        }),
};

export const SpaceSetup: Story = {
    render() {
        const source = {
            account_display_name: "Community operations",
            display_name: "Mentors & Volunteers",
            icon_name: "phone",
            provider_key: "whatsapp",
            source_ref: "wa-community-planning",
            source_type: "group",
        };
        const attachment = {icon_name: source.icon_name, id: 41, source};
        const results = render_source_results({
            has_more: true,
            has_sources: true,
            sources: [
                source,
                {
                    account_display_name: "Product organization",
                    display_name: "Research repository",
                    icon_name: "link-alt",
                    provider_key: "workspace",
                    source_ref: "workspace-research",
                    source_type: "workspace",
                },
            ],
        });
        const content = render_space_setup({
            accounts: [{display_name: "Community operations", id: 3, provider_name: "WhatsApp"}],
            eligible_users: [{full_name: "Amina Niyonkuru", user_id: 14}],
            has_accounts: true,
            has_attachments: true,
            has_eligible_users: true,
            has_module_catalog: true,
            has_module_installations: true,
            launch_ready: false,
            launch_requirements: [
                {icon_name: "check", label: "At least one active Source", met: true},
                {icon_name: "check", label: "At least one confirmed teammate", met: true},
                {
                    icon_name: "warning",
                    label: "No pending teammate suggestions",
                    met: false,
                },
                {icon_name: "check", label: "No paused Module bindings", met: true},
            ],
            module_catalog: [
                {
                    attachments: [attachment],
                    description:
                        "Creates a concise daily view of decisions, follow-ups, and unanswered questions.",
                    destination_topic: "Daily brief",
                    icon_name: "file-text",
                    id: 22,
                    is_installed: false,
                    name: "Conversation Digest",
                    supports_manual: true,
                    supports_new_source: true,
                    supports_schedule: true,
                    version: "1.4",
                },
            ],
            space: {
                attachments: [attachment],
                category: {name: "Community"},
                description: "Coordinate the people and evidence needed for the next launch.",
                membership_suggestions: [
                    {full_name: "Maya Chen", suggested_role: "subscriber", user_id: 10},
                ],
                memberships: [
                    {
                        full_name: "Ava Rodriguez",
                        is_administrator: true,
                        role: "contributor",
                        user_id: 7,
                    },
                    {
                        full_name: "Jordan Lee",
                        is_administrator: false,
                        role: "subscriber",
                        user_id: 8,
                    },
                ],
                module_installations: [
                    {id: 19, name: "Suggested Actions", state: "enabled", version: "2.1"},
                ],
                name: "Community launch",
            },
        }).replace(
            '<div id="cf-source-discovery-results"></div>',
            () => `<div id="cf-source-discovery-results">${results}</div>`,
        );

        return render_open_dialog({
            content,
            id: "cf-space-setup-dialog",
            setup: setup_space_setup_dialog,
            submitLabel: "Attach Source",
            title: "Space Setup",
        });
    },
};
