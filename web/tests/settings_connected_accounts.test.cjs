"use strict";

const assert = require("node:assert/strict");

const z = require("zod/mini");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {noop, run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
const confirm_dialog = mock_esm("../src/confirm_dialog");
const dialog_widget = mock_esm("../src/dialog_widget");
const hover_connected_accounts = mock_esm("../src/hover_connected_accounts", {
    connected_account_schema: z.any(),
    connected_account_grant_schema: z.any(),
    get_accounts: noop,
    get_grants_for_account: noop,
    get_account: noop,
    upsert_account: noop,
    upsert_grant: noop,
});
const people = mock_esm("../src/people");
const current_user = {is_admin: true};
mock_esm("../src/state_data", {current_user});
const timerender = mock_esm("../src/timerender");
const ui_report = mock_esm("../src/ui_report");

const settings_connected_accounts = zrequire("settings_connected_accounts");

function account(overrides = {}) {
    return {
        id: 7,
        provider_key: "whatsapp",
        provider_name: "WhatsApp",
        external_account_id: "d38c68c4-d70f-44ec-a17e-c7c845f91c03",
        display_name: "Founder conversations",
        connection_kind: "remote_studio",
        incoming_webhook_bot_id: null,
        created_by_id: 10,
        owner_id: 10,
        approval_state: "approved",
        health_status: "healthy",
        health_checked_at: "2026-08-11T00:00:00+00:00",
        link_state: "linked",
        link_expires_at: null,
        ...overrides,
    };
}

function grant(overrides = {}) {
    return {
        id: 12,
        account_id: 7,
        user_id: 20,
        state: "active",
        all_selectors: false,
        selectors: [
            {
                selector_type: "whatsapp_group",
                source_ref: "src_0123456789abcdef0123456789abcdef",
                display_name: "Leadership | Group",
            },
        ],
        ...overrides,
    };
}

run_test("rerender guards and renders empty state", ({override}) => {
    settings_connected_accounts.reset();
    override(hover_connected_accounts, "get_accounts", () => []);
    settings_connected_accounts.rerender();

    current_user.is_admin = false;
    settings_connected_accounts.set_up();
    current_user.is_admin = true;

    settings_connected_accounts.set_up();
    $("#hover-connected-accounts-list").attr("data-empty", "No accounts");
    settings_connected_accounts.rerender();

    $.reset_selector("#hover-connected-accounts-list");
    $.set_results("#hover-connected-accounts-list", []);
    settings_connected_accounts.rerender();
});

run_test("renders account and grant labels", ({mock_template, override}) => {
    settings_connected_accounts.reset();
    override(people, "get_by_user_id", (user_id) => ({full_name: `User ${user_id}`}));
    override(timerender, "get_full_datetime", () => "rendered date");
    const accounts = [
        account({
            id: 7,
            approval_state: "pending",
            health_status: "unknown",
            owner_id: null,
            health_checked_at: null,
        }),
        account({id: 8, approval_state: "approved", health_status: "healthy"}),
        account({id: 9, approval_state: "revoked", health_status: "degraded"}),
        account({id: 10, approval_state: "approved", health_status: "unavailable"}),
    ];
    override(hover_connected_accounts, "get_accounts", () => accounts);
    override(hover_connected_accounts, "get_grants_for_account", (account_id) =>
        account_id === 7
            ? [
                  grant({all_selectors: true}),
                  grant({id: 13, selectors: []}),
                  grant({id: 14, state: "revoked"}),
              ]
            : [],
    );
    const rendered = [];
    mock_template("settings/connected_account_card.hbs", false, (data) => {
        rendered.push(data);
        return `card-${data.account.id}`;
    });

    settings_connected_accounts.set_up();
    assert.equal($("#hover-connected-accounts-list").html(), "card-7card-8card-9card-10");
    assert.equal(rendered[0].account.owner_name, "translated: Former member");
    assert.equal(rendered[0].account.approval_label, "translated: Pending approval");
    assert.equal(rendered[0].account.health_label, "translated: Health unknown");
    assert.equal(rendered[0].account.health_checked_label, "translated: Not checked");
    assert.equal(rendered[0].grants[0].scope_label, "translated: All selectors");
    assert.equal(rendered[0].grants[1].scope_label, "translated: No selectors (deny all)");
    assert.equal(rendered[0].grants[2].scope_label, "Leadership | Group");
    assert.equal(rendered[2].account.approval_label, "translated: Revoked");
    assert.equal(rendered[2].account.health_label, "translated: Degraded");
    assert.equal(rendered[3].account.health_label, "translated: Unavailable");
});

run_test("approval controls patch accounts and report errors", ({override}) => {
    settings_connected_accounts.reset();
    const selected_account = account();
    override(hover_connected_accounts, "get_accounts", () => []);
    override(hover_connected_accounts, "get_account", () => selected_account);
    let patched;
    override(channel, "patch", (options) => {
        patched = options;
    });
    let upserted;
    override(hover_connected_accounts, "upsert_account", (value) => {
        upserted = value;
    });
    let reported;
    override(ui_report, "error", (...args) => {
        reported = args;
    });
    settings_connected_accounts.set_up();
    const $card = $.create("account card").attr("data-connected-account-id", "7");
    const $button = $.create("account button");
    $button.set_closest_results("[data-connected-account-id]", $card);
    const $section = $("#connected-account-settings");

    $section
        .get_on_handler("click.hover-connected-accounts", ".approve-connected-account")
        .call($button[0]);
    assert.equal(patched.data.approval_state, '"approved"');
    patched.success({connected_account: selected_account});
    assert.equal(upserted, selected_account);
    patched.error({status: 500});
    assert.equal(reported[0], "translated: Could not update Connected Account.");

    $section
        .get_on_handler("click.hover-connected-accounts", ".restore-connected-account")
        .call($button[0]);
    assert.equal(patched.data.approval_state, '"approved"');

    let confirmation;
    override(confirm_dialog, "launch", (options) => {
        confirmation = options;
    });
    $section
        .get_on_handler("click.hover-connected-accounts", ".revoke-connected-account")
        .call($button[0]);
    confirmation.on_click();
    assert.equal(patched.data.approval_state, '"revoked"');
});

run_test("admin starts WhatsApp linking through Hover's own server route", ({override}) => {
    settings_connected_accounts.reset();
    override(hover_connected_accounts, "get_accounts", () => []);
    let request;
    override(channel, "post", (options) => {
        request = options;
    });
    settings_connected_accounts.set_up();

    $("#connected-account-settings")
        .get_on_handler("click.hover-connected-accounts", ".link-whatsapp-account")
        .call();

    assert.equal(request.url, "/json/hover/connected_accounts/whatsapp/link");
});

run_test("grant controls validate, save, edit, and revoke grants", ({mock_template, override}) => {
    settings_connected_accounts.reset();
    const selected_account = account();
    const selected_grant = grant();
    override(hover_connected_accounts, "get_accounts", () => []);
    override(hover_connected_accounts, "get_account", () => selected_account);
    override(hover_connected_accounts, "get_grants_for_account", () => [selected_grant]);
    override(people, "get_realm_active_human_users", () => [{user_id: 20, full_name: "Grace"}]);
    mock_template("settings/connected_account_grant_modal.hbs", false, () => "grant modal");
    let dialog;
    override(dialog_widget, "launch", (options) => {
        dialog = options;
    });
    let submit_request;
    override(dialog_widget, "submit_api_request", (...args) => {
        submit_request = args;
    });
    let hidden = false;
    override(dialog_widget, "hide_dialog_spinner", () => {
        hidden = true;
    });
    let validation_error;
    override(ui_report, "client_error", (message) => {
        validation_error = message;
    });
    let upserted;
    override(hover_connected_accounts, "upsert_grant", (value) => {
        upserted = value;
    });
    settings_connected_accounts.set_up();

    const $account_card = $.create("grant account card").attr("data-connected-account-id", "7");
    const $grant_card = $.create("grant card").attr("data-connected-account-grant-id", "12");
    const $button = $.create("grant button");
    $button.set_closest_results("[data-connected-account-id]", $account_card);
    $button.set_closest_results("[data-connected-account-grant-id]", $grant_card);
    const $section = $("#connected-account-settings");

    $section
        .get_on_handler("click.hover-connected-accounts", ".add-connected-account-grant")
        .call($button[0]);
    assert.equal(dialog.modal_title_text, "translated: Assign Connected Account");
    $("#connected_account_grant_scope").val("restricted");
    $("#connected_account_selectors").val("invalid");
    dialog.on_click();
    assert.equal(hidden, true);
    assert.equal(
        validation_error,
        "translated: Each selector must use: selector type | opaque source reference | display name.",
    );

    $("#connected_account_selectors").val(
        "whatsapp_group | src_0123456789abcdef0123456789abcdef | Leadership | Group",
    );
    $("#connected_account_grantee").val("20");
    dialog.on_click();
    assert.equal(submit_request[1], "/json/hover/connected_accounts/7/grants");
    assert.equal(submit_request[2].user_id, "20");
    assert.equal(JSON.parse(submit_request[2].selectors)[0].display_name, "Leadership | Group");
    submit_request[3].success_continuation({connected_account_grant: selected_grant});
    assert.equal(upserted, selected_grant);

    $section
        .get_on_handler("click.hover-connected-accounts", ".edit-connected-account-grant")
        .call($button[0]);
    assert.equal(dialog.modal_title_text, "translated: Edit Connected Account grant");
    dialog.on_shown();

    let confirmation;
    override(confirm_dialog, "launch", (options) => {
        confirmation = options;
    });
    let delete_request;
    override(channel, "del", (options) => {
        delete_request = options;
    });
    $section
        .get_on_handler("click.hover-connected-accounts", ".revoke-connected-account-grant")
        .call($button[0]);
    confirmation.on_click();
    assert.equal(delete_request.url, "/json/hover/connected_accounts/7/grants/12");
    delete_request.success({connected_account_grant: {...selected_grant, state: "revoked"}});
    assert.equal(upserted.state, "revoked");
});
