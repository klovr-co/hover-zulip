import {$} from "jquery";
import * as z from "zod/mini";

import render_hover_pipelines_view from "../templates/hover_pipelines_view.hbs";

import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as stream_data from "./stream_data.ts";
import * as user_settings from "./user_settings.ts";

const data_source_schema = z.object({
    id: z.number(),
    name: z.string(),
    provider_key: z.string(),
    provider_name: z.string(),
    provider_logo_url: z.nullable(z.string()),
    state: z.enum(["active", "disabled", "needs_attention"]),
    health_status: z.enum(["unknown", "healthy", "degraded"]),
});
const topic_schema = z.object({
    input_destination: z.string(),
    input_topic: z.string(),
    input_availability: z.enum(["available", "topic_unavailable"]),
    data_sources: z.array(data_source_schema),
});
const source_warning_schema = z.object({
    data_source_id: z.number(),
    data_source_name: z.string(),
    state: z.enum(["active", "disabled", "needs_attention"]),
    health_status: z.enum(["unknown", "healthy", "degraded"]),
});
const pipeline_schema = z.object({
    id: z.number(),
    name: z.string(),
    instruction: z.string(),
    input_destination: z.nullable(z.string()),
    input_topic: z.string(),
    input_availability: z.enum(["available", "topic_unavailable"]),
    run_health: z.enum(["not_run", "healthy", "failed"]),
    data_sources: z.array(data_source_schema),
    source_warnings: z.array(source_warning_schema),
    cadence: z.enum(["daily", "weekdays", "weekly"]),
    weekday: z.nullable(z.number()),
    local_time: z.string(),
    timezone: z.string(),
    output_destination: z.string(),
    output_topic: z.string(),
    lifecycle_state: z.enum(["active", "draft", "paused"]),
    status: z.enum(["active", "draft", "paused", "needs_attention"]),
    available_transitions: z.array(z.enum(["activate", "pause", "resume", "edit"])),
    last_run_at: z.nullable(z.string()),
    date_created: z.string(),
});
type DataSource = z.infer<typeof data_source_schema>;
type Topic = z.infer<typeof topic_schema>;
type Pipeline = z.infer<typeof pipeline_schema>;
type Stage = "index" | "select" | "configure" | "review";
type PipelineFilter = "all" | Pipeline["lifecycle_state"];
type LifecycleTransition = "activate" | "pause" | "resume";
type Draft = {
    name: string;
    instruction: string;
    cadence: "daily" | "weekdays" | "weekly";
    weekday: number | null;
    local_time: string;
    timezone: string;
    output_destination: string;
    output_topic: string;
};

const PIPELINES_URL = "/json/hover/pipelines";
let visible = false;
let loaded = false;
let loading = false;
let load_error = false;
let stage: Stage = "index";
let pipelines: Pipeline[] = [];
let topics: Topic[] = [];
let selected_topic: Topic | undefined;
let can_create = false;
let index_query = "";
let topic_query = "";
let pipeline_filter: PipelineFilter = "all";
const expanded_pipeline_ids = new Set<number>();
let draft = fresh_draft();
let editing_pipeline: Pipeline | undefined;
let repairing_input = false;
let pending_pipeline_id: number | undefined;
const pipeline_feedback = new Map<number, {kind: "success" | "error"; message: string}>();

function fresh_draft(): Draft {
    return {
        name: "",
        instruction: "",
        cadence: "daily",
        weekday: 4,
        local_time: "09:00",
        timezone:
            user_settings.user_settings?.timezone ??
            new Intl.DateTimeFormat().resolvedOptions().timeZone,
        output_destination: "",
        output_topic: "",
    };
}

function topic_key(destination: string, topic: string): string {
    return `${destination.toLocaleLowerCase()}\u{0}${topic.trim().toLocaleLowerCase()}`;
}

