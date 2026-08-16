"use strict";

const assert = require("node:assert/strict");

const render_dialog = require("../templates/dialog_widget.hbs");

const {run_test} = require("./lib/test.cjs");

run_test("renders the Cofounder dialog contract", () => {
    const html = render_dialog({
        close_on_overlay_click: true,
        modal_content_html: "<p>Dialog content</p>",
        modal_exit_button_text: "Cancel",
        modal_submit_button_text: "Save changes",
        modal_submit_button_variant: "primary",
        modal_title_text: "Workspace settings",
        modal_unique_id: "dialog_widget_modal_1",
    });

    assert.match(html, /class="micromodal cf-theme cf-dialog-root"/);
    assert.match(html, /class="modal__container cf-dialog"/);
    assert.match(html, /role="dialog" aria-modal="true" aria-labelledby="dialog_title"/);
    assert.doesNotMatch(html, /aria-describedby="dialog_subtitle"/);
    assert.match(html, /cf-button--secondary[^>]*dialog_exit_button/);
    assert.match(html, /cf-button--primary[^>]*dialog_submit_button/);
    assert.match(html, /cf-dialog__spinner" aria-hidden="true"/);
    assert.match(html, /<svg class="cf-icon cf-icon--compact"/);
    assert.doesNotMatch(html, /zulip-icon/);
});

run_test("associates the Cofounder dialog subtitle with the dialog", () => {
    const html = render_dialog({
        modal_content_html: "<p>Dialog content</p>",
        modal_exit_button_text: "Cancel",
        modal_submit_button_text: "Save changes",
        modal_subtitle_html: "Changes are visible to everyone.",
        modal_title_text: "Workspace settings",
        modal_unique_id: "dialog_widget_modal_subtitle",
    });

    assert.match(html, /aria-describedby="dialog_subtitle"/);
    assert.match(html, /id="dialog_subtitle" class="modal__subtitle cf-dialog__subtitle"/);
});

run_test("renders a destructive Cofounder dialog action", () => {
    const html = render_dialog({
        close_on_overlay_click: false,
        is_compact: true,
        modal_content_html: "This cannot be undone.",
        modal_exit_button_text: "Cancel",
        modal_submit_button_text: "Delete all drafts",
        modal_submit_button_variant: "danger",
        modal_title_text: "Delete all drafts",
        modal_unique_id: "dialog_widget_modal_2",
    });

    assert.match(html, /ignore-overlay-click/);
    assert.match(html, /cf-button--danger[^>]*dialog_submit_button/);
    assert.doesNotMatch(html, /class="modal__content cf-dialog__body/);
});

run_test("renders an initially loading Cofounder dialog action", () => {
    const html = render_dialog({
        close_on_overlay_click: false,
        modal_buttons_disabled: true,
        modal_content_html: "Saving changes.",
        modal_exit_button_text: "Cancel",
        modal_submit_button_busy: "true",
        modal_submit_button_text: "Save changes",
        modal_submit_button_variant: "primary",
        modal_title_text: "Workspace settings",
        modal_unique_id: "dialog_widget_modal_3",
    });

    assert.match(html, /dialog_exit_button[^>]* disabled/);
    assert.match(html, /dialog_submit_button[^>]* disabled[^>]*aria-busy="true"/);
});
