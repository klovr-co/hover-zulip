"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

let stream_id;
let topic;
let current_space;
let observer_callback;
let feed_available = true;

const modules = [
    {
        key: "progress",
        name: "Progress Tracker",
        icon: "zulip-icon-trending-up",
        topic: "Progress Topic",
        count: 3,
    },
];
const sources = [
    {
        source_key: "42",
        name: "Mentors & Volunteers",
        icon_class: "fa fa-whatsapp",
        attachment_id: 10,
    },
    {
        source_key: "43",
        name: "Event calendar",
        icon_class: "fa fa-plug",
        attachment_id: 11,
    },
];

mock_esm("../src/narrow_state", {
    stream_id: () => stream_id,
    topic: () => topic,
});
mock_esm("../src/hover_spaces", {
    get_by_stream_id: () => current_space,
    get_sidebar_modules: () => modules,
    get_sidebar_sources: () => sources,
});

set_global("to_$", () => $("window-stub"));
set_global(
    "MutationObserver",
    class {
        constructor(callback) {
            observer_callback = callback;
        }

        observe(target, options) {
            assert.equal(target, $("#message_feed_container")[0]);
            assert.deepEqual(options, {childList: true, subtree: true});
        }
    },
);
set_global("document", {
    body: $("body")[0],
    querySelector(selector) {
        assert.equal(selector, "#message_feed_container");
        return feed_available ? $("#message_feed_container")[0] : null;
    },
});

const hover_all_view = zrequire("hover_all_view");

function button(attributes, label = "") {
    const wrapper = {
        attr(name, value) {
            if (value === undefined) {
                return attributes[name];
            }
            attributes[name] = value;
            return wrapper;
        },
        addClass() {
            return wrapper;
        },
        clone() {
            const clone = {
                children() {
                    return {
                        remove() {
                            return {
                                end() {
                                    return clone;
                                },
                            };
                        },
                    };
                },
                text() {
                    return label;
                },
            };
            return clone;
        },
    };
    return {to_$: () => wrapper};
}

run_test("renders stable Module and Source filter keys", () => {
    const html = require("../templates/hover_all_view_filters.hbs")({
        space_name: "AIMTO Events",
        modules: [
            {
                key: "conversation_digest",
                name: "Conversation Digest",
                icon: "zulip-icon-align-left",
                count: 3,
            },
        ],
        sources: [
            {
                source_key: "42",
                name: "Mentors & Volunteers",
                icon_class: "fa fa-whatsapp",
                count: 7,
            },
        ],
    });

    assert.match(html, /data-hover-filter-key="conversation_digest"/);
    assert.match(html, /data-hover-filter-key="42"/);
    assert.match(html, />Conversation Digest<span>3<\/span>/);
    assert.match(html, />Mentors &amp; Volunteers<span\s*>7<\/span>/);
});

run_test("renders latest and full-history controls for a Module topic", () => {
    const html = require("../templates/hover_module_view_filters.hbs")({
        space_name: "AIMTO Events",
        module_name: "Progress Tracker",
    });

    assert.match(html, /data-hover-history="latest"/);
    assert.match(html, /data-hover-history="all"/);
    assert.match(html, />Progress Tracker<\/strong>/);
    assert.match(html, /Earlier updates remain in Full history/);
});