function focus_input_at_end(selector: string): void {
    const input = $(selector).trigger("focus").get(0);
    if (input instanceof HTMLInputElement) {
        input.setSelectionRange(input.value.length, input.value.length);
    }
}

export function deduplicate_topics_for_testing(topic_rows: Topic[]): Topic[] {
    const by_key = new Map<string, Topic>();
    for (const row of topic_rows) {
        const key = topic_key(row.input_destination, row.input_topic);
        const existing = by_key.get(key);
        if (existing === undefined) {
            by_key.set(key, {...row, data_sources: [...row.data_sources]});
            continue;
        }
        const source_ids = new Set(existing.data_sources.map((source) => source.id));
        existing.data_sources.push(
            ...row.data_sources.filter((source) => !source_ids.has(source.id)),
        );
        if (row.input_availability === "available") {
            existing.input_availability = "available";
        }
    }
    return by_key.values().toArray();
}

function display_time(time: string): string {
    const [hours = "9", minutes = "00"] = time.split(":", 2);
    const hour = Number(hours);
    return `${hour % 12 || 12}:${minutes} ${hour >= 12 ? "PM" : "AM"}`;
}

function weekday_label(day: number | null): string {
    return [
        $t({defaultMessage: "Monday"}),
        $t({defaultMessage: "Tuesday"}),
        $t({defaultMessage: "Wednesday"}),
        $t({defaultMessage: "Thursday"}),
        $t({defaultMessage: "Friday"}),
        $t({defaultMessage: "Saturday"}),
        $t({defaultMessage: "Sunday"}),
    ][day ?? 4]!;
}

function schedule_label(item: Pick<Pipeline, "cadence" | "weekday" | "local_time">): string {
    if (item.cadence === "weekly") {
        return $t(
            {defaultMessage: "Every {weekday} at {time}"},
            {weekday: weekday_label(item.weekday), time: display_time(item.local_time)},
        );
    }
    return $t(
        {defaultMessage: "{cadence} at {time}"},
        {
            cadence:
                item.cadence === "weekdays"
                    ? $t({defaultMessage: "Every weekday"})
                    : $t({defaultMessage: "Every day"}),
            time: display_time(item.local_time),
        },
    );
}

export function schedule_summary_for_testing(
    cadence: Pipeline["cadence"],
    weekday: number | null,
    local_time: string,
): string {
    return schedule_label({cadence, weekday, local_time});
}

function source_has_warning(source: DataSource): boolean {
    return source.state !== "active" || source.health_status === "degraded";
}

function filtered_pipelines(): Pipeline[] {
    const query = index_query.trim().toLocaleLowerCase();
    return pipelines.filter(
        (item) =>
            (pipeline_filter === "all" || item.lifecycle_state === pipeline_filter) &&
            `${item.name} ${item.instruction} ${item.input_destination ?? ""} ${item.input_topic}`
                .toLocaleLowerCase()
                .includes(query),
    );
}

export function lifecycle_actions_for_testing(
    lifecycle_state: Pipeline["lifecycle_state"],
    input_availability: Pipeline["input_availability"],
    available_transitions: Pipeline["available_transitions"],
): {
    can_activate: boolean;
    can_continue_setup: boolean;
    can_show_pause: boolean;
    can_show_resume: boolean;
    can_pause: boolean;
    can_resume: boolean;
    topic_needs_repair: boolean;
} {
    const transitions = new Set(available_transitions);
    return {
        can_activate: lifecycle_state === "draft" && transitions.has("activate"),
        can_continue_setup: lifecycle_state === "draft" && transitions.has("edit"),
        can_show_pause: lifecycle_state === "active",
        can_show_resume: lifecycle_state === "paused",
        can_pause: lifecycle_state === "active" && transitions.has("pause"),
        can_resume: lifecycle_state === "paused" && transitions.has("resume"),
        topic_needs_repair: input_availability === "topic_unavailable",
    };
}

