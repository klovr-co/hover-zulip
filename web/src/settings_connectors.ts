import {$} from "jquery";
import * as z from "zod/mini";

import render_connector_catalog from "../templates/settings/connector_catalog.hbs";
import render_connector_empty_row from "../templates/settings/connector_empty_row.hbs";
import render_connector_handoff from "../templates/settings/connector_handoff.hbs";
import render_connector_modal_stage from "../templates/settings/connector_modal_stage.hbs";
import render_connector_row from "../templates/settings/connector_row.hbs";
import render_connector_setup from "../templates/settings/connector_setup.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";

const connector_schema = z.object({
    id: z.number(),
    name: z.string(),
    provider_key: z.string(),
    provider_name: z.string(),
    provider_logo_url: z.nullable(z.string()),
    setup_instructions_url: z.nullable(z.string()),
    credential_identity_id: z.number(),
    destination: z.nullable(z.string()),
    destination_id: z.nullable(z.number()),
    topic: z.string(),
    event_options: z.array(z.string()),
    state: z.enum(["active", "disabled", "needs_attention"]),
    reconciliation_state: z.enum(["canonical", "legacy", "ambiguous"]),
    health_status: z.enum(["unknown", "healthy", "degraded"]),
    last_delivery_status: z.enum(["never", "success", "failure"]),
    owner: z.nullable(z.string()),
    owner_id: z.nullable(z.number()),
    is_owner: z.boolean(),
    can_manage: z.boolean(),
    last_successful_delivery: z.nullable(z.string()),
    last_delivery_attempt: z.nullable(z.string()),
    date_updated: z.string(),
    webhook_url: z.optional(z.string()),
});

const connector_list_response_schema = z.object({connectors: z.array(connector_schema)});
const connector_response_schema = z.object({connector: connector_schema});

export type Connector = z.infer<typeof connector_schema>;
type Provider = (typeof realm)["realm_incoming_webhook_bots"][number] & {
    key: string;
    name: string;
};
type ConnectorMode = "create" | "reconcile" | "update";
type ConnectorTab = "all" | "yours";

const CONNECTORS_URL = "/json/hover/connectors";

let connectors: Connector[] = [];
let modal_connector: Connector | undefined;
let modal_mode: ConnectorMode = "create";
let modal_provider: Provider | undefined;

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
    show_fallbacks: boolean;
    provider_keys: string[];
} {
    const providers = catalogue_providers(query);
    return {
        has_results: providers.length > 0,
        show_fallbacks: providers.length === 0,
        provider_keys: providers.map((provider) => provider.key),
    };
}

function render_catalogue(query: string): string {
    const providers = catalogue_providers(query);
    return render_connector_catalog({
        query,
        providers,
        has_results: providers.length > 0,
        slack_logo_url: provider_from_registry("slack_incoming")?.logo_url,
    });
}

function active_tab($container: JQuery): ConnectorTab {
    const selected_tab = $container.find(".tab-switcher .selected").attr("data-tab-key");
    if (selected_tab === "yours") {
        return "yours";
    }
    if (selected_tab === "all") {
        return "all";
    }
    return $container.attr("id")?.startsWith("personal-") === true ? "yours" : "all";
}

function connector_status(connector: Connector): {key: string; label: string} {
    if (connector.state === "disabled") {
        return {key: "disabled", label: $t({defaultMessage: "Disabled"})};
    }
    if (
        connector.state === "needs_attention" ||
        connector.reconciliation_state === "ambiguous" ||
        connector.health_status === "degraded"
    ) {
        return {key: "attention", label: $t({defaultMessage: "Needs attention"})};
    }
    return {key: "active", label: $t({defaultMessage: "Active"})};
}

function last_update(connector: Connector): {relative: string; title: string} {
    const timestamp = connector.last_successful_delivery ?? connector.last_delivery_attempt;
    if (timestamp === null) {
        return {
            relative: $t({defaultMessage: "Not yet delivered"}),
            title: $t({defaultMessage: "Waiting for the first delivery"}),
        };
    }
    const date = new Date(timestamp);
    return {
        relative: timerender.relative_time_string_from_date(date, true),
        title: timerender.get_full_datetime(date),
    };
}

