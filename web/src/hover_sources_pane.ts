import render_hover_sources_pane from "../templates/hover_sources_pane.hbs";

import * as hover_evidence from "./hover_evidence.ts";
import {$t} from "./i18n.ts";
import * as message_store from "./message_store.ts";
import * as message_view from "./message_view.ts";

let request_id = 0;
let current_url: string | undefined;
let return_focus: HTMLElement | undefined;

function host(): HTMLElement | null {
    return document.querySelector("#hover-sources-pane");
}

function render(context: Record<string, unknown>): void {
    const pane = host();
    if (pane === null) {
        return;
    }
    pane.innerHTML = render_hover_sources_pane(context);
}

function focus_result(): void {
    host()?.querySelector<HTMLElement>("[data-hover-sources-result]")?.focus();
}

export function close(): void {
    request_id += 1;
    current_url = undefined;
    const pane = host();
    if (pane !== null) {
        pane.hidden = true;
        pane.replaceChildren();
    }
    document.body.classList.remove("hover-sources-pane-open");
    if (return_focus?.isConnected) {
        return_focus.focus();
    }
    return_focus = undefined;
}

export function open(url: string, trigger?: HTMLElement): void {
    const pane = host();
    if (pane === null) {
        return;
    }
    current_url = url;
    return_focus = trigger ?? return_focus;
    request_id += 1;
    const own_request_id = request_id;
    pane.hidden = false;
    document.body.classList.add("hover-sources-pane-open");
    render({loading: true});
    pane.querySelector<HTMLElement>("[data-hover-sources-result]")?.focus();

    hover_evidence.fetch_evidence(url, {
        success(evidence) {
            if (own_request_id !== request_id) {
                return;
            }
            render({
                evidence,
                empty: evidence.groups.length === 0 && evidence.forbidden_count === 0,
                has_forbidden: evidence.forbidden_count > 0,
                forbidden_message:
                    evidence.forbidden_count === 1
                        ? $t({defaultMessage: "1 supporting message is unavailable."})
                        : $t(
                              {defaultMessage: "{count} supporting messages are unavailable."},
                              {count: evidence.forbidden_count},
                          ),
            });
            focus_result();
        },
        error(error) {
            if (own_request_id !== request_id) {
                return;
            }
            render({
                error: true,
                retryable: error.retryable,
                alert_class: error.retryable ? "alert-warning" : "alert-error",
            });
            focus_result();
        },
    });
}

function open_message(button: HTMLElement): void {
    const message_id = Number.parseInt(button.dataset["messageId"] ?? "", 10);
    const stream_id = Number.parseInt(button.dataset["streamId"] ?? "", 10);
    const topic_name = button.dataset["topicName"];
    if (!Number.isSafeInteger(message_id) || !Number.isSafeInteger(stream_id) || !topic_name) {
        return;
    }
    const message = message_store.get(message_id);
    if (message !== undefined) {
        message_view.narrow_to_message_near(message, "Hover sources pane");
        return;
    }
    message_view.show(
        [
            {operator: "channel", operand: String(stream_id)},
            {operator: "topic", operand: topic_name},
            {operator: "near", operand: String(message_id)},
        ],
        {trigger: "Hover sources pane"},
    );
}

export function initialize(): void {
    document.body.addEventListener(
        "click",
        (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }
            const evidence_button = event.target.closest<HTMLElement>(".hover-view-evidence");
            if (evidence_button !== null) {
                const url = evidence_button.dataset["evidenceUrl"];
                if (url !== undefined) {
                    event.preventDefault();
                    event.stopPropagation();
                    open(url, evidence_button);
                }
                return;
            }
            if (event.target.closest(".hover-sources-pane-close") !== null) {
                close();
                return;
            }
            if (event.target.closest(".hover-sources-pane-retry") !== null) {
                if (current_url !== undefined) {
                    open(current_url);
                }
                return;
            }
            const message_button = event.target.closest<HTMLElement>(".hover-open-source-message");
            if (message_button !== null) {
                open_message(message_button);
            }
        },
        {capture: true},
    );
    document.addEventListener(
        "keydown",
        (event) => {
            if (event.key === "Escape" && !host()?.hidden) {
                event.preventDefault();
                event.stopImmediatePropagation();
                close();
            }
        },
        {capture: true},
    );
}