function filtered_topic_groups(): {space: string; topics: object[]}[] {
    const query = topic_query.trim().toLocaleLowerCase();
    const grouped = new Map<string, object[]>();
    for (const topic of deduplicate_topics_for_testing(topics)) {
        if (`${topic.input_destination} ${topic.input_topic}`.toLocaleLowerCase().includes(query)) {
            const sources = topic.data_sources.map((source) => ({
                ...source,
                provider_initial: source.provider_name.slice(0, 1),
                has_warning: source_has_warning(source),
            }));
            const rows = grouped.get(topic.input_destination) ?? [];
            rows.push({
                ...topic,
                topic_key: topic_key(topic.input_destination, topic.input_topic),
                selected_class:
                    selected_topic !== undefined &&
                    topic_key(selected_topic.input_destination, selected_topic.input_topic) ===
                        topic_key(topic.input_destination, topic.input_topic)
                        ? "is-selected"
                        : "",
                is_unavailable: topic.input_availability === "topic_unavailable",
                aria_disabled: topic.input_availability === "topic_unavailable" ? "true" : "false",
                unavailable_class:
                    topic.input_availability === "topic_unavailable" ? "is-unavailable" : "",
                available: topic.input_availability === "available",
                sources,
                source_count: sources.length,
                has_sources: sources.length > 0,
                has_multiple_sources: sources.length > 1,
            });
            grouped.set(topic.input_destination, rows);
        }
    }
    return [...grouped]
        .toSorted(([a], [b]) => a.localeCompare(b))
        .map(([space, topic_rows]) => ({space, topics: topic_rows}));
}

