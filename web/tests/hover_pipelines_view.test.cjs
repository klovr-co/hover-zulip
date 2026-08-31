"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../src/channel", {});
mock_esm("../src/inbox_ui", {});
mock_esm("../src/left_sidebar_navigation_area", {});
mock_esm("../src/recent_view_ui", {});
mock_esm("../src/stream_data", {
    subscribed_subs: () => [],
    can_post_messages_in_stream: () => true,
});
mock_esm("../src/timerender", {});
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

run_test("selection uses existing unassigned data sources", () => {
    const sources = [
        {id: 1, name: "GitHub · Verona", pipeline_name: null},
        {id: 2, name: "GitLab · Engineering", pipeline_name: "Release digest"},
        {id: 3, name: "Customer feedback", pipeline_name: null},
    ];
    assert.deepEqual(hover_pipelines_view.source_selection_context_for_testing(sources, "git"), {
        source_ids: [1],
        source_limit: 1,
    });
});

run_test("selection remains single-source when all available sources are shown", () => {
    assert.deepEqual(
        hover_pipelines_view.source_selection_context_for_testing(
            [
                {id: 1, name: "GitHub · Verona", pipeline_name: null},
                {id: 2, name: "Customer feedback", pipeline_name: null},
            ],
            "",
        ),
        {
            source_ids: [1, 2],
            source_limit: 1,
        },
    );
});
