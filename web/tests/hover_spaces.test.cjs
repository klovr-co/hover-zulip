"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const hover_spaces = zrequire("hover_spaces");

const setup_space = {
    id: 1,
    name: "Launch readiness",
    description: "Prepare the program before launch.",
    state: "setup",
    category: {id: 10, name: "Programs"},
    created_by_id: 5,
    stream_id: null,
    attachments: [],
};

const launched_space = {
    id: 2,
    name: "Annual summit",
    description: "",
    state: "launched",
    category: {id: 11, name: "Events"},
    created_by_id: 5,
    stream_id: 99,
    attachments: [],
};

run_test("initialize and look up spaces", () => {
    hover_spaces.initialize({hover_spaces: [setup_space, launched_space]});

    assert.equal(hover_spaces.get_by_id(setup_space.id), setup_space);
    assert.equal(hover_spaces.get_by_stream_id(launched_space.stream_id), launched_space);
    assert.equal(hover_spaces.get_by_stream_id(404), undefined);
    assert.deepEqual(hover_spaces.get_setup_spaces(), [setup_space]);
    assert.deepEqual(hover_spaces.get_all(), [launched_space, setup_space]);
});

run_test("upsert, remove, and clear", () => {
    hover_spaces.initialize({hover_spaces: [setup_space]});
    const renamed_space = {...setup_space, name: "Launch plan"};
    hover_spaces.upsert(renamed_space);
    assert.equal(hover_spaces.get_by_id(setup_space.id), renamed_space);

    hover_spaces.remove(setup_space.id);
    assert.deepEqual(hover_spaces.get_all(), []);

    hover_spaces.upsert(launched_space);
    hover_spaces.clear();
    assert.deepEqual(hover_spaces.get_all(), []);
});

run_test("server-projected attachments become provider-neutral sidebar Sources", () => {
    const attached_space = {
        ...setup_space,
        attachments: [
            {
                id: 31,
                state: "active",
                history_window: "today",
                history_timezone: "America/Los_Angeles",
                history_start_at: "2026-08-10T07:00:00+00:00",
                custom_start_date: null,
                can_browse_records: true,
                source: {
                    id: 41,
                    provider_key: "whatsapp",
                    source_type: "group",
                    display_name: "Leadership group",
                    account_id: 51,
                    account_display_name: "Founder conversations",
                },
            },
            {
                id: 32,
                state: "active",
                history_window: "custom",
                history_timezone: "UTC",
                history_start_at: "2026-08-01T00:00:00+00:00",
                custom_start_date: "2026-08-01",
                can_browse_records: false,
                source: {
                    id: 42,
                    provider_key: "future_provider",
                    source_type: "workspace",
                    display_name: "Operations workspace",
                    account_id: 52,
                    account_display_name: "Operations",
                },
            },
        ],
    };
    assert.deepEqual(hover_spaces.get_sidebar_sources(attached_space), [
        {
            key: "whatsapp",
            source_key: "41",
            name: "Leadership group",
            detail: "Founder conversations · group",
            icon_class: "fa fa-whatsapp",
            is_external: false,
            attachment_id: 31,
            can_browse_records: true,
            is_history_retained: false,
        },
        {
            key: "future_provider",
            source_key: "42",
            name: "Operations workspace",
            detail: "Operations · workspace",
            icon_class: "fa fa-plug",
            is_external: false,
            attachment_id: 32,
            can_browse_records: false,
            is_history_retained: false,
        },
    ]);
});