function render(): void {
    if (!visible) {
        return;
    }
    const output_destinations = stream_data
        .subscribed_subs()
        .filter((stream) => stream_data.can_post_messages_in_stream(stream))
        .map((stream) => ({name: stream.name, selected: stream.name === draft.output_destination}));
    const pipeline_rows = filtered_pipelines().map((item) => {
        const is_expanded = expanded_pipeline_ids.has(item.id);
        const actions = lifecycle_actions_for_testing(
            item.lifecycle_state,
            item.input_availability,
            item.available_transitions,
        );
        const is_pending = pending_pipeline_id === item.id;
        const feedback = pipeline_feedback.get(item.id);
        return {
            ...item,
            ...actions,
            input_destination_label:
                item.input_destination ?? $t({defaultMessage: "Space unavailable"}),
            schedule_label:
                item.lifecycle_state === "draft"
                    ? $t({defaultMessage: "Not scheduled"})
                    : schedule_label(item),
            status_label:
                item.status === "needs_attention"
                    ? $t({defaultMessage: "Needs attention"})
                    : item.status === "active"
                      ? $t({defaultMessage: "Active"})
                      : item.status === "paused"
                        ? $t({defaultMessage: "Paused"})
                        : $t({defaultMessage: "Draft"}),
            last_run_label:
                item.last_run_at === null
                    ? $t({defaultMessage: "Not run yet"})
                    : new Intl.DateTimeFormat(undefined, {
                          dateStyle: "medium",
                          timeStyle: "short",
                      }).format(new Date(item.last_run_at)),
            expanded: is_expanded,
            expanded_class: is_expanded ? "is-expanded" : "",
            aria_expanded: is_expanded ? "true" : "false",
            expand_label: is_expanded
                ? $t({defaultMessage: "Collapse pipeline details"})
                : $t({defaultMessage: "Expand pipeline details"}),
            topic_unavailable: item.input_availability === "topic_unavailable",
            topic_unavailable_while_paused:
                item.input_availability === "topic_unavailable" &&
                item.lifecycle_state === "paused",
            is_pending,
            pause_disabled: is_pending || !actions.can_pause,
            resume_disabled: is_pending || !actions.can_resume,
            transition_permission_note:
                !is_pending &&
                item.input_availability === "available" &&
                ((actions.can_show_pause && !actions.can_pause) ||
                    (actions.can_show_resume && !actions.can_resume)),
            transition_unavailable_note:
                !is_pending &&
                actions.can_show_resume &&
                item.input_availability === "topic_unavailable",
            pause_label: is_pending
                ? $t({defaultMessage: "Pausing…"})
                : $t({defaultMessage: "Pause pipeline"}),
            resume_label: is_pending
                ? $t({defaultMessage: "Resuming…"})
                : $t({defaultMessage: "Resume pipeline"}),
            has_feedback: feedback !== undefined,
            feedback_message: feedback?.message,
            feedback_class:
                feedback?.kind === "success"
                    ? "hover-pipeline-request-status--success"
                    : "hover-pipeline-request-status--error",
            has_source_warnings: item.source_warnings.length > 0,
            source_warnings: item.source_warnings.map((warning) => ({
                ...warning,
                label: $t(
                    {defaultMessage: "{source} is {status}."},
                    {
                        source: warning.data_source_name,
                        status:
                            warning.health_status === "degraded"
                                ? $t({defaultMessage: "degraded"})
                                : warning.state === "disabled"
                                  ? $t({defaultMessage: "disabled"})
                                  : $t({defaultMessage: "needs attention"}),
                    },
                ),
            })),
            source_count: item.data_sources.length,
            source_metadata: item.data_sources.map((source) => ({
                ...source,
                provider_initial: source.provider_name.slice(0, 1),
            })),
            has_sources: item.data_sources.length > 0,
            run_health_label:
                item.run_health === "failed"
                    ? $t({defaultMessage: "Last run needs attention"})
                    : item.run_health === "healthy"
                      ? $t({defaultMessage: "Last run succeeded"})
                      : $t({defaultMessage: "No run health yet"}),
        };
    });
    const topic_groups = filtered_topic_groups();
    const same_topic =
        selected_topic !== undefined &&
        topic_key(selected_topic.input_destination, selected_topic.input_topic) ===
            topic_key(draft.output_destination, draft.output_topic);
    const permission_limited = !loading && pipelines.length === 0 && !can_create;
    $("#hover-pipelines-view").html(
        render_hover_pipelines_view({
            is_index: stage === "index",
            is_select: stage === "select",
            is_configure: stage === "configure",
            is_review: stage === "review",
            is_repairing: repairing_input,
            is_editing_draft: editing_pipeline?.lifecycle_state === "draft",
            can_save_as_draft:
                editing_pipeline === undefined || editing_pipeline.lifecycle_state === "draft",
            can_create,
            permission_limited,
            permission_class: permission_limited ? "hover-pipeline-permission-limited" : "",
            step_one_class: stage === "select" ? "is-active" : "is-complete",
            step_two_class:
                stage === "configure" ? "is-active" : stage === "review" ? "is-complete" : "",
            step_three_class: stage === "review" ? "is-active" : "",
            step_one_complete: stage === "configure" || stage === "review",
            step_two_complete: stage === "review",
            index_query,
            pipelines: pipeline_rows,
            has_pipelines: pipeline_rows.length > 0,
            filter_all_class: pipeline_filter === "all" ? "is-selected" : "",
            filter_active_class: pipeline_filter === "active" ? "is-selected" : "",
            filter_draft_class: pipeline_filter === "draft" ? "is-selected" : "",
            filter_paused_class: pipeline_filter === "paused" ? "is-selected" : "",
            empty_heading: loading
                ? $t({defaultMessage: "Loading pipelines…"})
                : load_error
                  ? $t({defaultMessage: "Could not load pipelines"})
                  : permission_limited
                    ? $t({defaultMessage: "No pipelines you can access"})
                    : pipelines.length === 0
                      ? $t({defaultMessage: "No pipelines yet"})
                      : $t({defaultMessage: "No pipelines match this view"}),
            empty_description: permission_limited
                ? $t({
                      defaultMessage:
                          "Ask a workspace administrator for access to create or view pipelines.",
                  })
                : pipelines.length === 0
                  ? $t({
                        defaultMessage: "Create one to process messages from any accessible Topic.",
                    })
                  : $t({defaultMessage: "Try another search or status filter."}),
            topic_query,
            topic_groups,
            has_topics: topic_groups.some((group) => group.topics.length > 0),
            topics_empty_heading:
                topics.length === 0
                    ? $t({defaultMessage: "No accessible Topics"})
                    : $t({defaultMessage: "No Topics match your search"}),
            topics_empty_description:
                topics.length === 0
                    ? $t({defaultMessage: "Join a Space with Topics before creating a pipeline."})
                    : $t({defaultMessage: "Try a different Space or Topic name."}),
            selected_topic,
            can_continue: selected_topic?.input_availability === "available",
            selected_topic_has_sources: (selected_topic?.data_sources.length ?? 0) > 0,
            selected_topic_sources: selected_topic?.data_sources.map((source) => ({
                ...source,
                provider_initial: source.provider_name.slice(0, 1),
                has_warning: source_has_warning(source),
            })),
            selected_topic_source_count: selected_topic?.data_sources.length ?? 0,
            draft,
            output_destinations,
            cadence_daily: draft.cadence === "daily",
            cadence_weekdays: draft.cadence === "weekdays",
            cadence_weekly: draft.cadence === "weekly",
            same_topic,
            review_schedule: schedule_label(draft),
        }),
    );
}

