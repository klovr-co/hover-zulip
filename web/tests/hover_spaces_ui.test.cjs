"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

let folders;
let users;
let accounts;
let grants;
let launches;
let submissions;
let posts;
let gets;
let dels;
let client_errors;
let spinner_hide_count;
let sidebar_update_count;

const state_data = mock_esm("../src/state_data", {
    current_user: {user_id: 5},
    realm: {realm_hover_enabled: true},
});
mock_esm("../src/channel_folders", {get_channel_folders: () => folders});
mock_esm("../src/people", {get_realm_active_human_users: () => users});
mock_esm("../src/hover_connected_accounts", {
    get_accounts: () => accounts,
    get_grants_for_account: () => grants,
});
mock_esm("../src/channel", {
    post(options) {
        posts.push(options);
        return {};
    },
    get(options) {
        gets.push(options);
        return {};
    },
    del(options) {
        dels.push(options);
        return {};
    },
});
mock_esm("../src/dialog_widget", {
    launch(options) {
        launches.push(options);
        return options.id ?? "hover-space-modal";
    },
    submit_api_request(request, url, data, options) {
        submissions.push({request, url, data, options});
    },
    hide_dialog_spinner() {
        spinner_hide_count += 1;
    },
    close(callback) {
        callback?.();
    },
});
mock_esm("../src/stream_list", {
    update_streams_sidebar() {
        sidebar_update_count += 1;
    },
});
mock_esm("../src/ui_report", {
    client_error(message) {
        client_errors.push(message);
    },
});

const hover_spaces = zrequire("hover_spaces");
const hover_spaces_ui = zrequire("hover_spaces_ui");

function attachment() {
    return {
        id: 41,
        state: "active",
        history_window: "today",
        history_timezone: "UTC",
        history_start_at: "2026-08-17T00:00:00Z",
        custom_start_date: null,
        can_browse_records: true,
        source: {
            id: 51,
            provider_key: "whatsapp",
            provider_name: "WhatsApp",
            source_type: "group",
            display_name: "Launch team",
            external_url: "",
            supports_live_capture: true,
            account_id: 7,
            account_display_name: "Founder conversations",
        },
        integration_routes: [],
    };
}

function installation(overrides = {}) {
    return {
        id: 81,
        state: "enabled",
        version_id: 71,
        definition_key: "progress",
        name: "Progress",
        version: "1.0.0",
        output_type: "progress_update",
        destination_topic: "Progress",
        navigation_icon: "zulip-icon-check",
        navigation_order: 10,
        content_hash: "a".repeat(64),
        activated_at: "2026-08-17T00:00:00Z",
        processing_start_at: null,
        activation_timezone: "UTC",
        policy_revision: 1,
        policy_hash: "b".repeat(64),
        predecessor_id: null,
        bindings: [{requirement_key: "conversation", attachment_id: 41}],
        triggers: [
            {
                kind: "manual",
                cadence: null,
                local_time: null,
                timezone: null,
                debounce_seconds: null,
            },
        ],
        ...overrides,
    };
}

function module_version() {
    return {
        id: 71,
        definition_key: "progress",
        name: "Progress",
        description: "Summarize progress.",
        version: "1.0.0",
        output_type: "progress_update",
        lookback_days: 30,
        destination_topic: "Progress",
        maximum_runtime_seconds: 300,
        navigation_icon: "zulip-icon-check",
        navigation_order: 10,
        content_hash: "a".repeat(64),
        published_at: "2026-08-17T00:00:00Z",
        requirements: [
            {
                id: 91,
                key: "conversation",
                capability: "messages",
                minimum_count: 1,
                maximum_count: 2,
            },
        ],
        supported_triggers: ["manual", "new_source", "schedule"],
    };
}

function space(overrides = {}) {
    return {
        id: 11,
        name: "Launch plan",
        description: "Prepare the launch.",
        state: "setup",
        category: {id: 3, name: "Projects"},
        created_by_id: 5,
        stream_id: null,
        attachments: [attachment()],
        administrators: [{user_id: 5, full_name: "Owner"}],
        memberships: [
            {
                id: 21,
                user_id: 6,
                full_name: "Existing member",
                role: "subscriber",
                is_administrator: false,
            },
        ],
        membership_suggestions: [
            {
                id: 31,
                user_id: 7,
                full_name: "Suggested member",
                suggested_role: "contributor",
                state: "pending",
                match_basis: "verified_email",
            },
        ],
        module_installations: [installation()],
        module_catalog: [module_version()],
        ...overrides,
    };
}

