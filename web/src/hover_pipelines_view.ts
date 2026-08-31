import {$} from "jquery";
import * as z from "zod/mini";

import render_hover_pipelines_view from "../templates/hover_pipelines_view.hbs";

import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as stream_data from "./stream_data.ts";
import * as timerender from "./timerender.ts";

const connector_schema = z.object({
    id: z.number(),
    name: z.string(),
    provider_key: z.string(),
    provider_name: z.string(),
    provider_logo_url: z.nullable(z.string()),
    destination: z.nullable(z.string()),
    topic: z.string(),
    event_options: z.array(z.string()),
    state: z.enum(["active", "disabled", "needs_attention"]),
    reconciliation_state: z.enum(["canonical", "legacy", "ambiguous"]),
    health_status: z.enum(["unknown", "healthy", "degraded"]),
    last_successful_delivery: z.nullable(z.string()),
    last_delivery_attempt: z.nullable(z.string()),
    pipeline_name: z.nullable(z.string()),
});
const pipeline_schema = z.object({
    id: z.number(),
    name: z.string(),
    instruction: z.string(),
    connector_id: z.number(),
    source_name: z.string(),
    provider_key: z.string(),
    provider_name: z.string(),
    provider_logo_url: z.nullable(z.string()),
    source_destination: z.nullable(z.string()),
    source_topic: z.string(),
    event_options: z.array(z.string()),
    cadence: z.enum(["daily", "weekdays", "weekly"]),
    weekday: z.nullable(z.number()),
    local_time: z.string(),
    timezone: z.string(),
    output_destination: z.string(),
    output_topic: z.string(),
    status: z.enum(["active", "draft", "needs_attention"]),
    last_run_at: z.nullable(z.string()),
    date_created: z.string(),
});
type Connector = z.infer<typeof connector_schema>;
type Pipeline = z.infer<typeof pipeline_schema>;
type Stage = "index" | "select" | "configure" | "review";
type PipelineFilter = "all" | "active" | "draft";
type SourceFilter = "all" | "connected" | "attention";
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
const CONNECTORS_URL = "/json/hover/connectors";
let visible = false;
let loaded = false;
let loading = false;
let load_error = false;
let stage: Stage = "index";
let pipelines: Pipeline[] = [];
let connectors: Connector[] = [];
let connector: Connector | undefined;
let can_create = false;
let index_query = "";
let source_query = "";
let pipeline_filter: PipelineFilter = "all";
let source_filter: SourceFilter = "all";
let draft = fresh_draft();