function load_data(): void {
    loading = true;
    load_error = false;
    render();
    void channel.get({
        url: PIPELINES_URL,
        success(raw) {
            const response = z
                .object({
                    pipelines: z.array(pipeline_schema),
                    topics: z.array(topic_schema),
                    can_create: z.boolean(),
                })
                .parse(raw);
            pipelines = response.pipelines;
            topics = deduplicate_topics_for_testing(response.topics);
            can_create = response.can_create;
            loaded = true;
            loading = false;
            render();
        },
        error() {
            loading = false;
            load_error = true;
            render();
        },
    });
}

function begin_creation(): void {
    editing_pipeline = undefined;
    repairing_input = false;
    stage = "select";
    selected_topic = undefined;
    topic_query = "";
    draft = fresh_draft();
    render();
}

function begin_repair(pipeline_id: number): void {
    const pipeline = pipelines.find((item) => item.id === pipeline_id);
    if (pipeline === undefined) {
        return;
    }
    editing_pipeline = pipeline;
    repairing_input = true;
    stage = "select";
    selected_topic = undefined;
    topic_query = "";
    draft = {
        name: pipeline.name,
        instruction: pipeline.instruction,
        cadence: pipeline.cadence,
        weekday: pipeline.weekday,
        local_time: pipeline.local_time,
        timezone: pipeline.timezone,
        output_destination: pipeline.output_destination,
        output_topic: pipeline.output_topic,
    };
    render();
}

function begin_draft_edit(pipeline_id: number): void {
    const pipeline = pipelines.find((item) => item.id === pipeline_id);
    if (pipeline?.lifecycle_state !== "draft" || !pipeline.available_transitions.includes("edit")) {
        return;
    }
    editing_pipeline = pipeline;
    repairing_input = pipeline.input_availability === "topic_unavailable";
    draft = {
        name: pipeline.name,
        instruction: pipeline.instruction,
        cadence: pipeline.cadence,
        weekday: pipeline.weekday,
        local_time: pipeline.local_time,
        timezone: pipeline.timezone,
        output_destination: pipeline.output_destination,
        output_topic: pipeline.output_topic,
    };
    selected_topic = topics.find(
        (item) =>
            pipeline.input_destination !== null &&
            topic_key(item.input_destination, item.input_topic) ===
                topic_key(pipeline.input_destination, pipeline.input_topic),
    );
    stage = selected_topic?.input_availability === "available" ? "configure" : "select";
    topic_query = "";
    render();
}

