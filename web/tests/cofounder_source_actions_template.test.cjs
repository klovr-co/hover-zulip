"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_source_actions = require("../templates/cofounder/components/source_actions.hbs");

const {run_test} = require("./lib/test.cjs");

const project_root = path.resolve(__dirname, "../..");
const component_css = fs.readFileSync(
    path.join(project_root, "web/styles/cofounder/components/source-actions.css"),
    "utf8",
);
const story_source = fs.readFileSync(
    path.join(project_root, "web/stories/cofounder_source_actions.stories.ts"),
    "utf8",
);

run_test("Source actions preserve group, count, and availability semantics", () => {
    const html = render_source_actions({
        evidence_url: "#sources",
        integrations: [
            {count: 3, key: "whatsapp", name: "WhatsApp", url: "#whatsapp"},
            {count: 2, key: "instagram", name: "Instagram unavailable"},
        ],
    });

    assert.match(
        html,
        /class="cf-source-actions" role="group" aria-label="(?:translated: )?Knowledge sources"/,
    );
    assert.match(html, /data-cf-evidence-url="#sources"[\s\S]*aria-haspopup="dialog"/);
    assert.match(html, /target="_blank"[\s\S]*rel="noopener noreferrer"/);
    assert.match(html, /aria-label="WhatsApp: 3"/);
    assert.match(html, /cf-source-action--static"[\s\S]*role="img"/);
    assert.match(html, /aria-label="Instagram unavailable: 2"/);
});

run_test("Source action states use contrast-safe Cofounder tokens", () => {
    assert.match(
        component_css,
        /\.cf-source-action:is\(:hover, :focus-visible\)[\s\S]*color: var\(--cf-color-accent-hover\);[\s\S]*background: var\(--cf-surface-selected\);/,
    );
    assert.match(
        component_css,
        /\.cf-source-action--static \{[\s\S]*color: var\(--cf-text-secondary\);/,
    );
    assert.doesNotMatch(
        component_css,
        /\.cf-source-action--static \{[\s\S]*color: var\(--cf-text-tertiary\);/,
    );
    assert.match(
        component_css,
        /\.cf-source-actions \{[\s\S]*min-width: 0;[\s\S]*max-width: 100%;/,
    );
    assert.match(
        component_css,
        /\.cf-source-action \{[\s\S]*max-width: 100%;[\s\S]*overflow-wrap: anywhere;/,
    );
    assert.match(component_css, /\.cf-source-action__count \{[\s\S]*overflow-wrap: anywhere;/);
    assert.match(
        component_css,
        /@media \(hover: none\), \(width <= 600px\) \{[\s\S]*\.cf-source-actions__label \{[\s\S]*flex-basis: 100%;/,
    );
});

run_test("Source action story exposes deterministic request feedback", () => {
    assert.match(story_source, /storybook-source-actions__feedback/);
    assert.match(story_source, /Source evidence dialog requested\./);
    assert.match(story_source, /event\.preventDefault\(\)/);
    assert.match(story_source, /Source integration/);
});
