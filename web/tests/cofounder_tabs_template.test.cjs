"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_tabs = require("../templates/cofounder/components/tabs.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("renders the standalone Cofounder tabs contract", () => {
    const html = render_tabs({
        aria_label: "Source views",
        custom_classes: "cf-tabs--fill",
        tabs: [
            {id: 0, key: "overview", label: "Overview", selected: true},
            {id: 1, key: "activity", label: "Activity"},
            {id: 2, key: "permissions", label: "Permissions", disabled: true},
        ],
    });

    assert.match(html, /class="cf-tabs cf-tabs--fill" role="tablist"/);
    assert.match(html, /aria-label="Source views"/);
    assert.equal((html.match(/role="tab"/g) ?? []).length, 3);
    assert.match(html, /cf-tabs__tab cf-tabs__tab--selected/);
    assert.match(html, /aria-selected="true"[^>]+tabindex="0"/);
    assert.match(html, /cf-tabs__tab cf-tabs__tab--disabled/);
    assert.match(html, /aria-disabled="true"/);
    const css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/tabs.css"),
        "utf8",
    );
    const story_source = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_tabs.stories.ts"),
        "utf8",
    );
    assert.match(css, /\.cf-tabs__tab--selected \{[\s\S]*?color: var\(--cf-color-accent-hover\)/);
    assert.match(story_source, /select_tab/);
    assert.match(
        story_source,
        /candidate\.classList\.toggle\("cf-tabs__tab--selected", selected\)/,
    );
    assert.match(story_source, /event\.key !== "ArrowLeft"/);
    assert.match(
        story_source,
        /candidate !== undefined[\s\S]*candidate\.getAttribute\("aria-disabled"\) !== "true"/,
    );
    assert.match(story_source, /tab\.focus\(\)/);
    assert.doesNotMatch(html, /tab-switcher/);
    assert.doesNotMatch(html, /ind-tab/);
});
