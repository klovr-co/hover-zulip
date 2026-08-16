"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const pipeline_library = zrequire("hover_pipeline_library");

function version({id = 11, name = "Topic Analysis", archived = false} = {}) {
    return {
        id,
        definition_key: "topic_analysis",
        name,
        description: "Find the themes that moved a conversation.",
        version: "1.0.0",
        output_type: "generated_update",
        destination_topic: "Topic Analysis",
        navigation_icon: "zulip-icon-bot",
        navigation_order: 20,
        content_hash: "a".repeat(64),
        published_at: "2026-08-17T01:00:00Z",
        lookback_days: 7,
        maximum_runtime_seconds: 300,
        archived,
        requirements: [
            {
                key: "source",
                capability: "records_read",
                minimum_count: 1,
                maximum_count: 3,
            },
        ],
        supported_triggers: ["manual"],
    };
}

function contract({name = "Campaign Brief", stable_key = "campaign_brief"} = {}) {
    return {
        stable_key,
        name,
        description: "Build a source-backed campaign brief.",
        version: "1.0.0",
        input_contract: {type: "source_records", required_fields: ["text"]},
        lookback_days: 14,
        runtime_key: "pipeline_runtime_v1",
        prompt_key: "campaign_brief_v1",
        integration_keys: ["documents"],
        output_type: "generated_update",
        output_template: {format: "markdown", sections: ["summary", "evidence"]},
        maximum_runtime_seconds: 420,
        destination_topic: "Campaign Brief",
        navigation_icon: "zulip-icon-bot",
        navigation_order: 40,
        requirements: [
            {
                key: "source",
                capability: "records_read",
                minimum_count: 1,
                maximum_count: 2,
            },
        ],
        supported_triggers: ["manual", "schedule"],
    };
}

function response({can_archive = false} = {}) {
    return {
        definitions: [
            {
                id: 1,
                stable_key: "topic_analysis",
                name: "Topic Analysis",
                description: "Find themes.",
                archived: false,
                versions: [version()],
            },
            {
                id: 2,
                stable_key: "old_pipeline",
                name: "Archived Pipeline",
                description: "No longer discoverable.",
                archived: true,
                versions: [version({id: 12, name: "Archived Pipeline", archived: true})],
            },
        ],
        drafts: [
            {
                id: 21,
                definition_id: null,
                based_on_version_id: null,
                author_id: 8,
                collaborator_user_ids: [9],
                revision: 3,
                state: "draft",
                published_version_id: null,
                date_updated: "2026-08-17T02:00:00Z",
                contract: contract(),
            },
        ],
        creator_user_ids: [8, 9],
        permissions: {
            can_create: true,
            can_manage_creators: false,
            can_archive,
        },
    };
}

run_test("validates and selects the browser-safe Pipeline Library projection", () => {
    const parsed = pipeline_library.replace(response());
    assert.ok(parsed);
    assert.deepEqual(
        pipeline_library.visible_definitions().map((definition) => definition.name),
        ["Topic Analysis"],
    );
    assert.equal(pipeline_library.sorted_drafts()[0].contract.name, "Campaign Brief");
    assert.equal(pipeline_library.can_edit_draft(parsed.drafts[0], 9), true);
    assert.equal(pipeline_library.can_edit_draft(parsed.drafts[0], 10), false);
});

run_test("administrators can inspect archived entries and published drafts stay immutable", () => {
    const parsed = pipeline_library.replace(response({can_archive: true}));
    assert.ok(parsed);
    assert.deepEqual(
        pipeline_library.visible_definitions().map((definition) => definition.name),
        ["Archived Pipeline", "Topic Analysis"],
    );
    const published = {...parsed.drafts[0], state: "published", published_version_id: 99};
    assert.equal(pipeline_library.can_edit_draft(published, 8), false);
});

run_test("rejects malformed private contracts without replacing current state", () => {
    const valid = pipeline_library.replace(response());
    assert.ok(valid);
    assert.equal(
        pipeline_library.replace({
            ...response(),
            drafts: [{...response().drafts[0], contract: {...contract(), runtime_key: 42}}],
        }),
        undefined,
    );
    assert.equal(pipeline_library.get(), valid);
});

run_test("creates a complete, provider-neutral blank authoring contract", () => {
    const blank = pipeline_library.blank_contract();
    assert.equal(blank.version, "1.0.0");
    assert.equal(blank.lookback_days, 7);
    assert.deepEqual(blank.supported_triggers, ["manual"]);
    assert.equal(JSON.stringify(blank).includes("credential"), false);
    assert.equal(JSON.stringify(blank).includes("endpoint"), false);
});

run_test("validates the authoritative draft returned with a mutation", () => {
    const draft = response().drafts[0];
    assert.deepEqual(pipeline_library.draft_from_mutation({...response(), draft}), draft);
    assert.equal(
        pipeline_library.draft_from_mutation({...response(), draft: {...draft, revision: "3"}}),
        undefined,
    );
});