function select_topic(destination: string, topic: string): void {
    const candidate = topics.find(
        (item) =>
            topic_key(item.input_destination, item.input_topic) === topic_key(destination, topic),
    );
    if (candidate?.input_availability !== "available") {
        return;
    }
    selected_topic = candidate;
    render();
}

function continue_from_topic(): void {
    if (selected_topic?.input_availability !== "available") {
        return;
    }
    if (editing_pipeline === undefined) {
        draft.name = $t({defaultMessage: "{topic} brief"}, {topic: selected_topic.input_topic});
        draft.instruction = $t({
            defaultMessage: "Summarize the most important updates and next steps.",
        });
        draft.output_destination = selected_topic.input_destination;
        draft.output_topic = selected_topic.input_topic;
    }
    stage = "configure";
    render();
}

function read_form(): void {
    draft = {
        ...draft,
        name: String($("#hover_pipeline_name").val() ?? "").trim(),
        instruction: String($("#hover_pipeline_instruction").val() ?? "").trim(),
        cadence: z
            .enum(["daily", "weekdays", "weekly"])
            .parse(String($("#hover_pipeline_cadence").val())),
        weekday:
            String($("#hover_pipeline_cadence").val()) === "weekly"
                ? Number($("#hover_pipeline_weekday").val() ?? 4)
                : null,
        local_time: String($("#hover_pipeline_time").val() ?? "09:00"),
        output_destination: String($("#hover_pipeline_output_destination").val() ?? ""),
        output_topic: String($("#hover_pipeline_output_topic").val() ?? "").trim(),
    };
}

function pipeline_request_data(
    lifecycle_state: "active" | "draft" | undefined,
): Record<string, string> {
    if (selected_topic === undefined) {
        return {};
    }
    return {
        input_destination_name: JSON.stringify(selected_topic.input_destination),
        input_topic: JSON.stringify(selected_topic.input_topic),
        name: JSON.stringify(draft.name),
        instruction: JSON.stringify(draft.instruction),
        cadence: JSON.stringify(draft.cadence),
        weekday: JSON.stringify(draft.weekday),
        local_time: JSON.stringify(draft.local_time),
        timezone: JSON.stringify(draft.timezone),
        output_destination_name: JSON.stringify(draft.output_destination),
        output_topic: JSON.stringify(draft.output_topic),
        ...(lifecycle_state !== undefined && {
            lifecycle_state: JSON.stringify(lifecycle_state),
        }),
    };
}

function persist_pipeline(lifecycle_state: "active" | "draft" | undefined): void {
    if (selected_topic === undefined) {
        return;
    }
    const $buttons = $(".hover-pipeline-submit, .hover-pipeline-save-draft").prop("disabled", true);
    if (lifecycle_state === "draft") {
        $(".hover-pipeline-save-draft").text($t({defaultMessage: "Saving…"}));
    }
    const editing_id = editing_pipeline?.id;
    const was_draft = editing_pipeline?.lifecycle_state === "draft";
    const submit = editing_id === undefined ? channel.post : channel.patch;
    void submit({
        url: pipeline_submission_target_for_testing(editing_id),
        data: pipeline_request_data(lifecycle_state),
        success(raw) {
            const saved = z.object({pipeline: pipeline_schema}).parse(raw).pipeline;
            pipelines =
                editing_id === undefined
                    ? [...pipelines, saved]
                    : pipelines.map((item) => (item.id === editing_id ? saved : item));
            pipeline_feedback.set(saved.id, {
                kind: "success",
                message:
                    lifecycle_state === "draft"
                        ? $t({defaultMessage: "Draft saved."})
                        : lifecycle_state === "active" && was_draft
                          ? $t({defaultMessage: "Pipeline activated."})
                          : editing_id === undefined
                            ? $t({defaultMessage: "Pipeline created."})
                            : $t({defaultMessage: "Pipeline repaired."}),
            });
            expanded_pipeline_ids.add(saved.id);
            editing_pipeline = undefined;
            repairing_input = false;
            stage = "index";
            render();
            focus_pipeline_row(saved.id);
        },
        error() {
            $buttons.prop("disabled", false);
            $(".hover-pipeline-save-draft").text($t({defaultMessage: "Save as draft"}));
            $(".hover-pipeline-request-status").text(
                $t({
                    defaultMessage:
                        "Could not save the pipeline. Review the details and try again.",
                }),
            );
        },
    });
}

