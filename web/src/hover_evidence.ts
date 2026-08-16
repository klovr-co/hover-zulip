import {$} from "jquery";
import * as z from "zod/mini";

import render_hover_evidence_modal from "../templates/hover_evidence_modal.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t} from "./i18n.ts";

const evidence_schema = z.object({
    evidence_ref: z.string(),
    source_ref: z.string(),
    sender: z.object({ref: z.string(), display_name: z.string()}),
    timestamp: z.string(),
    content: z.object({
        text: z.nullable(z.string()),
        voice_transcript: z.nullable(z.string()),
        media_description: z.nullable(z.string()),
    }),
    media: z.nullable(
        z.object({
            type: z.string(),
            mime_type: z.nullable(z.string()),
            byte_size: z.nullable(z.number()),
            sha256: z.nullable(z.string()),
            available: z.boolean(),
        }),
    ),
});

const evidence_response_schema = z.object({evidence: z.array(evidence_schema)});
const error_response_schema = z.object({retryable: z.optional(z.boolean())});

function present_evidence(
    response: unknown,
): (z.infer<typeof evidence_schema> & {display_timestamp: string})[] {
    const {evidence} = evidence_response_schema.parse(response);
    return evidence.map((item) => ({
        ...item,
        display_timestamp: new Intl.DateTimeFormat(undefined, {
            dateStyle: "medium",
            timeStyle: "short",
        }).format(new Date(item.timestamp)),
    }));
}

function focus_result($content: JQuery): void {
    $content.find("[data-cf-evidence-result]").trigger("focus");
}

function replace_content($content: JQuery, html: string): void {
    const $simplebar_content = $content.find(".simplebar-content");
    ($simplebar_content.length > 0 ? $simplebar_content : $content).html(html);
}

export function load_evidence($content: JQuery, url: string): void {
    replace_content($content, render_hover_evidence_modal({loading: true}));
    focus_result($content);
    void channel.post({
        url,
        success(response) {
            try {
                const evidence = present_evidence(response);
                replace_content(
                    $content,
                    render_hover_evidence_modal({evidence, empty: evidence.length === 0}),
                );
            } catch {
                replace_content(
                    $content,
                    render_hover_evidence_modal({error: true, retryable: false}),
                );
            }
            focus_result($content);
        },
        error(xhr) {
            const parsed = error_response_schema.safeParse(xhr.responseJSON);
            const retryable =
                parsed.success && parsed.data.retryable !== undefined
                    ? parsed.data.retryable
                    : [429, 502, 503, 504].includes(xhr.status);
            replace_content(
                $content,
                render_hover_evidence_modal({
                    error: true,
                    retryable,
                    evidence_url: url,
                }),
            );
            focus_result($content);
        },
    });
}

export function show_evidence(url: string): void {
    const modal_id = dialog_widget.launch({
        modal_title_text: $t({defaultMessage: "Sources"}),
        modal_content_html: render_hover_evidence_modal({loading: true}),
        modal_submit_button_text: $t({defaultMessage: "Close"}),
        single_footer_button: true,
        close_on_submit: true,
        on_click() {
            // The single footer button only closes the dialog.
        },
    });
    const $content = $(`#${CSS.escape(modal_id)} .modal__content`);
    load_evidence($content, url);
}

export function initialize(): void {
    document.body.addEventListener(
        "click",
        (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }
            const button = event.target.closest<HTMLElement>("[data-cf-evidence-url]");
            if (button === null) {
                return;
            }
            const url = button.dataset["cfEvidenceUrl"];
            if (url === undefined) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            show_evidence(url);
        },
        {capture: true},
    );
    $("body").on("click", "[data-cf-evidence-retry-url]", (event) => {
        event.preventDefault();
        const $button = $(event.currentTarget);
        const url = $button.attr("data-cf-evidence-retry-url");
        if (url !== undefined) {
            load_evidence($button.closest(".modal__content"), url);
        }
    });
}
