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
        approval_assignable_users: [{full_name: "Morgan Lee", user_id: 12}],
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

function setup_pending_story(canvas: HTMLElement): void {
    const panel = canvas.querySelector<HTMLElement>(".cf-suggested-action");
    const wording = canvas.querySelector<HTMLTextAreaElement>("[data-cf-action-wording]");
    const assignee = canvas.querySelector<HTMLSelectElement>("[data-cf-action-assignee]");
    const due_date = canvas.querySelector<HTMLInputElement>("[data-cf-action-due-date]");
    const reason = canvas.querySelector<HTMLInputElement>("[data-cf-action-reason]");
    const approve = canvas.querySelector<HTMLButtonElement>('[data-cf-action-decision="approve"]');
    const reject = canvas.querySelector<HTMLButtonElement>(
        '[data-cf-action-decision="not_action"]',
    );
    const status = canvas.querySelector<HTMLElement>("[data-cf-action-status]");
    if (
        panel === null ||
        wording === null ||
        assignee === null ||
        due_date === null ||
        reason === null ||
        approve === null ||
        reject === null ||
        status === null
    ) {
        return;
    }

    const current_context = (): object => {
        const selected_assignee = assignee.selectedOptions[0]?.textContent?.trim() ?? "Unassigned";
        const due_label = due_date.value
            ? new Intl.DateTimeFormat("en", {dateStyle: "long"}).format(
                  new Date(`${due_date.value}T00:00:00`),
              )
            : "No due date";
        return {
            due_date: due_label,
            responsibility: selected_assignee,
            todo_assignee: selected_assignee,
            todo_assignable_users: [{full_name: "Morgan Lee", user_id: 12}].filter(
                ({user_id}) => user_id !== Number(assignee.value),
            ),
            todo_has_assignee: assignee.value !== "",
            wording: wording.value.trim(),
        };
    };
    const render_outcome = (mode: "active" | "not_action", outcome: string): void => {
        const latest_reason = reason.value.trim();
        canvas.innerHTML = render_suggested_action({
            ...context_for(mode),
            ...current_context(),
            ...(mode === "not_action" && {latest_reason}),
        });
        const next_panel = canvas.querySelector<HTMLElement>(".cf-suggested-action");
        const next_status = canvas.querySelector<HTMLElement>("[data-cf-action-status]");
        if (next_panel !== null && next_status !== null) {
            next_status.textContent = outcome;
            next_panel.focus();
            if (mode === "active") {
                setup_active_story(canvas);
            } else {
                setup_not_action_story(canvas);
            }
        }
    };
    const validate_wording = (): boolean => {
        const valid = wording.value.trim() !== "";
        approve.disabled = !valid;
        wording.setAttribute("aria-invalid", String(!valid));
        status.textContent = valid
            ? "Changes are ready for review."
            : "Action wording is required.";
        return valid;
    };

    wording.addEventListener("input", validate_wording);
    approve.addEventListener("click", () => {
        if (!validate_wording()) {
            wording.focus();
            return;
        }
        render_outcome("active", "Approved and created Todo #73.");
    });
    reject.addEventListener("click", () => {
        render_outcome("not_action", "Marked as not an action.");
    });
}

function setup_active_story(canvas: HTMLElement): void {
    const select = canvas.querySelector<HTMLSelectElement>("[data-cf-todo-assignee]");
    const assign = canvas.querySelector<HTMLButtonElement>('[data-cf-todo-operation="assign"]');
    const complete = canvas.querySelector<HTMLButtonElement>('[data-cf-todo-operation="complete"]');
    const assignee_label = canvas.querySelector<HTMLElement>("[data-cf-todo-assignee-label]");
    const status = canvas.querySelector<HTMLElement>("[data-cf-todo-status]");
    if (
        select === null ||
        assign === null ||
        complete === null ||
        assignee_label === null ||
        status === null
    ) {
        return;
    }

    let current_assignee = select.value;
    const selected_name = (): string =>
        select.selectedOptions[0]?.textContent?.trim() ?? "Unassigned";
    select.addEventListener("change", () => {
        assign.disabled = select.value === current_assignee;
        status.textContent = assign.disabled
            ? "Todo assignment is unchanged."
            : `Ready to assign Todo #73 to ${selected_name()}.`;
    });
    assign.addEventListener("click", () => {
        current_assignee = select.value;
        select.dataset["cfCurrentAssignee"] = current_assignee;
        assignee_label.textContent = `Assigned to ${selected_name()}`;
        assign.disabled = true;
        status.textContent = `Todo #73 assigned to ${selected_name()}.`;
        select.focus();
    });
    complete.addEventListener("click", () => {
        canvas.innerHTML = render_suggested_action({
            ...context_for("completed"),
            responsibility: selected_name(),
            todo_assignee: selected_name(),
            todo_assignee_user_id: Number(select.value),
        });
        const next_panel = canvas.querySelector<HTMLElement>(".cf-suggested-action");
        const next_status = canvas.querySelector<HTMLElement>("[data-cf-todo-status]");
        if (next_panel !== null && next_status !== null) {
            next_status.textContent = "Todo #73 completed.";
            next_panel.focus();
            setup_completed_story(canvas);
        }
    });
}

function setup_completed_story(canvas: HTMLElement): void {
    const reopen = canvas.querySelector<HTMLButtonElement>('[data-cf-todo-operation="reopen"]');
    if (reopen === null) {
        return;
    }

    reopen.addEventListener("click", () => {
        canvas.innerHTML = render_suggested_action(context_for("active"));
        const next_panel = canvas.querySelector<HTMLElement>(".cf-suggested-action");
        const next_status = canvas.querySelector<HTMLElement>("[data-cf-todo-status]");
        if (next_panel !== null && next_status !== null) {
            next_status.textContent = "Todo #73 reopened.";
            next_panel.focus();
            setup_active_story(canvas);
        }
    });
}

function setup_not_action_story(canvas: HTMLElement): void {
    const restore = canvas.querySelector<HTMLButtonElement>('[data-cf-action-decision="restore"]');
    if (restore === null) {
        return;
    }

    restore.addEventListener("click", () => {
        canvas.innerHTML = render_suggested_action(context_for("pending"));
        const next_panel = canvas.querySelector<HTMLElement>(".cf-suggested-action");
        const next_status = canvas.querySelector<HTMLElement>("[data-cf-action-status]");
        if (next_panel !== null && next_status !== null) {
            next_status.textContent = "Restored for review.";
            next_panel.focus();
            setup_pending_story(canvas);
        }
    });
}

function render_story(args: SuggestedActionArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme cf-workflow-story";
    canvas.innerHTML = render_suggested_action(context_for(args.mode));
    switch (args.mode) {
        case "pending":
            setup_pending_story(canvas);
            break;
        case "active":
            setup_active_story(canvas);
            break;
        case "completed":
            setup_completed_story(canvas);
            break;
        case "not_action":
            setup_not_action_story(canvas);
            break;
    }
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
