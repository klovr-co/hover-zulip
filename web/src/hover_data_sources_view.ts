import {$} from "jquery";
import * as z from "zod/mini";

import render_hover_data_sources_view from "../templates/hover_data_sources_view.hbs";

import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
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
    webhook_url: z.optional(z.string()),
});
type Connector = z.infer<typeof connector_schema>;
type Provider = (typeof realm)["realm_incoming_webhook_bots"][number] & {key: string; name: string};
type Stage = "index" | "catalogue" | "setup" | "handoff";
type SourceFilter = "all" | "connected" | "attention";

const CONNECTORS_URL = "/json/hover/connectors";
let visible = false;
let loaded = false;
let loading = false;
let load_error = false;
let stage: Stage = "index";
let sources: Connector[] = [];
let connector: Connector | undefined;
let provider: Provider | undefined;
let provider_query = "";
let index_query = "";
let source_filter: SourceFilter = "all";
let setup_name = "";
let setup_destination = "";
let setup_topic = "";
let topic_menu_open = false;
let setup_error = "";

function focus_input_at_end(selector: string): void {
    const input = $(selector).trigger("focus").get(0);
    if (input instanceof HTMLInputElement) {
        input.setSelectionRange(input.value.length, input.value.length);
    }
}

function provider_from_registry(provider_key: string): Provider | undefined {
    const key = provider_key === "rest_api" ? "json" : provider_key;
    const item = realm.realm_incoming_webhook_bots.find((candidate) => candidate.name === key);
    if (item === undefined) {
        return undefined;
    }
    if (provider_key === "rest_api") {
        return {
            ...item,
            key: "rest_api",
            name: $t({defaultMessage: "REST API"}),
            display_name: $t({defaultMessage: "REST API"}),
            description: $t({defaultMessage: "Internal tools and custom payloads"}),
            supports_event_filters: false,
            all_event_types: null,
        };
    }
    return {...item, key: item.name, name: item.display_name};
}

function catalogue_providers(query: string): Provider[] {
    const normalized = query.trim().toLocaleLowerCase();
    if (normalized === "") {
        return [];
    }
    return realm.realm_incoming_webhook_bots
        .filter((item) =>
            `${item.display_name} ${item.description}`.toLocaleLowerCase().includes(normalized),
        )
        .map((item) => ({...item, key: item.name, name: item.display_name}))
        .toSorted((a, b) => a.name.localeCompare(b.name));
}

export function catalogue_context_for_testing(query: string): {
    has_results: boolean;
    provider_keys: string[];
} {
    const providers = catalogue_providers(query);
    return {has_results: providers.length > 0, provider_keys: providers.map((item) => item.key)};
}

function title_case(value: string): string {
    const label = value.replaceAll("_", " ");
    return label.charAt(0).toLocaleUpperCase() + label.slice(1);
}

function status(source: Connector): {key: "active" | "needs_attention"; label: string} {
    const attention =
        source.state !== "active" ||
        source.reconciliation_state === "ambiguous" ||
        source.health_status === "degraded";
    return attention
        ? {key: "needs_attention", label: $t({defaultMessage: "Needs attention"})}
        : {key: "active", label: $t({defaultMessage: "Connected"})};
}

function last_event(source: Connector): string {
    const timestamp = source.last_successful_delivery ?? source.last_delivery_attempt;
    return timestamp === null
        ? $t({defaultMessage: "No events yet"})
        : timerender.relative_time_string_from_date(new Date(timestamp), true);
}

function filtered_sources(): Connector[] {
    const query = index_query.trim().toLocaleLowerCase();
    return sources.filter((source) => {
        const source_status = status(source).key;
        const matches_filter =
            source_filter === "all" ||
            (source_filter === "connected" && source_status === "active") ||
            (source_filter === "attention" && source_status === "needs_attention");
        return (
            matches_filter &&
            `${source.name} ${source.provider_name} ${source.destination ?? ""} ${source.topic}`
                .toLocaleLowerCase()
                .includes(query)
        );
    });
}

function default_topic(selected: Provider): string {
    if (selected.key === "slack_incoming") {
        return $t({defaultMessage: "Signals"});
    }
    if (selected.key === "rest_api") {
        return $t({defaultMessage: "Internal tools"});
    }
    return $t({defaultMessage: "{provider} activity"}, {provider: selected.name});
}

function setup_topic_options(): string[] {
    const stream = stream_data.subscribed_subs().find((item) => item.name === setup_destination);
    if (stream === undefined) {
        return [];
    }
    return stream_topic_history.get_recent_topic_names(stream.stream_id);
}

