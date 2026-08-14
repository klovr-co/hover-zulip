"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, mock_jquery, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const ui_util = mock_esm("../src/ui_util");

let env;

function make_tab(i) {
    const $self = {};

    assert.equal(env.tabs.length, i);

    $self.stub = true;
    $self.class = i === 0 ? "cf-tabs__tab cf-tabs__tab--selected" : "cf-tabs__tab";
    $self.visible = true;
    $self.attributes = {
        "aria-selected": i === 0 ? "true" : "false",
        "data-tab-id": i,
        "data-tab-key": ["keyboard-shortcuts", "message-formatting", "search-operators"][i],
        tabindex: i === 0 ? 0 : -1,
    };

    $self.addClass = (c) => {
        $self.class += " " + c;
        const tokens = $self.class.trim().split(/ +/);
        $self.class = [...new Set(tokens)].join(" ");
        return $self;
    };

    $self.removeClass = (c) => {
        const tokens = $self.class.trim().split(/ +/);
        $self.class = tokens.filter((token) => token !== c).join(" ");
        return $self;
    };

    $self.hasClass = (c) => {
        const tokens = $self.class.trim().split(/ +/);
        return tokens.includes(c);
    };

    $self.css = (prop) => {
        assert.equal(prop, "display");
        if ($self.visible) {
            return "";
        }
        return "none";
    };

    $self.attr = (name, value) => {
        if (typeof name === "object") {
            Object.assign($self.attributes, name);
            return $self;
        }
        if (value !== undefined) {
            $self.attributes[name] = value;
            return $self;
        }
        return $self.attributes[name];
    };

    $self.removeAttr = (name) => {
        $self.attributes[name] = undefined;
        return $self;
    };

    $self.trigger = (type) => {
        if (type === "focus") {
            env.focused_tab = i;
        } else if (type === "click") {
            env.click_f.call(env.tabs[i]);
        }
    };

    env.tabs.push($self);

    return $self;
}

const tabs = (function () {
    return {
        stub: true,

        on(name, f) {
            if (name === "click") {
                env.click_f = f;
            } else if (name === "keydown") {
                env.keydown_f = f;
            }
        },

        off(name) {
            if (name === "click") {
                env.click_f = undefined;
            }
        },

        removeClass(c) {
            for (const $tab of env.tabs) {
                $tab.removeClass(c);
            }
            return this;
        },

        attr(attributes) {
            for (const $tab of env.tabs) {
                $tab.attr(attributes);
            }
            return this;
        },

        eq: (idx) => env.tabs[idx],
    };
})();

function make_switcher() {
    return {
        stub: true,

        children: [],

        classList: new Set(["cf-tabs", "stream_sorter_toggle"]),

        append(child) {
            this.children.push(child);
        },

        addClass(c) {
            this.classList.add(c);
            this.addedClass = c;
        },

        find(sel) {
            switch (sel) {
                case ".cf-tabs__tab":
                    return tabs;
                /* istanbul ignore next */
                default:
                    throw new Error("unknown selector: " + sel);
            }
        },
    };
}

mock_jquery((sel) => {
    if (sel.stub) {
        // The component often redundantly re-wraps objects.
        return sel;
    }

    if (typeof sel === "string" && sel.startsWith('<div class="cf-tabs stream_sorter_toggle"')) {
        for (let i = 0; i < 3; i += 1) {
            make_tab(i);
        }
        env.switcher.children.push(...env.tabs);
        return env.switcher;
    }

    /* istanbul ignore next */
    throw new Error("unknown selector: " + sel);
});

const components = zrequire("components");

const LEFT_KEY = {key: "ArrowLeft", preventDefault: noop, stopPropagation: noop};
const RIGHT_KEY = {key: "ArrowRight", preventDefault: noop, stopPropagation: noop};
const ENTER_KEY = {key: "Enter", preventDefault: noop, stopPropagation: noop};

