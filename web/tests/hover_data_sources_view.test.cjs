"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../src/channel", {});
mock_esm("../src/inbox_ui", {});
mock_esm("../src/left_sidebar_navigation_area", {});
mock_esm("../src/recent_view_ui", {});
mock_esm("../src/stream_data", {});
mock_esm("../src/timerender", {});
mock_esm("../src/state_data", {
    realm: {
        realm_incoming_webhook_bots: [
            {
                display_name: "GitHub",
                name: "github",
                logo_url: "/github.svg",
                description: "Repository activity",
                all_event_types: ["push"],
            },
            {
                display_name: "GitLab",
                name: "gitlab",
                logo_url: "/gitlab.svg",
                description: "Projects and pipelines",
                all_event_types: ["push"],
            },
        ],
    },
});

const view = zrequire("hover_data_sources_view");

run_test("connector catalogue stays in the data source flow", () => {
    assert.deepEqual(view.catalogue_context_for_testing("git"), {
        has_results: true,
        provider_keys: ["github", "gitlab"],
    });
    assert.deepEqual(view.catalogue_context_for_testing(""), {
        has_results: false,
        provider_keys: [],
    });
});
