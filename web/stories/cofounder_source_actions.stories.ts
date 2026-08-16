import type {Meta, StoryObj} from "@storybook/html";

import render_source_actions from "../templates/cofounder/components/source_actions.hbs";

type SourceActionsArgs = Record<string, never>;

const integrations = [
    {
        count: 3,
        id: null,
        key: "whatsapp",
        name: "WhatsApp",
        url: "#whatsapp",
    },
    {
        count: 1,
        id: null,
        key: "github",
        name: "GitHub",
        url: "#github",
    },
    {
        count: 2,
        id: null,
        key: "instagram",
        name: "Instagram unavailable",
        url: undefined,
    },
];

function render_story(): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme storybook-component";
    canvas.innerHTML = `<div class="storybook-component-stack">${render_source_actions({
        evidence_url: "#sources",
        integrations,
    })}<p class="storybook-source-actions__feedback" role="status" aria-live="polite" aria-atomic="true"></p></div>`;
    const feedback = canvas.querySelector<HTMLElement>(".storybook-source-actions__feedback");
    canvas
        .querySelector<HTMLButtonElement>("[data-cf-evidence-url]")
        ?.addEventListener("click", () => {
            if (feedback) {
                feedback.textContent = "Source evidence dialog requested.";
            }
        });
    for (const link of canvas.querySelectorAll<HTMLAnchorElement>(".cf-source-action[href]")) {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            if (feedback) {
                feedback.textContent = `${link.getAttribute("aria-label") ?? "Source integration"} requested.`;
            }
        });
    }
    return canvas;
}

const meta = {
    title: "Cofounder/Components/Source actions",
    parameters: {layout: "padded"},
    render: render_story,
} satisfies Meta<SourceActionsArgs>;

export default meta;
type Story = StoryObj<SourceActionsArgs>;

export const Default: Story = {};

export const NarrowTouch: Story = {
    parameters: {
        viewport: {defaultViewport: "mobile1"},
    },
};
