import {$} from "jquery";

import render_hover_todos_overlay from "../templates/hover_todos_overlay.hbs";

import * as browser_history from "./browser_history.ts";
import * as hover_todos from "./hover_todos.ts";
import {$t} from "./i18n.ts";
import type {HoverTodo} from "./message_store.ts";
import * as overlays from "./overlays.ts";

type TodoRenderContext = HoverTodo & {
    is_active: boolean;
    is_completed: boolean;
    due_label: string;
    assignee_label: string;
    assignable_options: {user_id: number; full_name: string}[];
    source_hash: string;
    latest_event?: HoverTodo["recent_events"][number];
};

function format(todo: HoverTodo): TodoRenderContext {
    return {
        ...todo,
        is_active: todo.state === "active",
        is_completed: todo.state === "completed",
        due_label: todo.due_date ?? $t({defaultMessage: "No due date"}),
        assignee_label: todo.assignee?.full_name ?? $t({defaultMessage: "Unassigned"}),
        assignable_options: todo.assignable_users.filter(
            (user) => user.user_id !== todo.assignee?.user_id,
        ),
        source_hash: `#near/${todo.generated_item.message_id}`,
        ...(todo.recent_events[0] !== undefined && {latest_event: todo.recent_events[0]}),
    };
}

function render(): string {
    const todos = hover_todos.sorted().map((todo) => format(todo));
    return render_hover_todos_overlay({todos, empty: todos.length === 0});
}

export function launch(): void {
    const rendered_todos_overlay = render();
    $("#reminders-overlay-container").html(rendered_todos_overlay);
    overlays.open_overlay({
        name: "reminders",
        $overlay: $("#reminders-overlay"),
        on_close() {
            browser_history.exit_overlay();
        },
    });
    $("#reminders-overlay .hover-todo-card").first().trigger("focus");
}

export function rerender(): void {
    if (!overlays.reminders_open() || $("#reminders-overlay").attr("data-hover-todos") !== "true") {
        return;
    }
    const $active_element = document.activeElement === null ? $() : $(document.activeElement);
    const focused_id = $active_element.closest("[data-hover-todo-id]").attr("data-hover-todo-id");
    const rendered_todos_overlay = render();
    $("#reminders-overlay-container").html(rendered_todos_overlay);
    if (focused_id !== undefined) {
        $(`#reminders-overlay [data-hover-todo-id='${CSS.escape(focused_id)}']`).trigger("focus");
    }
}

export function initialize(): void {
    $("body").on("hover_todos_changed", rerender);
}
