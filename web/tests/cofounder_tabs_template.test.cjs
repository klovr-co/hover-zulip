"use strict";

const assert = require("node:assert/strict");

const {run_test} = require("./lib/test.cjs");

const render_tabs = require("../templates/cofounder/components/tabs.hbs");

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
    assert.doesNotMatch(html, /tab-switcher/);
    assert.doesNotMatch(html, /ind-tab/);
});
