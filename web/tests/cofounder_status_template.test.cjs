"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_status = require("../templates/cofounder/components/status.hbs");

const {run_test} = require("./lib/test.cjs");

const status_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/status.css"),
    "utf8",
);
const foundations_css = fs.readFileSync(
    path.join(__dirname, "../styles/cofounder/components/foundations.css"),
    "utf8",
);
const storybook_css = fs.readFileSync(path.join(__dirname, "../stories/storybook.css"), "utf8");

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

run_test("Cofounder statuses serialize tones, icons, and contextual names", () => {
    const neutral = render_status({label: "Approval required"});
    const contextual = render_status({
        "aria-label": "Release status: Completed",
        icon: "check",
        label: "Completed",
        tone: "success",
    });

    assert.match(neutral, /^<span class="cf-status">/);
    assert.match(contextual, /cf-status cf-status--success/);
    assert.match(contextual, /aria-label="Release status: Completed"/);
    assert.match(contextual, /cf-icon[^>]*aria-hidden="true"/);
    assert.doesNotMatch(`${neutral}${contextual}`, /role="status"|zulip-icon|<i(?:\s|>)/);
});

run_test("Cofounder statuses own compact geometry, contrast, and hostile-label containment", () => {
    assert.match(status_css, /\.cf-status\s*{[^}]*box-sizing:\s*border-box/s);
    assert.match(status_css, /max-inline-size:\s*100%/);
    assert.match(status_css, /min-height:\s*22px/);
    assert.match(
        status_css,
        /\.cf-status > span:last-child\s*{[^}]*min-width:\s*0[^}]*overflow:\s*hidden[^}]*text-overflow:\s*ellipsis/s,
    );
    assert.match(
        status_css,
        /\.cf-status--success\s*{[^}]*color:\s*var\(--cf-color-success-strong\)/s,
    );
    assert.doesNotMatch(storybook_css, /\.storybook-state-specimen > span\s*{/);
    assert.match(
        storybook_css,
        /\.storybook-state-specimen > \.storybook-state-specimen__caption\s*{/,
    );
    assert.ok(
        contrast(token("--cf-color-success-strong"), token("--cf-color-success-soft")) >= 4.5,
    );
});
