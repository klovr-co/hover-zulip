import type {Meta, StoryObj} from "@storybook/html";

import render_editions from "../templates/hover_editions_view.hbs";

type EditionsArgs = {
    mode: "all" | "focus" | "loading" | "retry" | "empty";
};

const items = [
    {
        detail: "The launch notes are ready for final review, with the remaining assumptions clearly marked for the owners.",
        title: "Launch notes moved into final review",
        update: {
            evidence_url: "#sources",
            space_name: "Product",
            topic: "Launch plan",
            url: "#update-41",
        },
    },
    {
        detail: "The onboarding checklist now uses the approved Cofounder controls and can move into the next release.",
        title: "Component migration was approved",
        update: {
            evidence_url: null,
            space_name: "Design",
            topic: "Component migration",
            url: "#update-42",
        },
    },
];

const sections = [
    {has_items: true, items: [items[0]], key: "urgency", label: "A good place to start"},
    {has_items: true, items: [items[1]], key: "guidance", label: "Suggested next step"},
];

function context_for(mode: EditionsArgs["mode"]): object {
    const base = {
        active_panel_id: "cf-edition-panel-morning",
        active_tab_id: "cf-edition-tab-morning",
        all_mode: false,
        can_go_next: false,
        can_go_previous: false,
        current_slide: null,
        display_date: "August 13, 2026",
        edition: null,
        edition_marker: "Morning",
        end_of_day_aria_selected: "false",
        end_of_day_tabindex: "-1",
        focus_mode: false,
        has_items: false,
        inactive_panel_id: "cf-edition-panel-end-of-day",
        inactive_tab_id: "cf-edition-tab-end-of-day",
        loading: false,
        morning_aria_selected: "true",
        morning_tabindex: "0",
        selected_morning: true,
        sections: [],
        show_retry: false,
        slide_count: 0,
        slide_number: 0,
        status: "",
    };
    if (mode === "loading") {
        return {...base, loading: true, status: "Preparing your latest edition…"};
    }
    if (mode === "retry") {
        return {...base, show_retry: true, status: "Your edition could not be loaded."};
    }
    const edition = {
        all_clear: mode !== "empty",
        covered_end: "2026-08-13T10:32:00+08:00",
        title: "What deserves your attention today",
    };
    if (mode === "focus") {
        return {
            ...base,
            can_go_next: true,
            can_go_previous: false,
            current_slide: {...items[0], section_label: "A good place to start"},
            edition,
            focus_mode: true,
            slide_count: 2,
            slide_number: 1,
        };
    }
    return {
        ...base,
        all_mode: true,
        edition,
        has_items: mode !== "empty",
        sections: mode === "empty" ? [] : sections,
    };
}

function render_story(args: EditionsArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme cf-editions-view";
    canvas.innerHTML = render_editions(context_for(args.mode));
    return canvas;
}

const meta = {
    title: "Cofounder/Patterns/Editions",
    parameters: {layout: "fullscreen"},
    args: {mode: "all"},
    render: render_story,
} satisfies Meta<EditionsArgs>;

export default meta;
type Story = StoryObj<EditionsArgs>;

export const FullEdition: Story = {};
export const FocusView: Story = {args: {mode: "focus"}};
export const Loading: Story = {args: {mode: "loading"}};
export const Retry: Story = {args: {mode: "retry"}};
export const Empty: Story = {args: {mode: "empty"}};
export const NarrowTouch: Story = {
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
