import type {Meta, StoryObj} from "@storybook/html";

import render_global_search from "../templates/hover_search_view.hbs";

type GlobalSearchArgs = {
    mode: "populated" | "searching" | "empty";
};

const knowledge = [
    {
        byline: "Progress Tracker",
        display_time: "Today at 10:32 AM",
        kind_label: "Generated update",
        message_id: 42,
        rendered_content_html:
            "<p>The venue handoff is ready. Signage files and the delivery plan are both confirmed.</p>",
        saved: true,
        space: {id: 3, name: "AIMTO Events"},
        timestamp: "2026-08-14T10:32:00+08:00",
        topic: "Venue operations",
        url: "#venue-handoff",
    },
    {
        byline: "Aisha Rahman",
        display_time: "Yesterday at 4:18 PM",
        kind_label: "Human post",
        message_id: 43,
        rendered_content_html:
            "<p>The east loading bay is available before 8:30 AM. Security has the final supplier list.</p>",
        saved: false,
        space: {id: 3, name: "AIMTO Events"},
        timestamp: "2026-08-13T16:18:00+08:00",
        topic: "Venue operations",
        url: "#loading-bay",
    },
];

const sources = [
    {
        display_time: "Today at 9:12 AM",
        record: {
            content: {
                media_description: null,
                text: "The latest floor plan is approved for guest signage production.",
                voice_transcript: "Use the east loading bay for deliveries before 8:30 AM.",
            },
            sender_display_name: "Morgan Lee",
            timestamp: "2026-08-14T09:12:00+08:00",
        },
        source: {display_name: "Venue team"},
        space: {id: 3, name: "AIMTO Events"},
    },
];

function context_for(mode: GlobalSearchArgs["mode"]): object {
    if (mode === "searching") {
        return {
            has_knowledge: false,
            has_query: true,
            has_sources: false,
            knowledge: [],
            knowledge_count: 0,
            query: "venue handoff",
            searching: true,
            source_count: 0,
            sources: [],
            status: "Searching confirmed Spaces…",
        };
    }
    if (mode === "empty") {
        return {
            has_knowledge: false,
            has_query: true,
            has_sources: false,
            knowledge: [],
            knowledge_count: 0,
            query: "unmatched planning note",
            searching: false,
            source_count: 0,
            sources: [],
            status: "No results found. Try a different name, topic, or phrase.",
        };
    }
    return {
        has_knowledge: true,
        has_query: true,
        has_sources: true,
        knowledge,
        knowledge_count: knowledge.length,
        query: "venue handoff",
        searching: false,
        source_count: sources.length,
        sources,
        status: "",
    };
}

function render_story(args: GlobalSearchArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme cf-global-search";
    canvas.innerHTML = render_global_search(context_for(args.mode));
    canvas.addEventListener("submit", (event) => {
        if (
            !(event.target instanceof HTMLFormElement) ||
            event.target.id !== "cf-global-search-form"
        ) {
            return;
        }
        event.preventDefault();
        const input = canvas.querySelector<HTMLInputElement>("#cf-global-search-input");
        const query = input?.value.trim().replaceAll(/\s+/g, " ") ?? "";
        canvas.innerHTML = render_global_search({
            ...context_for("searching"),
            has_query: query !== "",
            query,
            searching: query !== "",
            status: query === "" ? "" : "Searching confirmed Spaces…",
        });
        canvas
            .querySelector<HTMLElement>(
                query === "" ? "#cf-global-search-input" : ".cf-global-search__status",
            )
            ?.focus();
    });
    canvas.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const button = event.target.closest<HTMLButtonElement>(".cf-global-search__save");
        const label = button?.querySelector<HTMLElement>(".cf-button__label");
        if (button === null || label === null || label === undefined) {
            return;
        }
        const saved = button.getAttribute("aria-pressed") === "true";
        button.setAttribute("aria-pressed", String(!saved));
        label.textContent = saved ? "Save" : "Remove from Saved";
    });
    return canvas;
}

const meta = {
    title: "Cofounder/Patterns/Global search",
    parameters: {layout: "fullscreen"},
    args: {mode: "populated"},
    render: render_story,
} satisfies Meta<GlobalSearchArgs>;

export default meta;
type Story = StoryObj<GlobalSearchArgs>;

export const Populated: Story = {};
export const Searching: Story = {args: {mode: "searching"}};
export const Empty: Story = {args: {mode: "empty"}};
export const NarrowTouch: Story = {
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