function submit_pipeline(): void {
    persist_pipeline(
        repairing_input
            ? undefined
            : editing_pipeline === undefined || editing_pipeline.lifecycle_state === "draft"
              ? "active"
              : undefined,
    );
}

function save_draft(): void {
    if (stage === "configure") {
        read_form();
    }
    persist_pipeline("draft");
}

function focus_pipeline_row(pipeline_id: number): void {
    if (filtered_pipelines().some((pipeline) => pipeline.id === pipeline_id)) {
        $(`[data-pipeline-row="${pipeline_id}"]`).trigger("focus");
        return;
    }
    $(`[data-pipeline-filter="${pipeline_filter}"]`).trigger("focus");
}

export function lifecycle_transition_target_for_testing(
    transition: LifecycleTransition,
): Pipeline["lifecycle_state"] {
    return transition === "pause" ? "paused" : "active";
}

function transition_pipeline(pipeline_id: number, transition: LifecycleTransition): void {
    const pipeline = pipelines.find((item) => item.id === pipeline_id);
    if (
        pending_pipeline_id !== undefined ||
        !pipeline?.available_transitions.includes(transition)
    ) {
        return;
    }
    pending_pipeline_id = pipeline_id;
    pipeline_feedback.delete(pipeline_id);
    render();
    void channel.patch({
        url: pipeline_submission_target_for_testing(pipeline_id),
        data: {
            lifecycle_state: JSON.stringify(lifecycle_transition_target_for_testing(transition)),
        },
        success(raw) {
            const saved = z.object({pipeline: pipeline_schema}).parse(raw).pipeline;
            pipelines = pipelines.map((item) => (item.id === pipeline_id ? saved : item));
            pending_pipeline_id = undefined;
            pipeline_feedback.set(pipeline_id, {
                kind: "success",
                message:
                    transition === "pause"
                        ? $t({defaultMessage: "Pipeline paused."})
                        : transition === "resume"
                          ? $t({defaultMessage: "Pipeline resumed."})
                          : $t({defaultMessage: "Pipeline activated."}),
            });
            render();
            focus_pipeline_row(pipeline_id);
        },
        error() {
            pending_pipeline_id = undefined;
            pipeline_feedback.set(pipeline_id, {
                kind: "error",
                message:
                    transition === "pause"
                        ? $t({defaultMessage: "Could not pause this Pipeline. Try again."})
                        : $t({defaultMessage: "Could not resume this Pipeline. Try again."}),
            });
            render();
            focus_pipeline_row(pipeline_id);
        },
    });
}

export function pipeline_submission_target_for_testing(pipeline_id: number | undefined): string {
    return pipeline_id === undefined ? PIPELINES_URL : `${PIPELINES_URL}/${pipeline_id}`;
}

export function show(): void {
    visible = true;
    inbox_ui.hide();
    recent_view_ui.hide();
    $(
        "#hover-source-view, #hover-awareness-view, #hover-search-view, #hover-editions-view, #hover-data-sources-view, #message_feed_container, #compose",
    ).hide();
    $("#hover-pipelines-view").show();
    left_sidebar_navigation_area.select_top_left_corner_item(".top_left_pipelines");
    if (!loaded) {
        load_data();
    } else {
        render();
    }
}

export function hide(): void {
    if (!visible) {
        return;
    }
    visible = false;
    $("#hover-pipelines-view").hide();
    $("#message_feed_container, #compose").show();
}

