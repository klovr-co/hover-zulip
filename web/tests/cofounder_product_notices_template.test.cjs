"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const render_message_sent_banner = require("../templates/compose_banner/message_sent_banner.hbs");
const render_upload_banner = require("../templates/compose_banner/upload_banner.hbs");
const render_modal_banner = require("../templates/modal_banner/modal_banner.hbs");
const render_mark_as_read_disabled_banner = require("../templates/unread_banner/mark_as_read_disabled_banner.hbs");
const render_mark_as_read_only_in_conversation_view = require("../templates/unread_banner/mark_as_read_only_in_conversation_view.hbs");
const render_mark_as_read_turned_off_banner = require("../templates/unread_banner/mark_as_read_turned_off_banner.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("message sent notice preserves its production and story contracts", () => {
    const html = render_message_sent_banner({
        action_button_text: "View message",
        banner_text: "Your message was sent.",
        classname: "sent_scroll_to_view",
        link_msg_id: 42,
    });
    const compose_notifications = fs.readFileSync(
        path.join(__dirname, "../src/compose_notifications.ts"),
        "utf8",
    );
    const compose_setup = fs.readFileSync(path.join(__dirname, "../src/compose_setup.ts"), "utf8");
    const button_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/button.css"),
        "utf8",
    );
    const notice_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/notice.css"),
        "utf8",
    );
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_product_notices.stories.ts"),
        "utf8",
    );

    assert.match(html, /role="status"/);
    assert.match(html, /cf-notice--success/);
    assert.match(html, /sent_scroll_to_view/);
    assert.match(html, /cf-button--success cf-notice__action/);
    assert.match(html, /data-message-id="42"/);
    assert.doesNotMatch(html, /action-button/);
    assert.match(compose_notifications, /\.sent_scroll_to_view \.cf-notice__action/);
    assert.doesNotMatch(compose_notifications, /\.sent_scroll_to_view \.action-button/);
    assert.match(
        compose_setup,
        /closest\("\.message_edit_form, #compose"\)[\s\S]*\.find\("textarea"\)[\s\S]*trigger\("focus"\)/,
    );
    assert.match(button_css, /\.cf-button--success \{\s*border-color: var\(--cf-color-success\)/);
    assert.match(button_css, /\.cf-button\[hidden\],[\s\S]*\.cf-button\.hide/);
    assert.match(notice_css, /\.cf-notice\[hidden\],[\s\S]*\.cf-notice\.hide/);
    assert.match(story, /Message sent notice dismissed\./);
    assert.match(story, /Message \$\{action\.dataset\["messageId"\]/);
    assert.match(story, /Restore message notice/);
    assert.match(story, /classList\.add\("hide"\)/);
    assert.match(story, /classList\.remove\("hide"\)/);
    assert.match(story, /restore\.focus\(\)/);
});

