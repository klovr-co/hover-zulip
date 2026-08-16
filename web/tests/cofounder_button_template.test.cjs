"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_button = require("../templates/cofounder/components/button.hbs");

const {run_test} = require("./lib/test.cjs");

const button_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/button.css"),
    "utf8",
);
const foundations_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/foundations.css"),
    "utf8",
);

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

run_test("Cofounder button template exposes native state and content contracts", () => {
    const icon_label = render_button({
        icon: "activity",
        label: "View activity",
        variant: "secondary",
    });
    const loading = render_button({
        "aria-busy": "true",
        icon: "clock",
        label: "Saving…",
        variant: "primary",
    });
    const compact = render_button({compact: true, label: "Reset", variant: "ghost"});
    const icon_only = render_button({"aria-label": "Add item", icon: "plus", variant: "secondary"});
    const disabled = render_button({disabled: true, label: "Unavailable", variant: "secondary"});

    assert.match(icon_label, /^<button type="button"/);
    assert.match(icon_label, /cf-icon[^>]*aria-hidden="true"/);
    assert.match(loading, /aria-busy="true"/);
    assert.match(compact, /cf-button--compact/);
    assert.match(icon_only, /cf-button--icon-only[^>]*aria-label="Add item"/);
    assert.match(disabled, / disabled/);
    assert.doesNotMatch(
        `${icon_label}${loading}${compact}${icon_only}${disabled}`,
        /zulip-icon|<i(?:\s|>)/,
    );
});

run_test("Every Cofounder button intent has a complete visual state contract", () => {
    for (const variant of ["primary", "secondary", "ghost", "danger", "success"]) {
        assert.match(button_css, new RegExp(`\\.cf-button--${variant}:hover\\s*{`));
        assert.match(button_css, new RegExp(`\\.cf-button--${variant}:active\\s*{`));
    }
    assert.match(
        button_css,
        /\.cf-button:focus-visible\s*{[^}]*outline:\s*2px solid var\(--cf-focus\)/s,
    );
    assert.match(button_css, /max-inline-size:\s*100%/);
    assert.ok(
        contrast(token("--cf-color-success-strong"), token("--cf-color-success-soft")) >= 4.5,
    );
});
