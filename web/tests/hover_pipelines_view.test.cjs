"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../src/channel", {});
mock_esm("../src/inbox_ui", {});
mock_esm("../src/left_sidebar_navigation_area", {});
mock_esm("../src/recent_view_ui", {});
mock_esm("../src/stream_data", {subscribed_subs: () => []});
mock_esm("../src/state_data", {
    realm: {
        realm_incoming_webhook_bots: [
            {
                display_name: "GitHub",
                name: "github",
                logo_url: "/static/images/integrations/logos/github.svg",
                description: "Repository activity and deployment events",
                supports_event_filters: true,
                setup_instructions_url: "/integrations/doc/github",
                all_event_types: ["push", "deployment"],
            },
            {
                display_name: "GitLab",
                name: "gitlab",
                logo_url: "/static/images/integrations/logos/gitlab.svg",
                description: "Projects, issues and pipelines",
                supports_event_filters: true,
                setup_instructions_url: "/integrations/doc/gitlab",
                all_event_types: ["push"],
            },
        ],
    },
});

const hover_pipelines_view = zrequire("hover_pipelines_view");

run_test("catalogue selection always describes a single source", () => {
    assert.deepEqual(hover_pipelines_view.catalogue_context_for_testing("git"), {
        has_results: true,
        provider_keys: ["github", "gitlab"],
        source_limit: 1,
    });
});

run_test("empty catalogue does not promote arbitrary providers", () => {
    assert.deepEqual(hover_pipelines_view.catalogue_context_for_testing(""), {
        has_results: false,
        provider_keys: [],
        source_limit: 1,
    });
});
