"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_help = require("../templates/popovers/navbar/navbar_help_menu_popover.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("Navbar menus use typed Cofounder icons", () => {
    const directory = path.join(__dirname, "../templates/popovers/navbar");
    const source = fs
        .readdirSync(directory)
        .map((file) => fs.readFileSync(path.join(directory, file), "utf8"))
        .join("");
    const html = render_help({
        corporate_enabled: true,
        is_admin: true,
        is_owner: true,
        popover_hotkey_hints: "?",
    });

    assert.match(html, /cf-menu/);
    assert.match(html, /cf-icon/);
    assert.doesNotMatch(source, /zulip-icon|\bfa(?:\s|-)|icon_class/);
    assert.doesNotMatch(html, /zulip-icon|\bfa(?:\s|-)|icon_class/);
});
