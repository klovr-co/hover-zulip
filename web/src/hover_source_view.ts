import Handlebars from "handlebars";
import {$} from "jquery";
import _ from "lodash";
import * as z from "zod/mini";

import render_hover_source_record from "../templates/hover_source_record.hbs";
import render_hover_source_view from "../templates/hover_source_view.hbs";

import * as channel from "./channel.ts";
import * as hover_spaces from "./hover_spaces.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as recent_view_ui from "./recent_view_ui.ts";

const record_schema = z.object({
    id: z.string(),
    sender_display_name: z.string(),
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
            available: z.boolean(),
        }),
    ),
    reply_context: z.nullable(
        z.object({
            sender_display_name: z.string(),
            timestamp: z.string(),
            excerpt: z.string(),
        }),
    ),
});
const response_schema = z.object({
    source: z.object({
        attachment_id: z.number(),
        display_name: z.string(),
        provider_key: z.string(),
        source_type: z.string(),
        account_display_name: z.string(),
        state: z.enum(["active", "detached"]),
    }),
    records: z.array(record_schema),
    next_cursor: z.string(),
    has_more: z.boolean(),
});
type SourceRecord = z.infer<typeof record_schema>;

let current_space_id: number | undefined;
let current_attachment_id: number | undefined;
let current_query = "";
let next_cursor = "";
let has_more = false;
let records = new Map<string, SourceRecord>();
let request_generation = 0;
let request: JQuery.jqXHR<unknown> | undefined;
let status = "";
let show_retry = false;
let loading_older = false;
let retry_cursor: string | undefined;
let restore_focus_hash: string | undefined;

function display_size(bytes: number | null): string | undefined {
    if (bytes === null) {
        return undefined;
    }
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    return `${(bytes / 1024).toFixed(bytes < 10_240 ? 1 : 0)} KB`;
}

function render(): void {
    if (current_space_id === undefined || current_attachment_id === undefined) {
        return;
    }
    const space = hover_spaces.get_by_id(current_space_id);
    const attachment = space?.attachments.find(({id}) => id === current_attachment_id);
    if (space === undefined || !attachment?.can_browse_records) {
        close_for_revocation();
        return;
    }
    const formatted = records
        .values()
        .toArray()
        .toSorted((a, b) => a.timestamp.localeCompare(b.timestamp) || a.id.localeCompare(b.id))
        .map((record) => ({
            ...record,
            display_time: new Intl.DateTimeFormat(undefined, {
                hour: "numeric",
                minute: "2-digit",
            }).format(new Date(record.timestamp)),
            date_label: new Intl.DateTimeFormat(undefined, {dateStyle: "long"}).format(
                new Date(record.timestamp),
            ),
            media: record.media && {
                ...record.media,
                display_size: display_size(record.media.byte_size),
            },
        }));
    const date_groups = Map.groupBy(formatted, ({date_label}) => date_label)
        .entries()
        .map(([date_label, grouped_records]) => ({
            date_label,
            records_html: new Handlebars.SafeString(
                grouped_records.map((record) => render_hover_source_record(record)).join(""),
            ),
        }))
        .toArray();
    $("#hover-source-view").html(
        render_hover_source_view({
            space_name: space.name,
            source: {...attachment.source, is_history_retained: attachment.state === "detached"},
            icon_class:
                attachment.source.provider_key === "whatsapp" ? "fa fa-whatsapp" : "fa fa-plug",
            query: current_query,
            status,
            show_retry,
            show_load_older: has_more && !loading_older,
            date_groups,
        }),
    );
}

