import {$} from "jquery";
import * as z from "zod/mini";

import render_hover_pipelines_view from "../templates/hover_pipelines_view.hbs";

import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";

const connector_schema = z.object({
    id: z.number(),
    provider_key: z.string(),
    provider_name: z.string(),
    provider_logo_url: z.nullable(z.string()),
    destination: z.nullable(z.string()),
    topic: z.string(),
    event_options: z.array(z.string()),
    webhook_url: z.optional(z.string()),
});
const pipeline_schema = z.object({
    id: z.number(),
    name: z.string(),
    instruction: z.string(),
    connector_id: z.number(),
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
const connector_response_schema = z.object({connector: connector_schema});
const pipelines_response_schema = z.object({
    pipelines: z.array(pipeline_schema),
    can_create: z.boolean(),
});
const pipeline_response_schema = z.object({pipeline: pipeline_schema});

type Connector = z.infer<typeof connector_schema>;
type Pipeline = z.infer<typeof pipeline_schema>;
type Stage = "index" | "catalogue" | "setup" | "handoff" | "configure" | "review";
type PipelineFilter = "all" | "active" | "draft";
type Provider = (typeof realm)["realm_incoming_webhook_bots"][number] & {
    key: string;
    name: string;
};
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
let rendered_stage: Stage | undefined;
let pipelines: Pipeline[] = [];
let can_create = false;
let selected_provider: Provider | undefined;
let connector: Connector | undefined;
let provider_query = "";
let index_query = "";
let pipeline_filter: PipelineFilter = "all";
let draft = fresh_draft();

function fresh_draft(): Draft {
    const timezone = new Intl.DateTimeFormat().resolvedOptions().timeZone;
    return {
        name: "",
        instruction: "",
        cadence: "daily",
        weekday: 4,
        local_time: "09:00",
        timezone,
        output_destination: "",
        output_topic: "",
    };
}

function provider_from_registry(provider_key: string): Provider | undefined {
    const integration_key = provider_key === "rest_api" ? "json" : provider_key;
    const provider = realm.realm_incoming_webhook_bots.find(
        (item) => item.name === integration_key,
    );
    if (provider === undefined) {
        return undefined;
    }
    if (provider_key === "rest_api") {
        return {
            ...provider,
            key: "rest_api",
            name: $t({defaultMessage: "REST API"}),
            display_name: $t({defaultMessage: "REST API"}),
            description: $t({defaultMessage: "Internal tools and custom payloads"}),
            supports_event_filters: false,
            all_event_types: null,
        };
    }
    return {...provider, key: provider.name, name: provider.display_name};
}

function catalogue_providers(query: string): Provider[] {
    const normalized_query = query.trim().toLocaleLowerCase();
    if (normalized_query === "") {
        return [];
    }
    return realm.realm_incoming_webhook_bots
        .filter(
            (provider) =>
                provider.display_name.toLocaleLowerCase().includes(normalized_query) ||
                provider.description.toLocaleLowerCase().includes(normalized_query),
        )
        .map((provider) => ({...provider, key: provider.name, name: provider.display_name}))
        .toSorted((a, b) => a.name.localeCompare(b.name));
}

export function catalogue_context_for_testing(query: string): {
    has_results: boolean;
    provider_keys: string[];
    source_limit: number;
} {
    const providers = catalogue_providers(query);
    return {
        has_results: providers.length > 0,
        provider_keys: providers.map((provider) => provider.key),
        source_limit: 1,
    };
}

function title_case_event(event_name: string): string {
    const label = event_name.replaceAll("_", " ");
    return label.charAt(0).toLocaleUpperCase() + label.slice(1);
}

function display_time(time: string): string {
    const [hours = "9", minutes = "00"] = time.split(":");
    const hour = Number(hours);
    return `${hour % 12 || 12}:${minutes} ${hour >= 12 ? "PM" : "AM"}`;
}

function cadence_label(cadence: Pipeline["cadence"]): string {
    if (cadence === "weekdays") {
        return $t({defaultMessage: "Weekdays"});
    }
    if (cadence === "weekly") {
        return $t({defaultMessage: "Every week"});
    }
    return $t({defaultMessage: "Every day"});
}

function weekday_label(weekday: number | null): string {
    const labels = [
        $t({defaultMessage: "Monday"}),
        $t({defaultMessage: "Tuesday"}),
        $t({defaultMessage: "Wednesday"}),
        $t({defaultMessage: "Thursday"}),
        $t({defaultMessage: "Friday"}),
        $t({defaultMessage: "Saturday"}),
        $t({defaultMessage: "Sunday"}),
    ];
    return labels[weekday ?? 4] ?? labels[4]!;
}

function schedule_label(item: Pipeline): string {
    if (item.cadence === "weekly") {
        return $t(
            {defaultMessage: "Every {weekday} at {time}"},
            {weekday: weekday_label(item.weekday), time: display_time(item.local_time)},
        );
    }
    return $t(
        {defaultMessage: "{cadence} at {time}"},
        {cadence: cadence_label(item.cadence), time: display_time(item.local_time)},
    );
}

function setup_intro(provider: Provider): string {
    if (provider.key === "slack_incoming") {
        return $t({
            defaultMessage:
                "We’ll create a URL you can paste into any service that supports Slack Incoming Webhooks.",
        });
    }
    if (provider.key === "rest_api") {
        return $t({
            defaultMessage:
                "Create a dedicated endpoint for an internal tool or a service with a custom JSON payload.",
        });
    }
    return $t(
        {defaultMessage: "Choose where {provider} updates should appear in Hover."},
        {provider: provider.name},
    );
}

function default_topic(provider: Provider): string {
    if (provider.key === "slack_incoming") {
        return $t({defaultMessage: "Signals"});
    }
    if (provider.key === "rest_api") {
        return $t({defaultMessage: "Internal tools"});
    }
    return $t({defaultMessage: "{provider} activity"}, {provider: provider.name});
}

function filtered_pipelines(): Pipeline[] {
    const query = index_query.trim().toLocaleLowerCase();
    return pipelines.filter((item) => {
        const matches_filter =
            pipeline_filter === "all" ||
            (pipeline_filter === "active" && item.status === "active") ||
            (pipeline_filter === "draft" && item.status === "draft");
        return (
            matches_filter &&
            [item.name, item.instruction, item.provider_name]
                .join(" ")
                .toLocaleLowerCase()
                .includes(query)
        );
    });
}

function render(): void {
    if (!visible) {
        return;
    }
    const providers = catalogue_providers(provider_query);
    const destinations = stream_data
        .subscribed_subs()
        .filter((stream) => !stream.is_archived)
        .map((stream) => ({
            name: stream.name,
            selected:
                stream.name ===
                (stage === "setup"
                    ? (connector?.destination ?? draft.output_destination)
                    : draft.output_destination),
        }));
    const provider = selected_provider;
    const events =
        provider?.all_event_types?.map((event) => ({
            name: event,
            label: title_case_event(event),
            selected:
                connector === undefined ||
                connector.event_options.length === 0 ||
                connector.event_options.includes(event),
        })) ?? [];
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
    const stage_changed = rendered_stage !== stage;
    $("#hover-pipelines-view").html(
        render_hover_pipelines_view({
            is_index: stage === "index",
            is_catalogue: stage === "catalogue",
            is_source_setup: stage === "setup",
            is_handoff: stage === "handoff",
            is_configure: stage === "configure",
            is_review: stage === "review",
            can_create,
            step_one_active: stage === "catalogue" || stage === "setup",
            step_one_complete: stage === "handoff" || stage === "configure" || stage === "review",
            step_two_active: stage === "configure",
            step_two_complete: stage === "review",
            step_three_active: stage === "review",
            provider_query,
            providers,
            has_provider_results: providers.length > 0,
            slack_logo_url: provider_from_registry("slack_incoming")?.logo_url,
            provider,
            has_connector: connector !== undefined,
            setup_intro: provider === undefined ? "" : setup_intro(provider),
            connect_heading:
                provider === undefined
                    ? ""
                    : $t({defaultMessage: "Connect {provider}"}, {provider: provider.name}),
            source_topic: connector?.topic ?? (provider === undefined ? "" : default_topic(provider)),
            destinations,
            output_destinations: destinations,
            events,
            has_events: events.length > 0,
            event_filter_label:
                provider === undefined
                    ? ""
                    : $t(
                          {defaultMessage: "Choose {provider} events"},
                          {provider: provider.name},
                      ),
            connector,
            back_to_provider_configuration:
                connector === undefined
                    ? ""
                    : $t(
                          {defaultMessage: "Back to {provider} configuration"},
                          {provider: connector.provider_name},
                      ),
            handoff_heading:
                connector === undefined
                    ? ""
                    : $t(
                          {defaultMessage: "Add the webhook to {provider}"},
                          {provider: connector.provider_name},
                      ),
            handoff_subtitle:
                connector === undefined
                    ? ""
                    : $t(
                          {
                              defaultMessage:
                                  "Copy this URL into your {provider} webhook settings. This pipeline uses one data source.",
                          },
                          {provider: connector.provider_name},
                      ),
            finish_setup_heading:
                connector === undefined
                    ? ""
                    : $t(
                          {defaultMessage: "Finish setup in {provider}"},
                          {provider: connector.provider_name},
                      ),
            is_github: connector?.provider_key === "github",
            draft,
            cadence_daily: draft.cadence === "daily",
            cadence_weekdays: draft.cadence === "weekdays",
            cadence_weekly: draft.cadence === "weekly",
            weekday_monday: draft.weekday === 0,
            weekday_tuesday: draft.weekday === 1,
            weekday_wednesday: draft.weekday === 2,
            weekday_thursday: draft.weekday === 3,
            weekday_friday: draft.weekday === 4,
            weekday_saturday: draft.weekday === 5,
            weekday_sunday: draft.weekday === 6,
            events_label:
                connector?.event_options.length === 0
                    ? $t(
                          {defaultMessage: "All supported {provider} events"},
                          {provider: connector.provider_name ?? ""},
                      )
                    : connector?.event_options.map(title_case_event).join(", "),
            review_schedule:
                draft.cadence === "weekly"
                    ? $t(
                          {defaultMessage: "Every {weekday} at {time}"},
                          {
                              weekday: weekday_label(draft.weekday),
                              time: display_time(draft.local_time),
                          },
                      )
                    : `${cadence_label(draft.cadence)} at ${display_time(draft.local_time)}`,
            review_notice:
                connector === undefined
                    ? ""
                    : $t(
                          {
                              defaultMessage:
                                  "Once created, Hover will collect {provider} activity and post the first summary at the next scheduled run.",
                          },
                          {provider: connector.provider_name},
                      ),
            index_query,
            pipelines: pipeline_rows,
            filter_all: pipeline_filter === "all",
            filter_active: pipeline_filter === "active",
            filter_draft: pipeline_filter === "draft",
            empty_heading: loading
                ? $t({defaultMessage: "Loading pipelines…"})
                : load_error
                  ? $t({defaultMessage: "Could not load pipelines"})
                : pipelines.length === 0
                  ? $t({defaultMessage: "No pipelines yet"})
                  : $t({defaultMessage: "No pipelines match this view"}),
            empty_description: loading
                ? ""
                : load_error
                  ? $t({defaultMessage: "Try again."})
                : pipelines.length === 0
                  ? $t({defaultMessage: "Create one to turn connected updates into summaries."})
                  : $t({defaultMessage: "Try another search or status filter."}),
        }),
    );
    rendered_stage = stage;
    if (stage_changed) {
        const heading = document.querySelector<HTMLElement>(
            "#hover-pipelines-view .hover-pipeline-stage h2, #hover-pipelines-view h1",
        );
        heading?.setAttribute("tabindex", "-1");
        heading?.focus({preventScroll: true});
    }
}

function load_pipelines(): void {
    loading = true;
    load_error = false;
    render();
    void channel.get({
        url: PIPELINES_URL,
        success(raw_data) {
            const response = pipelines_response_schema.parse(raw_data);
            pipelines = response.pipelines;
            can_create = response.can_create;
            loaded = true;
            loading = false;
            load_error = false;
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
    stage = "catalogue";
    selected_provider = undefined;
    connector = undefined;
    provider_query = "";
    draft = fresh_draft();
    render();
    $(".hover-pipeline-provider-search").trigger("focus");
}

function set_default_draft(provider: Provider, destination: string): void {
    const provider_name = provider.name;
    draft.name =
        provider.key === "github"
            ? $t({defaultMessage: "GitHub release brief"})
            : $t({defaultMessage: "{provider} summary"}, {provider: provider_name});
    draft.instruction =
        provider.key === "github"
            ? $t({
                  defaultMessage:
                      "Summarize release progress, deployment blockers, and decisions that need follow-up.",
              })
            : $t(
                  {defaultMessage: "Summarize the most important {provider} updates and next steps."},
                  {provider: provider_name},
              );
    draft.output_destination = destination;
    draft.output_topic = draft.name;
}

function selected_events(): string[] {
    const provider = selected_provider;
    if (provider?.all_event_types === null || provider?.all_event_types === undefined) {
        return [];
    }
    const selected = $(".hover-pipeline-event-options input:checked")
        .map((_index, element) => String($(element).val()))
        .get();
    return selected.length === provider.all_event_types.length ? [] : selected;
}

function submit_source(): void {
    const provider = selected_provider;
    if (provider === undefined) {
        return;
    }
    const destination_name = String($(".hover-pipeline-source-destination").val() ?? "");
    const topic = String($(".hover-pipeline-source-topic").val() ?? "").trim();
    if (
        provider.all_event_types !== null &&
        provider.all_event_types !== undefined &&
        $(".hover-pipeline-event-options input:checked").length === 0
    ) {
        $(".hover-pipeline-request-status").text(
            $t({defaultMessage: "Choose at least one event."}),
        );
        return;
    }
    const $button = $("#hover_pipeline_source_form button[type='submit']").prop("disabled", true);
    const creating_connector = connector === undefined;
    const data = {
        ...(creating_connector ? {provider_key: JSON.stringify(provider.key)} : {}),
        destination_name: JSON.stringify(destination_name),
        topic: JSON.stringify(topic),
        event_options: JSON.stringify(selected_events()),
    };
    const request = creating_connector ? channel.post : channel.patch;
    void request({
        url: creating_connector ? CONNECTORS_URL : `${CONNECTORS_URL}/${connector!.id}`,
        data,
        success(raw_data) {
            connector = connector_response_schema.parse(raw_data).connector;
            if (creating_connector) {
                set_default_draft(provider, destination_name);
            }
            stage = "handoff";
            render();
        },
        error() {
            $button.prop("disabled", false);
            $(".hover-pipeline-request-status").text(
                $t({defaultMessage: "Could not save the webhook settings. Check these values."}),
            );
        },
    });
}

function read_configure_form(): void {
    draft = {
        ...draft,
        name: String($("#hover_pipeline_name").val() ?? "").trim(),
        instruction: String($("#hover_pipeline_instruction").val() ?? "").trim(),
        cadence: String($("#hover_pipeline_cadence").val()) as Draft["cadence"],
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
        success(raw_data) {
            const created = pipeline_response_schema.parse(raw_data).pipeline;
            pipelines = [...pipelines, created];
            stage = "index";
            render();
        },
        error() {
            $button.prop("disabled", false);
            $(".hover-pipeline-request-status").text(
                $t({defaultMessage: "Could not create the pipeline. Review the details and try again."}),
            );
        },
    });
}

export function show(): void {
    visible = true;
    inbox_ui.hide();
    recent_view_ui.hide();
    $(
        "#hover-source-view, #hover-awareness-view, #hover-search-view, #hover-editions-view, #message_feed_container, #compose",
    ).hide();
    $("#hover-pipelines-view").show();
    left_sidebar_navigation_area.select_top_left_corner_item(".top_left_pipelines");
    if (!loaded) {
        load_pipelines();
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
    $("body").on("input", ".hover-pipeline-provider-search", (event) => {
        provider_query = String($(event.currentTarget).val() ?? "");
        render();
        const input = document.querySelector<HTMLInputElement>(".hover-pipeline-provider-search");
        input?.focus();
        input?.setSelectionRange(provider_query.length, provider_query.length);
    });
    $("body").on("click", ".hover-pipeline-provider-choice", (event) => {
        const provider_key = String($(event.currentTarget).attr("data-provider-key"));
        selected_provider = provider_from_registry(provider_key);
        if (selected_provider === undefined) {
            return;
        }
        stage = "setup";
        render();
    });
    $("body").on("submit", "#hover_pipeline_source_form", (event) => {
        event.preventDefault();
        submit_source();
    });
    $("body").on("click", ".hover-pipeline-copy", () => {
        const url = connector?.webhook_url;
        if (url === undefined) {
            return;
        }
        void navigator.clipboard.writeText(url).then(() => {
            $(".hover-pipeline-copy").text($t({defaultMessage: "Copied"}));
        });
    });
    $("body").on("click", ".hover-pipeline-to-configure", () => {
        stage = "configure";
        render();
    });
    $("body").on("submit", "#hover_pipeline_configure_form", (event) => {
        event.preventDefault();
        read_configure_form();
        stage = "review";
        render();
    });
    $("body").on("click", ".hover-pipeline-submit", submit_pipeline);
    $("body").on("click", ".hover-pipeline-change-source, .hover-pipeline-edit-source", () => {
        stage = "setup";
        render();
    });
    $("body").on("click", ".hover-pipeline-edit-configure", () => {
        stage = "configure";
        render();
    });
    $("body").on("change", "#hover_pipeline_cadence", () => {
        read_configure_form();
        render();
        $("#hover_pipeline_cadence").trigger("focus");
    });
    $("body").on("click", ".hover-pipeline-back", (event) => {
        const target = $(event.currentTarget).attr("data-pipeline-back");
        if (target === "catalogue" || target === "setup" || target === "handoff" || target === "configure") {
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
            $(`[data-pipeline-filter='${value}']`).trigger("focus");
        }
    });
}
