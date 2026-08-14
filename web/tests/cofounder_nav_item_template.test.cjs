"use strict";

const assert = require("node:assert/strict");

const render_nav_item = require("../templates/cofounder/components/nav_item.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("Cofounder navigation item renders semantic states", () => {
    const html = render_nav_item({
        href: "#for-you",
        icon: "inbox",
        label: "For You",
        selected: true,
        reserve_badge: true,
        badge_visible: true,
        badge: 12,
        supports_masked_unread: true,
        masked_unread_label: "Some unread messages are hidden",
        action_label: "For You options",
    });

    assert.match(html, /class="cf-nav-item cf-nav-item--selected"/);
    assert.match(html, /href="#for-you"/);
    assert.match(html, /aria-current="page"/);
    assert.match(html, /cf-nav-item__label">For You/);
    assert.match(html, /cf-nav-item__badge">12/);
    assert.match(html, /aria-label="For You options"/);
    assert.doesNotMatch(html, /zulip-icon/);
});

run_test("Cofounder navigation item reserves empty and disabled states", () => {
    const html = render_nav_item({
        href: "#daily-brief",
        icon: "sun",
        label: "Daily Brief",
        disabled: true,
        reserve_badge: true,
        badge_visible: false,
    });

    assert.match(html, /cf-nav-item--disabled/);
    assert.match(html, /aria-disabled="true" tabindex="-1"/);
    assert.match(html, /cf-nav-item__badge hide/);
});