function render(): void {
    if (!visible) {
        return;
    }
    const providers = catalogue_providers(provider_query);
    const rows = filtered_sources().map((source) => {
        const source_status = status(source);
        return {
            ...source,
            provider_initial: source.provider_name.slice(0, 1),
            provider_description:
                provider_from_registry(source.provider_key)?.description ?? source.provider_name,
            status_key: source_status.key,
            status_label: source_status.label,
            last_event: last_event(source),
        };
    });
    const destinations = stream_data
        .subscribed_subs()
        .filter((stream) => stream_data.can_post_messages_in_stream(stream))
        .map((stream) => ({name: stream.name, selected: stream.name === setup_destination}));
    const topic_options = setup_topic_options().map((name) => ({name}));
    const destination_preview =
        setup_destination === "" || setup_topic.trim() === ""
            ? $t({defaultMessage: "Choose a Space and Topic to see the publishing destination."})
            : $t(
                  {defaultMessage: "{source} syncs into {space} › {topic}"},
                  {
                      source:
                          setup_name !== ""
                              ? setup_name
                              : (provider?.name ?? $t({defaultMessage: "This data source"})),
                      space: setup_destination,
                      topic: setup_topic.trim(),
                  },
              );
    const events =
        provider?.all_event_types?.map((name) => ({name, label: title_case(name)})) ?? [];
    $("#hover-data-sources-view").html(
        render_hover_data_sources_view({
            is_index: stage === "index",
            is_catalogue: stage === "catalogue",
            is_setup: stage === "setup",
            is_handoff: stage === "handoff",
            step_one_class: stage === "catalogue" ? "is-active" : "is-complete",
            step_two_class:
                stage === "setup" ? "is-active" : stage === "handoff" ? "is-complete" : "",
            step_three_class: stage === "handoff" ? "is-active" : "",
            step_one_complete: stage !== "catalogue",
            step_two_complete: stage === "handoff",
            index_query,
            filter_all_class: source_filter === "all" ? "is-selected" : "",
            filter_connected_class: source_filter === "connected" ? "is-selected" : "",
            filter_attention_class: source_filter === "attention" ? "is-selected" : "",
            sources: rows,
            has_sources: rows.length > 0,
            empty_heading: loading
                ? $t({defaultMessage: "Loading data sources…"})
                : load_error
                  ? $t({defaultMessage: "Could not load data sources"})
                  : sources.length === 0
                    ? $t({defaultMessage: "No data sources yet"})
                    : $t({defaultMessage: "No data sources match this view"}),
            empty_description:
                sources.length === 0
                    ? $t({defaultMessage: "Add one to publish webhook events into Hover."})
                    : $t({defaultMessage: "Try another search or status filter."}),
            provider_query,
            providers,
            has_provider_results: providers.length > 0,
            slack_logo_url: provider_from_registry("slack_incoming")?.logo_url,
            provider,
            destinations,
            has_destinations: destinations.length > 0,
            permission_disabled: destinations.length === 0,
            source_name: setup_name,
            source_topic: setup_topic,
            topic_options,
            has_topic_options: topic_options.length > 0,
            topic_menu_open,
            destination_preview,
            setup_error,
            events,
            has_events: events.length > 0,
            connect_heading:
                provider === undefined
                    ? ""
                    : $t({defaultMessage: "Connect {provider}"}, {provider: provider.name}),
            setup_intro: $t({
                defaultMessage: "Choose where each incoming event should appear in Hover.",
            }),
            event_filter_label:
                provider === undefined
                    ? ""
                    : $t({defaultMessage: "Choose {provider} events"}, {provider: provider.name}),
            connector,
            back_to_configuration:
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
            finish_setup_heading:
                connector === undefined
                    ? ""
                    : $t(
                          {defaultMessage: "Finish setup in {provider}"},
                          {provider: connector.provider_name},
                      ),
        }),
    );
}

