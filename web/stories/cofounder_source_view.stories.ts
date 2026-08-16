import type {Meta, StoryObj} from "@storybook/html";
import Handlebars from "handlebars";

import render_source_record from "../templates/hover_source_record.hbs";
import render_source_view from "../templates/hover_source_view.hbs";

type SourceViewArgs = {
    mode: "populated" | "loading" | "retry" | "empty";
};

const records = [
    {
        content: {
            media_description: "The latest venue floor plan, shared for final confirmation.",
            text: "The main entrance is confirmed. Guest signage can move into production.",
            voice_transcript: "Use the east loading bay for deliveries before 8:30 AM.",
        },
        display_time: "9:12 AM",
        id: "record-41",
        media: {
            available: false,
            display_size: "2.0 MB",
            mime_type: "application/pdf",
            type: "document",
        },
        reply_context: {
            excerpt: "Can the venue team confirm the delivery entrance?",
            sender_display_name: "Morgan Lee",
            timestamp: "2026-08-13T08:55:00+08:00",
        },
        sender_display_name: "Aisha Rahman",
        timestamp: "2026-08-13T09:12:00+08:00",
    },
    {
        content: {
            media_description: null,
            text: "Catering has acknowledged the final guest count and dietary notes.",
            voice_transcript: null,
        },
        display_time: "10:04 AM",
        id: "record-42",
        media: null,
        reply_context: null,
        sender_display_name: "Priya Shah",
        timestamp: "2026-08-13T10:04:00+08:00",
    },
];

const older_record = {
    content: {
        media_description: null,
        text: "The first delivery window was reserved with venue operations.",
        voice_transcript: null,
    },
    display_time: "4:28 PM",
    id: "record-40",
    media: null,
    reply_context: null,
    sender_display_name: "Daniel Okafor",
    timestamp: "2026-08-12T16:28:00+08:00",
};

function setup_populated_story(canvas: HTMLElement): void {
    const form = canvas.querySelector<HTMLFormElement>("#cf-source-search-form");
    const search = canvas.querySelector<HTMLInputElement>("#cf-source-search");
    const status = canvas.querySelector<HTMLElement>("#cf-source-view-status");
    const record_list = canvas.querySelector<HTMLElement>("#cf-source-record-list");
    const load_older = canvas.querySelector<HTMLButtonElement>("#cf-source-load-older");
    if (
        form === null ||
        search === null ||
        status === null ||
        record_list === null ||
        load_older === null
    ) {
        return;
    }

    const filter_records = (): void => {
        const query = search.value.trim().replaceAll(/\s+/g, " ").toLocaleLowerCase();
        let visible_count = 0;
        for (const group of record_list.querySelectorAll<HTMLElement>(
            ":scope > .cf-source-view__date-group",
        )) {
            let group_count = 0;
            for (const record of group.querySelectorAll<HTMLElement>(
                ":scope > .cf-source-record",
            )) {
                const visible = record.textContent?.toLocaleLowerCase().includes(query) ?? false;
                record.hidden = !visible;
                if (visible) {
                    group_count += 1;
                    visible_count += 1;
                }
            }
            group.hidden = group_count === 0;
        }
        status.textContent =
            visible_count === 0
                ? "No records match this search."
                : `${visible_count} Source ${visible_count === 1 ? "record" : "records"} shown.`;
    };
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        filter_records();
    });
    search.addEventListener("input", () => {
        status.textContent = "Press Search to update Source records.";
    });
    search.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            filter_records();
        }
    });
    load_older.addEventListener("click", () => {
        const section = globalThis.document.createElement("section");
        section.className = "cf-source-view__date-group";
        const heading = globalThis.document.createElement("h2");
        heading.textContent = "August 12, 2026";
        heading.tabIndex = -1;
        section.append(heading);
        section.insertAdjacentHTML("beforeend", render_source_record(older_record));
        record_list.prepend(section);
        load_older.remove();
        status.textContent = "1 older Source record loaded.";
        heading.focus();
    });
}