function discovered_source() {
    return {
        source_ref: "src_0123456789abcdef0123456789abcdef",
        provider_key: "whatsapp",
        source_type: "group",
        display_name: "Launch team",
        account_id: 7,
        account_display_name: "Founder conversations",
    };
}

function reset() {
    folders = [
        {id: 3, name: "Projects", is_archived: false},
        {id: 4, name: "Archive", is_archived: true},
    ];
    users = [
        {user_id: 8, full_name: "Zoë"},
        {user_id: 6, full_name: "Existing member"},
        {user_id: 9, full_name: "Ada"},
    ];
    accounts = [
        {
            id: 7,
            provider_name: "WhatsApp",
            display_name: "Founder conversations",
            approval_state: "approved",
        },
        {
            id: 8,
            provider_name: "WhatsApp",
            display_name: "Pending",
            approval_state: "pending",
        },
    ];
    grants = [{account_id: 7, user_id: 5, state: "active"}];
    launches = [];
    submissions = [];
    posts = [];
    gets = [];
    dels = [];
    client_errors = [];
    spinner_hide_count = 0;
    sidebar_update_count = 0;
    state_data.realm.realm_hover_enabled = true;
    hover_spaces.initialize({hover_spaces: [space()]});
}

run_test("creates a Space from trimmed modal input", () => {
    reset();
    hover_spaces_ui.open_create_space();

    const options = launches.at(-1);
    assert.equal(options.modal_title_text, "translated: Create Space");
    assert.doesNotMatch(options.modal_content_html, /Archive/);
    options.on_shown();
    assert.equal($("#new_hover_space_name").is_focused(), true);

    $("#new_hover_space_name").val("  New launch  ");
    $("#new_hover_space_description").val("  Details  ");
    $("#new_hover_space_category").val("3.8");
    options.on_click();

    const submission = submissions.at(-1);
    assert.equal(submission.url, "/json/hover/spaces");
    assert.deepEqual(submission.data, {
        name: "New launch",
        description: "Details",
        category_id: "3",
    });
    const created_space = space({name: "New launch"});
    submission.options.success_continuation({space: created_space});
    assert.equal(hover_spaces.get_by_id(11).name, "New launch");
    assert.equal(sidebar_update_count, 1);
});

run_test("setup ignores disabled realms and non-setup Spaces", () => {
    reset();
    state_data.realm.realm_hover_enabled = false;
    hover_spaces_ui.open_setup_space(11);
    assert.equal(launches.length, 0);

    state_data.realm.realm_hover_enabled = true;
    hover_spaces.initialize({hover_spaces: [space({state: "launched", stream_id: 99})]});
    hover_spaces_ui.open_setup_space(11);
    hover_spaces_ui.open_setup_space(404);
    assert.equal(launches.length, 0);
});