run_test("filters native Space history and refreshes on navigation", ({mock_template}) => {
    let all_context;
    let module_context;
    mock_template("hover_all_view_filters.hbs", false, (context) => {
        all_context = context;
        return "<div class='hover-all-view-filters'></div>";
    });
    mock_template("hover_module_view_filters.hbs", false, (context) => {
        module_context = context;
        return "<div class='hover-module-view-filters'></div>";
    });

    current_space = {
        name: "AIMTO Events",
        attachments: [{id: 10, generated_count: 7}, {id: 11}],
    };

    const $teammate = $("<teammate-row>");
    const $raw_source = $("<raw-source-row>").addClass(
        "hover-raw-source-record hover-source-id--42",
    );
    const $latest_module = $("<latest-module-row>").addClass("hover-module--progress");
    const $earlier_module = $("<earlier-module-row>").addClass(
        "hover-module--progress hover-lineage-earlier",
    );
    const rows = [$teammate, $raw_source, $latest_module, $earlier_module];
    for (const $row of rows) {
        $row.set_matches(
            ".hover-raw-source-record, .hover-lineage-earlier",
            $row === $raw_source || $row === $earlier_module,
        );
        $row.set_matches(".hover-lineage-earlier", $row === $earlier_module);
    }
    $.set_results(
        "#message_feed_container .message_row",
        rows.map(($row) => $row[0]),
    );
    $("#message_feed_container")[0].prepend = () => {};
    $(".hover-all-view-filters, .hover-module-view-filters")[0].remove = () => {};

    stream_id = undefined;
    topic = undefined;
    hover_all_view.initialize();
    clock.tick(0);
    assert.equal(document.body.classList.contains("hover-space-all-view"), false);

    stream_id = 4;
    hover_all_view.test.refresh();
    assert.equal(document.body.classList.contains("hover-space-all-view"), true);
    assert.equal(all_context.space_name, "AIMTO Events");
    assert.deepEqual(
        all_context.sources.map((source) => source.count),
        [7, 0],
    );
    assert.equal($raw_source.hasClass("hover-all-filtered-out"), true);
    assert.equal($earlier_module.hasClass("hover-all-filtered-out"), true);
    assert.equal($teammate.hasClass("hover-all-filtered-out"), false);

    const filter_handler = $("body").get_on_handler("click", ".hover-all-filter");
    filter_handler({
        currentTarget: button(
            {"data-hover-filter": "module", "data-hover-filter-key": "progress"},
            "Progress Tracker",
        ),
    });
    assert.equal($latest_module.hasClass("hover-all-filtered-out"), false);
    assert.equal($earlier_module.hasClass("hover-all-filtered-out"), true);
    assert.equal($teammate.hasClass("hover-all-filtered-out"), true);
    assert.match($(".hover-all-view-filters__status").text(), /Progress Tracker/);

    filter_handler({
        currentTarget: button(
            {"data-hover-filter": "source", "data-hover-filter-key": "42"},
            "Mentors & Volunteers",
        ),
    });
    assert.equal($raw_source.hasClass("hover-all-filtered-out"), false);
    assert.equal($latest_module.hasClass("hover-all-filtered-out"), true);

    filter_handler({currentTarget: button({"data-hover-filter": "all"}, "All")});
    assert.equal($raw_source.hasClass("hover-all-filtered-out"), true);

    topic = "progress topic";
    hover_all_view.test.refresh();
    assert.equal(document.body.classList.contains("hover-space-module-view"), true);
    assert.deepEqual(module_context, {
        space_name: "AIMTO Events",
        module_name: "Progress Tracker",
    });
    assert.equal($earlier_module.hasClass("hover-all-filtered-out"), true);

    const history_handler = $("body").get_on_handler("click", ".hover-module-history-filter");
    history_handler({currentTarget: button({"data-hover-history": "all"})});
    assert.equal($earlier_module.hasClass("hover-all-filtered-out"), false);
    assert.match($(".hover-module-view-filters__status").text(), /complete chronological/);
    history_handler({currentTarget: button({"data-hover-history": "latest"})});
    assert.equal($earlier_module.hasClass("hover-all-filtered-out"), true);

    observer_callback();
    topic = "unknown topic";
    observer_callback();
    hover_all_view.test.refresh();
    assert.equal(document.body.classList.contains("hover-space-module-view"), false);
    filter_handler({currentTarget: button({"data-hover-filter": "all"}, "All")});

    current_space = undefined;
    hover_all_view.test.refresh();

    $("window-stub").get_on_handler("hashchange")();
    clock.tick(1);

    feed_available = false;
    $.reset_selector("window-stub");
    $.reset_selector("body");
    hover_all_view.initialize();
    clock.tick(0);
});
