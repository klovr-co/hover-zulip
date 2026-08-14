import type {Meta, StoryObj} from "@storybook/html";

import render_suggested_action from "../templates/hover_suggested_action.hbs";

type SuggestedActionArgs = {
    mode: "pending" | "active" | "completed" | "not_action";
};

function context_for(mode: SuggestedActionArgs["mode"]): object {
    const is_pending = mode === "pending";
    const is_approved = mode === "active" || mode === "completed";
    const is_not_action = mode === "not_action";
    return {
        approval_assignable_users: [
            {full_name: "Priya Shah", user_id: 11},
            {full_name: "Morgan Lee", user_id: 12},
        ],
        approval_assignee_user_id: 11,
        approval_due_date: "2026-08-20",
        approval_has_assignee: true,
        due_date: "August 20, 2026",
        is_approved,
        is_not_action,
        is_pending,
        latest_actor: "Aisha Rahman",
        latest_reason: "This is already covered by the launch checklist.",
        latest_time: "August 13, 2026 at 10:18 AM",
        message_id: 42,
        responsibility: "Priya Shah",
        state_label: is_pending
            ? "Awaiting confirmation"
            : is_not_action
              ? "Not an action"
              : mode === "completed"
                ? "Completed Todo"
                : "Active Todo",
        state_tone: is_pending
            ? "warning"
            : is_not_action
              ? "neutral"
              : mode === "completed"
                ? "success"
                : "accent",
        todo_assignee: "Priya Shah",
        todo_assignee_user_id: 11,
        todo_assignable_users: [{full_name: "Morgan Lee", user_id: 12}],
        todo_has_assignee: true,
        todo_id: 73,
        todo_is_active: mode === "active",
        todo_is_completed: mode === "completed",
        todo_latest_actor: "Priya Shah",
        todo_latest_time: "August 13, 2026 at 10:32 AM",
        wording: "Publish the reviewed venue plan and confirm the delivery entrance.",
    };
}

function render_story(args: SuggestedActionArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme cf-workflow-story";
    canvas.innerHTML = render_suggested_action(context_for(args.mode));
    return canvas;
}

const meta = {
    title: "Cofounder/Workflow/Suggested action",
    args: {mode: "pending"},
    render: render_story,
} satisfies Meta<SuggestedActionArgs>;

export default meta;
type Story = StoryObj<SuggestedActionArgs>;

export const Pending: Story = {};
export const ActiveTodo: Story = {args: {mode: "active"}};
export const CompletedTodo: Story = {args: {mode: "completed"}};
export const NotAnAction: Story = {args: {mode: "not_action"}};
export const NarrowTouch: Story = {
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