function render_list($container: JQuery): void {
    const query = String($container.find(".connector-search").val() ?? "")
        .trim()
        .toLocaleLowerCase();
    const tab = active_tab($container);
    const visible_connectors = connectors.filter((connector) => {
        const matches_tab = tab === "all" || connector.is_owner;
        const searchable = [
            connector.provider_name,
            connector.destination ?? "",
            connector.topic,
            connector.owner ?? "",
        ]
            .join(" ")
            .toLocaleLowerCase();
        return matches_tab && searchable.includes(query);
    });
    const $rows = $container.find(".connector-rows").empty();
    for (const connector of visible_connectors) {
        const status = connector_status(connector);
        const updated = last_update(connector);
        $rows.append(
            $(
                render_connector_row({
                    ...connector,
                    status_key: status.key,
                    status_label: status.label,
                    last_update: updated.relative,
                    last_update_title: updated.title,
                    can_copy:
                        connector.reconciliation_state === "canonical" &&
                        connector.state !== "disabled",
                    can_rotate:
                        connector.can_manage &&
                        connector.reconciliation_state === "canonical" &&
                        connector.state !== "disabled",
                    needs_reconciliation: connector.reconciliation_state === "ambiguous",
                    is_disabled: connector.state === "disabled",
                }),
            ),
        );
    }
    if (visible_connectors.length === 0) {
        $rows.append(
            $(
                render_connector_empty_row({
                    heading:
                        query === ""
                            ? $t({defaultMessage: "No connectors yet"})
                            : $t({defaultMessage: "No matching connectors"}),
                    description:
                        query === ""
                            ? $t({defaultMessage: "Add one to start receiving updates in Hover."})
                            : $t({defaultMessage: "Try a different search term."}),
                }),
            ),
        );
    }
}

function render_all_lists(): void {
    $(".connector-management").each(function () {
        render_list($(this));
    });
}

function load_connectors(): void {
    void channel.get({
        url: CONNECTORS_URL,
        success(raw_data) {
            connectors = connector_list_response_schema.parse(raw_data).connectors;
            render_all_lists();
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Could not load connectors."}),
                xhr,
                $(".connector-list-status"),
            );
        },
    });
}

function modal_stage(): JQuery {
    return $(".connector-modal-stage");
}

function render_catalogue_stage(query: string): void {
    modal_provider = undefined;
    modal_stage().html(render_catalogue(query));
    modal_stage().find<HTMLInputElement>(".connector-provider-search").trigger("focus");
}

function render_catalogue_results(query: string): void {
    const $rendered_catalogue = $(render_catalogue(query));
    modal_stage()
        .find(".connector-catalog-results")
        .html($rendered_catalogue.find(".connector-catalog-results").html() ?? "");
}

function selected_events(provider: Provider): string[] {
    if (!provider.supports_event_filters || provider.all_event_types === null) {
        return [];
    }
    const selected = modal_stage()
        .find<HTMLInputElement>(".connector-event-options input:checked")
        .map((_index, element) => element.value)
        .get();
    return selected.length === provider.all_event_types.length ? [] : selected;
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
        {defaultMessage: "Choose where {provider} updates should appear."},
        {provider: provider.name},
    );
}

function event_label(event_name: string): string {
    const label = event_name.replaceAll("_", " ");
    return label.charAt(0).toLocaleUpperCase() + label.slice(1);
}

