import {$} from "jquery";
import * as z from "zod/mini";

import render_connected_account_card from "../templates/settings/connected_account_card.hbs";
import render_connected_account_grant_modal from "../templates/settings/connected_account_grant_modal.hbs";

import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as hover_connected_accounts from "./hover_connected_accounts.ts";
import type {ConnectedAccount, ConnectedAccountGrant} from "./hover_connected_accounts.ts";
import {$t, $t_html} from "./i18n.ts";
import * as people from "./people.ts";
import {current_user} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";

const account_response_schema = z.object({
    connected_account: hover_connected_accounts.connected_account_schema,
});
const grant_response_schema = z.object({
    connected_account_grant: hover_connected_accounts.connected_account_grant_schema,
});
const source_ref_pattern = /^src_[0-9a-f]{32}$/;
const selector_type_pattern = /^[a-z][a-z0-9_]{0,63}$/;

let loaded = false;

function user_name(user_id: number | null): string {
    if (user_id === null) {
        return $t({defaultMessage: "Former member"});
    }
    return people.get_by_user_id(user_id).full_name;
}

function approval_label(state: ConnectedAccount["approval_state"]): string {
    switch (state) {
        case "pending":
            return $t({defaultMessage: "Pending approval"});
        case "approved":
            return $t({defaultMessage: "Approved"});
        case "revoked":
            return $t({defaultMessage: "Revoked"});
    }
    throw new Error("Unknown approval state");
}

function health_label(status: ConnectedAccount["health_status"]): string {
    switch (status) {
        case "unknown":
            return $t({defaultMessage: "Health unknown"});
        case "healthy":
            return $t({defaultMessage: "Healthy"});
        case "degraded":
            return $t({defaultMessage: "Degraded"});
        case "unavailable":
            return $t({defaultMessage: "Unavailable"});
    }
    throw new Error("Unknown health status");
}

function scope_label(grant: ConnectedAccountGrant): string {
    if (grant.all_selectors) {
        return $t({defaultMessage: "All selectors"});
    }
    if (grant.selectors.length === 0) {
        return $t({defaultMessage: "No selectors (deny all)"});
    }
    return grant.selectors.map((selector) => selector.display_name).join(", ");
}

function card_html(account: ConnectedAccount): string {
    const grants = hover_connected_accounts.get_grants_for_account(account.id).map((grant) => ({
        ...grant,
        user_name: user_name(grant.user_id),
        scope_label: scope_label(grant),
        is_revoked: grant.state === "revoked",
    }));
    return render_connected_account_card({
        account: {
            ...account,
            approval_label: approval_label(account.approval_state),
            health_label: health_label(account.health_status),
            health_checked_label:
                account.health_checked_at === null
                    ? $t({defaultMessage: "Not checked"})
                    : timerender.get_full_datetime(new Date(account.health_checked_at)),
            owner_name: user_name(account.owner_id),
            creator_name: user_name(account.created_by_id),
            is_pending: account.approval_state === "pending",
            is_approved: account.approval_state === "approved",
            is_revoked: account.approval_state === "revoked",
        },
        grants,
        has_grants: grants.length > 0,
    });
}

export function rerender(): void {
    if (!loaded) {
        return;
    }
    const $list = $("#hover-connected-accounts-list");
    if ($list.length === 0) {
        return;
    }
    const accounts = hover_connected_accounts.get_accounts();
    if (accounts.length === 0) {
        $list
            .empty()
            .append(
                $("<p>").addClass("hover-connected-account-empty").text($list.attr("data-empty")!),
            );
        return;
    }
    $list.html(accounts.map((account) => card_html(account)).join(""));
}

function parse_selector_lines():
    {selector_type: string; source_ref: string; display_name: string}[] | undefined {
    const lines = $<HTMLTextAreaElement>("#connected_account_selectors")
        .val()!
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line !== "");
    const selectors = [];
    for (const line of lines) {
        const [selector_type = "", source_ref = "", ...display_name_parts] = line
            .split("|")
            .map((part) => part.trim());
        const display_name = display_name_parts.join(" | ");
        if (
            !selector_type_pattern.test(selector_type) ||
            !source_ref_pattern.test(source_ref) ||
            display_name === ""
        ) {
            ui_report.client_error(
                $t_html({
                    defaultMessage:
                        "Each selector must use: selector type | opaque source reference | display name.",
                }),
                $("#dialog_error"),
            );
            return undefined;
        }
        selectors.push({selector_type, source_ref, display_name});
    }
    return selectors;
}

function grant_selector_lines(grant: ConnectedAccountGrant | undefined): string {
    if (grant === undefined) {
        return "";
    }
    return grant.selectors
        .map(
            (selector) =>
                `${selector.selector_type} | ${selector.source_ref} | ${selector.display_name}`,
        )
        .join("\n");
}

