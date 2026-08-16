"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_text_field = require("../templates/cofounder/components/text_field.hbs");

const {run_test} = require("./lib/test.cjs");

const field_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/form-field.css"),
    "utf8",
);
const foundations_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/foundations.css"),
    "utf8",
);
const legacy_css = fs.readFileSync(path.join(__dirname, "../styles/zulip.css"), "utf8");

function relative_luminance(hex) {
    const channels = hex
        .match(/\w\w/g)
        .map((channel) => Number.parseInt(channel, 16) / 255)
        .map((channel) =>
            channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
        );
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(first, second) {
    const first_luminance = relative_luminance(first);
    const second_luminance = relative_luminance(second);
    return (
        (Math.max(first_luminance, second_luminance) + 0.05) /
        (Math.min(first_luminance, second_luminance) + 0.05)
    );
}

function token(name) {
    return foundations_css.match(new RegExp(`${name}:\\s*(#[0-9a-f]{6})`, "i"))[1];
}

run_test("Cofounder text fields serialize labels, descriptions, and native states", () => {
    const required = render_text_field({
        hint: "Shown to everyone.",
        id: "workspace-name",
        label: "Workspace name",
        required: true,
    });
    const invalid = render_text_field({
        error: "Enter a valid name.",
        id: "project-name",
        label: "Project name",
    });
    const disabled = render_text_field({
        disabled: true,
        id: "managed-name",
        label: "Managed workspace",
    });

    assert.match(required, /<label class="cf-field__label" for="workspace-name">/);
    assert.match(required, /required aria-required="true"/);
    assert.match(required, /aria-describedby="workspace-name-hint"/);
    assert.match(required, /id="workspace-name-hint"/);
    assert.match(required, /cf-field__required" aria-hidden="true"/);
    assert.match(invalid, /cf-field cf-field--error/);
    assert.match(invalid, /aria-invalid="true" aria-describedby="project-name-error"/);
    assert.match(invalid, /id="project-name-error"/);
    assert.match(disabled, / disabled/);
});

run_test("Cofounder text fields own contrast, state precedence, and containment", () => {
    assert.match(legacy_css, /input:not\(\.input-element, \.cf-field__control\)/);
    assert.match(field_css, /\.cf-field\s*{[^}]*min-width:\s*0/s);
    assert.match(field_css, /\.cf-field__control\s*{[^}]*min-width:\s*0/s);
    assert.match(field_css, /overflow-wrap:\s*anywhere/);
    assert.match(
        field_css,
        /\.cf-field__control::placeholder\s*{[^}]*color:\s*var\(--cf-text-secondary\)[^}]*opacity:\s*1/s,
    );
    assert.match(
        field_css,
        /\.cf-field--error \.cf-field__control:hover:not\(:disabled\),\s*\.cf-field--error \.cf-field__control:focus\s*{[^}]*border-color:\s*var\(--cf-color-danger\)/s,
    );
    assert.ok(contrast(token("--cf-color-ink-soft"), token("--cf-color-paper")) >= 4.5);
});
