import type {Meta, StoryObj} from "@storybook/html";

import render_awareness_view from "../templates/hover_awareness_view.hbs";

type AwarenessArgs = {
    retry: boolean;
};

const avatar = (initials: string, color: string): string =>
    `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="108" height="108"><rect width="108" height="108" rx="18" fill="${color}"/><text x="54" y="59" text-anchor="middle" dominant-baseline="middle" fill="white" font-family="system-ui" font-size="34" font-weight="650">${initials}</text></svg>`)}`;

const items = [
    {
        avatar_url: avatar("AR", "#3768a6"),
        card_class: "cf-awareness-card cf-awareness-card--generated cf-awareness-card--unread",
        display_time: "Today at 10:32 AM",
        evidence_url: "#sources",
        has_history: true,
        has_reasons: true,
        history_count: 3,
        history_url: "#history",
        importance: "high",
        importance_tone: "danger",
        is_unread: true,
        message_id: 41,
        message_url: "#update-41",
        output_label: "Progress update",
        reason_labels: ["Mentioned you", "Review requested"],
        rendered_content:
            "<p>The launch notes are ready for a final pass before we share them with the team.</p>",
        reviewed_summary: "Final wording confirmed by the launch owners.",
        sender_name: "Ava Rodriguez",
        source_summary: "From project updates",
        sources: [],
        space_name: "Product",
        timestamp: "2026-08-13T10:32:00+08:00",
        todo_due_date: "Friday",
        todo_status: "Active",
        topic: "Launch plan",
    },
    {
        avatar_url: avatar("HB", "#57745d"),
        card_class: "cf-awareness-card cf-awareness-card--generated",
        display_time: "Yesterday at 4:18 PM",
        evidence_url: "#sources",
        has_history: false,
        has_reasons: true,
        history_count: 1,
        history_url: "#history",
        importance: "normal",
        is_unread: false,
        message_id: 42,
        message_url: "#update-42",
        output_label: "Decision",
        reason_labels: ["You own this"],
        rendered_content:
            "<p>The onboarding checklist now uses the approved Cofounder components.</p>",
        reviewed_summary: "Migration approved for the next release.",
        sender_name: "Hover Bot",
        source_summary: "From design review",
        sources: [],
        space_name: "Design",
        timestamp: "2026-08-12T16:18:00+08:00",
        todo_due_date: undefined,
        todo_status: undefined,
        topic: "Component migration",
    },
];

function render_awareness(args: AwarenessArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme cf-awareness-view";
    canvas.innerHTML = render_awareness_view({
        has_items: !args.retry,
        items: args.retry ? [] : items,
        show_retry: args.retry,
        status: args.retry ? "Live awareness could not be loaded." : "",
        title: "For You",
    });
    return canvas;
}

const meta = {
    title: "Cofounder/Patterns/Awareness",
    parameters: {layout: "fullscreen"},
    args: {retry: false},
    render: render_awareness,
} satisfies Meta<AwarenessArgs>;

export default meta;
type Story = StoryObj<AwarenessArgs>;

export const ForYou: Story = {};

export const NarrowTouch: Story = {
    parameters: {
        viewport: {defaultViewport: "mobile1"},
    },
};

export const RetryState: Story = {
    args: {retry: true},
};
