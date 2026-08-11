"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const hover_connected_accounts = zrequire("hover_connected_accounts");

const account = {
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
};

const grant = {
    id: 12,
    account_id: account.id,
    user_id: 20,
    state: "active",
    all_selectors: false,
    selectors: [
        {
            selector_type: "whatsapp_group",
            source_ref: "src_0123456789abcdef0123456789abcdef",
            display_name: "Leadership group",
        },
    ],
};

run_test("initialize and query sanitized account state", () => {
    hover_connected_accounts.initialize({
        hover_connected_accounts: [account],
        hover_connected_account_grants: [grant],
    });
    assert.equal(hover_connected_accounts.get_account(account.id), account);
    assert.deepEqual(hover_connected_accounts.get_accounts(), [account]);
    assert.deepEqual(hover_connected_accounts.get_grants_for_account(account.id), [grant]);
});

run_test("upsert account and grant", () => {
    hover_connected_accounts.initialize({
        hover_connected_accounts: [],
        hover_connected_account_grants: [],
    });
    hover_connected_accounts.upsert_account(account);
    hover_connected_accounts.upsert_grant(grant);
    assert.equal(hover_connected_accounts.get_account(account.id), account);
    assert.deepEqual(hover_connected_accounts.get_grants_for_account(account.id), [grant]);
});

run_test("replace and validate API response", () => {
    hover_connected_accounts.replace_from_response({
        connected_accounts: [account],
        connected_account_grants: [grant],
    });
    assert.deepEqual(hover_connected_accounts.get_accounts(), [account]);
    assert.throws(() =>
        hover_connected_accounts.replace_from_response({
            connected_accounts: [account],
            connected_account_grants: [
                {...grant, selectors: [{...grant.selectors[0], source_ref: 123}]},
            ],
        }),
    );
});
