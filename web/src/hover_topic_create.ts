import {$} from "jquery";
import * as z from "zod/mini";

import render_hover_source_discovery_results from "../templates/hover_source_discovery_results.hbs";
import render_hover_summary_settings from "../templates/hover_summary_settings.hbs";
import render_hover_topic_create from "../templates/hover_topic_create.hbs";

import * as channel from "./channel.ts";
import * as compose_actions from "./compose_actions.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as hover_connected_accounts from "./hover_connected_accounts.ts";
import * as hover_spaces from "./hover_spaces.ts";
import {$t, $t_html} from "./i18n.ts";
import {current_user} from "./state_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as ui_report from "./ui_report.ts";

const discovered_source_schema = z.object({
    source_ref: z.string(),
    provider_key: z.string(),
    source_type: z.string(),
    display_name: z.string(),
    account_id: z.number(),
    account_display_name: z.string(),
});
const discovery_response_schema = z.object({
    sources: z.array(discovered_source_schema),
    next_cursor: z.string(),
    has_more: z.boolean(),
});
const preview_response_schema = z.object({source: discovered_source_schema});
const space_mutation_response_schema = z.object({space: hover_spaces.hover_space_schema});
const attach_response_schema = z.object({
    space: hover_spaces.hover_space_schema,
    attachment: hover_spaces.hover_space_attachment_schema,
    created: z.boolean(),
});
const topic_kind_schema = z.enum(["regular", "source", "summary"]);
const summary_input_value_schema = z.object({
    topic_name: z.string(),
    kind: z.enum(["regular", "source"]),
    attachment_id: z.nullable(z.number()),
});

type DiscoveredSource = z.output<typeof discovered_source_schema>;

export function start_regular(stream_id: number, topic: string, trigger: string): void {
    compose_actions.start({
        message_type: "stream",
        stream_id,
        topic,
        trigger,
        keep_composebox_empty: true,
    });
}

function refresh_space(raw_data: unknown, on_space_updated?: () => void): void {
    const {space} = space_mutation_response_schema.parse(raw_data);
    hover_spaces.upsert(space);
    on_space_updated?.();
}