run_test("basics", () => {
    env = {
        keydown_f: undefined,
        click_f: undefined,
        tabs: [],
        focused_tab: undefined,
        switcher: make_switcher(),
    };

    let callback_args;
    let callback_value;

    let widget = null;
    widget = components.toggle({
        selected: 0,
        values: [
            {label: $t({defaultMessage: "Keyboard shortcuts"}), key: "keyboard-shortcuts"},
            {label: $t({defaultMessage: "Message formatting"}), key: "message-formatting"},
            {label: $t({defaultMessage: "Search filters"}), key: "search-operators"},
        ],
        html_class: "stream_sorter_toggle",
        callback(name, key) {
            assert.equal(callback_args, undefined);
            callback_args = [name, key];

            // The subs code tries to get a widget value in the middle of a
            // callback, which can lead to obscure bugs.
            if (widget) {
                callback_value = widget.value();
            }
        },
    });

    assert.equal(widget.get(), env.switcher);

    assert.deepEqual(env.switcher.children, env.tabs);

    assert.equal(env.switcher.classList.has("cf-tabs"), true);
    assert.equal(env.switcher.classList.has("stream_sorter_toggle"), true);

    assert.equal(env.focused_tab, 0);
    assert.equal(env.tabs[0].class, "cf-tabs__tab cf-tabs__tab--selected");
    assert.equal(env.tabs[0].attr("aria-selected"), "true");
    assert.equal(env.tabs[0].attr("tabindex"), 0);
    assert.equal(env.tabs[1].class, "cf-tabs__tab");
    assert.equal(env.tabs[2].class, "cf-tabs__tab");
    assert.deepEqual(callback_args, ["translated: Keyboard shortcuts", "keyboard-shortcuts"]);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");
    assert.equal(widget.key(), "keyboard-shortcuts");

    callback_args = undefined;

    widget.goto("message-formatting");
    assert.equal(env.focused_tab, 1);
    assert.equal(env.tabs[0].class, "cf-tabs__tab");
    assert.equal(env.tabs[0].attr("aria-selected"), "false");
    assert.equal(env.tabs[0].attr("tabindex"), -1);
    assert.equal(env.tabs[1].class, "cf-tabs__tab cf-tabs__tab--selected");
    assert.equal(env.tabs[2].class, "cf-tabs__tab");
    assert.deepEqual(callback_args, ["translated: Message formatting", "message-formatting"]);
    assert.equal(widget.value(), "translated: Message formatting");
    assert.equal(widget.key(), "message-formatting");

    // Go to same tab twice and make sure we get callback.
    callback_args = undefined;
    widget.goto("message-formatting");
    assert.deepEqual(callback_args, ["translated: Message formatting", "message-formatting"]);

    callback_args = undefined;
    env.keydown_f.call(env.tabs[env.focused_tab], RIGHT_KEY);
    assert.equal(env.focused_tab, 2);
    assert.equal(env.tabs[0].class, "cf-tabs__tab");
    assert.equal(env.tabs[1].class, "cf-tabs__tab");
    assert.equal(env.tabs[2].class, "cf-tabs__tab cf-tabs__tab--selected");
    assert.deepEqual(callback_args, ["translated: Search filters", "search-operators"]);
    assert.equal(widget.value(), "translated: Search filters");
    assert.equal(widget.value(), callback_value);

    // try to crash the key handler
    env.keydown_f.call(env.tabs[env.focused_tab], RIGHT_KEY);
    assert.equal(widget.value(), "translated: Search filters");

    callback_args = undefined;

    env.keydown_f.call(env.tabs[env.focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Message formatting");

    callback_args = undefined;

    env.keydown_f.call(env.tabs[env.focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");

    // try to crash the key handler
    env.keydown_f.call(env.tabs[env.focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");

    callback_args = undefined;
    widget.disable_tab("message-formatting");

    env.keydown_f.call(env.tabs[env.focused_tab], RIGHT_KEY);
    assert.equal(widget.value(), "translated: Search filters");

    callback_args = undefined;

    env.keydown_f.call(env.tabs[env.focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");

    ui_util.convert_enter_to_click = () => {
        env.tabs[2].trigger("click");
    };
    callback_args = undefined;
    env.keydown_f.call(env.tabs[2], ENTER_KEY);
    assert.equal(widget.value(), "translated: Search filters");

    widget.enable_tab("message-formatting");

    callback_args = undefined;
    env.tabs[1].visible = false;
    env.keydown_f.call(env.tabs[env.focused_tab], LEFT_KEY);
    assert.equal(widget.value(), "translated: Keyboard shortcuts");

    env.tabs[1].visible = true;

    callback_args = undefined;

    env.click_f.call(env.tabs[1]);
    assert.equal(widget.value(), "translated: Message formatting");

    callback_args = undefined;
    widget.disable_tab("search-operators");
    assert.equal(env.tabs[2].hasClass("cf-tabs__tab--disabled"), true);
    assert.equal(env.tabs[2].class, "cf-tabs__tab cf-tabs__tab--disabled");
    assert.equal(env.tabs[2].attr("aria-disabled"), "true");
    assert.equal(env.tabs[2].attr("tabindex"), -1);

    widget.goto("keyboard-shortcuts");
    assert.equal(env.focused_tab, 0);
    widget.goto("search-operators");
    assert.equal(env.focused_tab, 0);

    blueslip.expect("warn", "Incorrect tab name given.", 3);
    widget.disable_tab("incorrect-tab");
    widget.enable_tab("incorrect-tab");
    widget.goto("incorrect-tab");
});
