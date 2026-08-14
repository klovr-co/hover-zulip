"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_section_header = require("../templates/buddy_list/section_header.hbs");
const render_presence_row = require("../templates/presence_row.hbs");
const render_right_sidebar = require("../templates/right_sidebar.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("People sidebar uses standalone Cofounder component contracts", () => {
    const source = [
        "../templates/right_sidebar.hbs",
        "../templates/presence_row.hbs",
        "../templates/buddy_list/section_header.hbs",
        "../templates/buddy_list/view_all_subscribers.hbs",
        "../templates/buddy_list/view_all_users.hbs",
        "../templates/cofounder/components/member_name.hbs",
    ]
        .map((file) => fs.readFileSync(path.join(__dirname, file), "utf8"))
        .join("");
    const sidebar_html = render_right_sidebar();
    const row_html = render_presence_row({
        has_status_text: true,
        href: "#dm/7",
        name: "Ava Rodriguez",
        num_unread: 3,
        status_text: "Reviewing the launch brief",
        user_circle_class: "user-circle-active",
        user_id: 7,
        user_list_style: {WITH_AVATAR: false, WITH_STATUS: true},
    });
    const section_html = render_section_header({
        header_text: "Members",
        id: "members-heading",
        is_collapsed: false,
    });

    assert.match(sidebar_html, /cf-people-sidebar/);
    assert.match(sidebar_html, /cf-search-field/);
    assert.match(sidebar_html, /id="userlist-header-search" class="cf-search-field/);
    assert.match(
        sidebar_html,
        /class="cf-field__control cf-search-field__control user-list-filter"/,
    );
    assert.match(sidebar_html, /cf-people-sidebar__menu/);
    assert.match(row_html, /cf-member-row--status/);
    assert.match(row_html, /cf-presence-dot--user-circle-active/);
    assert.match(row_html, /cf-member-row__unread/);
    assert.match(section_html, /aria-expanded="true"/);
    assert.match(section_html, /cf-people-sidebar__section-toggle/);
    assert.doesNotMatch(
        source + sidebar_html + row_html + section_html,
        /zulip-icon|\bfa(?:\s|-)|(?:^|[\s"])icon-button(?:[\s"]|$)|user_sidebar_entry|user-presence-link|buddy-list-(?:heading|section-toggle|section-container|subsection-header)|selectable_sidebar_block|my_user_status|right-sidebar-wrappable-text|view-all-(?:subscribers|users)-link|invite-user-(?:shortcut|link)|with_avatars|narrow-filter|unread_count|user-profile-picture|avatar-preload-background|sidebar-menu-icon/,
    );
});
