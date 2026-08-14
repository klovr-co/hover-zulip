"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_setup_row = require("../templates/hover_space_setup_sidebar_row.hbs");
const render_stream_sidebar_row = require("../templates/stream_sidebar_row.hbs");

const {run_test} = require("./lib/test.cjs");

const project_root = path.resolve(__dirname, "../..");
const component_css = fs.readFileSync(
    path.join(project_root, "web/styles/cofounder/components/space-navigation.css"),
    "utf8",
);
const behavior_source = ["sidebar_ui.ts", "stream_list.ts", "topic_list.ts"]
    .map((file) => fs.readFileSync(path.join(project_root, "web/src", file), "utf8"))
    .join("\n");
const setup_behavior_source = fs.readFileSync(
    path.join(project_root, "web/src/sidebar_ui.ts"),
    "utf8",
);

const source = {
    detail: "WhatsApp · Live since 8/11/2026",
    icon_name: "phone",
    is_external: false,
    key: "whatsapp",
    name: "Mentors & Volunteers",
    source_key: "41",
    url: "#source-41",
};

run_test("Space navigation uses owned modules, sources, icons, and behavior hooks", () => {
    const html = render_stream_sidebar_row({
        can_post_messages: true,
        color: "#57745d",
        has_hover_ai_modules: true,
        hover_ai_modules: [
            {
                count: 4,
                has_count: true,
                icon_name: "file-text",
                key: "conversation_digest",
                name: "Conversation Digest",
                url: "#digest",
            },
        ],
        hover_attached_sources: [source],
        id: 7,
        invite_only: true,
        is_archived: false,
        is_empty_topic_only_channel: false,
        is_hover_space: true,
        is_muted: false,
        is_web_public: false,
        name: "AIMTO Events",
        url: "#aimto-events",
    });

    assert.match(html, /class="cf-module-nav"/);
    assert.match(html, /class="cf-source-ledger"/);
    assert.match(html, /data-cf-module-key="conversation_digest"/);
    assert.match(html, /data-cf-source-key="41"/);
    assert.match(html, /class="cf-icon cf-icon--compact cf-module-nav__icon"/);
    assert.doesNotMatch(
        html,
        /hover-ai-modules|hover-source-ledger|data-hover-(?:module|source)-key|zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/,
    );
    assert.match(behavior_source, /\.cf-module-nav/);
    assert.doesNotMatch(behavior_source, /\.hover-ai-modules/);
    assert.doesNotMatch(component_css, /var\(--(?:ds|hover)-|#[0-9a-f]{3,8}\b|hsl\(/i);
});

run_test("setup Space row composes the same source ledger without legacy hooks", () => {
    const html = render_setup_row({
        has_hover_attached_sources: true,
        hover_attached_sources: [source],
        id: 8,
        name: "Community launch",
    });

    assert.match(html, /class="cf-space-setup narrow-filter" data-cf-space-id="8"/);
    assert.match(html, /class="cf-space-setup__main"/);
    assert.match(html, /class="cf-space-setup__status">(?:translated: )?Setup/);
    assert.match(html, /class="cf-source-ledger"/);
    assert.doesNotMatch(
        html + setup_behavior_source,
        /hover-space-setup-row|data-hover-space-id|hover-source-ledger|subscription_block|selectable_sidebar_block|stream-privacy|stream-name|zulip-icon|\bfa(?:\s|-)|<i(?:\s|>)/,
    );
    assert.match(setup_behavior_source, /\.cf-space-setup__main/);
});
