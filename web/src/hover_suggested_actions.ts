import {$} from "jquery";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import * as hover_request_id from "./hover_request_id.ts";
import * as hover_spaces from "./hover_spaces.ts";
import * as hover_todos from "./hover_todos.ts";
import {$t} from "./i18n.ts";
import * as message_live_update from "./message_live_update.ts";
import * as message_store from "./message_store.ts";
import {
    type HoverGeneratedItem,
    hover_generated_item_schema,
    hover_suggested_action_schema,
} from "./message_store.ts";

type Decision = "approve" | "not_action" | "restore";

const response_schema = z.object({
    changed: z.boolean(),
    suggested_action: hover_suggested_action_schema,
});
const conflict_schema = z.object({suggested_action: hover_suggested_action_schema});

const request_ids = new Map<number, string>();

export function apply_projection(message_id: number, generated_item: HoverGeneratedItem): boolean {
    const message = message_store.get(message_id);
    const incoming = generated_item.suggested_action;
    const current = message?.hover_generated_item?.suggested_action;
    if (
        message === undefined ||
        incoming === null ||
        (current !== null && current !== undefined && incoming.version < current.version)
    ) {
        return false;
    }
    message.hover_generated_item = generated_item;
    if (incoming.todo !== null) {
        hover_todos.apply_projection(incoming.todo);
    }
    request_ids.delete(message_id);
    message_live_update.rerender_messages_view_by_message_ids([message_id]);
    return true;
}

function submit(message_id: number, decision: Decision): void {
    const message = message_store.get(message_id);
    const item = message?.hover_generated_item;
    const action = item?.suggested_action;
    if (
        message?.type !== "stream" ||
        item === undefined ||
        action === null ||
        action === undefined
    ) {
        return;
    }
    const space = hover_spaces.get_by_stream_id(message.stream_id);
    if (space === undefined) {
        return;
    }
    const request_id = request_ids.get(message_id) ?? hover_request_id.generate();
    request_ids.set(message_id, request_id);
    const $panel = $(`[data-cf-suggested-action-message-id='${message_id}']`);
    $panel.find("button").prop("disabled", true);
    $panel.find("[data-cf-action-status]").text($t({defaultMessage: "Saving…"}));
    const reason =
        decision === "not_action"
            ? ($panel.find<HTMLInputElement>("[data-cf-action-reason]").val() ?? "").trim()
            : null;
    const data: Record<string, number | string | null> = {
        decision,
        request_id,
        expected_version: action.version,
        reason,
    };
    if (decision === "approve") {
        data["wording"] = $panel.find<HTMLTextAreaElement>("[data-cf-action-wording]").val() ?? "";
        data["assignee_user_id"] = String(
            $panel.find<HTMLSelectElement>("[data-cf-action-assignee]").val() ?? "",
        );
        data["due_date"] = $panel.find<HTMLInputElement>("[data-cf-action-due-date]").val() ?? "";
    }
    void channel.post({
        url: `/json/hover/spaces/${space.id}/generated-items/${item.id}/suggested-action/decisions`,
        data,
        success(raw_data) {
            const response = response_schema.parse(raw_data);
            apply_projection(message_id, {...item, suggested_action: response.suggested_action});
            $(`[data-cf-suggested-action-message-id='${message_id}']`).trigger("focus");
        },
        error(xhr) {
            const conflict = conflict_schema.safeParse(xhr.responseJSON);
            if (xhr.status === 409 && conflict.success) {
                apply_projection(message_id, {
                    ...item,
                    suggested_action: conflict.data.suggested_action,
                });
                request_ids.delete(message_id);
            } else {
                $panel.find("button").prop("disabled", false);
                $panel
                    .find("[data-cf-action-status]")
                    .text($t({defaultMessage: "Could not save. Try again."}));
            }
        },
    });
}

export function initialize(): void {
    // Message-pane clicks stop propagating at #main_div, so handlers for
    // controls rendered inside a message must be delegated from that root.
    $("#main_div").on("click", "[data-cf-action-decision]", (event) => {
        event.stopPropagation();
        const $button = $(event.currentTarget);
        const message_id = Number($button.attr("data-cf-message-id"));
        const decision = $button.attr("data-cf-action-decision");
        if (
            Number.isSafeInteger(message_id) &&
            (decision === "approve" || decision === "not_action" || decision === "restore")
        ) {
            submit(message_id, decision);
        }
    });
}

export const event_schema = z.object({
    id: z.number(),
    type: z.literal("hover_suggested_action"),
    message_id: z.number(),
    generated_item: hover_generated_item_schema,
});

export const _testing = {request_ids, submit};