run_test("coordinates Source discovery, preview, and attachment", () => {
    reset();
    $("#hover_source_account").val("7");
    $("#hover_source_query").val("  launch  ");
    $("#hover_source_history_window").val("today");
    hover_spaces_ui.open_setup_space(11);

    const options = launches.at(-1);
    assert.equal(options.modal_title_text, "translated: Space Setup");
    assert.match(options.modal_content_html, /Launch plan/);
    options.on_click();
    assert.equal(client_errors.length, 1);
    assert.equal(spinner_hide_count, 1);

    options.on_shown();
    assert.equal(posts.at(-1).url, "/json/hover/spaces/11/sources/discover");
    assert.deepEqual(posts.at(-1).data, {
        account_id: "7",
        query: '"launch"',
        cursor: "null",
        limit: "20",
    });
    posts.at(-1).success({
        sources: [discovered_source()],
        next_cursor: "page-2",
        has_more: true,
    });
    assert.match($("#hover_source_discovery_results").html(), /Launch team/);

    const $panel = $("#hover-source-attachment-panel");
    $panel.get_on_handler("click", ".hover-source-next-button")();
    assert.equal(posts.at(-1).data.cursor, '"page-2"');
    posts.at(-1).success({sources: [], next_cursor: "", has_more: false});
    assert.equal(
        $("#hover_source_discovery_status").text(),
        "translated: No permitted Sources found.",
    );

    $panel.get_on_handler("click", ".hover-source-search-button")();
    posts.at(-1).error({status: 429});
    assert.match($("#hover_source_discovery_status").text(), /temporarily unavailable/);
    posts.at(-1).error({status: 400});
    assert.match($("#hover_source_discovery_status").text(), /could not be completed/);

    let prevented = false;
    let stopped = false;
    const $preview = $("#preview-source").attr("data-source-ref", discovered_source().source_ref);
    $panel.get_on_handler(
        "click",
        ".hover-source-preview-button",
    )({
        currentTarget: $preview[0],
        preventDefault() {
            prevented = true;
        },
        stopPropagation() {
            stopped = true;
        },
    });
    assert.equal(prevented, true);
    assert.equal(stopped, true);
    posts.at(-1).success({source: discovered_source()});
    assert.equal($("#hover_source_preview").hasClass("hide"), false);
    assert.equal(
        $("#hover_source_discovery_status").text(),
        "translated: Source identity verified.",
    );

    $("#hover_source_history_window").val("custom").trigger("change");
    options.on_click();
    assert.equal(client_errors.length, 2);
    $("#hover_source_custom_start_date").val("2026-08-01");
    options.on_click();
    const submission = submissions.at(-1);
    assert.equal(submission.url, "/json/hover/spaces/11/sources");
    assert.equal(submission.data.custom_start_date, '"2026-08-01"');
    submission.options.error_continuation({status: 409});
    assert.match($("#hover_source_discovery_status").text(), /immutable history window/);
    submission.options.error_continuation({status: 400});
    submission.options.success_continuation({
        space: space(),
        attachment: attachment(),
        created: true,
    });
    assert.equal(sidebar_update_count, 1);

    const $candidate = $("#candidate").val(discovered_source().source_ref);
    $panel.get_on_handler(
        "change",
        "input[name='hover_source_candidate']",
    )({
        currentTarget: $candidate[0],
    });
    posts.at(-1).success({source: discovered_source()});

    $("#hover_source_account").trigger("change");
    assert.equal($("#hover_source_preview").hasClass("hide"), true);
    $("#hover_source_history_window").val("today").trigger("change");
    let key_prevented = false;
    $("#hover_source_query").get_on_handler("keydown")({
        key: "Enter",
        preventDefault() {
            key_prevented = true;
        },
    });
    assert.equal(key_prevented, true);
});

