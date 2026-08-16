"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

global.HTMLFormElement = class HTMLFormElement {};

const requests = [];
let dialog_config;

function request(method, options) {
    requests.push({method, ...options});
}

mock_esm("../src/channel", {
    get: (options) => request("GET", options),
    post: (options) => request("POST", options),
    patch: (options) => request("PATCH", options),
    del: (options) => request("DELETE", options),
    xhr_error_message: (message) => message,
});
mock_esm("../src/dialog_widget", {
    launch(config) {
        dialog_config = config;
        $("#hover_pipeline_library_root").html(config.modal_content_html);
        config.post_render();
    },
});
mock_esm("../src/people", {
    maybe_get_user_by_id(user_id) {
        return {
            7: {user_id: 7, full_name: "Ada Admin"},
            8: {user_id: 8, full_name: "Casey Creator"},
            9: {user_id: 9, full_name: "Morgan Maker"},
        }[user_id];
    },
    get_realm_active_human_users() {
        return [
            {user_id: 7, full_name: "Ada Admin", is_guest: false},
            {user_id: 8, full_name: "Casey Creator", is_guest: false},
            {user_id: 9, full_name: "Morgan Maker", is_guest: false},
        ];
    },
});
mock_esm("../src/state_data", {
    current_user: {user_id: 7, is_guest: false},
    realm: {realm_hover_enabled: true},
});

const pipeline_library_ui = zrequire("hover_pipeline_library_ui");

const contract = {
    stable_key: "campaign_brief",
    name: "Campaign Brief",
    description: "Build a source-backed campaign brief.",
    version: "1.0.0",
    input_contract: {type: "source_records"},
    lookback_days: 14,
    runtime_key: "pipeline_runtime_v1",
    prompt_key: "campaign_brief_v1",
    integration_keys: ["documents"],
    output_type: "generated_update",
    output_template: {format: "markdown"},
    maximum_runtime_seconds: 420,
    destination_topic: "Campaign Brief",
    navigation_icon: "zulip-icon-bot",
    navigation_order: 40,
    requirements: [{key: "source", capability: "records_read", minimum_count: 1, maximum_count: 2}],
    supported_triggers: ["manual"],
};

const topic_analysis = {
    id: 11,
    definition_key: "topic_analysis",
    name: "Topic Analysis",
    description: "Find themes.",
    version: "1.0.0",
    output_type: "generated_update",
    destination_topic: "Topic Analysis",
    navigation_icon: "zulip-icon-bot",
    navigation_order: 20,
    content_hash: "a".repeat(64),
    published_at: "2026-08-17T01:00:00Z",
    lookback_days: 7,
    maximum_runtime_seconds: 300,
    archived: false,
    requirements: [{key: "source", capability: "records_read", minimum_count: 1, maximum_count: 1}],
    supported_triggers: ["manual"],
};

function library() {
    return {
        definitions: [
            {
                id: 1,
                stable_key: "topic_analysis",
                name: "Topic Analysis",
                description: "Find themes.",
                archived: false,
                versions: [topic_analysis],
            },
            {
                id: 2,
                stable_key: "marketing_digest",
                name: "Marketing Digest",
                description: "Summarize campaign movement.",
                archived: false,
                versions: [
                    {
                        ...topic_analysis,
                        id: 12,
                        definition_key: "marketing_digest",
                        name: "Marketing Digest",
                        destination_topic: "Marketing Digest",
                    },
                ],
            },
        ],
        drafts: [
            {
                id: 21,
                definition_id: null,
                based_on_version_id: null,
                author_id: 8,
                collaborator_user_ids: [9],
                revision: 2,
                state: "draft",
                published_version_id: null,
                date_updated: "2026-08-17T02:00:00Z",
                contract,
            },
        ],
        creator_user_ids: [8, 9],
        permissions: {can_create: true, can_manage_creators: true, can_archive: true},
    };
}

