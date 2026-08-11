import {$} from "jquery";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import * as message_live_update from "./message_live_update.ts";
import * as message_store from "./message_store.ts";
import {type HoverTodo, hover_todo_schema} from "./message_store.ts";

const list_response_schema = z.object({todos: z.array(hover_todo_schema)});
const mutation_response_schema = z.object({changed: z.boolean(), todo: hover_todo_schema});
const conflict_schema = z.object({todo: hover_todo_schema});

export const todos = new Map<number, HoverTodo>();
const request_ids = new Map<number, string>();

function announce_change(): void {
    $("body").trigger("hover_todos_changed");
}

export function apply_projection(todo: HoverTodo): boolean {
    const current = todos.get(todo.id);
    const message = message_store.get(todo.generated_item.message_id);
    const action = message?.hover_generated_item?.suggested_action;
    const embedded = action?.todo?.id === todo.id ? action.todo : undefined;
    if (
        (current !== undefined && todo.version < current.version) ||
        (embedded !== undefined && todo.version < embedded.version)
    ) {
        return false;
    }
    todos.set(todo.id, todo);
    request_ids.delete(todo.id);
    if (
        action !== null &&
        action !== undefined &&
        message.hover_generated_item?.id === todo.generated_item.id &&
        (action.todo === null || action.todo.id === todo.id)
    ) {
        action.todo = todo;
        message_live_update.rerender_messages_view_by_message_ids([todo.generated_item.message_id]);
    }
    announce_change();
    return true;
}

export function get_count(): number {
    return [...todos.values()].filter((todo) => todo.state === "active").length;
}

export function sorted(): HoverTodo[] {
    return [...todos.values()].sort((left, right) => {
        if (left.state !== right.state) {
            return left.state === "active" ? -1 : 1;
        }
        return (left.due_date ?? "9999-12-31").localeCompare(right.due_date ?? "9999-12-31");
    });
}

export function submit(todo_id: number, operation: "assign" | "complete" | "reopen"): void {
    const todo = todos.get(todo_id);
    if (todo === undefined) {
        return;
    }
    const request_id = request_ids.get(todo_id) ?? crypto.randomUUID();
    request_ids.set(todo_id, request_id);
    const $containers = $(`[data-hover-todo-id='${todo_id}']`);
    $containers.find("button, select").prop("disabled", true);
    $containers.find("[data-hover-todo-status]").text($t({defaultMessage: "Saving…"}));
    const assignee_user_id =
        operation === "assign"
            ? $containers.first().find<HTMLSelectElement>("[data-hover-todo-assignee]").val()
            : undefined;
    void channel.post({
        url: `/json/hover/spaces/${todo.space.id}/todos/${todo.id}/events`,
        data: {
            operation,
            request_id,
            expected_version: todo.version,
            ...(assignee_user_id !== undefined && assignee_user_id !== "" && {assignee_user_id}),
        },
        success(raw_data) {
            apply_projection(mutation_response_schema.parse(raw_data).todo);
            $(`[data-hover-todo-id='${todo_id}']`).first().trigger("focus");
        },
        error(xhr) {
            const conflict = conflict_schema.safeParse(xhr.responseJSON);
            if (xhr.status === 409 && conflict.success) {
                apply_projection(conflict.data.todo);
                request_ids.delete(todo_id);
                return;
            }
            $containers.find("button, select").prop("disabled", false);
            $containers
                .find("[data-hover-todo-status]")
                .text($t({defaultMessage: "Could not save. Try again."}));
        },
    });
}

export function initialize(): void {
    void channel.get({
        url: "/json/hover/todos",
        success(raw_data) {
            const response = list_response_schema.parse(raw_data);
            for (const todo of response.todos) {
                apply_projection(todo);
            }
            announce_change();
        },
    });
    $("body").on("click", "[data-hover-todo-operation]", (event) => {
        const $button = $(event.currentTarget);
        const todo_id = Number($button.attr("data-hover-todo-id"));
        const operation = $button.attr("data-hover-todo-operation");
        if (
            Number.isSafeInteger(todo_id) &&
            (operation === "assign" || operation === "complete" || operation === "reopen")
        ) {
            submit(todo_id, operation);
        }
    });
}

export const event_schema = z.object({
    id: z.number(),
    type: z.literal("hover_todo"),
    message_id: z.number(),
    todo: hover_todo_schema,
});

export const _testing = {request_ids};
