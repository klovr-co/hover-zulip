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
        presence_label: "Active now",
        status_text: "Reviewing the launch brief",
        unread_id: "people-sidebar-unread-7",
        user_actions_label: "User actions for Ava Rodriguez",
        user_circle_class: "user-circle-active",
        user_id: 7,
        user_list_style: {WITH_AVATAR: false, WITH_STATUS: true},
    });
    const section_html = render_section_header({
        controls_id: "members-list",
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
    assert.match(row_html, /role="img" aria-label="Active now"/);
    assert.match(row_html, /aria-label="User actions for Ava Rodriguez"/);
    assert.match(row_html, /aria-describedby="people-sidebar-unread-7"/);
    assert.match(
        row_html,
        /id="people-sidebar-unread-7"[^>]+aria-label="translated: Unread messages: 3"/,
    );
    const component_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/people-sidebar.css"),
        "utf8",
    );
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_people_sidebar.stories.ts"),
        "utf8",
    );
    const data_table_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/data-table.css"),
        "utf8",
    );
    const user_card_popover = fs.readFileSync(
        path.join(__dirname, "../src/user_card_popover.ts"),
        "utf8",
    );
    assert.match(component_css, /\.cf-member-row__unread:not\(\.hide\)[\s\S]*max-width: 37px/);
    assert.match(
        component_css,
        /\.cf-member-row--avatar \{\s*grid-template-columns: minmax\(0, 1fr\)/,
    );
    assert.match(story, /visible_count === 1 \? "person" : "people"/);
    assert.match(story, /conversation selected\./);
    assert.match(story, /actions opened\./);
    assert.doesNotMatch(data_table_css, /(?:^|\n)\.cf-presence-dot(?:\s|,|\{)/);
    assert.doesNotMatch(user_card_popover, /on\("keydown", "\.cf-member-row__actions"/);
    assert.match(section_html, /aria-expanded="true"/);
    assert.match(section_html, /aria-controls="members-list"/);
    assert.match(section_html, /cf-people-sidebar__section-toggle/);
    assert.doesNotMatch(
        source + sidebar_html + row_html + section_html,
        /zulip-icon|\bfa(?:\s|-)|(?:^|[\s"])icon-button(?:[\s"]|$)|user_sidebar_entry|user-presence-link|buddy-list-(?:heading|section-toggle|section-container|subsection-header)|selectable_sidebar_block|my_user_status|right-sidebar-wrappable-text|view-all-(?:subscribers|users)-link|invite-user-(?:shortcut|link)|with_avatars|narrow-filter|unread_count|user-profile-picture|avatar-preload-background|sidebar-menu-icon/,
    );
});