run_test("opens, validates, and renders examples through the ordinary definition path", () => {
    pipeline_library_ui.open();
    assert.equal(dialog_config.id, "hover-pipeline-library-modal");
    assert.equal(requests.length, 1);
    assert.equal(requests[0].method, "GET");
    assert.equal(requests[0].url, "/json/hover/pipeline-library");

    requests[0].success(library());
    const html = $("#hover_pipeline_library_root").html();
    assert.match(html, /Pipeline Creator/);
    assert.match(html, /Private draft/);
    assert.match(html, /Campaign Brief/);
    assert.match(html, /Topic Analysis/);
    assert.match(html, /Marketing Digest/);
    assert.match(html, /Immutable/);
    assert.doesNotMatch(html, /pipeline_runtime_v1/);
    assert.doesNotMatch(html, /campaign_brief_v1/);

    const $root = $("#hover_pipeline_library_root");

    $("#hover_pipeline_creator_user").val("7");
    const $grant_form = $("#pipeline-grant-form-for-test");
    $grant_form.set_find_results("button[type='submit']", $("#pipeline-grant-button-for-test"));
    $root.get_on_handler(
        "submit",
        "[data-pipeline-grant-creator]",
    )({
        preventDefault() {},
        currentTarget: $grant_form,
    });
    assert.equal(requests.at(-1).method, "POST");
    assert.equal(requests.at(-1).url, "/json/hover/pipeline-library/creators");
    assert.deepEqual(requests.at(-1).data, {user_id: "7"});

    const $revoke = $("#pipeline-revoke-button-for-test").attr("data-pipeline-revoke-creator", "9");
    $root.get_on_handler("click", "[data-pipeline-revoke-creator]")({currentTarget: $revoke});
    assert.equal(requests.at(-1).method, "DELETE");
    assert.equal(requests.at(-1).url, "/json/hover/pipeline-library/creators/9");

    const $successor = $("#pipeline-successor-button-for-test").attr(
        "data-pipeline-create-successor",
        "11",
    );
    $root.get_on_handler(
        "click",
        "[data-pipeline-create-successor]",
    )({
        currentTarget: $successor,
    });
    assert.equal(requests.at(-1).url, "/json/hover/pipeline-library/versions/11/successor");

    const $archive_definition = $("#pipeline-archive-definition-for-test").attr(
        "data-pipeline-archive-definition",
        "1",
    );
    $root.get_on_handler(
        "click",
        "[data-pipeline-archive-definition]",
    )({
        currentTarget: $archive_definition,
    });
    assert.equal(requests.at(-1).url, "/json/hover/pipeline-library/definitions/1/archive");

    const $archive_version = $("#pipeline-archive-version-for-test").attr(
        "data-pipeline-archive-version",
        "11",
    );
    $root.get_on_handler(
        "click",
        "[data-pipeline-archive-version]",
    )({
        currentTarget: $archive_version,
    });
    assert.equal(requests.at(-1).url, "/json/hover/pipeline-library/versions/11/archive");

    const open_draft = $root.get_on_handler("click", "[data-pipeline-open-draft]");
    const $draft_button = $("#pipeline-draft-button-for-test").attr(
        "data-pipeline-open-draft",
        "21",
    );
    open_draft({currentTarget: $draft_button});
    const editor_html = $root.html();
    assert.match(editor_html, /Private version workshop/);
    assert.match(editor_html, /Input contract \(JSON\)/);
    assert.match(editor_html, /pipeline_runtime_v1/);
    assert.match(editor_html, /Morgan Maker/);

    $(".hover-pipeline-editor").attr("data-draft-id", "21");

    $("#hover_pipeline_collaborator_user").val("7");
    $root.get_on_handler(
        "click",
        "[data-pipeline-add-collaborator]",
    )({
        currentTarget: $("#pipeline-add-collaborator-for-test"),
    });
    assert.equal(requests.at(-1).url, "/json/hover/pipeline-library/drafts/21/collaborators");
    assert.deepEqual(requests.at(-1).data, {user_id: "7"});

    const $remove_collaborator = $("#pipeline-remove-collaborator-for-test").attr(
        "data-pipeline-remove-collaborator",
        "9",
    );
    $root.get_on_handler(
        "click",
        "[data-pipeline-remove-collaborator]",
    )({
        currentTarget: $remove_collaborator,
    });
    assert.equal(requests.at(-1).method, "DELETE");
    assert.equal(requests.at(-1).url, "/json/hover/pipeline-library/drafts/21/collaborators/9");

    const publish = $root.get_on_handler("click", "[data-pipeline-publish]");
    const $publish_button = $("#pipeline-publish-button-for-test");
    const editor_fields = Object.entries({
        stable_key: contract.stable_key,
        name: contract.name,
        description: contract.description,
        version: contract.version,
        input_contract: JSON.stringify(contract.input_contract),
        lookback_days: String(contract.lookback_days),
        runtime_key: contract.runtime_key,
        prompt_key: contract.prompt_key,
        integration_keys: contract.integration_keys.join(", "),
        output_type: contract.output_type,
        output_template: JSON.stringify(contract.output_template),
        maximum_runtime_seconds: String(contract.maximum_runtime_seconds),
        destination_topic: contract.destination_topic,
        navigation_icon: contract.navigation_icon,
        navigation_order: String(contract.navigation_order),
        requirements: JSON.stringify(contract.requirements),
    });
    for (const [name, value] of editor_fields) {
        $(`#hover_pipeline_draft_form [name='${name}']`).val(value);
    }
    $("#hover_pipeline_draft_form input[name='supported_trigger']:checked").val("manual");
    publish({currentTarget: $publish_button});
    const save_before_publish = requests.at(-1);
    assert.equal(save_before_publish.method, "PATCH");
    assert.equal(save_before_publish.url, "/json/hover/pipeline-library/drafts/21");
    assert.equal(save_before_publish.data.revision, "2");

    const saved_library = library();
    saved_library.drafts[0].revision = 3;
    save_before_publish.success({...saved_library, draft: saved_library.drafts[0]});
    assert.equal(requests.at(-1).method, "POST");
    assert.equal(requests.at(-1).url, "/json/hover/pipeline-library/drafts/21/publish");
    assert.deepEqual(requests.at(-1).data, {revision: "3"});

    dialog_config.on_hidden();
    $.clear_all_elements();
});

run_test("ordinary members receive a read-only published shelf", () => {
    pipeline_library_ui.open();
    const request = requests.at(-1);
    assert.equal(request.method, "GET");
    request.success({
        ...library(),
        drafts: [],
        creator_user_ids: [],
        permissions: {
            can_create: false,
            can_manage_creators: false,
            can_archive: false,
        },
    });

    const html = $("#hover_pipeline_library_root").html();
    assert.match(html, /Published library · Read-only/);
    assert.match(html, /Topic Analysis/);
    assert.match(html, /Marketing Digest/);
    assert.doesNotMatch(html, /New pipeline/);
    assert.doesNotMatch(html, /Visible drafts/);
    assert.doesNotMatch(html, /Draft successor/);
    assert.doesNotMatch(html, /Archive version/);

    dialog_config.on_hidden();
    $.clear_all_elements();
});
