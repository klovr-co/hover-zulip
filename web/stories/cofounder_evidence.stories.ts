import type {Meta, StoryObj} from "@storybook/html";

import render_evidence from "../templates/hover_evidence_modal.hbs";

type EvidenceArgs = {
    state: "loading" | "results" | "retryable" | "missing" | "empty";
};

const evidence = [
    {
        content: {
            media_description: null,
            text: "The release owner confirmed that the notes are ready for final review.",
            voice_transcript: null,
        },
        display_timestamp: "Aug 13, 2026, 10:28 AM",
        media: null,
        sender: {display_name: "Ava Rodriguez"},
        timestamp: "2026-08-13T10:28:00+08:00",
    },
    {
        content: {
            media_description: "Screenshot of the approved launch checklist.",
            text: null,
            voice_transcript: null,
        },
        display_timestamp: "Aug 13, 2026, 10:30 AM",
        media: {available: true, type: "image"},
        sender: {display_name: "Hover Bot"},
        timestamp: "2026-08-13T10:30:00+08:00",
    },
];

function context_for(state: EvidenceArgs["state"]): object {
    if (state === "loading") {
        return {loading: true};
    }
    if (state === "retryable") {
        return {error: true, evidence_url: "#retry", retryable: true};
    }
    if (state === "missing") {
        return {error: true, retryable: false};
    }
    if (state === "empty") {
        return {empty: true};
    }
    return {evidence};
}

function render_story(args: EvidenceArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme storybook-component";
    canvas.innerHTML = `<div class="storybook-component-stack storybook-component-stack-vertical" style="max-width:720px">${render_evidence(context_for(args.state))}</div>`;
    canvas.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const retry_button = event.target.closest<HTMLElement>("[data-cf-evidence-retry-url]");
        const stack = canvas.querySelector<HTMLElement>(".storybook-component-stack");
        if (retry_button === null || stack === null) {
            return;
        }
        event.preventDefault();
        stack.innerHTML = render_evidence(context_for("loading"));
        stack.querySelector<HTMLElement>("[data-cf-evidence-result]")?.focus();
    });
    return canvas;
}

const meta = {
    title: "Cofounder/Patterns/Evidence",
    parameters: {layout: "padded"},
    args: {state: "results"},
    render: render_story,
} satisfies Meta<EvidenceArgs>;

export default meta;
type Story = StoryObj<EvidenceArgs>;

export const Results: Story = {};
export const Loading: Story = {args: {state: "loading"}};
export const RetryableError: Story = {args: {state: "retryable"}};
export const Missing: Story = {args: {state: "missing"}};
export const Empty: Story = {args: {state: "empty"}};