run_test("coordinates membership and Module mutations through modal callbacks", () => {
    reset();
    $("#hover_source_account").val("7");
    hover_spaces_ui.open_setup_space(11);
    const options = launches.at(-1);
    options.on_shown();

    const $membership_panel = $("#hover-space-membership-panel");
    const membership_handler = $membership_panel.get_on_handler(
        "click",
        "[data-membership-action]",
    );
    $(".hover-member-role-select[data-user-id='7']").val("contributor");
    const $confirm = $("#confirm-member")
        .attr("data-membership-action", "confirm-suggestion")
        .attr("data-user-id", "7");
    membership_handler({currentTarget: $confirm[0]});
    assert.equal(posts.at(-1).url, "/json/hover/spaces/11/members");
    posts.at(-1).error();
    assert.match(client_errors.at(-1), /Could not update Space membership/);
    posts.at(-1).success({space: space()});
    assert.equal(launches.at(-1).modal_title_text, "translated: Space Setup");

    const $remove = $("#remove-member")
        .attr("data-membership-action", "remove")
        .attr("data-user-id", "6");
    membership_handler({currentTarget: $remove[0]});
    assert.equal(dels.at(-1).url, "/json/hover/spaces/11/members/6");
    dels.at(-1).error();
    dels.at(-1).success({space: space()});

    const $promote = $("#promote-member")
        .attr("data-membership-action", "promote")
        .attr("data-user-id", "6");
    membership_handler({currentTarget: $promote[0]});
    assert.equal(posts.at(-1).url, "/json/hover/spaces/11/admins");
    posts.at(-1).error();
    posts.at(-1).success();

    const role_handler = $(".hover-member-role-select").get_on_handler("change");
    const $role = $("#member-role").attr("data-user-id", "6").val("contributor");
    const $row = $("#member-row");
    $role.set_closest_results(".hover-member-row", $row);
    $row.set_find_results("[data-membership-action='confirm-suggestion']", []);
    role_handler({currentTarget: $role[0]});
    assert.equal(posts.at(-1).url, "/json/hover/spaces/11/members");

    $("#hover_member_user").val("8");
    $("#hover_member_role").val("subscriber");
    $(".hover-member-add-button").get_on_handler("click")();
    assert.deepEqual(posts.at(-1).data, {user_id: "8", role: '"subscriber"'});

    const $trigger = $("#module-trigger").val("schedule");
    const $card = $("#module-card").attr("data-version-id", "71");
    $trigger.set_closest_results(".hover-module-card", $card);
    $card.set_find_results(".hover-module-schedule-fields", $("#schedule-fields"));
    $card.set_find_results(".hover-module-debounce-field", $("#debounce-field"));
    $(".hover-module-trigger-select").get_on_handler("change")({currentTarget: $trigger[0]});

    const $attachment_input = $("#module-attachment");
    $attachment_input[0].value = "41";
    $card.set_find_results("input[data-module-attachment]:checked", $attachment_input);
    $card.set_find_results(".hover-module-trigger-select", $trigger);
    $card.set_find_results(".hover-module-backfill-start", $("#backfill").val("2026-08-01"));
    $card.set_find_results(".hover-module-cadence", $("#cadence").val("weekly"));
    $card.set_find_results(".hover-module-local-time", $("#local-time").val("09:30"));
    $card.set_find_results(
        ".hover-module-backfill-confirm",
        $("#backfill-confirm").prop("checked", true),
    );
    const fake_jquery_prototype = Object.getPrototypeOf($card);
    fake_jquery_prototype.map = function (callback) {
        const values = Array.from(this, (element, index) => callback(index, element));
        return {get: () => values};
    };
    const $install = $("#install-module");
    $install.set_closest_results(".hover-module-card", $card);
    $(".hover-module-install-button").get_on_handler("click")({currentTarget: $install[0]});
    assert.equal(posts.at(-1).url, "/json/hover/spaces/11/modules");
    assert.equal(posts.at(-1).data.cadence, '"weekly"');
    posts.at(-1).error();
    assert.match(client_errors.at(-1), /Could not enable this Module/);
    posts.at(-1).success({space: space(), installation: installation()});

    $trigger.val("new_source");
    $(".hover-module-trigger-select").get_on_handler("change")({currentTarget: $trigger[0]});
    $("#backfill").val("");
    $(".hover-module-install-button").get_on_handler("click")({currentTarget: $install[0]});
    assert.equal(posts.at(-1).data.debounce_seconds, "300");
    assert.equal(posts.at(-1).data.backfill_start_at, "null");

    const $disable = $("#disable-module").attr("data-installation-id", "81");
    $(".hover-module-disable-button").get_on_handler("click")({currentTarget: $disable[0]});
    assert.equal(posts.at(-1).url, "/json/hover/module-installations/81/disable");
    posts.at(-1).error();
    assert.match(client_errors.at(-1), /Could not disable this Module/);
    posts.at(-1).success();
    assert.equal(gets.at(-1).url, "/json/hover/spaces/11");
    gets.at(-1).success({space: space()});

    $(".hover-space-launch-button").get_on_handler("click")();
    assert.equal(posts.at(-1).url, "/json/hover/spaces/11/launch");
    posts.at(-1).error();
    assert.match(client_errors.at(-1), /Launch is not ready/);
    posts.at(-1).success({space: space({state: "launched", stream_id: 99}), created: true});
    assert.equal(hover_spaces.get_by_id(11).state, "launched");
    assert.ok(sidebar_update_count >= 3);
    delete fake_jquery_prototype.map;
});
