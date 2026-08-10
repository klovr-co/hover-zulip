"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const hover = zrequire("hover");

run_test("recognizes Hover AI updates", () => {
    assert.equal(hover.is_generated_update({sender_email: "hover-ai@hover.test"}), true);
    assert.equal(hover.is_generated_update({sender_email: "aisha@hover.test"}), false);
});

run_test("classifies AIMTO native module topics", () => {
    assert.equal(hover.AIMTO_AI_MODULES.length, 6);
    assert.deepEqual(hover.get_module_from_topic("Suggested Actions"), {
        key: "suggested_actions",
        name: "Suggested Actions",
        icon: "zulip-icon-sparkles",
    });
    assert.equal(hover.get_module_from_topic("Conversation Digest").key, "conversation_digest");
    assert.equal(hover.get_module_from_topic("Summary"), undefined);
});

run_test("extracts source integrations for a generated update footer", () => {
    const rendered_content =
        '<p>Event readiness update</p><ul><li><strong>WhatsApp · Mentors</strong></li><li><strong>WhatsApp · Volunteers</strong></li><li><strong>WhatsApp · Resident Lounge</strong></li><li><a href="https://github.com/ashvinpraveen/learnaimto">GitHub · LearnAIMTO</a></li><li><a href="https://www.instagram.com/aimto_26/">Instagram · @aimto_26</a></li></ul>';

    assert.deepEqual(hover.get_source_integrations(rendered_content), [
        {key: "whatsapp", name: "WhatsApp", icon_class: "fa fa-whatsapp", count: 3},
        {
            key: "github",
            name: "GitHub",
            icon_class: "fa fa-github",
            count: 1,
            url: "https://github.com/ashvinpraveen/learnaimto",
        },
        {
            key: "instagram",
            name: "Instagram",
            icon_class: "fa fa-instagram",
            count: 1,
            url: "https://www.instagram.com/aimto_26/",
        },
    ]);
});

run_test("returns no integrations for an ordinary message", () => {
    const rendered_content = "<p>A human project update without linked sources.</p>";

    assert.deepEqual(hover.get_source_integrations(rendered_content), []);
});

run_test("lists the five sources attached to AIMTO", () => {
    const sources = hover.get_aimto_attached_sources("#narrow/aimto/summary", {
        mentors_volunteers: "#narrow/search/mentors",
    });

    assert.equal(sources.length, 5);
    assert.deepEqual(
        sources.map((source) => source.key),
        ["whatsapp", "whatsapp", "whatsapp", "github", "instagram"],
    );
    assert.equal(sources[0].url, "#narrow/search/mentors");
    assert.equal(sources[1].url, "#narrow/aimto/summary");
    assert.deepEqual(
        sources.slice(0, 3).map((source) => source.source_key),
        ["mentors_volunteers", "resident_lounge", "volunteers_500"],
    );
    assert.equal(sources[3].url, "https://github.com/ashvinpraveen/learnaimto");
    assert.equal(sources[4].name, "@aimto_26");
});

run_test("provides stable source search operands", () => {
    assert.equal(hover.get_source_search_operand("resident_lounge"), "Resident Lounge");
});

run_test("describes the source context without creating extra bot identities", () => {
    assert.equal(
        hover.get_source_context("<ul><li><strong>WhatsApp · Resident Lounge</strong></li></ul>"),
        "From Resident Lounge",
    );
    assert.equal(
        hover.get_source_context(
            '<ul><li><strong>WhatsApp · Mentors</strong></li><li><a href="https://github.com/example/repo">GitHub · repo</a></li></ul>',
        ),
        "Across 2 sources",
    );
});
