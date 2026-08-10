import {$} from "jquery";
import * as z from "zod/mini";

import render_create_hover_space_modal from "../templates/create_hover_space_modal.hbs";
import render_hover_space_setup_modal from "../templates/hover_space_setup_modal.hbs";

import * as channel from "./channel.ts";
import * as channel_folders from "./channel_folders.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as hover_spaces from "./hover_spaces.ts";
import {$t} from "./i18n.ts";
import {realm} from "./state_data.ts";
import * as stream_list from "./stream_list.ts";

const create_space_response_schema = z.object({space: hover_spaces.hover_space_schema});

export function open_create_space(): void {
    const categories = channel_folders
        .get_channel_folders()
        .filter((folder) => !folder.is_archived);
    const modal_content_html = render_create_hover_space_modal({
        categories,
        max_name_length: 60,
        max_description_length: 1024,
    });

    function create_space(): void {
        const category_id = Number.parseInt(
            $<HTMLSelectElement>("#new_hover_space_category").val() ?? "",
            10,
        );
        const data = {
            name: $<HTMLInputElement>("#new_hover_space_name").val()!.trim(),
            description: $<HTMLTextAreaElement>("#new_hover_space_description").val()!.trim(),
            category_id: JSON.stringify(category_id),
        };
        dialog_widget.submit_api_request(channel.post, "/json/hover/spaces", data, {
            success_continuation(response_data) {
                const {space} = create_space_response_schema.parse(response_data);
                hover_spaces.upsert(space);
                stream_list.update_streams_sidebar(true);
            },
        });
    }

    dialog_widget.launch({
        modal_title_text: $t({defaultMessage: "Create Space"}),
        modal_content_html,
        modal_submit_button_text: $t({defaultMessage: "Create in Setup"}),
        form_id: "create_hover_space_form",
        on_click: create_space,
        loading_spinner: true,
        on_shown: () => $("#new_hover_space_name").trigger("focus"),
    });
}

export function open_setup_space(space_id: number): void {
    if (!realm.realm_hover_enabled) {
        return;
    }
    const space = hover_spaces.get_by_id(space_id);
    if (space === undefined || space.state !== "setup") {
        return;
    }
    dialog_widget.launch({
        modal_title_text: $t({defaultMessage: "Space Setup"}),
        modal_content_html: render_hover_space_setup_modal({space}),
        modal_exit_button_text: $t({defaultMessage: "Close"}),
        single_footer_button: true,
        on_click: () => dialog_widget.close(),
    });
}
