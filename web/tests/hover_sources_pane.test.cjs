"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const hover_evidence = mock_esm("../src/hover_evidence");
mock_esm("../src/i18n", {
    $t({defaultMessage}, values = {}) {
        return defaultMessage.replace("{count}", () => String(values.count ?? ""));
    },
});

const classes = new Set();
const focused_result = {
    focus_count: 0,
    focus() {
        this.focus_count += 1;
    },
};
const pane = {
    hidden: true,
    innerHTML: "",
    querySelector() {
        return focused_result;
    },
    replaceChildren() {
        this.innerHTML = "";
    },
};
set_global("document", {
    body: {
        classList: {
            add(name) {
                classes.add(name);
            },
            remove(name) {
                classes.delete(name);
            },
        },
    },
    querySelector(selector) {
        return selector === "#hover-sources-pane" ? pane : undefined;
    },
});

const hover_sources_pane = zrequire("hover_sources_pane");

run_test(
    "owns loading, stale-response, loaded, error, and focus state",
    ({override, mock_template}) => {
        const renders = [];
        const requests = [];
        mock_template("hover_sources_pane.hbs", false, (context) => {
            renders.push(context);
            return JSON.stringify(context);
        });
        override(hover_evidence, "fetch_evidence", (url, callbacks) => {
            requests.push({url, callbacks});
        });

        const first_trigger = {
            isConnected: true,
            focus_count: 0,
            focus() {
                this.focus_count += 1;
            },
        };
        const second_trigger = {
            isConnected: true,
            focus_count: 0,
            focus() {
                this.focus_count += 1;
            },
        };

        hover_sources_pane.open("/evidence/first", first_trigger);
        assert.equal(pane.hidden, false);
        assert.equal(classes.has("hover-sources-pane-open"), true);
        assert.deepEqual(renders.at(-1), {loading: true});

        hover_sources_pane.open("/evidence/second", second_trigger);
        const render_count = renders.length;
        requests[0].callbacks.success({groups: [], forbidden_count: 0});
        assert.equal(renders.length, render_count, "a stale response must not replace the pane");

        requests[1].callbacks.success({groups: [], forbidden_count: 0});
        assert.equal(renders.at(-1).empty, true);
        assert.equal(renders.at(-1).has_forbidden, false);

        hover_sources_pane.open("/evidence/error", second_trigger);
        requests[2].callbacks.error({retryable: true});
        assert.equal(renders.at(-1).error, true);
        assert.equal(renders.at(-1).retryable, true);

        hover_sources_pane.close();
        assert.equal(pane.hidden, true);
        assert.equal(classes.has("hover-sources-pane-open"), false);
        assert.equal(second_trigger.focus_count, 1);
    },
);
