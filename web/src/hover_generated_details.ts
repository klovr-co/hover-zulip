import {$} from "jquery";

import render_hover_generated_details_modal from "../templates/hover_generated_details_modal.hbs";

import * as dialog_widget from "./dialog_widget.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_store from "./message_store.ts";

function display_time(value: string | null): string | undefined {
    if (value === null) {
        return undefined;
    }
    return new Intl.DateTimeFormat(undefined, {dateStyle: "medium", timeStyle: "short"}).format(
        new Date(value),
    );
}

export function show(message_id: number, show_history: boolean): void {
    const message = message_store.get(message_id);
    const generated = message?.hover_generated_item;
    if (message === undefined || generated === undefined) {
        return;
    }
    const presentation = {
        ...generated.presentation,
        display_occurred_at: display_time(generated.presentation.occurred_at),
        display_generated_at: display_time(generated.presentation.generated_at),
        display_published_at: display_time(generated.presentation.published_at),
    };
    const history = generated.lineage.history.map((entry) => ({
        ...entry,
        display_time: display_time(entry.occurred_at),
        url:
            message.type === "stream"
                ? `${hash_util.by_stream_url(message.stream_id)}/near/${entry.message_id}`
                : message.url,
    }));
    const modal_id = dialog_widget.launch({
        modal_title_text: show_history
            ? $t({defaultMessage: "Update history"})
            : $t({defaultMessage: "Update details"}),
        modal_content_html: render_hover_generated_details_modal({
            module: generated.module,
            presentation,
            show_history,
            history,
        }),
        modal_submit_button_text: $t({defaultMessage: "Close"}),
        single_footer_button: true,
        close_on_submit: true,
        on_click() {
            return undefined;
        },
    });
    $(`#${CSS.escape(modal_id)} [data-hover-generated-details]`).trigger("focus");
}

export function initialize(): void {
    document.body.addEventListener(
        "click",
        (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }
            const button = event.target.closest<HTMLElement>(
                ".hover-generated-details-button, .hover-generated-history-button",
            );
            const message_id = Number(button?.dataset["hoverMessageId"]);
            if (button === null || !Number.isSafeInteger(message_id)) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            show(message_id, button.classList.contains("hover-generated-history-button"));
        },
        {capture: true},
    );
}
