import {$} from "jquery";

import * as compose_reply from "./compose_reply.ts";
import * as hover_response from "./hover_response.ts";
import * as message_store from "./message_store.ts";

export function initialize(): void {
    // Message-pane clicks stop propagating at #main_div.
    $("#main_div").on("click", ".cf-review-detail__review", (event) => {
        event.preventDefault();
        const $button = $(event.currentTarget);
        const message_id = Number($button.attr("data-cf-review-message-id"));
        const field_path = $button.attr("data-cf-review-field-path");
        const message = message_store.get(message_id);
        if (message === undefined || field_path === undefined) {
            return;
        }
        compose_reply.respond_to_message({
            message_id,
            keep_composebox_empty: true,
            trigger: "hover review request",
        });
        hover_response.preselect_review_field(field_path);
    });
}
