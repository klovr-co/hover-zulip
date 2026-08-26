import {$} from "jquery";

import * as compose_ui from "./compose_ui.ts";

const formatting_expanded_class = "hover-formatting-expanded";

function toggle_formatting_controls(): void {
    const $messagebox = $("#send_message_form .messagebox");
    const expanded = !$messagebox.hasClass(formatting_expanded_class);

    $messagebox.toggleClass(formatting_expanded_class, expanded);
    $("[data-hover-compose-action='format']").attr("aria-expanded", String(expanded));
}

function insert_mention(): void {
    compose_ui.insert_and_scroll_into_view("@", $("#compose-textarea"));
}

export function initialize(): void {
    const $compose = $("#compose");

    $compose.on("click", "[data-hover-compose-action='format']", (event) => {
        event.preventDefault();
        toggle_formatting_controls();
    });

    $compose.on("click", "[data-hover-compose-action='mention']", (event) => {
        event.preventDefault();
        insert_mention();
    });
}
