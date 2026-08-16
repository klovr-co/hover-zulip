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

const slides = [
    {...items[0], section_label: "A good place to start"},
    {...items[1], section_label: "Suggested next step"},
];

function context_for(mode: EditionsArgs["mode"], selected_morning = true, slide_index = 0): object {
    const selected_edition = selected_morning ? "morning" : "end-of-day";
    const inactive_edition = selected_morning ? "end-of-day" : "morning";
    const base = {
        active_panel_id: `cf-edition-panel-${selected_edition}`,
        active_tab_id: `cf-edition-tab-${selected_edition}`,
        all_mode: false,
        can_go_next: false,
        can_go_previous: false,
        current_slide: null,
        display_date: "August 13, 2026",
        edition: null,
        edition_marker: selected_morning ? "Morning" : "End of day",
        end_of_day_aria_selected: selected_morning ? "false" : "true",
        end_of_day_tabindex: selected_morning ? "-1" : "0",
        focus_mode: false,
        has_items: false,
        inactive_panel_id: `cf-edition-panel-${inactive_edition}`,
        inactive_tab_id: `cf-edition-tab-${inactive_edition}`,
        loading: false,
        morning_aria_selected: selected_morning ? "true" : "false",
        morning_tabindex: selected_morning ? "0" : "-1",
        panel_aria_busy: mode === "loading" ? "true" : "false",
        selected_morning,
        sections: [],
        show_retry: false,
        slide_count: 0,
        slide_number: 0,
        status: "",
        status_aria_live: mode === "retry" ? "assertive" : "polite",
        status_class:
            mode === "retry" ? "cf-edition-status cf-edition-status--error" : "cf-edition-status",
        status_role: mode === "retry" ? "alert" : "status",
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
            can_go_next: slide_index < slides.length - 1,
            can_go_previous: slide_index > 0,
            current_slide: slides[slide_index],
            edition,
            focus_mode: true,
            slide_count: 2,
            slide_number: slide_index + 1,
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
    let mode = args.mode;
    let selected_morning = true;
    let slide_index = 0;

    function render(focus_selector?: string): void {
        canvas.innerHTML = render_editions(context_for(mode, selected_morning, slide_index));

        if (focus_selector) {
            canvas.querySelector<HTMLElement>(focus_selector)?.focus();
        }
    }

    canvas.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const button = event.target.closest<HTMLButtonElement>("button");
        if (!button) {
            return;
        }
        if (button.matches(".cf-edition-tab")) {
            selected_morning = button.dataset["edition"] === "morning";
            slide_index = 0;
            render(`#${button.id}`);
            return;
        }
        switch (button.id) {
            case "cf-edition-focus-view": {
                mode = "focus";
                slide_index = 0;
                render(".cf-edition-carousel");
                break;
            }
            case "cf-edition-view-all": {
                mode = "all";
                render("#cf-edition-focus-view");
                break;
            }
            case "cf-edition-previous": {
                slide_index = Math.max(0, slide_index - 1);
                render(".cf-edition-carousel");
                break;
            }
            case "cf-edition-next": {
                slide_index = Math.min(slides.length - 1, slide_index + 1);
                render(".cf-edition-carousel");
                break;
            }
            case "cf-edition-retry": {
                mode = "loading";
                render(".cf-edition-status");
                break;
            }
        }
    });
    canvas.addEventListener("keydown", (event) => {
        if (
            event.target instanceof Element &&
            event.target.matches(".cf-edition-carousel") &&
            ["ArrowLeft", "ArrowRight"].includes(event.key)
        ) {
            event.preventDefault();
            slide_index = Math.max(
                0,
                Math.min(slides.length - 1, slide_index + (event.key === "ArrowLeft" ? -1 : 1)),
            );
            render(".cf-edition-carousel");
            return;
        }
        if (
            !(event.target instanceof Element) ||
            !event.target.matches(".cf-edition-tab") ||
            !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
        ) {
            return;
        }
        event.preventDefault();
        selected_morning =
            event.key === "Home" ? true : event.key === "End" ? false : !selected_morning;
        slide_index = 0;
        render(selected_morning ? "#cf-edition-tab-morning" : "#cf-edition-tab-end-of-day");
    });

    render();
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