function load_sources(): void {
    loading = true;
    load_error = false;
    render();
    void channel.get({
        url: CONNECTORS_URL,
        success(raw) {
            sources = z.object({connectors: z.array(connector_schema)}).parse(raw).connectors;
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

function selected_events(): string[] {
    if (provider?.all_event_types === null || provider?.all_event_types === undefined) {
        return [];
    }
    const selected = $(".hover-pipeline-event-options input:checked")
        .map((_i, element) => String($(element).val()))
        .get();
    return selected.length === provider.all_event_types.length ? [] : selected;
}

function update_event_selection_toggle($options: JQuery): void {
    const $events = $options.find("input[type='checkbox']");
    const all_selected =
        $events.length > 0 && $events.get().every((event) => $(event).prop("checked") === true);
    $options
        .find(".hover-pipeline-event-selection-toggle")
        .text(
            all_selected
                ? $t({defaultMessage: "Deselect all"})
                : $t({defaultMessage: "Select all"}),
        );
}

function submit_source(): void {
    if (provider === undefined) {
        return;
    }
    setup_name = String($(".hover-data-source-name").val() ?? "").trim();
    setup_destination = String($(".hover-data-source-destination").val() ?? "");
    setup_topic = String($(".hover-data-source-topic").val() ?? "").trim();
    if (setup_name === "" || setup_destination === "" || setup_topic === "") {
        setup_error = $t({
            defaultMessage: "Choose a destination Space and Topic before continuing.",
        });
        render();
        return;
    }
    const $button = $("#hover_data_source_form button[type='submit']").prop("disabled", true);
    void channel.post({
        url: CONNECTORS_URL,
        data: {
            provider_key: JSON.stringify(provider.key),
            name: JSON.stringify(setup_name),
            destination_name: JSON.stringify(setup_destination),
            topic: JSON.stringify(setup_topic),
            event_options: JSON.stringify(selected_events()),
        },
        success(raw) {
            connector = z.object({connector: connector_schema}).parse(raw).connector;
            sources = [...sources, connector];
            stage = "handoff";
            render();
        },
        error() {
            $button.prop("disabled", false);
            $(".hover-pipeline-request-status").text(
                $t({defaultMessage: "Could not create the data source. Check these values."}),
            );
        },
    });
}

export function show(): void {
    visible = true;
    inbox_ui.hide();
    recent_view_ui.hide();
    $(
        "#hover-source-view, #hover-awareness-view, #hover-search-view, #hover-editions-view, #hover-pipelines-view, #message_feed_container, #compose",
    ).hide();
    $("#hover-data-sources-view").show();
    left_sidebar_navigation_area.select_top_left_corner_item(".top_left_data_sources");
    if (!loaded) {
        load_sources();
    } else {
        render();
    }
}

export function hide(): void {
    if (!visible) {
        return;
    }
    visible = false;
    $("#hover-data-sources-view").hide();
    $("#message_feed_container, #compose").show();
}

export function initialize(): void {
    $("body").on("click", ".hover-data-source-create", () => {
        stage = "catalogue";
        provider = undefined;
        connector = undefined;
        provider_query = "";
        render();
    });
    $("body").on("input", ".hover-data-source-provider-search", (event) => {
        provider_query = String($(event.currentTarget).val() ?? "");
        render();
        focus_input_at_end(".hover-data-source-provider-search");
    });
    $("body").on("click", ".hover-data-source-provider-choice", (event) => {
        provider = provider_from_registry(String($(event.currentTarget).attr("data-provider-key")));
        if (provider !== undefined) {
            setup_name = provider.name;
            setup_topic = default_topic(provider);
            setup_destination =
                stream_data
                    .subscribed_subs()
                    .find((stream) => stream_data.can_post_messages_in_stream(stream))?.name ?? "";
            topic_menu_open = false;
            setup_error = "";
            stage = "setup";
            render();
        }
    });
    $("body").on("submit", "#hover_data_source_form", (event) => {
        event.preventDefault();
        submit_source();
    });
    $("body").on("click", ".hover-pipeline-event-selection-toggle", (event) => {
        const $options = $(event.currentTarget).closest(".hover-pipeline-event-options");
        const $events = $options.find<HTMLInputElement>("input[type='checkbox']");
        const should_select = $events.get().some((event) => !event.checked);
        $events.prop("checked", should_select);
        update_event_selection_toggle($options);
    });
    $("body").on("change", ".hover-pipeline-event-options input[type='checkbox']", (event) => {
        update_event_selection_toggle(
            $(event.currentTarget).closest(".hover-pipeline-event-options"),
        );
    });
    $("body").on("input", ".hover-data-source-name", (event) => {
        setup_name = String($(event.currentTarget).val() ?? "");
        $(".hover-data-source-destination-preview strong").text(
            `${setup_name !== "" ? setup_name : (provider?.name ?? "")} syncs into ${setup_destination} › ${setup_topic}`,
        );
    });
    $("body").on("change", ".hover-data-source-destination", (event) => {
        setup_destination = String($(event.currentTarget).val() ?? "");
        topic_menu_open = true;
        render();
        $(".hover-data-source-topic").trigger("focus");
    });
    $("body").on("focus click", ".hover-data-source-topic", () => {
        if (!topic_menu_open) {
            topic_menu_open = true;
            render();
            $(".hover-data-source-topic").trigger("focus");
        }
    });
    $("body").on("input", ".hover-data-source-topic", (event) => {
        setup_topic = String($(event.currentTarget).val() ?? "");
        setup_error = "";
        $(".hover-data-source-destination-preview strong").text(
            `${setup_name !== "" ? setup_name : (provider?.name ?? "")} syncs into ${setup_destination} › ${setup_topic}`,
        );
    });
    $("body").on("click", ".hover-data-source-topic-option", (event) => {
        setup_topic = $(event.currentTarget).attr("data-topic") ?? "";
        topic_menu_open = false;
        render();
    });
    $("body").on("click", ".hover-data-source-copy", () => {
        if (connector?.webhook_url !== undefined) {
            void navigator.clipboard.writeText(connector.webhook_url);
        }
    });
    $("body").on("click", ".hover-data-source-finish", () => {
        stage = "index";
        render();
    });
    $("body").on("click", ".hover-data-source-back", (event) => {
        const target = $(event.currentTarget).attr("data-source-back");
        if (target === "index" || target === "catalogue" || target === "setup") {
            stage = target;
            render();
        }
    });
    $("body").on("input", ".hover-data-source-index-search", (event) => {
        index_query = String($(event.currentTarget).val() ?? "");
        render();
        focus_input_at_end(".hover-data-source-index-search");
    });
    $("body").on("click", "[data-source-filter]", (event) => {
        const value = $(event.currentTarget).attr("data-source-filter");
        if (value === "all" || value === "connected" || value === "attention") {
            source_filter = value;
            render();
        }
    });
}
