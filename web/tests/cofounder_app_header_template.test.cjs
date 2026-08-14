"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_navbar = require("../templates/navbar.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("application header uses standalone Cofounder contracts", () => {
    const html = render_navbar({embedded: false, user_avatar: "/avatar/7"});
    const behavior_source = [
        "../src/gear_menu.ts",
        "../src/left_sidebar_tooltips.ts",
        "../src/navbar_help_menu.ts",
        "../src/navbar_menus.ts",
        "../src/personal_menu_popover.ts",
        "../src/search.ts",
        "../src/sidebar_ui.ts",
        "../src/ui_init.js",
        "../src/user_events.ts",
    ]
        .map((file) => fs.readFileSync(path.join(__dirname, file), "utf8"))
        .join("");
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/app-header.css"),
        "utf8",
    );
    const search_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/app-header-search.css"),
        "utf8",
    );

    assert.match(html, /<nav[^>]+cf-app-header__nav/);
    assert.match(html, /cf-app-header__brand-mark[^>]*>H</);
    assert.match(html, /cf-app-header__brand-name[^>]*>HOVER</);
    assert.match(html, /id="searchbox_form" class="cf-app-header__search"/);
    assert.match(html, /cf-app-header__search-container/);
    assert.match(html, /cf-app-header__search-input/);
    assert.match(html, /id="search_exit"[^>]+cf-app-header__search-close/);
    assert.match(html, /id="help-menu"[^>]+cf-app-header__item/);
    assert.match(html, /id="gear-menu"[^>]+cf-app-header__item/);
    assert.match(html, /id="personal-menu"[^>]+cf-app-header__item/);
    assert.match(html, /cf-app-header__avatar-image/);
    assert.equal((html.match(/id="login_button"/g) ?? []).length, 1);
    assert.match(behavior_source, /cf-app-header__search--expanded/);
    assert.match(behavior_source, /cf-app-header__item--active/);
    assert.match(component_css, /var\(--cf-surface-paper\)/);
    assert.match(search_css, /\.cf-app-header__search--expanded/);
    assert.match(search_css, /\.cf-app-header__search-container/);
    assert.doesNotMatch(component_css, /var\(--ds-/);
    assert.equal(fs.existsSync(path.join(__dirname, "../styles/search.css")), false);
    assert.doesNotMatch(
        html + behavior_source + component_css + search_css,
        /zulip-icon|\bfa(?:\s|-)|header-button|navbar-item|navbar-search|search_icon|search_close_button|search-input-and-pills|active-navbar-menu|left-sidebar-toggle-button|header-button-avatar/,
    );
});
