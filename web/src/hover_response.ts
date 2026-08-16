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
    $("#hover-response-controls").prop("hidden", true);
    $("#hover-review-field").val("");
    $("#hover-review-value").val("");
}

export function configure_for_reply(message: Message | undefined): void {
    clear();
    const generated_item = message?.hover_generated_item;
    if (generated_item === undefined || message?.type !== "stream") {
        return;
    }

    generated_item_id = generated_item.id;
    const $field = $("#hover-review-field").empty();
    $field.append(
        $("<option>")
            .val("")
            .text($t({defaultMessage: "Choose a field"})),
    );
    for (const key of Object.keys(generated_item.reviewed_payload).toSorted()) {
        $field.append($("<option>").val(key).text(key.replaceAll("_", " ")));
    }
    $("#hover-response-controls").prop("hidden", false);
    render_type();
}

function render_type(): void {
    $(".hover-response-type__button").each((_index, element) => {
        const selected = $(element).attr("data-hover-response-type") === response_type;
        $(element).toggleClass("selected", selected).attr("aria-checked", String(selected));
    });
    $("[data-hover-reply-help]").prop("hidden", response_type !== "reply");
    $(".hover-review-patch").prop("hidden", response_type !== "review");
}

export function select_response_type(selected: ResponseType): void {
    response_type = selected;
    render_type();
}

export function preselect_review_field(field_path: string): void {
    select_response_type("review");
    $("#hover-review-field").val(field_path);
    $("#hover-review-value").trigger("focus");
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
        const field = String($("#hover-review-field").val() ?? "").trim();
        const value = String($("#hover-review-value").val() ?? "").trim();
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
    $("body").on("click", ".hover-response-type__button", (event) => {
        const selected = $(event.currentTarget).attr("data-hover-response-type");
        if (selected === "reply" || selected === "review") {
            select_response_type(selected);
        }
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
        for (const detail of response.generated_item.disputed_details ?? []) {
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
    if (root_message_ids.size > 0) {
        message_live_update.rerender_messages_view_by_message_ids([...root_message_ids]);
    }
}

export const _testing = {
    get_generated_item_id(): number | undefined {
        return generated_item_id;
    },
};
