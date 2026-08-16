import type {Meta, StoryObj} from "@storybook/html";

import render_todos from "../templates/hover_todos_overlay.hbs";

type TodosArgs = {
    empty: boolean;
};

const todos = [
    {
        assignee: {full_name: "Priya Shah", user_id: 11},
        assignee_label: "Priya Shah",
        assignable_options: [{full_name: "Morgan Lee", user_id: 12}],
        due_label: "August 20, 2026",
        generated_item: {evidence_count: 3, evidence_url: "#sources"},
        id: 73,
        is_active: true,
        is_completed: false,
        latest_event: {
            actor: {full_name: "Aisha Rahman"},
            occurred_at: "August 13, 2026 at 10:18 AM",
        },
        source_hash: "#near/42",
        space: {name: "AIMTO Events"},
        state_label: "Active",
        state_tone: "accent",
        wording: "Publish the reviewed venue plan and confirm the delivery entrance.",
    },
    {
        assignee: {full_name: "Morgan Lee", user_id: 12},
        assignee_label: "Morgan Lee",
        assignable_options: [],
        due_label: "August 13, 2026",
        generated_item: {evidence_count: 0, evidence_url: null},
        id: 74,
        is_active: false,
        is_completed: true,
        latest_event: null,
        source_hash: "#near/43",
        space: {name: "Launch plan"},
        state_label: "Completed",
        state_tone: "success",
        wording: "Confirm the final catering count with the venue team.",
    },
];

