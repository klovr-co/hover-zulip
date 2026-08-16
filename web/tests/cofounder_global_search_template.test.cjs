"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const template = fs.readFileSync(
    path.join(__dirname, "../templates/hover_search_view.hbs"),
    "utf8",
);
const component_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/global-search.css"),
    "utf8",
);
const app_css = fs.readFileSync(path.join(__dirname, "../styles/cofounder/app.css"), "utf8");

assert.match(template, /cf-global-search__shell/);
assert.match(template, /cofounder\/components\/icon name="lock"/);
assert.match(template, /cf-global-search__save/);
assert.doesNotMatch(template, /class="[^"]*hover-search-|zulip-icon|button-reset-style/);
assert.match(component_css, /\.cf-global-search__result/);
assert.doesNotMatch(component_css, /\.hover-search-|#[0-9a-f]{3,8}\b|--ds-/i);
assert.doesNotMatch(app_css, /\.hover-search-/);
