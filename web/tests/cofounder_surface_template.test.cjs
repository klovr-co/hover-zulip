"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_surface_example = require("../stories/templates/cofounder_surface_example.hbs");

const {run_test} = require("./lib/test.cjs");

const surface_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/surface.css"),
    "utf8",
);
const surface_template = fs.readFileSync(
    path.join(__dirname, "../templates/cofounder/components/surface.hbs"),
    "utf8",
);
const storybook_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");

run_test("Cofounder surface story exposes named base, raised, and overlay variants", () => {
    const html = render_surface_example();

    assert.equal((html.match(/class="cf-surface/g) ?? []).length, 3);
    assert.equal((html.match(/cf-surface--raised/g) ?? []).length, 1);
    assert.equal((html.match(/cf-surface--overlay/g) ?? []).length, 1);
    assert.match(html, /<h2 id="surface-base-title">translated: Review launch campaign<\/h2>/);
    assert.match(html, /aria-labelledby="surface-base-title"/);
    assert.match(html, /aria-labelledby="surface-raised-title"/);
    assert.match(html, /aria-labelledby="surface-overlay-title"/);
    assert.doesNotMatch(html, /style=/);
});

run_test("Cofounder surfaces own intrinsic containment and responsive story actions", () => {
    assert.match(surface_template, /aria-labelledby="{{aria-labelledby}}"/);
    assert.match(surface_css, /\.cf-surface\s*{[^}]*box-sizing:\s*border-box/s);
    assert.match(surface_css, /min-inline-size:\s*0/);
    assert.match(surface_css, /max-inline-size:\s*100%/);
    assert.match(surface_css, /overflow-wrap:\s*anywhere/);
    assert.match(surface_css, /\.cf-surface > \*\s*{[^}]*min-width:\s*0/s);
    assert.match(
        storybook_css,
        /\.storybook-surface-story\s*{[^}]*box-sizing:\s*border-box[^}]*width:\s*min\(100%, 520px\)/s,
    );
    assert.match(
        storybook_css,
        /\.storybook-surface-actions\s*{[^}]*flex-wrap:\s*wrap[^}]*min-width:\s*0/s,
    );
});