run_test("upload notice exposes synchronized progress and distinct actions", () => {
    const html = render_upload_banner({
        banner_text: "Uploading product-brief.pdf…",
        banner_type: "info",
        cancel_button_label: "Cancel upload of product-brief.pdf",
        file_id: "product-brief",
        hide_button_label: "Hide upload progress for product-brief.pdf",
        is_upload_process_tracker: true,
        progress_label: "Upload progress for product-brief.pdf",
    });
    const upload_source = fs.readFileSync(path.join(__dirname, "../src/upload.ts"), "utf8");
    const compose_css = fs.readFileSync(path.join(__dirname, "../styles/compose.css"), "utf8");
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_product_notices.stories.ts"),
        "utf8",
    );

    assert.match(html, /role="progressbar"/);
    assert.match(html, /aria-label="Upload progress for product-brief\.pdf"/);
    assert.match(html, /aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"/);
    assert.match(html, /aria-label="Cancel upload of product-brief\.pdf"/);
    assert.match(html, /aria-label="Hide upload progress for product-brief\.pdf"/);
    assert.match(upload_source, /attr\("aria-valuenow", Math\.round\(percent_complete\)\)/);
    assert.match(compose_css, /\.moving_bar \{[\s\S]*height: 4px[\s\S]*var\(--cf-color-accent\)/);
    assert.match(
        compose_css,
        /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.upload_banner \.moving_bar[\s\S]*transition: none/,
    );
    assert.match(story, /style\.setProperty\("width", "42%"\)/);
    assert.match(story, /Upload of \$\{filename\} canceled\./);
    assert.match(story, /Upload progress for \$\{filename\} hidden\./);
});

run_test("modal warning preserves retry, announcement, and focus contracts", () => {
    const html = render_modal_banner({
        banner_text: "Some participants are not subscribed to this channel.",
        banner_type: "warning",
        button_text: "Review participants",
        classname: "unsubscribed-participants-warning",
    });
    const stream_popover = fs.readFileSync(
        path.join(__dirname, "../src/stream_popover.ts"),
        "utf8",
    );
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_product_notices.stories.ts"),
        "utf8",
    );

    assert.match(html, /role="alert"/);
    assert.match(html, /cf-notice--warning unsubscribed-participants-warning/);
    assert.match(html, /cf-notice__action[^>]*>Review participants/);
    assert.match(stream_popover, /event\.currentTarget/);
    assert.match(stream_popover, /attr\("aria-busy"\) === "true"/);
    assert.match(stream_popover, /attr\(\{"aria-busy": "true", "aria-disabled": "true"\}\)/);
    assert.match(stream_popover, /closest\("\.cf-notice"\)\.remove\(\)/);
    assert.match(stream_popover, /Participants subscribed to the channel/);
    assert.match(stream_popover, /\.dialog_submit_button"\)\.trigger\("focus"\)/);
    assert.match(stream_popover, /attr\(\{"aria-busy": "false", "aria-disabled": "false"\}\)/);
    assert.match(
        stream_popover,
        /Failed to subscribe participants[\s\S]*\$status_box[\s\S]*\$action_button\.trigger\("focus"\)/,
    );
    assert.match(story, /function render_modal_warning_notice/);
    assert.match(story, /Reviewing participants…/);
    assert.match(story, /action\.getAttribute\("aria-busy"\) === "true"/);
    assert.match(story, /action\.setAttribute\("aria-disabled", "true"\)/);
    assert.match(story, /Participant review opened\./);
    assert.match(story, /Participant subscription warning dismissed\./);
    assert.match(story, /Restore participant warning/);
    assert.match(story, /action\?\.focus\(\)/);
});

run_test("reading-state notices remain clone-safe and restore focus", () => {
    const variants = [
        render_mark_as_read_disabled_banner(),
        render_mark_as_read_only_in_conversation_view(),
        render_mark_as_read_turned_off_banner(),
    ];
    const unread_ui = fs.readFileSync(path.join(__dirname, "../src/unread_ui.ts"), "utf8");
    const notice_css = fs.readFileSync(
        path.join(__dirname, "../styles/cofounder/components/notice.css"),
        "utf8",
    );
    const typing_css = fs.readFileSync(
        path.join(__dirname, "../styles/typing_notifications.css"),
        "utf8",
    );
    const story = fs.readFileSync(
        path.join(__dirname, "../stories/cofounder_product_notices.stories.ts"),
        "utf8",
    );

    for (const html of variants) {
        assert.match(html, /cf-notice--info mark-as-read-state-banner/);
        assert.match(html, /cf-notice__content mark-as-read-state-content/);
        assert.match(html, /cf-notice__action mark-view-read/);
        assert.doesNotMatch(html, /id="mark_(?:as_read|view_read)/);
    }
    assert.equal(variants.join("").match(/id="[^"]+"/g), null);
    assert.match(unread_ui, /\.on\("click", "\.mark-view-read"/);
    assert.match(
        unread_ui,
        /\.mark-as-read-state-banner \.cf-notice__close[\s\S]*user_closed_unread_banner = true/,
    );
    assert.match(
        unread_ui,
        /message_list\.tabIndex = -1[\s\S]*message_list\.focus\(\{preventScroll: true\}\)/,
    );
    assert.match(typing_css, /\.mark-as-read-state-banner/);
    assert.doesNotMatch(typing_css, /#mark_as_read_turned_off_banner/);
    assert.match(
        notice_css,
        /\.cf-notice a:not\(\.cf-button\) \{[\s\S]*color: var\(--cf-color-accent-hover\)/,
    );
    assert.match(story, /function render_reading_state_notice/);
    assert.match(story, /Reading preferences selected\./);
    assert.match(story, /Messages in this view marked as read\./);
    assert.match(story, /Reading-state notice dismissed\./);
    assert.match(story, /Restore reading-state notice/);
    assert.match(story, /mark_read\?\.focus\(\)/);
});