function fresh_draft(): Draft {
    return {
        name: "",
        instruction: "",
        cadence: "daily",
        weekday: 4,
        local_time: "09:00",
        timezone: new Intl.DateTimeFormat().resolvedOptions().timeZone,
        output_destination: "",
        output_topic: "",
    };
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
function cadence_label(cadence: Pipeline["cadence"]): string {
    return cadence === "weekdays"
        ? $t({defaultMessage: "Weekdays"})
        : cadence === "weekly"
          ? $t({defaultMessage: "Every week"})
          : $t({defaultMessage: "Every day"});
}
function schedule_label(item: Pick<Pipeline, "cadence" | "weekday" | "local_time">): string {
    return item.cadence === "weekly"
        ? $t(
              {defaultMessage: "Every {weekday} at {time}"},
              {weekday: weekday_label(item.weekday), time: display_time(item.local_time)},
          )
        : $t(
              {defaultMessage: "{cadence} at {time}"},
              {cadence: cadence_label(item.cadence), time: display_time(item.local_time)},
          );
}
function source_status(source: Connector): {key: "active" | "needs_attention"; label: string} {
    const attention =
        source.state !== "active" ||
        source.reconciliation_state === "ambiguous" ||
        source.health_status === "degraded";
    return attention
        ? {key: "needs_attention", label: $t({defaultMessage: "Needs attention"})}
        : {key: "active", label: $t({defaultMessage: "Connected"})};
}
function source_last_event(source: Connector): string {
    const timestamp = source.last_successful_delivery ?? source.last_delivery_attempt;
    return timestamp === null
        ? $t({defaultMessage: "No events yet"})
        : timerender.relative_time_string_from_date(new Date(timestamp), true);
}
function title_case(value: string): string {
    const label = value.replaceAll("_", " ");
    return label.charAt(0).toLocaleUpperCase() + label.slice(1);
}

function filtered_pipelines(): Pipeline[] {
    const query = index_query.trim().toLocaleLowerCase();
    return pipelines.filter(
        (item) =>
            (pipeline_filter === "all" || item.status === pipeline_filter) &&
            `${item.name} ${item.instruction} ${item.source_name}`
                .toLocaleLowerCase()
                .includes(query),
    );
}
function selectable_sources(): Connector[] {
    const query = source_query.trim().toLocaleLowerCase();
    return connectors.filter((source) => {
        const status = source_status(source).key;
        const filter_match =
            source_filter === "all" ||
            (source_filter === "connected" && status === "active") ||
            (source_filter === "attention" && status === "needs_attention");
        return (
            source.pipeline_name === null &&
            filter_match &&
            `${source.name} ${source.provider_name} ${source.destination ?? ""} ${source.topic}`
                .toLocaleLowerCase()
                .includes(query)
        );
    });
}

export function source_selection_context_for_testing(
    source_rows: {id: number; name: string; pipeline_name: string | null}[],
    query: string,
): {source_ids: number[]; source_limit: number} {
    const normalized_query = query.trim().toLocaleLowerCase();
    return {
        source_ids: source_rows
            .filter(
                (source) =>
                    source.pipeline_name === null &&
                    source.name.toLocaleLowerCase().includes(normalized_query),
            )
            .map((source) => source.id),
        source_limit: 1,
    };
}

function render(): void {
    if (!visible) {
        return;
    }
    const output_destinations = stream_data
        .subscribed_subs()
        .filter((stream) => stream_data.can_post_messages_in_stream(stream))
        .map((stream) => ({name: stream.name, selected: stream.name === draft.output_destination}));
    const pipeline_rows = filtered_pipelines().map((item) => ({
        ...item,
        provider_initial: item.provider_name.slice(0, 1),
        schedule_label: schedule_label(item),
        status_label:
            item.status === "active"
                ? $t({defaultMessage: "Active"})
                : item.status === "draft"
                  ? $t({defaultMessage: "Draft"})
                  : $t({defaultMessage: "Needs attention"}),
        last_run_label:
            item.last_run_at === null
                ? $t({defaultMessage: "Not run yet"})
                : new Intl.DateTimeFormat(undefined, {
                      dateStyle: "medium",
                      timeStyle: "short",
                  }).format(new Date(item.last_run_at)),
    }));
    const source_rows = selectable_sources().map((source) => {
        const status = source_status(source);
        return {
            ...source,
            selected_class: source.id === connector?.id ? "is-selected" : "",
            status_key: status.key,
            status_label: status.label,
            last_event: source_last_event(source),
        };
    });
    $("#hover-pipelines-view").html(
        render_hover_pipelines_view({
            is_index: stage === "index",
            is_select: stage === "select",
            is_configure: stage === "configure",
            is_review: stage === "review",
            can_create,
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
            empty_heading: loading
                ? $t({defaultMessage: "Loading pipelines…"})
                : load_error
                  ? $t({defaultMessage: "Could not load pipelines"})
                  : pipelines.length === 0
                    ? $t({defaultMessage: "No pipelines yet"})
                    : $t({defaultMessage: "No pipelines match this view"}),
            empty_description:
                pipelines.length === 0
                    ? $t({defaultMessage: "Create one to turn connected updates into summaries."})
                    : $t({defaultMessage: "Try another search or status filter."}),
            source_query,
            sources: source_rows,
            has_sources: source_rows.length > 0,
            source_filter_all_class: source_filter === "all" ? "is-selected" : "",
            source_filter_connected_class: source_filter === "connected" ? "is-selected" : "",
            source_filter_attention_class: source_filter === "attention" ? "is-selected" : "",
            no_sources: !loading && source_rows.length === 0,
            connector,
            draft,
            output_destinations,
            cadence_daily: draft.cadence === "daily",
            cadence_weekdays: draft.cadence === "weekdays",
            cadence_weekly: draft.cadence === "weekly",
            weekday_friday: draft.weekday === 4,
            review_schedule: schedule_label(draft),
            events_label:
                connector?.event_options.length === 0
                    ? $t({defaultMessage: "All supported events"})
                    : connector?.event_options.map(title_case).join(", "),
            review_notice:
                connector === undefined
                    ? ""
                    : $t(
                          {
                              defaultMessage:
                                  "Hover will read new messages from {input} and post the summary to {output} at the next scheduled run.",
                          },
                          {
                              input: `${connector.destination ?? ""} › ${connector.topic}`,
                              output: `${draft.output_destination} › ${draft.output_topic}`,
                          },
                      ),
        }),
    );
}

function load_data(): void {
    loading = true;
    load_error = false;
    render();
    let pending = 2;
    const done = (): void => {
        pending -= 1;
        if (pending === 0) {
            loaded = true;
            loading = false;
            render();
        }
    };
    void channel.get({
        url: PIPELINES_URL,
        success(raw) {
            const response = z
                .object({pipelines: z.array(pipeline_schema), can_create: z.boolean()})
                .parse(raw);
            pipelines = response.pipelines;
            can_create = response.can_create;
            done();
        },
        error() {
            load_error = true;
            done();
        },
    });
    void channel.get({
        url: CONNECTORS_URL,
        success(raw) {
            connectors = z.object({connectors: z.array(connector_schema)}).parse(raw).connectors;
            done();
        },
        error() {
            load_error = true;
            done();
        },
    });
}

function begin_creation(): void {
    stage = "select";
    connector = undefined;
    source_query = "";
    source_filter = "all";
    draft = fresh_draft();
    render();
}
function select_source(source_id: number): void {
    connector = connectors.find((source) => source.id === source_id);
    render();
}
function continue_from_source(): void {
    if (connector === undefined || source_status(connector).key !== "active") {
        return;
    }
    draft.name =
        connector.provider_key === "github"
            ? $t({defaultMessage: "GitHub release brief"})
            : $t({defaultMessage: "{source} summary"}, {source: connector.name});
    draft.instruction =
        connector.provider_key === "github"
            ? $t({
                  defaultMessage:
                      "Summarize release progress, deployment blockers, and decisions that need follow-up.",
              })
            : $t({defaultMessage: "Summarize the most important updates and next steps."});
    draft.output_destination = connector.destination ?? "";
    draft.output_topic = draft.name;
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
function submit_pipeline(): void {
    if (connector === undefined) {
        return;
    }
    const $button = $(".hover-pipeline-submit").prop("disabled", true);
    void channel.post({
        url: PIPELINES_URL,
        data: {
            connector_id: JSON.stringify(connector.id),
            name: JSON.stringify(draft.name),
            instruction: JSON.stringify(draft.instruction),
            cadence: JSON.stringify(draft.cadence),
            weekday: JSON.stringify(draft.weekday),
            local_time: JSON.stringify(draft.local_time),
            timezone: JSON.stringify(draft.timezone),
            output_destination_name: JSON.stringify(draft.output_destination),
            output_topic: JSON.stringify(draft.output_topic),
        },
        success(raw) {
            const created = z.object({pipeline: pipeline_schema}).parse(raw).pipeline;
            pipelines = [...pipelines, created];
            connectors = connectors.map((source) =>
                source.id === connector?.id ? {...source, pipeline_name: created.name} : source,
            );
            stage = "index";
            render();
        },
        error() {
            $button.prop("disabled", false);
            $(".hover-pipeline-request-status").text(
                $t({
                    defaultMessage:
                        "Could not create the pipeline. Review the details and try again.",
                }),
            );
        },
    });
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
    $("body").on("click", ".hover-pipeline-source-choice", (event) => {
        select_source(Number($(event.currentTarget).attr("data-source-id")));
    });
    $("body").on("click", ".hover-pipeline-source-continue", continue_from_source);
    $("body").on("input", ".hover-pipeline-source-search", (event) => {
        source_query = String($(event.currentTarget).val() ?? "");
        render();
        $(".hover-pipeline-source-search").trigger("focus");
    });
    $("body").on("click", "[data-pipeline-source-filter]", (event) => {
        const value = $(event.currentTarget).attr("data-pipeline-source-filter");
        if (value === "all" || value === "connected" || value === "attention") {
            source_filter = value;
            render();
        }
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
    $("body").on("click", ".hover-pipeline-change-source, .hover-pipeline-edit-source", () => {
        stage = "select";
        render();
    });
    $("body").on("click", ".hover-pipeline-edit-configure", () => {
        stage = "configure";
        render();
    });
    $("body").on("click", ".hover-pipeline-submit", submit_pipeline);
    $("body").on("click", ".hover-pipeline-back", (event) => {
        const target = $(event.currentTarget).attr("data-pipeline-back");
        if (target === "index" || target === "select" || target === "configure") {
            stage = target;
            render();
        }
    });
    $("body").on("input", ".hover-pipeline-index-search", (event) => {
        index_query = String($(event.currentTarget).val() ?? "");
        render();
        $(".hover-pipeline-index-search").trigger("focus");
    });
    $("body").on("click", "[data-pipeline-filter]", (event) => {
        const value = $(event.currentTarget).attr("data-pipeline-filter");
        if (value === "all" || value === "active" || value === "draft") {
            pipeline_filter = value;
            render();
        }
    });
}
