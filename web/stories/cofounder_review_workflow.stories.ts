import type {Meta, StoryObj} from "@storybook/html";

import render_single_message from "../templates/single_message.hbs";

type ReviewWorkflowArgs = {
    narrow: boolean;
    resolved: boolean;
};

const avatar = `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72"><rect width="72" height="72" rx="14" fill="#57745d"/><text x="36" y="39" text-anchor="middle" dominant-baseline="middle" fill="white" font-family="system-ui" font-size="24" font-weight="650">HB</text></svg>`)}`;

function render_review_workflow(args: ReviewWorkflowArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = `cf-theme storybook-cf-message-items${args.narrow ? " storybook-cf-message-items--narrow" : ""}`;
    const state_label = args.resolved ? "Reviewed" : "Needs review";
    const state_tone = args.resolved ? "success" : "warning";
    canvas.innerHTML = `
        <header class="storybook-cf-message-items__header">
            <div>
                <p>COFOUNDER / WORKFLOW</p>
                <h2>Review request</h2>
                <span>Conflicting evidence, assignment, and resolution in the production message row.</span>
            </div>
            <strong>${args.narrow ? "390 px" : args.resolved ? "Resolved" : "Open"}</strong>
        </header>
        <main class="storybook-cf-message-items__stage">
            <div class="message-list storybook-cf-message-items__stack" role="list">
                ${render_single_message({
                    has_hover_disputed_details: true,
                    has_hover_revisions: false,
                    has_hover_source_integrations: false,
                    hover_has_history: false,
                    hover_history_count: 0,
                    hover_importance: "high",
                    hover_importance_tone: "danger",
                    hover_is_earlier: false,
                    hover_module_name: "Operations brief",
                    hover_output_label: "Venue plan",
                    hover_source_context: "Across 3 sources",
                    hover_state: args.resolved ? "reviewed" : "needs review",
                    hover_state_tone: args.resolved ? "success" : "warning",
                    hover_disputed_details: [
                        {
                            evidence_count: 2,
                            evidence_url: "#conflicting-sources",
                            field_label: "delivery entrance",
                            field_path: "delivery_entrance",
                            resolution_label: args.resolved ? "Reviewed by Priya Shah" : undefined,
                            show_review_action: !args.resolved,
                            state_label,
                            state_tone,
                            summary:
                                "The venue plan names the east entrance, while the coordinator confirmed loading through the south gate.",
                            target_label: args.resolved ? undefined : "Review requested from you",
                        },
                        {
                            evidence_count: 1,
                            evidence_url: "#uncertain-source",
                            field_label: "arrival time",
                            field_path: "arrival_time",
                            resolution_label: undefined,
                            show_review_action: false,
                            state_label: "Uncertain",
                            state_tone: "neutral",
                            summary:
                                "The latest source confirms the day but does not include an arrival time.",
                            target_label: undefined,
                        },
                    ],
                    hover_response_clarification_required: !args.resolved,
                    hover_review_request_state_label: args.resolved ? "Resolved" : "Open",
                    hover_review_request_state_tone: state_tone,
                    include_sender: true,
                    is_hidden: false,
                    is_hover_generated_update: true,
                    is_hover_response: true,
                    is_hover_review: true,
                    is_hover_review_request: true,
                    is_hover_suggested_action: false,
                    message_list_id: 1,
                    sender_is_bot: true,
                    small_avatar_url: avatar,
                    timestr: "10:38 AM",
                    msg: {
                        content:
                            "<p>The venue plan is ready, but two operational details still need a human decision.</p>",
                        failed_request: false,
                        id: 42,
                        is_stream: true,
                        locally_echoed: false,
                        message_reactions: [],
                        reminders: [],
                        sender_full_name: "Hover Bot",
                        sender_id: 10,
                        sent_by_me: false,
                        starred: false,
                        unread: !args.resolved,
                        url: "#message-42",
                    },
                })}
            </div>
        </main>`;
    return canvas;
}

const meta = {
    title: "Cofounder/Workflow/Review requests",
    parameters: {layout: "fullscreen"},
    args: {narrow: false, resolved: false},
    render: render_review_workflow,
} satisfies Meta<ReviewWorkflowArgs>;

export default meta;
type Story = StoryObj<ReviewWorkflowArgs>;

export const Open: Story = {};
export const Resolved: Story = {args: {resolved: true}};
export const NarrowTouch: Story = {args: {narrow: true}};
