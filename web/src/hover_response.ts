import {$} from "jquery";

import {$t} from "./i18n.ts";
import * as message_live_update from "./message_live_update.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";

type ResponseType = "reply" | "review";

let generated_item_id: number | undefined;
let response_type: ResponseType = "reply";

export function clear(): void {
    generated_item_id = undefined;
    response_type = "reply";
    $("#cf-review-composer-controls").prop("hidden", true);
    $("#cf-review-field").val("");
    $("#cf-review-value").val("");
}

export function configure_for_reply(message: Message | undefined): void {
    clear();
    const generated_item = message?.hover_generated_item;
    if (generated_item === undefined || message?.type !== "stream") {
        return;
    }

    generated_item_id = generated_item.id;
    const $field = $("#cf-review-field").empty();
    $field.append(
        $("<option>")
            .val("")
            .text($t({defaultMessage: "Choose a field"})),
    );
    for (const key of Object.keys(generated_item.reviewed_payload).toSorted()) {
        $field.append($("<option>").val(key).text(key.replaceAll("_", " ")));
    }
    $("#cf-review-composer-controls").prop("hidden", false);
    render_type();
}

function render_type(): void {
    $(".cf-review-composer__mode").each((_index, element) => {
        const selected = $(element).attr("data-cf-response-mode") === response_type;
        $(element).attr("aria-checked", String(selected));
        $(element).attr("tabindex", selected ? "0" : "-1");
    });
    $("[data-cf-reply-help]").prop("hidden", response_type !== "reply");
    $("[data-cf-review-patch]").prop("hidden", response_type !== "review");
}

export function select_response_type(selected: ResponseType): void {
    response_type = selected;
    render_type();
}

function keyboard_response_type(current: ResponseType, key: string): ResponseType | undefined {
    if (key === "Home") {
        return "reply";
    }
    if (key === "End") {
        return "review";
    }
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(key)) {
        return current === "reply" ? "review" : "reply";
    }
    return undefined;
}

export function preselect_review_field(field_path: string): void {
    select_response_type("review");
    $("#cf-review-field").val(field_path);
    $("#cf-review-value").trigger("focus");
}

export function get_request_data(): Record<string, number | string> {
    if (generated_item_id === undefined) {
        return {};
    }
    const data: Record<string, number | string> = {
        hover_generated_item_id: generated_item_id,
        hover_response_type: response_type,
    };
    if (response_type === "review") {
        const field = String($("#cf-review-field").val() ?? "").trim();
        const value = String($("#cf-review-value").val() ?? "").trim();
        if (field) {
            data["hover_review_field"] = field;
        }
        if (value) {
            data["hover_review_value"] = value;
        }
    }
    return data;
}

export function initialize(): void {
    $("body").on("click", ".cf-review-composer__mode", (event) => {
        const selected = $(event.currentTarget).attr("data-cf-response-mode");
        if (selected === "reply" || selected === "review") {
            select_response_type(selected);
        }
    });
    $("body").on("keydown", ".cf-review-composer__mode", (event) => {
        const current = $(event.currentTarget).attr("data-cf-response-mode");
        if (current !== "reply" && current !== "review") {
            return;
        }
        const selected = keyboard_response_type(current, event.key);
        if (selected === undefined) {
            return;
        }
        event.preventDefault();
        select_response_type(selected);
        $(`.cf-review-composer__mode[data-cf-response-mode="${selected}"]`).trigger("focus");
    });
}

export function apply_realtime_responses(messages: Message[]): void {
    const root_message_ids = new Set<number>();
    for (const message of messages) {
        const response = message.hover_response;
        if (response === undefined) {
            continue;
        }
        const root = message_store.get(response.root_message_id);
        if (root === undefined) {
            continue;
        }
        root.hover_generated_item = response.generated_item;
        root_message_ids.add(root.id);
        const disputed_details = response.generated_item.disputed_details ?? [];
        for (const detail of disputed_details) {
            const request_metadata = detail.review_request;
            if (request_metadata === null) {
                continue;
            }
            const request_message = message_store.get(request_metadata.message_id);
            if (request_message?.hover_review_request === undefined) {
                continue;
            }
            request_message.hover_review_request.generated_item = response.generated_item;
            request_message.hover_review_request.state = request_metadata.state;
            root_message_ids.add(request_message.id);
        }
    }
    if (root_message_ids.size === 0) {
        return;
    }
    message_live_update.rerender_messages_view_by_message_ids([...root_message_ids]);
}

export const _testing = {
    keyboard_response_type,
    get_generated_item_id(): number | undefined {
        return generated_item_id;
    },
};
