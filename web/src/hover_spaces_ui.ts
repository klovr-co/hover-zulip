import {$} from "jquery";
import * as z from "zod/mini";

import render_create_hover_space_modal from "../templates/create_hover_space_modal.hbs";
import render_hover_source_discovery_results from "../templates/hover_source_discovery_results.hbs";
import render_hover_space_setup_modal from "../templates/hover_space_setup_modal.hbs";

import * as channel from "./channel.ts";
import * as channel_folders from "./channel_folders.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as hover_connected_accounts from "./hover_connected_accounts.ts";
import * as hover_spaces from "./hover_spaces.ts";
import {$t, $t_html} from "./i18n.ts";
import * as people from "./people.ts";
import {current_user} from "./state_data.ts";
import * as stream_list from "./stream_list.ts";
import * as ui_report from "./ui_report.ts";

const create_space_response_schema = z.object({space: hover_spaces.hover_space_schema});
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
const attach_response_schema = z.object({
    space: hover_spaces.hover_space_schema,
    attachment: hover_spaces.hover_space_attachment_schema,
    created: z.boolean(),
});
const membership_response_schema = z.object({space: hover_spaces.hover_space_schema});
const launch_response_schema = z.object({
    space: hover_spaces.hover_space_schema,
    created: z.boolean(),
});
const module_mutation_response_schema = z.object({
    space: hover_spaces.hover_space_schema,
    installation: hover_spaces.hover_module_installation_schema,
});
type DiscoveredSource = z.output<typeof discovered_source_schema>;

export function open_create_space(): void {
    const categories = channel_folders
        .get_channel_folders()
        .filter((folder) => !folder.is_archived);
    const modal_content_html = render_create_hover_space_modal({
        categories,
        has_categories: categories.length > 0,
        max_name_length: 60,
        max_description_length: 1024,
    });

    function create_space(): void {
        const category_id = Math.trunc(
            Number($<HTMLSelectElement>("#new_hover_space_category").val()),
        );
        const data = {
            name: $<HTMLInputElement>("#new_hover_space_name").val()!.trim(),
            description: $<HTMLTextAreaElement>("#new_hover_space_description").val()!.trim(),
            category_id: JSON.stringify(categories.length > 0 ? category_id : null),
        };
        dialog_widget.submit_api_request(channel.post, "/json/hover/spaces", data, {
            success_continuation(response_data) {
                const {space} = create_space_response_schema.parse(response_data);
                hover_spaces.upsert(space);
                stream_list.update_streams_sidebar(true);
            },
        });
    }

    dialog_widget.launch({
        modal_title_text: $t({defaultMessage: "Create Space"}),
        modal_content_html,
        modal_submit_button_text: $t({defaultMessage: "Create in Setup"}),
        form_id: "create_hover_space_form",
        on_click: create_space,
        loading_spinner: true,
        on_shown: () => $("#new_hover_space_name").trigger("focus"),
    });
}