function open_grant_modal(account: ConnectedAccount, grant?: ConnectedAccountGrant): void {
    const users = people.get_realm_active_human_users().map((user) => ({
        user_id: user.user_id,
        full_name: user.full_name,
    }));
    const modal_content_html = render_connected_account_grant_modal({
        editing: grant !== undefined,
        users,
        selector_lines: grant_selector_lines(grant),
    });

    function submit_grant(): void {
        const all_selectors = $("#connected_account_grant_scope").val() === "all";
        const selectors = all_selectors ? [] : parse_selector_lines();
        if (selectors === undefined) {
            dialog_widget.hide_dialog_spinner();
            return;
        }
        const user_id = Math.trunc(
            Number($<HTMLSelectElement>("#connected_account_grantee").val()),
        );
        dialog_widget.submit_api_request(
            channel.post,
            `/json/hover/connected_accounts/${account.id}/grants`,
            {
                user_id: JSON.stringify(user_id),
                all_selectors: JSON.stringify(all_selectors),
                selectors: JSON.stringify(selectors),
            },
            {
                success_continuation(raw_data) {
                    const {connected_account_grant} = grant_response_schema.parse(raw_data);
                    hover_connected_accounts.upsert_grant(connected_account_grant);
                    rerender();
                },
            },
        );
    }

    dialog_widget.launch({
        modal_title_text:
            grant === undefined
                ? $t({defaultMessage: "Assign Connected Account"})
                : $t({defaultMessage: "Edit Connected Account grant"}),
        modal_content_html,
        modal_submit_button_text:
            grant?.state === "revoked"
                ? $t({defaultMessage: "Restore grant"})
                : $t({defaultMessage: "Save grant"}),
        form_id: "connected_account_grant_form",
        loading_spinner: true,
        on_click: submit_grant,
        on_shown() {
            if (grant !== undefined) {
                $("#connected_account_grantee").val(grant.user_id).prop("disabled", true);
            }
            $("#connected_account_grant_scope")
                .val(grant?.all_selectors === true ? "all" : "restricted")
                .off("change")
                .on("change", function () {
                    const is_all = $(this).val() === "all";
                    $(".connected-account-selector-input").toggle(!is_all);
                })
                .trigger("change");
        },
    });
}

function update_approval(account: ConnectedAccount, approval_state: "approved" | "revoked"): void {
    void channel.patch({
        url: `/json/hover/connected_accounts/${account.id}`,
        data: {approval_state: JSON.stringify(approval_state)},
        success(raw_data) {
            const {connected_account} = account_response_schema.parse(raw_data);
            hover_connected_accounts.upsert_account(connected_account);
            rerender();
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Could not update Connected Account."}),
                xhr,
                $("#connected-account-status"),
            );
        },
    });
}

function account_from_button(button: HTMLElement): ConnectedAccount {
    const account_id = Number.parseInt(
        $(button).closest("[data-connected-account-id]").attr("data-connected-account-id")!,
        10,
    );
    return hover_connected_accounts.get_account(account_id)!;
}

function grant_from_button(button: HTMLElement): ConnectedAccountGrant {
    const account = account_from_button(button);
    const grant_id = Number.parseInt(
        $(button)
            .closest("[data-connected-account-grant-id]")
            .attr("data-connected-account-grant-id")!,
        10,
    );
    return hover_connected_accounts
        .get_grants_for_account(account.id)
        .find((grant) => grant.id === grant_id)!;
}

export function set_up(): void {
    if (!current_user.is_admin) {
        return;
    }
    loaded = true;
    rerender();
    const $section = $("#connected-account-settings");
    $section.off("click.hover-connected-accounts");
    $section.on(
        "click.hover-connected-accounts",
        ".approve-connected-account",
        function (this: HTMLElement) {
            update_approval(account_from_button(this), "approved");
        },
    );
    $section.on(
        "click.hover-connected-accounts",
        ".restore-connected-account",
        function (this: HTMLElement) {
            update_approval(account_from_button(this), "approved");
        },
    );
    $section.on(
        "click.hover-connected-accounts",
        ".revoke-connected-account",
        function (this: HTMLElement) {
            const account = account_from_button(this);
            confirm_dialog.launch({
                modal_title_html: $t_html({defaultMessage: "Revoke Connected Account?"}),
                modal_content_html: $t_html({
                    defaultMessage: "All teammate grants will stop authorizing shared Space use.",
                }),
                on_click() {
                    update_approval(account, "revoked");
                },
            });
        },
    );
    $section.on(
        "click.hover-connected-accounts",
        ".add-connected-account-grant",
        function (this: HTMLElement) {
            open_grant_modal(account_from_button(this));
        },
    );
    $section.on(
        "click.hover-connected-accounts",
        ".edit-connected-account-grant",
        function (this: HTMLElement) {
            open_grant_modal(account_from_button(this), grant_from_button(this));
        },
    );
    $section.on(
        "click.hover-connected-accounts",
        ".revoke-connected-account-grant",
        function (this: HTMLElement) {
            const account = account_from_button(this);
            const grant = grant_from_button(this);
            confirm_dialog.launch({
                modal_title_html: $t_html({defaultMessage: "Revoke teammate grant?"}),
                modal_content_html: $t_html({
                    defaultMessage: "This teammate will no longer be authorized for this account.",
                }),
                on_click() {
                    void channel.del({
                        url: `/json/hover/connected_accounts/${account.id}/grants/${grant.id}`,
                        success(raw_data) {
                            const {connected_account_grant} = grant_response_schema.parse(raw_data);
                            hover_connected_accounts.upsert_grant(connected_account_grant);
                            rerender();
                        },
                    });
                },
            });
        },
    );
}

export function reset(): void {
    loaded = false;
}