export function open(
    stream_id: number,
    prefilled_topic = "",
    on_space_updated?: () => void,
): void {
    const space = hover_spaces.get_by_stream_id(stream_id);
    if (space === undefined) {
        start_regular(stream_id, prefilled_topic, "new topic");
        return;
    }
    if (space.stream_id === null) {
        start_regular(stream_id, prefilled_topic, "new topic");
        return;
    }
    const parent_stream_id = space.stream_id;
    const space_id = space.id;
    const can_manage =
        space.memberships.find((membership) => membership.user_id === current_user.user_id)
            ?.is_administrator ?? false;
    const accounts = hover_connected_accounts
        .get_accounts()
        .filter(
            (account) =>
                ["github", "posthog"].includes(account.provider_key) &&
                account.approval_state === "approved" &&
                hover_connected_accounts
                    .get_grants_for_account(account.id)
                    .some(
                        (grant) =>
                            grant.user_id === current_user.user_id && grant.state === "active",
                    ),
        );
    const summary_version = space.module_catalog.find(
        (version) =>
            version.definition_key === "conversation_digest" &&
            version.supported_triggers.includes("schedule"),
    );
    const source_descriptors = hover_spaces
        .get_descriptors_for_parent(parent_stream_id)
        .filter((descriptor) => descriptor.kind === "source");
    const source_topic_names = new Set(
        source_descriptors.map((descriptor) => descriptor.topic_name.toLocaleLowerCase()),
    );
    const regular_inputs = stream_topic_history
        .get_recent_topic_names(parent_stream_id)
        .filter((topic_name) => !source_topic_names.has(topic_name.toLocaleLowerCase()))
        .map((topic_name) => ({topic_name, kind: "regular", attachment_id: null}));
    const source_inputs = source_descriptors.map((descriptor) => ({
        topic_name: descriptor.topic_name,
        kind: "source",
        attachment_id: descriptor.source!.attachment_id,
    }));
    const summary_inputs = [...regular_inputs, ...source_inputs].map((input) => ({
        ...input,
        value: JSON.stringify(input),
    }));
    const timezone = new Intl.DateTimeFormat().resolvedOptions().timeZone;
    let selected_source: DiscoveredSource | undefined;

    function selected_kind(): "regular" | "source" | "summary" {
        return topic_kind_schema.parse(
            String($("input[name='hover_topic_kind']:checked").val() ?? "regular"),
        );
    }

    function set_source_status(message: string, state = "ready"): void {
        $("#hover_topic_source_status").attr("data-state", state).text(message);
    }

    function account_id(): number {
        return Math.trunc(Number($<HTMLSelectElement>("#hover_topic_source_account").val()));
    }

    function source_error(): void {
        selected_source = undefined;
        set_source_status(
            $t({defaultMessage: "Source discovery is temporarily unavailable. Try again."}),
            "error",
        );
        $("#hover_topic_source_results").empty();
    }

    function discover(): void {
        selected_source = undefined;
        set_source_status($t({defaultMessage: "Checking your permitted Sources…"}), "loading");
        void channel.post({
            url: `/json/hover/spaces/${space_id}/sources/discover`,
            data: {
                account_id: JSON.stringify(account_id()),
                query: JSON.stringify(
                    $<HTMLInputElement>("#hover_topic_source_query").val()!.trim(),
                ),
                cursor: "null",
                limit: "20",
            },
            success(raw_data) {
                const response = discovery_response_schema.parse(raw_data);
                $("#hover_topic_source_results").html(
                    render_hover_source_discovery_results({
                        ...response,
                        has_sources: response.sources.length > 0,
                    }),
                );
                set_source_status(
                    response.sources.length > 0
                        ? $t({defaultMessage: "Choose a Source."})
                        : $t({defaultMessage: "No permitted Sources found."}),
                );
            },
            error: source_error,
        });
    }

    function preview(source_ref: string): void {
        set_source_status($t({defaultMessage: "Verifying Source identity…"}), "loading");
        void channel.post({
            url: `/json/hover/spaces/${space_id}/sources/preview`,
            data: {account_id: JSON.stringify(account_id()), source_ref: JSON.stringify(source_ref)},
            success(raw_data) {
                selected_source = preview_response_schema.parse(raw_data).source;
                set_source_status(
                    $t({defaultMessage: "Source identity verified: {name}"}, {name: selected_source.display_name}),
                );
            },
            error: source_error,
        });
    }

    function attach_source(): void {
        if (selected_source === undefined) {
            ui_report.client_error(
                $t_html({defaultMessage: "Choose and verify a Source first."}),
                $("#dialog_error"),
            );
            dialog_widget.hide_dialog_spinner();
            return;
        }
        const account = hover_connected_accounts.get_account(account_id());
        void channel.post({
            url: `/json/hover/spaces/${space_id}/sources`,
            data: {
                account_id: JSON.stringify(account_id()),
                source_ref: JSON.stringify(selected_source.source_ref),
                history_window: JSON.stringify("last_30_days"),
                history_timezone: JSON.stringify(timezone),
                custom_start_date: "null",
            },
            success(raw_data) {
                const response = attach_response_schema.parse(raw_data);
                hover_spaces.upsert(response.space);
                if (
                    account?.connection_kind !== "native_integration" ||
                    account.incoming_webhook_bot_id === null ||
                    !response.attachment.source.supports_live_capture
                ) {
                    dialog_widget.close();
                    on_space_updated?.();
                    return;
                }
                void channel.post({
                    url: `/json/hover/spaces/${space_id}/integration-routes`,
                    data: {
                        attachment_id: JSON.stringify(response.attachment.id),
                        bot_user_id: JSON.stringify(account.incoming_webhook_bot_id),
                    },
                    success(route_data) {
                        refresh_space(route_data, on_space_updated);
                        dialog_widget.close();
                    },
                    error() {
                        dialog_widget.hide_dialog_spinner();
                        ui_report.client_error(
                            $t_html({
                                defaultMessage:
                                    "The Source was attached, but live delivery still needs setup.",
                            }),
                            $("#dialog_error"),
                        );
                    },
                });
            },
            error() {
                dialog_widget.hide_dialog_spinner();
                ui_report.client_error(
                    $t_html({defaultMessage: "Could not attach this Source."}),
                    $("#dialog_error"),
                );
            },
        });
    }

    function create_summary(): void {
        if (summary_version === undefined) {
            dialog_widget.hide_dialog_spinner();
            return;
        }
        const inputs = $("input[name='hover_summary_input']:checked")
            .map((_index, element) => {
                const input: unknown = JSON.parse(String($(element).val()));
                return summary_input_value_schema.parse(input);
            })
            .get();
        const member_ids = $("input[name='hover_summary_member']:checked")
            .map((_index, element) => Number($(element).val()))
            .get();
        dialog_widget.submit_api_request(
            channel.post,
            `/json/hover/spaces/${space_id}/summaries`,
            {
                version_id: JSON.stringify(summary_version.id),
                label: $<HTMLInputElement>("#hover_summary_name").val()!.trim(),
                inputs: JSON.stringify(inputs),
                local_time: $<HTMLInputElement>("#hover_summary_time").val()!,
                timezone,
                member_ids: JSON.stringify(member_ids),
            },
            {
                failure_msg_html: $t_html({defaultMessage: "Could not create this Summary."}),
                success_continuation(raw_data) {
                    refresh_space(raw_data, on_space_updated);
                },
            },
        );
    }

    function submit(): void {
        switch (selected_kind()) {
            case "regular": {
                const topic = $<HTMLInputElement>("#hover_regular_topic_name").val()!.trim();
                dialog_widget.close(() => {
                    start_regular(parent_stream_id, topic, "Hover chooser");
                });
                break;
            }
            case "source":
                attach_source();
                break;
            case "summary":
                create_summary();
                break;
        }
    }

    dialog_widget.launch({
        id: "hover-topic-create-modal",
        modal_title_text: $t({defaultMessage: "Create topic"}),
        modal_content_html: render_hover_topic_create({
            prefilled_topic,
            accounts,
            can_create_source: can_manage && accounts.length > 0,
            can_create_summary: can_manage && summary_version !== undefined,
            summary_inputs,
            members: space.memberships.map((membership) => ({
                ...membership,
                selected: membership.user_id === current_user.user_id,
            })),
            timezone,
        }),
        modal_submit_button_text: $t({defaultMessage: "Continue"}),
        form_id: "hover_topic_create_form",
        loading_spinner: true,
        on_click: submit,
        on_shown() {
            function update_panel(): void {
                const kind = selected_kind();
                $("[data-hover-topic-panel]").addClass("hide");
                $(`[data-hover-topic-panel='${kind}']`).removeClass("hide");
                $(".dialog_submit_button").text(
                    kind === "regular"
                        ? $t({defaultMessage: "Start message"})
                        : kind === "source"
                          ? $t({defaultMessage: "Attach Source"})
                          : $t({defaultMessage: "Create Summary"}),
                );
            }
            $("input[name='hover_topic_kind']").on("change", () => {
                update_panel();
                if (selected_kind() === "source" && accounts.length > 0) {
                    discover();
                }
            });
            $("#hover_topic_source_account").on("change", discover);
            $("#hover_topic_source_search").on("click", (event) => {
                event.preventDefault();
                discover();
            });
            $("#hover_topic_source_results").on(
                "change",
                "input[name='hover_source_candidate']",
                (event) => {
                    preview(String($(event.currentTarget).val() ?? ""));
                },
            );
            update_panel();
            $("#hover_regular_topic_name").trigger("focus");
        },
    });
}