function render_setup_stage(provider: Provider): void {
    modal_provider = provider;
    const connector = modal_connector;
    const selected_event_names = new Set(connector?.event_options);
    const all_events_selected = selected_event_names.size === 0;
    const destinations = stream_data
        .subscribed_subs()
        .filter((stream) => !stream.is_archived)
        .map((stream) => ({
            name: stream.name,
            selected: connector?.destination === stream.name,
        }));
    modal_stage().html(
        render_connector_setup({
            provider,
            intro: setup_intro(provider),
            destinations,
            topic: connector?.topic ?? default_topic(provider),
            events:
                provider.all_event_types?.map((event) => ({
                    name: event,
                    label: event_label(event),
                    selected: all_events_selected || selected_event_names.has(event),
                })) ?? [],
            event_filter_label: $t(
                {defaultMessage: "Choose {provider} events"},
                {provider: provider.name},
            ),
            event_note:
                provider.key === "slack_incoming"
                    ? $t({
                          defaultMessage:
                              "Choose the events in the service that sends the webhook.",
                      })
                    : $t({defaultMessage: "This connector accepts all supported updates."}),
            submit_label:
                modal_mode === "create"
                    ? $t({defaultMessage: "Create webhook URL"})
                    : modal_mode === "reconcile"
                      ? $t({defaultMessage: "Reconcile connector"})
                      : $t({defaultMessage: "Save changes"}),
        }),
    );
}

function setup_instruction(connector: Connector): string {
    if (connector.provider_key === "github") {
        return $t({
            defaultMessage: "Add this URL in your repository’s GitHub webhook settings.",
        });
    }
    if (connector.provider_key === "slack_incoming") {
        return $t({
            defaultMessage: "Paste this URL into the service that sends Slack-compatible webhooks.",
        });
    }
    if (connector.provider_key === "rest_api") {
        return $t({
            defaultMessage: "Send JSON payloads from your internal tool to this endpoint.",
        });
    }
    return $t(
        {defaultMessage: "Add this URL in {provider}’s webhook settings."},
        {provider: connector.provider_name},
    );
}

function provider_instruction(connector: Connector): string {
    if (connector.provider_key === "github") {
        return $t({
            defaultMessage: "In GitHub: Repository settings → Webhooks → Add webhook.",
        });
    }
    if (connector.provider_key === "slack_incoming") {
        return $t({
            defaultMessage:
                "In the sending service: choose Slack Incoming Webhook as the destination.",
        });
    }
    return $t({
        defaultMessage: "Follow the provider’s webhook setup instructions and use the URL above.",
    });
}

function render_handoff_stage(connector: Connector, ready: boolean): void {
    modal_connector = connector;
    $("#connector-dialog .modal__title").text(connector.provider_name);
    modal_stage().html(
        render_connector_handoff({
            ...connector,
            ready,
            setup_instruction: setup_instruction(connector),
            provider_instruction: provider_instruction(connector),
            setup_link_label: $t(
                {defaultMessage: "View {provider} setup instructions"},
                {provider: connector.provider_name},
            ),
            needs_reconciliation: connector.reconciliation_state === "ambiguous",
            is_disabled: connector.state === "disabled",
            is_legacy: connector.reconciliation_state !== "canonical",
        }),
    );
}

function show_request_error(xhr: JQuery.jqXHR, message: string): void {
    ui_report.error(message, xhr, $("#connector-dialog").find("#dialog_error"));
    modal_stage().find<HTMLButtonElement>(".connector-save").prop("disabled", false);
}

function submit_setup(): void {
    const provider = modal_provider;
    if (provider === undefined) {
        return;
    }
    const destination_name = String(modal_stage().find(".connector-destination").val() ?? "");
    const topic = String(modal_stage().find(".connector-topic").val() ?? "").trim();
    const event_options = selected_events(provider);
    modal_stage().find<HTMLButtonElement>(".connector-save").prop("disabled", true);
    const data: Record<string, string> = {
        destination_name: JSON.stringify(destination_name),
        topic: JSON.stringify(topic),
        event_options: JSON.stringify(event_options),
    };
    if (modal_mode !== "update") {
        data["provider_key"] = JSON.stringify(provider.key);
    }
    const success = (raw_data: unknown): void => {
        const connector = connector_response_schema.parse(raw_data).connector;
        render_handoff_stage(connector, modal_mode !== "update");
        load_connectors();
    };
    if (modal_mode === "create") {
        void channel.post({
            url: CONNECTORS_URL,
            data,
            success,
            error(xhr) {
                show_request_error(
                    xhr,
                    $t_html({defaultMessage: "Could not create the connector."}),
                );
            },
        });
        return;
    }
    const connector = modal_connector;
    if (connector === undefined) {
        return;
    }
    const url =
        modal_mode === "reconcile"
            ? `${CONNECTORS_URL}/${connector.id}/reconcile`
            : `${CONNECTORS_URL}/${connector.id}`;
    void channel.patch({
        url,
        data,
        success,
        error(xhr) {
            show_request_error(xhr, $t_html({defaultMessage: "Could not update the connector."}));
        },
    });
}

