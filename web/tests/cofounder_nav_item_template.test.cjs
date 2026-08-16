"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

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
        badge_label: "Unread messages",
        supports_masked_unread: true,
        masked_unread_label: "Some unread messages are hidden",
        action_label: "For You options",
    });

    assert.match(html, /class="cf-nav-item cf-nav-item--selected"/);
    assert.match(html, /href="#for-you"/);
    assert.match(html, /aria-current="page"/);
    assert.match(html, /cf-nav-item__label">For You/);
    assert.match(html, /cf-nav-item__badge[^>]*>12/);
    assert.match(html, /aria-label="Unread messages: 12"/);
    assert.match(html, /cf-nav-item__masked[^>]+role="img"/);
    assert.match(html, /aria-label="For You options"/);
    assert.match(html, /<button type="button" class="cf-nav-item__action/);
    assert.match(html, /aria-haspopup="menu"/);
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
    assert.doesNotMatch(html, /href="#daily-brief"/);
    assert.match(html, /cf-nav-item__badge hide/);
});

run_test("Cofounder navigation item owns responsive and Storybook behavior", () => {
    const css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/nav-item.css"),
        "utf8",
    );
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_nav_item.stories.ts"),
        "utf8",
    );
    const story_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");
    const sidebar_template = fs.readFileSync(
        path.join(__dirname, "../templates/left_sidebar.hbs"),
        "utf8",
    );

    assert.match(css, /color: var\(--cf-color-accent-hover\)/);
    assert.match(
        css,
        /\.cf-nav-item--selected \.cf-nav-item__badge[\s\S]*var\(--cf-color-accent\) 10%[\s\S]*var\(--cf-surface-paper\)/,
    );
    assert.match(css, /\.cf-nav-item__badge\s*{[^}]*max-width: 6ch;[^}]*text-overflow: ellipsis/s);
    assert.match(
        css,
        /@media \(width <= 600px\)[\s\S]*\.cf-nav-item__action\s*{[^}]*var\(--cf-control-height-touch\)/,
    );
    assert.match(
        css,
        /#left-sidebar-navigation-list:has\(> \.cf-nav-item\)\s*{[^}]*grid-auto-rows: minmax\(var\(--cf-control-height-touch\), auto\)/s,
    );
    assert.match(sidebar_template, /role="navigation" aria-label="{{t 'Workspace navigation'}}"/);
    assert.match(story, /production_view_metadata/);
    assert.match(story, /key: "hover_editions"/);
    assert.match(story, /fragment: "hover\/editions"/);
    assert.match(story, /fragment: "hover\/search"/);
    assert.match(story, /fragment: "narrow\/is\/starred"/);
    assert.match(story, /href: `#\${view\.fragment}`/);
    assert.doesNotMatch(story, /key: "daily_brief"/);
    assert.match(story, /left_sidebar_menu_icon_visible/);
    assert.match(story, /Some unread messages are hidden/);
    assert.match(story, /storybook-cf-nav-item__masked--visible/);
    assert.match(story, /cf-nav-item__action/);
    assert.doesNotMatch(story, /style=/);
    assert.match(story_css, /\.storybook-cf-nav-states/);
    assert.match(story_css, /\.storybook-cf-production-nav__feedback/);
    assert.match(
        story_css,
        /\.cf-nav-item__masked\.storybook-cf-nav-item__masked--visible\s*{[^}]*display: inline-flex/s,
    );
});
