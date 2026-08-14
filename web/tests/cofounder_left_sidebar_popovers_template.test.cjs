"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_views = require("../templates/popovers/left_sidebar/left_sidebar_views_popover.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("Left sidebar popovers use typed Cofounder icons", () => {
    const directory = path.join(__dirname, "../templates/popovers/left_sidebar");
    const source = [
        ...fs.readdirSync(directory).map((file) => path.join(directory, file)),
        path.join(__dirname, "../templates/popovers/left_sidebar_menu_popover.hbs"),
    ]
        .map((file) => fs.readFileSync(file, "utf8"))
        .join("");
    const html = render_views({
        is_home_view_active: true,
        show_unread_count: true,
        unread_messages_present: true,
        views: [
            {
                cf_icon: "inbox",
                css_class_suffix: "inbox",
                fragment: "inbox",
                has_unread_count: true,
                name: "Inbox",
                supports_masked_unread: true,
                tooltip_template_id: "inbox-tooltip-template",
                unread_count: 8,
                unread_count_type: "normal-count",
            },
        ],
    });

    assert.match(html, /cf-menu/);
    assert.match(html, /cf-icon/);
    assert.match(html, /masked-unread-icon/);
    assert.doesNotMatch(source, /zulip-icon|\bfa(?:\s|-)|icon_class/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|icon_class/);
});