async function copy_webhook_url(url: string, $status?: JQuery): Promise<void> {
    await navigator.clipboard.writeText(url);
    if ($status !== undefined) {
        ui_report.success($t_html({defaultMessage: "Webhook URL copied."}), $status, 1600);
    }
}

function fetch_connector(connector_id: number, continuation: (connector: Connector) => void): void {
    void channel.get({
        url: `${CONNECTORS_URL}/${connector_id}`,
        success(raw_data) {
            continuation(connector_response_schema.parse(raw_data).connector);
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Could not load the connector."}),
                xhr,
                $(".connector-list-status"),
            );
        },
    });
}

function launch_modal(content: string, title: string): void {
    const modal_content_html = render_connector_modal_stage({content});
    dialog_widget.launch({
        id: "connector-dialog",
        modal_title_text: title,
        modal_content_html,
        hide_footer: true,
        close_on_overlay_click: false,
        post_render(modal_id) {
            bind_modal_events($(`#${CSS.escape(modal_id)}`));
        },
    });
}

function open_catalogue(connector?: Connector): void {
    modal_connector = connector;
    modal_mode = connector === undefined ? "create" : "reconcile";
    launch_modal(
        render_catalogue(""),
        connector === undefined
            ? $t({defaultMessage: "Add integration"})
            : $t({defaultMessage: "Reconcile connector"}),
    );
}

function open_handoff(connector: Connector, ready = false): void {
    modal_connector = connector;
    const content = render_connector_handoff({
        ...connector,
        ready,
        setup_instruction: setup_instruction(connector),
        provider_instruction: provider_instruction(connector),
        setup_link_label: $t(
            {defaultMessage: "View {provider} setup instructions"},
            {provider: connector.provider_name},
        ),
        needs_reconciliation: connector.reconciliation_state === "ambiguous",
        is_disabled: connector.state === "disabled",
        is_legacy: connector.reconciliation_state !== "canonical",
    });
    launch_modal(content, connector.provider_name);
}

function switch_modal(continuation: () => void): void {
    if (modal_stage().length > 0) {
        dialog_widget.close(continuation);
    } else {
        continuation();
    }
}

function rotate_connector(connector_id: number): void {
    void channel.post({
        url: `${CONNECTORS_URL}/${connector_id}/rotate`,
        data: {},
        success(raw_data) {
            const connector = connector_response_schema.parse(raw_data).connector;
            if (modal_stage().length > 0) {
                render_handoff_stage(connector, true);
            } else {
                open_handoff(connector, true);
            }
            load_connectors();
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Could not rotate the webhook URL."}),
                xhr,
                $(".connector-action-status, .connector-list-status"),
            );
        },
    });
}

function disable_connector($button: JQuery, connector_id: number): void {
    if ($button.attr("data-confirming") !== "true") {
        $button.attr("data-confirming", "true").text($t({defaultMessage: "Disable now"}));
        return;
    }
    $button.prop("disabled", true);
    void channel.del({
        url: `${CONNECTORS_URL}/${connector_id}`,
        data: {},
        success(raw_data) {
            const connector = connector_response_schema.parse(raw_data).connector;
            if (modal_stage().length > 0) {
                render_handoff_stage(connector, false);
            }
            load_connectors();
        },
        error(xhr) {
            $button.prop("disabled", false);
            ui_report.error(
                $t_html({defaultMessage: "Could not disable the connector."}),
                xhr,
                $(".connector-action-status, .connector-list-status"),
            );
        },
    });
}