function load(cursor?: string): void {
    if (current_space_id === undefined || current_attachment_id === undefined) {
        return;
    }
    request?.abort();
    request_generation += 1;
    const generation = request_generation;
    loading_older = cursor !== undefined;
    retry_cursor = cursor;
    const previous_scroll_height = $("#hover-source-view").get(0)?.scrollHeight ?? 0;
    const previous_scroll_top = $("#hover-source-view").scrollTop() ?? 0;
    show_retry = false;
    status = loading_older
        ? $t({defaultMessage: "Loading older records…"})
        : $t({defaultMessage: "Loading Source records…"});
    render();
    request = channel.post({
        url: `/json/hover/spaces/${current_space_id}/sources/${current_attachment_id}/records/browse`,
        data: {
            cursor: JSON.stringify(cursor ?? null),
            limit: JSON.stringify(30),
            query: JSON.stringify(current_query),
        },
        success(raw_data) {
            if (generation !== request_generation) {
                return;
            }
            const response = response_schema.parse(raw_data);
            for (const record of response.records) {
                records.set(record.id, record);
            }
            next_cursor = response.next_cursor;
            has_more = response.has_more;
            loading_older = false;
            retry_cursor = undefined;
            status =
                records.size === 0
                    ? current_query
                        ? $t({defaultMessage: "No records match this search."})
                        : $t({
                              defaultMessage:
                                  "This Source has no records in its confirmed history.",
                          })
                    : "";
            render();
            if (cursor !== undefined) {
                const new_scroll_height = $("#hover-source-view").get(0)?.scrollHeight ?? 0;
                $("#hover-source-view").scrollTop(
                    previous_scroll_top + new_scroll_height - previous_scroll_height,
                );
            }
        },
        error(xhr, error_type) {
            if (generation !== request_generation || error_type === "abort") {
                return;
            }
            loading_older = false;
            const retryable = z
                .object({
                    retryable: z.boolean(),
                    error_code: z.string(),
                    retry_after_seconds: z.optional(z.nullable(z.number())),
                })
                .safeParse(xhr.responseJSON);
            const retry_data = retryable.success ? retryable.data : undefined;
            show_retry = retry_data?.retryable ?? false;
            status =
                show_retry && retry_data?.retry_after_seconds
                    ? $t(
                          {
                              defaultMessage:
                                  "Source records are rate limited. Try again in {seconds} seconds.",
                          },
                          {seconds: retry_data.retry_after_seconds},
                      )
                    : show_retry
                      ? $t({
                            defaultMessage:
                                "Source records are temporarily unavailable. Try again.",
                        })
                      : $t({
                            defaultMessage:
                                "Source records could not be loaded from the connected service.",
                        });
            render();
        },
    });
}

function close_for_revocation(): void {
    hide();
    window.location.hash = "";
}

export function show(space_id: number, attachment_id: number): boolean {
    const attachment = hover_spaces
        .get_by_id(space_id)
        ?.attachments.find(({id}) => id === attachment_id);
    if (!attachment?.can_browse_records) {
        return false;
    }
    inbox_ui.hide();
    recent_view_ui.hide();
    $("#message_feed_container, #compose").hide();
    $("#hover-source-view").show();
    restore_focus_hash = window.location.hash;
    if (current_space_id !== space_id || current_attachment_id !== attachment_id) {
        current_space_id = space_id;
        current_attachment_id = attachment_id;
        current_query = "";
        records.clear();
        load();
    } else {
        render();
    }
    return true;
}

export function hide(): void {
    if (current_space_id === undefined) {
        return;
    }
    request?.abort();
    request_generation += 1;
    $("#hover-source-view").hide();
    $("#message_feed_container, #compose").show();
    if (restore_focus_hash !== undefined) {
        $<HTMLAnchorElement>(`a[href='${restore_focus_hash}']`).trigger("focus");
    }
    clear();
}

export function clear(): void {
    request?.abort();
    current_space_id = undefined;
    current_attachment_id = undefined;
    current_query = "";
    next_cursor = "";
    has_more = false;
    records = new Map();
    status = "";
    show_retry = false;
    loading_older = false;
    retry_cursor = undefined;
    $("#hover-source-view").empty();
}

export function handle_space_event(): void {
    if (current_space_id !== undefined) {
        render();
    }
}

export function initialize(): void {
    function update_search(): void {
        const query = $<HTMLInputElement>("#hover-source-search")
            .val()!
            .trim()
            .replaceAll(/\s+/g, " ");
        if (query === current_query) {
            return;
        }
        current_query = query;
        records.clear();
        next_cursor = "";
        has_more = false;
        load();
    }
    const debounced_search = _.debounce(update_search, 350);
    $("body").on("input", "#hover-source-search", () => {
        debounced_search();
    });
    $("body").on("submit", "#hover-source-search-form", (event) => {
        event.preventDefault();
        debounced_search.cancel();
        update_search();
    });
    $("body").on("click", "#hover-source-load-older", () => {
        load(next_cursor);
    });
    $("body").on("click", "#hover-source-retry", () => {
        load(retry_cursor);
    });
}
