import type {Meta, StoryObj} from "@storybook/html";

import render_all_filters from "../templates/hover_all_view_filters.hbs";
import render_module_filters from "../templates/hover_module_view_filters.hbs";
import render_revision_trail from "../templates/hover_revision_history.hbs";

function render_feed_controls(): HTMLElement {
    const canvas = globalThis.document.createElement("main");
    canvas.className = "cf-theme storybook-cf-message-items";
    canvas.innerHTML = `${render_all_filters({
        modules: [
            {count: 4, icon_name: "file-text", key: "digest", name: "Conversation Digest"},
            {count: 2, icon_name: "check", key: "decisions", name: "Decisions"},
        ],
        sources: [
            {
                count: 7,
                icon_name: "phone",
                name: "Mentors & Volunteers",
                source_key: "41",
            },
        ],
        space_name: "AIMTO Events",
    })}${render_module_filters({
        module_name: "Conversation Digest",
        space_name: "AIMTO Events",
    })}<div class="storybook-cf-message-items__stage">${render_revision_trail({
        revisions: [
            {
                actor: {full_name: "Priya Shah"},
                field_path: "venue.access_gate",
                new_value_display: '"East gate"',
                previous_value_display: '"South gate"',
                reason: "Confirmed against the final site plan.",
                timestamp: "Aug 14 · 10:30 AM",
            },
            {
                actor: {full_name: "Aisha Rahman"},
                field_path: "delivery.window",
                new_value_display: '"Before 8:30 AM"',
                previous_value_display: '"Morning"',
                reason: "Reconciled with the venue coordinator.",
                timestamp: "Aug 14 · 9:48 AM",
            },
        ],
    })}</div>`;
    canvas.querySelector(".cf-revision-trail")?.setAttribute("open", "");
    canvas.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const button = event.target.closest<HTMLButtonElement>(".cf-feed-filter");
        if (button === null) {
            return;
        }
        const controls = button.closest<HTMLElement>(".cf-feed-controls");
        if (controls === null) {
            return;
        }
        const status = controls.querySelector<HTMLElement>(".cf-feed-controls__status");
        if (status === null) {
            return;
        }

        const selector =
            button.dataset["cfFeedFilter"] === undefined
                ? "[data-cf-feed-history]"
                : "[data-cf-feed-filter]";
        for (const candidate of controls.querySelectorAll<HTMLButtonElement>(selector)) {
            const selected = candidate === button;
            candidate.classList.toggle("cf-feed-filter--selected", selected);
            candidate.setAttribute("aria-pressed", String(selected));
        }

        if (button.dataset["cfFeedFilter"] !== undefined) {
            const label =
                button.querySelector(".cf-feed-filter__label")?.textContent.trim() ?? "All";
            status.textContent =
                button.dataset["cfFeedFilter"] === "all"
                    ? "Showing teammate posts and the latest meaningful state of every enabled Module."
                    : `Showing ${label} updates from the same native Space history.`;
            return;
        }
        status.textContent =
            button.dataset["cfFeedHistory"] === "all"
                ? "Showing the complete chronological Module history, including earlier insight states."
                : "Showing the latest state of each insight. Earlier updates remain in Full history.";
    });
    return canvas;
}

const meta = {
    title: "Cofounder/Patterns/Feed controls",
    parameters: {layout: "fullscreen"},
    render: render_feed_controls,
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const ProductionStates: Story = {};
export const NarrowTouch: Story = {
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
