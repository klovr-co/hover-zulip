import {$} from "jquery";
import _ from "lodash";
import * as z from "zod/mini";

import render_hover_awareness_view from "../templates/hover_awareness_view.hbs";

import * as channel from "./channel.ts";
import * as hover_awareness_state from "./hover_awareness_state.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import {hover_generated_item_schema} from "./message_store.ts";
import * as message_view_header from "./message_view_header.ts";
import * as people from "./people.ts";
import * as recent_view_ui from "./recent_view_ui.ts";

const surface_schema = z.enum(["for_you", "team_pulse"]);
export type AwarenessSurface = z.infer<typeof surface_schema>;

const awareness_item_schema = z.object({
    message_id: z.number(),
    generated_item_id: z.number(),
    space_id: z.number(),
    space_name: z.string(),
    stream_id: z.number(),
    topic: z.string(),
    rendered_content: z.string(),
    sender_id: z.number(),
    sender_name: z.string(),
    timestamp: z.string(),
    is_unread: z.boolean(),
    rank: z.number(),
    reasons: z.array(z.string()),
    hover_generated_item: hover_generated_item_schema,
});
const awareness_response_schema = z.object({
    surface: surface_schema,
    items: z.array(awareness_item_schema),
});

let current_surface: AwarenessSurface | undefined;
let request: JQuery.jqXHR<unknown> | undefined;
let request_generation = 0;
let status = "";
let show_retry = false;
let items: z.infer<typeof awareness_item_schema>[] = [];

const reason_labels = new Map([
    ["assignment", $t({defaultMessage: "Assigned to you"})],
    ["ownership", $t({defaultMessage: "You own this"})],
    ["mention", $t({defaultMessage: "Mentioned you"})],
    ["review_request", $t({defaultMessage: "Review requested"})],
    ["personal_activity", $t({defaultMessage: "Your activity"})],
    ["important", $t({defaultMessage: "Important"})],
    ["contributor_space", $t({defaultMessage: "Contributor Space"})],
    ["urgent", $t({defaultMessage: "Urgent"})],
    ["high_importance", $t({defaultMessage: "High importance"})],
    ["open_review", $t({defaultMessage: "Open review"})],
    ["active_todo", $t({defaultMessage: "Active Todo"})],
    ["material_change", $t({defaultMessage: "Material change"})],
]);

function reviewed_summary(payload: Record<string, unknown>, revision_count: number): string {
    if (revision_count === 0) {
        return "";
    }
    for (const key of ["summary", "wording", "decision", "title", "status"]) {
        const value = payload[key];
        if (typeof value === "string" && value.trim()) {
            return value;
        }
    }
    return $t({defaultMessage: "Updated through Review"});
}

