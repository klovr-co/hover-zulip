"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const hover = zrequire("hover");

run_test("recognizes Hover AI updates", () => {
    assert.equal(hover.is_generated_update({sender_email: "hover-ai@hover.test"}), true);
    assert.equal(hover.is_generated_update({sender_email: "aisha@hover.test"}), false);
});

run_test("adds accessible source logos to generated update evidence", () => {
    const rendered_content =
        '<p>Event readiness update</p><ul><li><strong>WhatsApp · Mentors</strong></li><li><a href="https://github.com/ashvinpraveen/learnaimto">GitHub · LearnAIMTO</a></li><li><a href="https://www.instagram.com/aimto_26/">Instagram · @aimto_26</a></li></ul>';

    const result = hover.add_source_logos(rendered_content);

    assert.match(result, /hover-source-logo--whatsapp/);
    assert.match(result, /fa-whatsapp/);
    assert.match(result, /hover-source-logo--github/);
    assert.match(result, /fa-github/);
    assert.match(result, /hover-source-logo--instagram/);
    assert.match(result, /fa-instagram/);
    assert.equal(result.match(/aria-hidden="true"/g).length, 3);
    assert.match(result, /WhatsApp · Mentors/);
    assert.match(result, /GitHub · LearnAIMTO/);
    assert.match(result, /Instagram · @aimto_26/);
});

run_test("leaves ordinary rendered message content unchanged", () => {
    const rendered_content = "<p>A human project update without linked sources.</p>";

    assert.equal(hover.add_source_logos(rendered_content), rendered_content);
});
