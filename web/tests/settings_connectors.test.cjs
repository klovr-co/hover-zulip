"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");
class FakeHTMLElement {}
set_global("HTMLElement", FakeHTMLElement);
const document_stub = set_global("document", {querySelectorAll: () => []});

const realm = {
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
        {
            display_name: "Slack-compatible webhook",
            name: "slack_incoming",
            logo_url: "/static/images/integrations/logos/slack.svg",
            description: "Updates from any Slack-compatible service",
            supports_event_filters: false,
            setup_instructions_url: "/integrations/doc/slack_incoming",
            all_event_types: null,
        },
        {
            display_name: "JSON",
            name: "json",
            logo_url: "/static/images/integrations/logos/zulip.svg",
            description: "Generic JSON payloads",
            supports_event_filters: false,
            setup_instructions_url: "/integrations/doc/json",
            all_event_types: null,
        },
    ],
};
mock_esm("../src/state_data", {realm});

const settings_connectors = zrequire("settings_connectors");

run_test("empty search shows only generic fallbacks", () => {
    assert.deepEqual(settings_connectors.catalogue_context_for_testing(""), {
        has_results: false,
        show_fallbacks: true,
        provider_keys: [],
    });
});

run_test("named providers appear only for matching searches", () => {
    assert.deepEqual(settings_connectors.catalogue_context_for_testing("git"), {
        has_results: true,
        show_fallbacks: false,
        provider_keys: ["github", "gitlab"],
    });
    assert.deepEqual(settings_connectors.catalogue_context_for_testing("PIPELINES"), {
        has_results: true,
        show_fallbacks: false,
        provider_keys: ["gitlab"],
    });
});

run_test("no named match restores Slack and REST fallback state", () => {
    assert.deepEqual(settings_connectors.catalogue_context_for_testing("custom internal tool"), {
        has_results: false,
        show_fallbacks: true,
        provider_keys: [],
    });
});

run_test("live update refetches a visible connector inventory", ({override}) => {
    let visible = false;
    const element = new FakeHTMLElement();
    element.offsetParent = {};
    override(document_stub, "querySelectorAll", () => (visible ? [element] : []));

    let request;
    override(channel, "get", (options) => {
        request = options;
    });

    settings_connectors.handle_live_update();
    assert.strictEqual(request, undefined);

    visible = true;
    settings_connectors.handle_live_update();
    assert.strictEqual(request.url, "/json/hover/connectors");
});
