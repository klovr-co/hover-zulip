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
    return host;
}

function render_production_review(narrow = false): HTMLElement {
    const host = render_production_toolbar();
    host.classList.add("storybook-production-compose--review");
    host.classList.toggle("storybook-production-compose--narrow", narrow);

    const controls = host.querySelector<HTMLElement>("#cf-review-composer-controls");
    controls?.removeAttribute("hidden");
    const reply = host.querySelector<HTMLElement>('[data-cf-response-mode="reply"]');
    const review = host.querySelector<HTMLElement>('[data-cf-response-mode="review"]');
    reply?.setAttribute("aria-checked", "false");
    review?.setAttribute("aria-checked", "true");
    host.querySelector<HTMLElement>("[data-cf-reply-help]")?.setAttribute("hidden", "");
    host.querySelector<HTMLElement>("[data-cf-review-patch]")?.removeAttribute("hidden");

    const field = host.querySelector<HTMLSelectElement>("#cf-review-field");
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
    const value = host.querySelector<HTMLInputElement>("#cf-review-value");
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
