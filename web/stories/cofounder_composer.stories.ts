import type {Meta, StoryObj} from "@storybook/html";

import render_composer from "../templates/cofounder/components/composer.hbs";
import render_production_compose from "../templates/compose.hbs";

type ComposerArgs = {
    channel?: string;
    disabled: boolean;
    placeholder: string;
    recipient?: string;
    value?: string;
};

const meta = {
    title: "Cofounder/Composer",
    args: {
        channel: "design",
        disabled: false,
        placeholder: "Compose a message",
        recipient: "Homepage redesign",
        value: "",
    },
    render: (args) => render_composer(args),
} satisfies Meta<ComposerArgs>;

export default meta;
type Story = StoryObj<ComposerArgs>;
type ReviewMode = "reply" | "review";

function is_review_mode(value: string | undefined): value is ReviewMode {
    return value === "reply" || value === "review";
}

function apply_review_mode(host: HTMLElement, selected: ReviewMode): void {
    for (const mode of host.querySelectorAll<HTMLButtonElement>(
        ":scope .cf-review-composer__mode",
    )) {
        const is_selected = mode.dataset["cfResponseMode"] === selected;
        mode.setAttribute("aria-checked", String(is_selected));
        mode.tabIndex = is_selected ? 0 : -1;
    }
    const reply_help = host.querySelector<HTMLElement>(":scope [data-cf-reply-help]");
    const review_patch = host.querySelector<HTMLElement>(":scope [data-cf-review-patch]");
    if (reply_help !== null) {
        reply_help.hidden = selected !== "reply";
    }
    if (review_patch !== null) {
        review_patch.hidden = selected !== "review";
    }
}

function initialize_review_mode(host: HTMLElement): void {
    const modes = [...host.querySelectorAll<HTMLButtonElement>(":scope .cf-review-composer__mode")];
    for (const [index, mode] of modes.entries()) {
        mode.addEventListener("click", () => {
            const selected = mode.dataset["cfResponseMode"];
            if (is_review_mode(selected)) {
                apply_review_mode(host, selected);
            }
        });
        mode.addEventListener("keydown", (event) => {
            let next_index: number | undefined;
            if (event.key === "Home") {
                next_index = 0;
            } else if (event.key === "End") {
                next_index = modes.length - 1;
            } else if (["ArrowLeft", "ArrowUp"].includes(event.key)) {
                next_index = (index - 1 + modes.length) % modes.length;
            } else if (["ArrowRight", "ArrowDown"].includes(event.key)) {
                next_index = (index + 1) % modes.length;
            }
            if (next_index === undefined) {
                return;
            }
            event.preventDefault();
            const next_mode = modes[next_index];
            if (next_mode === undefined || !is_review_mode(next_mode.dataset["cfResponseMode"])) {
                return;
            }
            apply_review_mode(host, next_mode.dataset["cfResponseMode"]);
            next_mode.focus();
        });
    }
}

function render_production_toolbar(): HTMLElement {
    const host = globalThis.document.createElement("div");
    host.id = "compose";
    host.className = "compose-box-open storybook-production-compose";

    const container = globalThis.document.createElement("div");
    container.id = "compose-container";
    container.innerHTML = render_production_compose({
        embedded: true,
        empty_string_topic_display_name: "general chat",
        file_upload_enabled: true,
        giphy_enabled: true,
        klipy_enabled: false,
        message_id: undefined,
        preview_mode_on: false,
        tenor_enabled: false,
    });
    host.append(container);

    const recipient_value = host.querySelector<HTMLElement>(
        ":scope #compose_select_recipient_widget .dropdown_widget_value",
    );
    if (recipient_value !== null) {
        recipient_value.textContent = "design";
    }
    const topic = host.querySelector<HTMLInputElement>(":scope #stream_message_recipient_topic");
    if (topic !== null) {
        topic.value = "Homepage redesign";
    }
    const direct_recipient = host.querySelector<HTMLElement>(":scope #compose-direct-recipient");
    if (direct_recipient !== null) {
        direct_recipient.hidden = true;
        direct_recipient.style.display = "none";
    }
    return host;
}

function render_production_review(narrow = false): HTMLElement {
    const host = render_production_toolbar();
    host.classList.add("storybook-production-compose--review");
    host.classList.toggle("storybook-production-compose--narrow", narrow);

    const controls = host.querySelector<HTMLElement>(":scope #cf-review-composer-controls");
    controls?.removeAttribute("hidden");
    apply_review_mode(host, "review");
    initialize_review_mode(host);

    const field = host.querySelector<HTMLSelectElement>(":scope #cf-review-field");
    if (field !== null) {
        for (const [label, option_value] of [
            ["venue", "venue"],
            ["delivery entrance", "delivery_entrance"],
        ] as const) {
            const option = globalThis.document.createElement("option");
            option.text = label;
            option.value = option_value;
            field.append(option);
        }
        field.value = "delivery_entrance";
    }
    const value = host.querySelector<HTMLInputElement>(":scope #cf-review-value");
    if (value !== null) {
        value.value = '"South gate"';
    }
    return host;
}

export const Default: Story = {};

export const Typing: Story = {
    args: {value: "The empty and loading states are ready for review."},
};

export const Disabled: Story = {
    args: {disabled: true},
};

export const ProductionToolbar: Story = {
    render: render_production_toolbar,
};

export const ProductionReview: Story = {
    render: () => render_production_review(),
};

export const ProductionReviewNarrow: Story = {
    render: () => render_production_review(true),
};