export function open_setup_space(space_id: number): void {
    const maybe_space = hover_spaces.get_by_id(space_id);
    if (maybe_space?.state !== "setup") {
        return;
    }
    const space = maybe_space;
    const related_user_ids = new Set([
        ...space.memberships.map((membership) => membership.user_id),
        ...space.membership_suggestions.map((suggestion) => suggestion.user_id),
    ]);
    const eligible_users = people
        .get_realm_active_human_users()
        .filter((user) => !related_user_ids.has(user.user_id))
        .toSorted((a, b) => a.full_name.localeCompare(b.full_name));
    const accounts = hover_connected_accounts
        .get_accounts()
        .filter(
            (account) =>
                account.approval_state === "approved" &&
                hover_connected_accounts
                    .get_grants_for_account(account.id)
                    .some(
                        (grant) =>
                            grant.user_id === current_user.user_id && grant.state === "active",
                    ),
        );
    const module_catalog = space.module_catalog.map((module) => ({
        ...module,
        attachments: space.attachments,
        is_installed: space.module_installations.some(
            (installation) =>
                installation.version_id === module.id && installation.state !== "disabled",
        ),
        supports_manual: module.supported_triggers.includes("manual"),
        supports_new_source: module.supported_triggers.includes("new_source"),
        supports_schedule: module.supported_triggers.includes("schedule"),
    }));
    let selected_source: DiscoveredSource | undefined;
    let next_cursor: string | undefined;

    function set_status(message: string, state: "loading" | "error" | "ready" = "ready"): void {
        $("#hover_source_discovery_status").attr("data-state", state).text(message);
    }

    function account_id(): number {
        return Math.trunc(Number($<HTMLSelectElement>("#hover_source_account").val()));
    }

    function discovery_error(xhr: JQuery.jqXHR<unknown>): void {
        $("#hover-space-setup-modal .dialog_submit_button").prop("disabled", true);
        const retryable = [429, 502, 503, 504].includes(xhr.status);
        set_status(
            retryable
                ? $t({defaultMessage: "Source discovery is temporarily unavailable. Try again."})
                : $t({defaultMessage: "Source discovery could not be completed."}),
            "error",
        );
        $("#hover_source_discovery_results").empty();
    }

    function discover(cursor?: string): void {
        selected_source = undefined;
        $("#hover-space-setup-modal .dialog_submit_button").prop("disabled", true);
        set_status($t({defaultMessage: "Checking your permitted Sources…"}), "loading");
        void channel.post({
            url: `/json/hover/spaces/${space.id}/sources/discover`,
            data: {
                account_id: JSON.stringify(account_id()),
                query: JSON.stringify($<HTMLInputElement>("#hover_source_query").val()!.trim()),
                cursor: JSON.stringify(cursor ?? null),
                limit: JSON.stringify(20),
            },
            success(raw_data) {
                const response = discovery_response_schema.parse(raw_data);
                next_cursor = response.has_more ? response.next_cursor : undefined;
                $("#hover_source_discovery_results").html(
                    render_hover_source_discovery_results({
                        ...response,
                        has_sources: response.sources.length > 0,
                    }),
                );
                set_status(
                    response.sources.length === 0
                        ? $t({defaultMessage: "No permitted Sources found."})
                        : $t({defaultMessage: "Choose a Source, then preview its identity."}),
                );
            },
            error: discovery_error,
        });
    }

    function preview(source_ref: string): void {
        set_status($t({defaultMessage: "Verifying Source identity…"}), "loading");
        void channel.post({
            url: `/json/hover/spaces/${space.id}/sources/preview`,
            data: {
                account_id: JSON.stringify(account_id()),
                source_ref: JSON.stringify(source_ref),
            },
            success(raw_data) {
                const {source} = preview_response_schema.parse(raw_data);
                selected_source = source;
                $("#hover-space-setup-modal .dialog_submit_button").prop("disabled", false);
                $<HTMLInputElement>(
                    `input[name='hover_source_candidate'][value='${source_ref}']`,
                ).prop("checked", true);
                $("#hover_source_preview")
                    .removeClass("hide")
                    .empty()
                    .append(
                        $("<span>")
                            .addClass("hover-source-preview-label")
                            .text($t({defaultMessage: "Verified preview"})),
                        $("<strong>").text(source.display_name),
                        $("<small>").text(
                            `${source.account_display_name} · ${source.provider_key} · ${source.source_type}`,
                        ),
                    );
                set_status($t({defaultMessage: "Source identity verified."}));
            },
            error: discovery_error,
        });
    }

    function attach(): void {
        if (selected_source === undefined) {
            ui_report.client_error(
                $t_html({defaultMessage: "Preview and select a Source before attaching it."}),
                $("#dialog_error"),
            );
            dialog_widget.hide_dialog_spinner();
            return;
        }
        const history_window = $<HTMLSelectElement>("#hover_source_history_window").val()!;
        const custom_start_date_value =
            $<HTMLInputElement>("#hover_source_custom_start_date").val() ?? "";
        const custom_start_date =
            history_window === "custom"
                ? custom_start_date_value === ""
                    ? null
                    : custom_start_date_value
                : null;
        if (history_window === "custom" && custom_start_date === null) {
            ui_report.client_error(
                $t_html({defaultMessage: "Choose a custom history start date."}),
                $("#dialog_error"),
            );
            dialog_widget.hide_dialog_spinner();
            return;
        }
        dialog_widget.submit_api_request(
            channel.post,
            `/json/hover/spaces/${space.id}/sources`,
            {
                account_id: JSON.stringify(account_id()),
                source_ref: JSON.stringify(selected_source.source_ref),
                history_window: JSON.stringify(history_window),
                history_timezone: JSON.stringify(
                    new Intl.DateTimeFormat().resolvedOptions().timeZone,
                ),
                custom_start_date: JSON.stringify(custom_start_date),
            },
            {
                failure_msg_html: $t_html({defaultMessage: "Could not attach this Source."}),
                success_continuation(raw_data) {
                    const {space: updated_space} = attach_response_schema.parse(raw_data);
                    hover_spaces.upsert(updated_space);
                    stream_list.update_streams_sidebar(true);
                },
                error_continuation(xhr) {
                    if (xhr.status === 409) {
                        set_status(
                            $t({
                                defaultMessage:
                                    "This Source already has a different immutable history window.",
                            }),
                            "error",
                        );
                    }
                },
            },
        );
    }

    function show_membership_error(): void {
        ui_report.client_error(
            $t_html({defaultMessage: "Could not update Space membership."}),
            $("#dialog_error"),
        );
    }

    function reopen_with_space(raw_data: unknown): void {
        const {space: updated_space} = membership_response_schema.parse(raw_data);
        hover_spaces.upsert(updated_space);
        stream_list.update_streams_sidebar(true);
        dialog_widget.close(() => {
            open_setup_space(space.id);
        });
    }

    function confirm_member(user_id: number, role: string): void {
        void channel.post({
            url: `/json/hover/spaces/${space.id}/members`,
            data: {user_id: JSON.stringify(user_id), role: JSON.stringify(role)},
            success: reopen_with_space,
            error: show_membership_error,
        });
    }

    dialog_widget.launch({
        id: "hover-space-setup-modal",
        modal_title_text: $t({defaultMessage: "Space Setup"}),
        modal_content_html: render_hover_space_setup_modal({
            space,
            accounts,
            eligible_users,
            has_attachments: space.attachments.length > 0,
            has_accounts: accounts.length > 0,
            has_eligible_users: eligible_users.length > 0,
            module_catalog,
            has_module_catalog: module_catalog.length > 0,
            has_module_installations: space.module_installations.length > 0,
        }),
        modal_submit_button_text: $t({defaultMessage: "Attach Source"}),
        form_id: "hover_source_attachment_form",
        loading_spinner: true,
        on_click: attach,
        on_shown() {
            const $panel = $("#hover-source-attachment-panel");
            $("#hover-space-setup-modal .dialog_submit_button").prop("disabled", true);
            $panel.on("click", ".hover-source-search-button", () => {
                discover();
            });
            $panel.on("click", ".hover-source-next-button", () => {
                discover(next_cursor);
            });
            $panel.on("click", ".hover-source-preview-button", (event) => {
                event.preventDefault();
                event.stopPropagation();
                preview($(event.currentTarget).attr("data-source-ref")!);
            });
            $panel.on("change", "input[name='hover_source_candidate']", (event) => {
                preview(String($(event.currentTarget).val() ?? ""));
            });
            $("#hover_source_account").on("change", () => {
                selected_source = undefined;
                next_cursor = undefined;
                $("#hover_source_preview").addClass("hide").empty();
                discover();
            });
            $("#hover_source_history_window")
                .on("change", function () {
                    const is_custom = $(this).val() === "custom";
                    $(".hover-source-custom-date").toggleClass("hide", !is_custom);
                    $("#hover_source_custom_start_date").prop("required", is_custom);
                })
                .trigger("change");
            $("#hover_source_query").on("keydown", (event) => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    discover();
                }
            });
            if (accounts.length > 0) {
                discover();
            }
            $("#hover-space-membership-panel").on("click", "[data-membership-action]", (event) => {
                const $button = $(event.currentTarget);
                const action = $button.attr("data-membership-action");
                const user_id = Number($button.attr("data-user-id"));
                switch (action) {
                    case "confirm-suggestion":
                        confirm_member(
                            user_id,
                            String(
                                $<HTMLSelectElement>(
                                    `.hover-member-role-select[data-user-id='${user_id}']`,
                                ).val(),
                            ),
                        );
                        break;
                    case "remove":
                        void channel.del({
                            url: `/json/hover/spaces/${space.id}/members/${user_id}`,
                            success: reopen_with_space,
                            error: show_membership_error,
                        });
                        break;
                    case "promote":
                        void channel.post({
                            url: `/json/hover/spaces/${space.id}/admins`,
                            data: {user_id: JSON.stringify(user_id)},
                            success() {
                                dialog_widget.close(() => {
                                    open_setup_space(space.id);
                                });
                            },
                            error: show_membership_error,
                        });
                        break;
                }
            });
            $(".hover-member-role-select").on("change", (event) => {
                const $select = $(event.currentTarget);
                const user_id = Number($select.attr("data-user-id"));
                const is_pending = $select
                    .closest(".hover-member-row")
                    .find("[data-membership-action='confirm-suggestion']").length;
                if (!is_pending) {
                    confirm_member(user_id, String($select.val()));
                }
            });
            $(".hover-member-add-button").on("click", () => {
                confirm_member(
                    Number($<HTMLSelectElement>("#hover_member_user").val()),
                    String($<HTMLSelectElement>("#hover_member_role").val()),
                );
            });
            $(".hover-module-trigger-select").on("change", (event) => {
                const $select = $(event.currentTarget);
                const $card = $select.closest(".hover-module-card");
                $card
                    .find(".hover-module-schedule-fields")
                    .toggleClass("hide", $select.val() !== "schedule");
                $card
                    .find(".hover-module-debounce-field")
                    .toggleClass("hide", $select.val() !== "new_source");
            });
            $(".hover-module-install-button").on("click", (event) => {
                const $card = $(event.currentTarget).closest(".hover-module-card");
                const version_id = Number($card.attr("data-version-id"));
                const attachment_ids = $card
                    .find<HTMLInputElement>("input[data-module-attachment]:checked")
                    .map((_index, element) => Number(element.value))
                    .get();
                const trigger_kind = String(
                    $card.find<HTMLSelectElement>(".hover-module-trigger-select").val(),
                );
                const backfill_value =
                    $card.find<HTMLInputElement>(".hover-module-backfill-start").val() ?? "";
                void channel.post({
                    url: `/json/hover/spaces/${space.id}/modules`,
                    data: {
                        version_id: JSON.stringify(version_id),
                        attachment_ids: JSON.stringify(attachment_ids),
                        trigger_kind: JSON.stringify(trigger_kind),
                        activation_timezone: new Intl.DateTimeFormat().resolvedOptions().timeZone,
                        cadence: JSON.stringify(
                            trigger_kind === "schedule"
                                ? $card.find<HTMLSelectElement>(".hover-module-cadence").val()
                                : null,
                        ),
                        local_time: JSON.stringify(
                            trigger_kind === "schedule"
                                ? $card.find<HTMLInputElement>(".hover-module-local-time").val()
                                : null,
                        ),
                        debounce_seconds: JSON.stringify(
                            trigger_kind === "new_source" ? 300 : null,
                        ),
                        backfill_start_at: JSON.stringify(
                            backfill_value === "" ? null : new Date(backfill_value).toISOString(),
                        ),
                        backfill_confirmed: JSON.stringify(
                            backfill_value !== "" &&
                                $card
                                    .find<HTMLInputElement>(".hover-module-backfill-confirm")
                                    .prop("checked"),
                        ),
                    },
                    success(raw_data) {
                        const {space: updated_space} =
                            module_mutation_response_schema.parse(raw_data);
                        hover_spaces.upsert(updated_space);
                        stream_list.update_streams_sidebar(true);
                        dialog_widget.close(() => {
                            open_setup_space(space.id);
                        });
                    },
                    error() {
                        ui_report.client_error(
                            $t_html({defaultMessage: "Could not enable this Module."}),
                            $("#dialog_error"),
                        );
                    },
                });
            });
            $(".hover-module-disable-button").on("click", (event) => {
                const installation_id = Number($(event.currentTarget).attr("data-installation-id"));
                void channel.post({
                    url: `/json/hover/module-installations/${installation_id}/disable`,
                    success() {
                        void channel.get({
                            url: `/json/hover/spaces/${space.id}`,
                            success: reopen_with_space,
                        });
                    },
                    error() {
                        ui_report.client_error(
                            $t_html({defaultMessage: "Could not disable this Module."}),
                            $("#dialog_error"),
                        );
                    },
                });
            });
            $(".hover-space-launch-button").on("click", () => {
                void channel.post({
                    url: `/json/hover/spaces/${space.id}/launch`,
                    success(raw_data) {
                        const {space: launched_space} = launch_response_schema.parse(raw_data);
                        hover_spaces.upsert(launched_space);
                        stream_list.update_streams_sidebar(true);
                        dialog_widget.close();
                    },
                    error() {
                        ui_report.client_error(
                            $t_html({
                                defaultMessage:
                                    "Launch is not ready. Resolve the highlighted setup requirements.",
                            }),
                            $("#dialog_error"),
                        );
                    },
                });
            });
        },
    });
}