function setup_retry_story(canvas: HTMLElement): void {
    const retry = canvas.querySelector<HTMLButtonElement>("#cf-source-retry");
    const status = canvas.querySelector<HTMLElement>("#cf-source-view-status");
    const record_list = canvas.querySelector<HTMLElement>("#cf-source-record-list");
    if (retry === null || status === null || record_list === null) {
        return;
    }

    retry.addEventListener("click", () => {
        const section = globalThis.document.createElement("section");
        section.className = "cf-source-view__date-group";
        const heading = globalThis.document.createElement("h2");
        heading.textContent = "August 13, 2026";
        heading.tabIndex = -1;
        section.append(heading);
        section.insertAdjacentHTML(
            "beforeend",
            records.map((record) => render_source_record(record)).join(""),
        );
        record_list.append(section);
        record_list.setAttribute("aria-busy", "false");
        status.classList.remove("cf-source-view__status--error");
        status.replaceChildren(
            globalThis.document.createTextNode("Source records restored. 2 records shown."),
        );
        retry.remove();
        heading.focus();
    });
}

function setup_empty_story(canvas: HTMLElement): void {
    const form = canvas.querySelector<HTMLFormElement>("#cf-source-search-form");
    const search = canvas.querySelector<HTMLInputElement>("#cf-source-search");
    const message = canvas.querySelector<HTMLElement>(".cf-source-view__status-message");
    const hint = canvas.querySelector<HTMLElement>(".cf-source-view__empty-hint");
    if (form === null || search === null || message === null || hint === null) {
        return;
    }

    const update_empty_result = (): void => {
        const query = search.value.trim().replaceAll(/\s+/g, " ");
        message.textContent = query
            ? `No records match “${query}”.`
            : "This Source has no records in its confirmed history.";
        hint.textContent = query
            ? "Try a different search phrase."
            : "Records will appear here after the connected Source imports confirmed history.";
    };
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        update_empty_result();
    });
    search.addEventListener("input", () => {
        message.textContent = "Press Search to check this Source.";
        hint.textContent = "The current empty-history view remains unchanged until you search.";
    });
    search.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            update_empty_result();
        }
    });
}

function context_for(mode: SourceViewArgs["mode"]): object {
    const base = {
        date_groups: [],
        empty_hint:
            mode === "empty"
                ? "Records will appear here after the connected Source imports confirmed history."
                : "",
        empty_icon: "archive",
        has_error: mode === "retry",
        is_empty: mode === "empty",
        provider_icon: "phone",
        is_loading: mode === "loading",
        query: "",
        show_load_older: false,
        show_retry: false,
        source: {
            account_display_name: "AIMTO conversations",
            display_name: "Venue team",
            is_history_retained: true,
            source_type: "WhatsApp group",
        },
        space_name: "AIMTO Events",
        status: "",
    };
    if (mode === "loading") {
        return {...base, status: "Loading Source records…"};
    }
    if (mode === "retry") {
        return {
            ...base,
            show_retry: true,
            status: "Source records are temporarily unavailable. Try again.",
        };
    }
    if (mode === "empty") {
        return {...base, status: "This Source has no records in its confirmed history."};
    }
    return {
        ...base,
        date_groups: [
            {
                date_label: "August 13, 2026",
                records_html: new Handlebars.SafeString(
                    records.map((record) => render_source_record(record)).join(""),
                ),
            },
        ],
        show_load_older: true,
    };
}

function render_story(args: SourceViewArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme cf-source-view";
    canvas.innerHTML = render_source_view(context_for(args.mode));
    switch (args.mode) {
        case "populated":
            setup_populated_story(canvas);
            break;
        case "retry":
            setup_retry_story(canvas);
            break;
        case "empty":
            setup_empty_story(canvas);
            break;
    }
    return canvas;
}

const meta = {
    title: "Cofounder/Patterns/Source browser",
    parameters: {layout: "fullscreen"},
    args: {mode: "populated"},
    render: render_story,
} satisfies Meta<SourceViewArgs>;

export default meta;
type Story = StoryObj<SourceViewArgs>;

export const Populated: Story = {};
export const Loading: Story = {args: {mode: "loading"}};
export const Retry: Story = {args: {mode: "retry"}};
export const Empty: Story = {args: {mode: "empty"}};
export const NarrowTouch: Story = {
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