export function open_summary_settings(
    installation_id: number,
    on_space_updated?: () => void,
): void {
    const space = hover_spaces
        .get_all()
        .find((candidate) =>
            candidate.module_installations.some(
                (installation) => installation.id === installation_id,
            ),
        );
    const installation = space?.module_installations.find(
        (candidate) => candidate.id === installation_id,
    );
    if (space?.stream_id === null || space === undefined || installation === undefined) {
        return;
    }
    const source_descriptors = hover_spaces
        .get_descriptors_for_parent(space.stream_id)
        .filter((descriptor) => descriptor.kind === "source");
    const source_names = new Set(
        source_descriptors.map((descriptor) => descriptor.topic_name.toLocaleLowerCase()),
    );
    const available_inputs = [
        ...stream_topic_history
            .get_recent_topic_names(space.stream_id)
            .filter((topic_name) => !source_names.has(topic_name.toLocaleLowerCase()))
            .map((topic_name) => ({topic_name, kind: "regular" as const, attachment_id: null})),
        ...source_descriptors.map((descriptor) => ({
            topic_name: descriptor.topic_name,
            kind: "source" as const,
            attachment_id: descriptor.source!.attachment_id,
        })),
    ];
    const selected_inputs = new Set(
        installation.inputs.map(
            (input) => `${input.kind}:${input.topic_name.toLocaleLowerCase()}`,
        ),
    );
    const schedule = installation.triggers.find((trigger) => trigger.kind === "schedule");

    dialog_widget.launch({
        id: "hover-summary-settings-modal",
        modal_title_text: $t({defaultMessage: "Summary settings"}),
        modal_content_html: render_hover_summary_settings({
            label: installation.label,
            inputs: available_inputs.map((input) => ({
                ...input,
                value: JSON.stringify(input),
                selected: selected_inputs.has(
                    `${input.kind}:${input.topic_name.toLocaleLowerCase()}`,
                ),
            })),
            members: space.memberships.map((membership) => ({
                ...membership,
                selected:
                    membership.user_id === current_user.user_id ||
                    installation.member_ids.includes(membership.user_id),
                fixed: membership.user_id === current_user.user_id,
            })),
            local_time: schedule?.local_time?.slice(0, 5) ?? "09:00",
            timezone:
                schedule?.timezone ?? new Intl.DateTimeFormat().resolvedOptions().timeZone,
        }),
        modal_submit_button_text: $t({defaultMessage: "Save changes"}),
        form_id: "hover_summary_settings_form",
        loading_spinner: true,
        on_click() {
            const inputs = $("input[name='hover_summary_settings_input']:checked")
                .map((_index, element) => {
                    const input: unknown = JSON.parse(String($(element).val()));
                    return summary_input_value_schema.parse(input);
                })
                .get();
            const member_ids = $("input[name='hover_summary_settings_member']:checked")
                .map((_index, element) => Number($(element).val()))
                .get();
            dialog_widget.submit_api_request(
                channel.patch,
                `/json/hover/summaries/${installation_id}`,
                {
                    label: $<HTMLInputElement>("#hover_summary_settings_name").val()!.trim(),
                    inputs: JSON.stringify(inputs),
                    local_time: $<HTMLInputElement>("#hover_summary_settings_time").val()!,
                    timezone: String($("#hover_summary_settings_timezone").data("timezone")),
                    member_ids: JSON.stringify(member_ids),
                },
                {
                    failure_msg_html: $t_html({
                        defaultMessage: "Could not update this Summary.",
                    }),
                    success_continuation(raw_data) {
                        refresh_space(raw_data, on_space_updated);
                    },
                },
            );
        },
        on_shown() {
            $("#hover_summary_settings_name").trigger("focus");
        },
    });
}
