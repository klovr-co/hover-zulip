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

function context_for(mode: SourceViewArgs["mode"]): object {
    const base = {
        date_groups: [],
        provider_icon: "phone",
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
        return {...base, status: "No records match this search."};
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