function render(): void {
    if (current_surface === undefined) {
        return;
    }
    const for_you = current_surface === "for_you";
    const formatted_items = items.map((item) => {
        const generated = item.hover_generated_item;
        const message_url = `#narrow/channel/${item.stream_id}/topic/${encodeURIComponent(item.topic)}/near/${item.message_id}`;
        const oldest_history_message_id = generated.lineage.history.at(-1)?.message_id;
        const history_url =
            oldest_history_message_id === undefined
                ? message_url
                : `#narrow/channel/${item.stream_id}/topic/${encodeURIComponent(item.topic)}/near/${oldest_history_message_id}`;
        const safe_module_key = generated.module.key.replaceAll(/[^a-zA-Z0-9_-]/g, "-");
        const todo = generated.suggested_action?.todo;
        return {
            ...item,
            card_class: item.is_unread
                ? `hover-awareness-card hover-generated-update hover-awareness-card--unread hover-module--${safe_module_key}`
                : `hover-awareness-card hover-generated-update hover-module--${safe_module_key}`,
            avatar_url: people.small_avatar_url_for_user_id(item.sender_id),
            display_time: new Intl.DateTimeFormat(undefined, {
                dateStyle: "medium",
                timeStyle: "short",
            }).format(new Date(item.timestamp)),
            message_url,
            history_url,
            output_label: generated.presentation.label,
            importance: generated.presentation.importance,
            source_summary: generated.source_summary,
            sources: generated.sources,
            reason_labels: item.reasons
                .map((reason) => reason_labels.get(reason))
                .filter((label): label is string => label !== undefined),
            has_reasons: item.reasons.some((reason) => reason_labels.has(reason)),
            reviewed_summary: reviewed_summary(
                generated.reviewed_payload,
                generated.revisions.length,
            ),
            has_history: generated.lineage.history_count > 1,
            history_count: generated.lineage.history_count,
            evidence_url: generated.evidence_url,
            todo_status:
                todo?.state === "active"
                    ? $t({defaultMessage: "Active"})
                    : todo?.state === "completed"
                      ? $t({defaultMessage: "Completed"})
                      : undefined,
            todo_due_date: todo?.due_date,
        };
    });
    $("#hover-awareness-view").html(
        render_hover_awareness_view({
            title: for_you ? $t({defaultMessage: "For You"}) : $t({defaultMessage: "Team Pulse"}),
            description: for_you
                ? $t({
                      defaultMessage:
                          "Updates that need your attention, ranked from your confirmed Spaces.",
                  })
                : $t({
                      defaultMessage: "Important team movement across the Spaces you can access.",
                  }),
            status,
            status_class:
                formatted_items.length > 0
                    ? "hover-awareness-status"
                    : "hover-awareness-status hover-awareness-status--panel",
            show_retry,
            has_items: formatted_items.length > 0,
            items: formatted_items,
        }),
    );
}

function load(): void {
    if (current_surface === undefined) {
        return;
    }
    request?.abort();
    request_generation += 1;
    const generation = request_generation;
    status = $t({defaultMessage: "Loading live awareness…"});
    show_retry = false;
    render();
    request = channel.get({
        url: "/json/hover/awareness",
        data: {surface: JSON.stringify(current_surface)},
        success(raw_data) {
            if (generation !== request_generation || current_surface === undefined) {
                return;
            }
            const response = awareness_response_schema.parse(raw_data);
            if (response.surface !== current_surface) {
                return;
            }
            items = response.items;
            status =
                items.length === 0
                    ? current_surface === "for_you"
                        ? $t({defaultMessage: "Nothing needs your attention right now."})
                        : $t({defaultMessage: "No important team developments yet."})
                    : "";
            render();
        },
        error(_xhr, error_type) {
            if (generation !== request_generation || error_type === "abort") {
                return;
            }
            status = $t({defaultMessage: "Live awareness could not be loaded."});
            show_retry = true;
            render();
        },
    });
}

const refresh_after_realtime_change = _.debounce(() => {
    if (current_surface !== undefined) {
        load();
    }
}, 100);

export function handle_realtime_change(): void {
    refresh_after_realtime_change();
}

export function is_visible(): boolean {
    const $view = $("#hover-awareness-view");
    return $view.length > 0 && $view.css("display") !== "none";
}

export function show(surface: AwarenessSurface): void {
    hover_awareness_state.set_surface(surface);
    inbox_ui.hide();
    recent_view_ui.hide();
    $("#hover-source-view, #message_feed_container, #compose").hide();
    $("#hover-awareness-view").show();
    message_view_header.render_title_area();
    if (surface !== current_surface) {
        current_surface = surface;
        items = [];
        load();
    } else {
        render();
    }
}

export function hide(): void {
    request?.abort();
    refresh_after_realtime_change.cancel();
    request_generation += 1;
    current_surface = undefined;
    hover_awareness_state.clear();
    items = [];
    status = "";
    show_retry = false;
    $("#hover-awareness-view").hide().empty();
    $("#message_feed_container, #compose").show();
    message_view_header.render_title_area();
}

export function initialize(): void {
    $("body").on("click", "#hover-awareness-retry", () => {
        load();
    });
}

export const test = {
    render,
    reset(): void {
        request?.abort();
        refresh_after_realtime_change.cancel();
        current_surface = undefined;
        request = undefined;
        request_generation = 0;
        status = "";
        show_retry = false;
        items = [];
        hover_awareness_state.clear();
    },
};
