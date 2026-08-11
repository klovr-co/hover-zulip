import {$} from "jquery";
import * as z from "zod/mini";

import render_hover_search_view from "../templates/hover_search_view.hbs";

import * as channel from "./channel.ts";
import * as hover_spaces from "./hover_spaces.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as message_flags from "./message_flags.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as starred_messages from "./starred_messages.ts";
import * as starred_messages_ui from "./starred_messages_ui.ts";

const knowledge_schema = z.object({
    kind: z.enum(["human", "generated"]),
    message_id: z.number(),
    space: z.object({id: z.number(), name: z.string()}),
    topic: z.string(),
    sender_name: z.string(),
    timestamp: z.string(),
    rendered_content: z.string(),
    module_name: z.string(),
    output_type: z.string(),
    saved: z.boolean(),
    saveable: z.literal(true),
    url: z.string(),
});
const source_schema = z.object({
    kind: z.literal("source"),
    space: z.object({id: z.number(), name: z.string()}),
    source: z.object({
        attachment_id: z.number(),
        display_name: z.string(),
        provider_key: z.string(),
        source_type: z.string(),
        account_display_name: z.string(),
        state: z.enum(["active", "detached"]),
    }),
    record: z.object({
        id: z.string(),
        sender_display_name: z.string(),
        timestamp: z.string(),
        content: z.object({
            text: z.nullable(z.string()),
            voice_transcript: z.nullable(z.string()),
            media_description: z.nullable(z.string()),
        }),
        media: z.nullable(z.unknown()),
        reply_context: z.nullable(z.unknown()),
    }),
    saveable: z.literal(false),
});
const response_schema = z.object({
    query: z.string(),
    knowledge: z.array(knowledge_schema),
    sources: z.array(source_schema),
    source_unavailable_count: z.number(),
});
type SearchResponse = z.infer<typeof response_schema>;

let response: SearchResponse = {
    query: "",
    knowledge: [],
    sources: [],
    source_unavailable_count: 0,
};
let status = "";
let visible = false;
let request: JQuery.jqXHR<unknown> | undefined;
let request_generation = 0;

function display_time(timestamp: string): string {
    return new Intl.DateTimeFormat(undefined, {dateStyle: "medium", timeStyle: "short"}).format(
        new Date(timestamp),
    );
}

function authorized_space_ids(): Set<number> {
    return new Set(
        hover_spaces
            .get_all()
            .filter((space) => space.state === "launched")
            .map((space) => space.id),
    );
}

function filter_unauthorized_results(search_response: SearchResponse): SearchResponse {
    const space_ids = authorized_space_ids();
    return {
        ...search_response,
        knowledge: search_response.knowledge.filter((result) => space_ids.has(result.space.id)),
        sources: search_response.sources.filter((result) => space_ids.has(result.space.id)),
    };
}

function render(): void {
    if (!visible) {
        return;
    }
    const knowledge = response.knowledge.map((result) => ({
        ...result,
        display_time: display_time(result.timestamp),
        kind_label:
            result.kind === "generated"
                ? $t({defaultMessage: "Generated update"})
                : $t({defaultMessage: "Human post"}),
        byline:
            result.kind === "generated" && result.module_name
                ? result.module_name
                : result.sender_name,
    }));
    const sources = response.sources.map((result) => ({
        ...result,
        display_time: display_time(result.record.timestamp),
    }));
    $("#hover-search-view").html(
        render_hover_search_view({
            query: response.query,
            status,
            has_query: response.query !== "",
            knowledge,
            sources,
            knowledge_count: knowledge.length,
            source_count: sources.length,
            has_knowledge: knowledge.length > 0,
            has_sources: sources.length > 0,
        }),
    );
}

function search(query: string): void {
    const normalized = query.trim().replaceAll(/\s+/g, " ");
    request?.abort();
    request_generation += 1;
    if (!normalized) {
        response = {
            query: "",
            knowledge: [],
            sources: [],
            source_unavailable_count: 0,
        };
        status = "";
        render();
        return;
    }
    const generation = request_generation;
    response = {
        query: normalized,
        knowledge: [],
        sources: [],
        source_unavailable_count: 0,
    };
    status = $t({defaultMessage: "Searching confirmed Spaces…"});
    render();
    request = channel.post({
        url: "/json/hover/search",
        data: {query: JSON.stringify(normalized)},
        success(raw_data) {
            if (generation !== request_generation) {
                return;
            }
            response = filter_unauthorized_results(response_schema.parse(raw_data));
            status = response.source_unavailable_count
                ? $t({defaultMessage: "Some Source evidence is temporarily unavailable."})
                : response.knowledge.length + response.sources.length === 0
                  ? $t({defaultMessage: "No results found."})
                  : "";
            render();
        },
        error(_xhr, error_type) {
            if (generation !== request_generation || error_type === "abort") {
                return;
            }
            status = $t({defaultMessage: "Search could not be completed. Try again."});
            render();
        },
    });
}

export function show(): void {
    visible = true;
    inbox_ui.hide();
    recent_view_ui.hide();
    $("#message_feed_container, #compose, #hover-source-view").hide();
    $("#hover-search-view").show();
    left_sidebar_navigation_area.select_top_left_corner_item(".top_left_hover_search");
    render();
}

export function hide(): void {
    if (!visible) {
        return;
    }
    visible = false;
    request?.abort();
    request_generation += 1;
    $("#hover-search-view").hide();
    $("#message_feed_container, #compose").show();
}

export function handle_space_event(): void {
    const previous_count = response.knowledge.length + response.sources.length;
    response = filter_unauthorized_results(response);
    if (previous_count !== response.knowledge.length + response.sources.length) {
        status = $t({defaultMessage: "Results updated after your Space access changed."});
        render();
    }
}

export function initialize(): void {
    $("body").on("submit", "#hover-global-search-form", (event) => {
        event.preventDefault();
        search(String($("#hover-global-search-input").val() ?? ""));
    });
    $("body").on("click", ".hover-search-save-button", (event) => {
        const message_id = Number($(event.currentTarget).attr("data-message-id"));
        const result = response.knowledge.find((item) => item.message_id === message_id);
        if (result === undefined) {
            return;
        }
        result.saved = !result.saved;
        starred_messages_ui.update_starred_flag(message_id, result.saved);
        message_flags.send_flag_update_for_messages(
            [message_id],
            "starred",
            result.saved ? "add" : "remove",
        );
        if (result.saved) {
            starred_messages.add([message_id]);
        } else {
            starred_messages.remove([message_id]);
        }
        starred_messages_ui.rerender_ui();
        render();
    });
}

export const test = {search};