export function initialize(): void {
    $("body").on("click", ".hover-pipeline-create", begin_creation);
    $("body").on("click", ".hover-pipeline-topic-choice", (event) => {
        const $choice = $(event.currentTarget);
        select_topic(String($choice.attr("data-space")), String($choice.attr("data-topic")));
    });
    $("body").on("click", ".hover-pipeline-topic-continue", continue_from_topic);
    $("body").on("input", ".hover-pipeline-topic-search", (event) => {
        topic_query = String($(event.currentTarget).val() ?? "");
        render();
        focus_input_at_end(".hover-pipeline-topic-search");
    });
    $("body").on("submit", "#hover_pipeline_configure_form", (event) => {
        event.preventDefault();
        read_form();
        stage = "review";
        render();
    });
    $("body").on("change", "#hover_pipeline_cadence", () => {
        read_form();
        render();
    });
    $("body").on(
        "input change",
        "#hover_pipeline_output_destination, #hover_pipeline_output_topic",
        () => {
            read_form();
            const same_topic =
                selected_topic !== undefined &&
                topic_key(selected_topic.input_destination, selected_topic.input_topic) ===
                    topic_key(draft.output_destination, draft.output_topic);
            $(".hover-pipeline-same-topic-note").prop("hidden", !same_topic);
        },
    );
    $("body").on("click", ".hover-pipeline-change-topic, .hover-pipeline-edit-topic", () => {
        stage = "select";
        render();
    });
    $("body").on("click", ".hover-pipeline-edit-configure", () => {
        stage = "configure";
        render();
    });
    $("body").on("click", ".hover-pipeline-submit", submit_pipeline);
    $("body").on("click", ".hover-pipeline-save-draft", save_draft);
    $("body").on("click", ".hover-pipeline-continue-setup", (event) => {
        begin_draft_edit(Number($(event.currentTarget).attr("data-pipeline-id")));
    });
    $("body").on("click", ".hover-pipeline-pause", (event) => {
        transition_pipeline(Number($(event.currentTarget).attr("data-pipeline-id")), "pause");
    });
    $("body").on("click", ".hover-pipeline-resume", (event) => {
        transition_pipeline(Number($(event.currentTarget).attr("data-pipeline-id")), "resume");
    });
    $("body").on("click", ".hover-pipeline-back", (event) => {
        const target = $(event.currentTarget).attr("data-pipeline-back");
        if (target === "index" || target === "select" || target === "configure") {
            stage = target;
            render();
        }
    });
    $("body").on("click", ".hover-pipeline-row-toggle", (event) => {
        const id = Number($(event.currentTarget).attr("data-pipeline-id"));
        if (expanded_pipeline_ids.has(id)) {
            expanded_pipeline_ids.delete(id);
        } else {
            expanded_pipeline_ids.add(id);
        }
        render();
    });
    $("body").on("click", ".hover-pipeline-repair-topic", (event) => {
        begin_repair(Number($(event.currentTarget).attr("data-pipeline-id")));
    });
    $("body").on("input", ".hover-pipeline-index-search", (event) => {
        index_query = String($(event.currentTarget).val() ?? "");
        render();
        focus_input_at_end(".hover-pipeline-index-search");
    });
    $("body").on("click", "[data-pipeline-filter]", (event) => {
        const value = $(event.currentTarget).attr("data-pipeline-filter");
        if (value === "all" || value === "active" || value === "draft" || value === "paused") {
            pipeline_filter = value;
            render();
        }
    });
}

export const test = {
    reset(): void {
        visible = false;
        loaded = false;
        loading = false;
        load_error = false;
        stage = "index";
        pipelines = [];
        topics = [];
        selected_topic = undefined;
        can_create = false;
        index_query = "";
        topic_query = "";
        pipeline_filter = "all";
        expanded_pipeline_ids.clear();
        draft = fresh_draft();
        editing_pipeline = undefined;
        repairing_input = false;
        pending_pipeline_id = undefined;
        pipeline_feedback.clear();
    },
};