function render_story(args: TodosArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "storybook-template-story storybook-todos-story";
    const story_todos = structuredClone(todos);
    const render_overlay = (outcome?: {
        focus: "assignee" | "card";
        status: string;
        todo_id: number;
    }): void => {
        canvas.innerHTML = render_todos({
            empty: args.empty,
            todos: args.empty ? [] : story_todos,
        });
        if (outcome === undefined) {
            return;
        }
        const card = canvas.querySelector<HTMLElement>(
            `[data-cf-todo-id="${CSS.escape(String(outcome.todo_id))}"]`,
        );
        if (card === null) {
            return;
        }
        const status = card.querySelector<HTMLElement>("[data-cf-todo-status]");
        if (status === null) {
            return;
        }
        status.textContent = outcome.status;
        if (outcome.focus === "assignee") {
            card.querySelector<HTMLSelectElement>("[data-cf-todo-assignee]")?.focus();
        } else {
            card.focus();
        }
    };

    canvas.addEventListener("change", (event) => {
        if (!(event.target instanceof HTMLSelectElement)) {
            return;
        }
        const select = event.target.closest<HTMLSelectElement>("[data-cf-todo-assignee]");
        const card = select?.closest<HTMLElement>("[data-cf-todo-id]");
        const assign = card?.querySelector<HTMLButtonElement>('[data-cf-todo-operation="assign"]');
        const status = card?.querySelector<HTMLElement>("[data-cf-todo-status]");
        if (
            select === null ||
            select === undefined ||
            assign === null ||
            assign === undefined ||
            status === null ||
            status === undefined
        ) {
            return;
        }
        assign.disabled = select.value === (select.dataset["cfCurrentAssignee"] ?? "");
        const selected_name = select.selectedOptions[0]?.textContent?.trim() ?? "Unassigned";
        status.textContent = assign.disabled
            ? "Todo assignment is unchanged."
            : `Ready to assign to ${selected_name}.`;
    });

    canvas.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const open = event.target.closest<HTMLButtonElement>("[data-cf-open-todos]");
        if (open !== null) {
            open.remove();
            const overlay = canvas.querySelector<HTMLElement>("#reminders-overlay");
            if (overlay !== null) {
                overlay.hidden = false;
                const focus_target =
                    canvas.querySelector<HTMLElement>(".cf-todo-card") ??
                    canvas.querySelector<HTMLButtonElement>(".cf-todos__close");
                focus_target?.focus();
            }
            return;
        }
        const close = event.target.closest<HTMLButtonElement>(".cf-todos__close");
        if (close !== null) {
            const overlay = canvas.querySelector<HTMLElement>("#reminders-overlay");
            if (overlay !== null) {
                overlay.hidden = true;
                const launcher = globalThis.document.createElement("button");
                launcher.type = "button";
                launcher.className = "cf-button cf-button--primary";
                launcher.dataset["cfOpenTodos"] = "";
                launcher.textContent = "Open Todos";
                canvas.prepend(launcher);
                launcher.focus();
            }
            return;
        }
        const card = event.target.closest<HTMLElement>(".cf-todo-card[data-cf-todo-id]");
        const todo_id = Number(card?.dataset["cfTodoId"]);
        const todo = story_todos.find(({id}) => id === todo_id);
        if (card === null || !Number.isSafeInteger(todo_id) || todo === undefined) {
            return;
        }
        const source = event.target.closest<HTMLAnchorElement>(".cf-todo-card__links > a");
        if (source !== null) {
            event.preventDefault();
            const status = card.querySelector<HTMLElement>("[data-cf-todo-status]");
            if (status !== null) {
                status.textContent = `Opened ${todo.space.name} in its source conversation.`;
                source.focus();
            }
            return;
        }
        const evidence = event.target.closest<HTMLButtonElement>("[data-cf-evidence-url]");
        if (evidence !== null) {
            const status = card.querySelector<HTMLElement>("[data-cf-todo-status]");
            if (status !== null) {
                status.textContent = `Opened ${todo.generated_item.evidence_count} sources for Todo #${todo.id}.`;
                evidence.focus();
            }
            return;
        }
        const operation = event.target.closest<HTMLButtonElement>("[data-cf-todo-operation]");
        const operation_name = operation?.dataset["cfTodoOperation"];
        if (operation === null) {
            return;
        }
        if (operation_name === "assign") {
            const select = card.querySelector<HTMLSelectElement>("[data-cf-todo-assignee]");
            const selected = select?.selectedOptions[0];
            if (operation.disabled || select === null || selected === undefined) {
                return;
            }
            const previous_assignee = todo.assignee;
            const selected_assignee = {
                full_name: selected.textContent?.trim() ?? "Unassigned",
                user_id: Number(selected.value),
            };
            todo.assignee = selected_assignee;
            todo.assignee_label = selected_assignee.full_name;
            todo.assignable_options = [previous_assignee, ...todo.assignable_options].filter(
                (candidate, index, candidates) =>
                    candidate.user_id !== selected_assignee.user_id &&
                    candidates.findIndex(({user_id}) => user_id === candidate.user_id) === index,
            );
            render_overlay({
                focus: "assignee",
                status: `Todo #${todo.id} assigned to ${selected_assignee.full_name}.`,
                todo_id,
            });
            return;
        }
        if (operation_name === "complete") {
            todo.is_active = false;
            todo.is_completed = true;
            todo.state_label = "Completed";
            todo.state_tone = "success";
            render_overlay({
                focus: "card",
                status: `Todo #${todo.id} completed.`,
                todo_id,
            });
            return;
        }
        if (operation_name === "reopen") {
            todo.is_active = true;
            todo.is_completed = false;
            todo.state_label = "Active";
            todo.state_tone = "accent";
            render_overlay({
                focus: "card",
                status: `Todo #${todo.id} reopened.`,
                todo_id,
            });
        }
    });

    render_overlay();
    return canvas;
}

const meta = {
    title: "Cofounder/Workflow/Todos",
    parameters: {layout: "fullscreen"},
    args: {empty: false},
    render: render_story,
} satisfies Meta<TodosArgs>;

export default meta;
type Story = StoryObj<TodosArgs>;

export const Home: Story = {};
export const Empty: Story = {args: {empty: true}};
export const NarrowTouch: Story = {
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