function bind_modal_events($dialog: JQuery): void {
    $dialog.on("input", ".connector-provider-search", (event) => {
        render_catalogue_results(String($(event.currentTarget).val() ?? ""));
    });
    $dialog.on("click", ".connector-provider-choice", (event) => {
        const provider = provider_from_registry(
            String($(event.currentTarget).attr("data-provider")),
        );
        if (provider !== undefined) {
            render_setup_stage(provider);
        }
    });
    $dialog.on("click", ".connector-back", () => {
        render_catalogue_stage("");
    });
    $dialog.on("submit", "#connector_setup_form", (event) => {
        event.preventDefault();
        submit_setup();
    });
    $dialog.on("click", ".copy-connector-handoff", () => {
        const url = modal_connector?.webhook_url;
        if (url !== undefined) {
            void copy_webhook_url(url, modal_stage().find(".connector-action-status"));
        }
    });
    $dialog.on("click", ".edit-connector", () => {
        const connector = modal_connector;
        if (connector === undefined) {
            return;
        }
        const provider = provider_from_registry(connector.provider_key);
        if (provider !== undefined) {
            modal_mode = "update";
            render_setup_stage(provider);
        }
    });
    $dialog.on("click", ".reconcile-connector", () => {
        modal_mode = "reconcile";
        $dialog.find(".modal__title").text($t({defaultMessage: "Reconcile connector"}));
        render_catalogue_stage("");
    });
    $dialog.on("click", ".rotate-connector", (event) => {
        rotate_connector(Number($(event.currentTarget).attr("data-connector-id")));
    });
    $dialog.on("click", ".disable-connector", (event) => {
        if (!(event.currentTarget instanceof HTMLButtonElement)) {
            return;
        }
        const $button = $(event.currentTarget);
        disable_connector($button, Number($button.attr("data-connector-id")));
    });
}

function bind_list_events($container: JQuery): void {
    $container
        .off("input.connector-search")
        .on("input.connector-search", ".connector-search", () => {
            render_list($container);
        });
    $container.off("click.connector-add").on("click.connector-add", ".add-connector", () => {
        open_catalogue();
    });
    $container
        .off("click.connector-copy")
        .on("click.connector-copy", ".copy-connector-url", (event) => {
            const $button = $(event.currentTarget);
            fetch_connector(Number($button.attr("data-connector-id")), (connector) => {
                if (connector.webhook_url !== undefined) {
                    void copy_webhook_url(
                        connector.webhook_url,
                        $container.find(".connector-list-status"),
                    );
                }
            });
        });
    $container
        .off("click.connector-view")
        .on("click.connector-view", ".view-connector", (event) => {
            fetch_connector(Number($(event.currentTarget).attr("data-connector-id")), open_handoff);
        });
    $container
        .off("click.connector-reconcile")
        .on("click.connector-reconcile", ".reconcile-connector", (event) => {
            const connector_id = Number($(event.currentTarget).attr("data-connector-id"));
            const connector = connectors.find((item) => item.id === connector_id);
            if (connector !== undefined) {
                switch_modal(() => {
                    open_catalogue(connector);
                });
            }
        });
    $container
        .off("click.connector-rotate")
        .on("click.connector-rotate", ".rotate-connector", (event) => {
            rotate_connector(Number($(event.currentTarget).attr("data-connector-id")));
        });
    $container
        .off("click.connector-disable")
        .on("click.connector-disable", ".disable-connector", (event) => {
            if (!(event.currentTarget instanceof HTMLButtonElement)) {
                return;
            }
            const $button = $(event.currentTarget);
            disable_connector($button, Number($button.attr("data-connector-id")));
        });
}

export function redraw_connectors(): void {
    render_all_lists();
}

export function handle_live_update(): void {
    const connector_management_visible = [
        ...document.querySelectorAll(".connector-management"),
    ].some((element) => element instanceof HTMLElement && element.offsetParent !== null);
    if (connector_management_visible) {
        load_connectors();
    }
}

export function set_up_connectors(): void {
    $(".connector-management").each(function () {
        bind_list_events($(this));
    });
    load_connectors();
}
