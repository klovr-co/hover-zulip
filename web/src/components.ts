import {$} from "jquery";
import assert from "minimalistic-assert";

import render_tabs from "../templates/cofounder/components/tabs.hbs";

import * as blueslip from "./blueslip.ts";
import * as keydown_util from "./keydown_util.ts";
import * as ui_util from "./ui_util.ts";

/* USAGE:
    Toggle x = components.toggle({
        selected: Integer selected_index,
        values: Array<Object> [
            {label: $t({defaultMessage: "String title"})}
        ],
        callback: function () {
            // .. on value change.
        },
    }).get();
*/

export type Toggle = {
    maybe_go_left: () => boolean;
    maybe_go_right: () => boolean;
    disable_tab: (name: string) => void;
    enable_tab: (name: string) => void;
    value: () => string | undefined;
    key: () => string | undefined;
    get: () => JQuery;
    goto: (name: string) => void;
    register_event_handlers: () => void;
};

export function toggle(opts: {
    html_class?: string;
    values: (({label: string; label_html?: never} | {label_html: string; label?: never}) & {
        key: string;
    })[];
    callback?: (label: string | undefined, value: string) => void;
    child_wants_focus?: boolean;
    selected?: number;
}): Toggle {
    const $component = $(
        render_tabs({
            aria_label: "",
            custom_classes: opts.html_class ?? "",
            tabs: opts.values.map((value, id) => ({
                id,
                key: value.key,
                label: value.label ?? "",
                label_html: value.label_html ?? "",
                selected: id === 0,
            })),
        }),
    );

    const meta = {
        $tabs: $component.find(".cf-tabs__tab"),
        idx: -1,
    };

    // Returns false if the requested tab is disabled.
    function select_tab(idx: number): boolean {
        const $elem = meta.$tabs.eq(idx);
        if ($elem.hasClass("cf-tabs__tab--disabled")) {
            return false;
        }
        if ($elem.css("display") === "none") {
            return false;
        }

        meta.$tabs
            .removeClass("cf-tabs__tab--selected")
            .attr({"aria-selected": "false", tabindex: -1});

        $elem.addClass("cf-tabs__tab--selected").attr({"aria-selected": "true", tabindex: 0});

        meta.idx = idx;
        if (opts.callback) {
            opts.callback(opts.values[idx]!.label, opts.values[idx]!.key);
        }

        if (!opts.child_wants_focus) {
            $elem.trigger("focus");
        }
        return true;
    }

    function maybe_go_left(): boolean {
        // Select the first non-disabled tab to the left, if any.
        let i = 1;
        while (meta.idx >= i) {
            if (select_tab(meta.idx - i)) {
                return true;
            }
            i += 1;
        }
        return false;
    }

    function maybe_go_right(): boolean {
        // Select the first non-disabled tab to the right, if any.
        let i = 1;
        while (meta.idx + i <= opts.values.length - 1) {
            if (select_tab(meta.idx + i)) {
                return true;
            }
            i += 1;
        }
        return false;
    }

    function register_event_handlers(): void {
        meta.$tabs.off("click");
        meta.$tabs.on("click", function () {
            const idx = Number($(this).attr("data-tab-id"));
            select_tab(idx);
        });
    }
    register_event_handlers();

    keydown_util.handle({
        $elem: meta.$tabs,
        handlers: {
            ArrowLeft: maybe_go_left,
            ArrowRight: maybe_go_right,
            Enter(e?: JQuery.KeyDownEvent) {
                assert(e !== undefined);
                ui_util.convert_enter_to_click(e);
                return true;
            },
        },
    });

    // We should arguably default opts.selected to 0.
    if (typeof opts.selected === "number") {
        select_tab(opts.selected);
    }

    const prototype = {
        // Skip disabled tabs and go to the next one.
        maybe_go_left,
        maybe_go_right,

        disable_tab(name: string) {
            const value = opts.values.find((o) => o.key === name);
            if (!value) {
                blueslip.warn("Incorrect tab name given.");
                return;
            }

            const idx = opts.values.indexOf(value);
            meta.$tabs
                .eq(idx)
                .addClass("cf-tabs__tab--disabled")
                .attr({"aria-disabled": "true", tabindex: -1});
        },

        enable_tab(name: string) {
            const value = opts.values.find((o) => o.key === name);
            if (!value) {
                blueslip.warn("Incorrect tab name given.");
                return;
            }

            const idx = opts.values.indexOf(value);
            const $tab = meta.$tabs.eq(idx).removeClass("cf-tabs__tab--disabled");
            $tab.removeAttr("aria-disabled");
            $tab.attr("tabindex", $tab.hasClass("cf-tabs__tab--selected") ? 0 : -1);
        },

        value() {
            if (meta.idx >= 0) {
                return opts.values[meta.idx]!.label;
            }
            /* istanbul ignore next */
            return undefined;
        },

        key() {
            if (meta.idx >= 0) {
                return opts.values[meta.idx]!.key;
            }
            /* istanbul ignore next */
            return undefined;
        },

        get() {
            return $component;
        },
        // go through the process of finding the correct tab for a given name,
        // and when found, select that one and provide the proper callback.
        goto(name: string) {
            const value = opts.values.find((o) => o.label === name || o.key === name);
            if (!value) {
                blueslip.warn("Incorrect tab name given.");
                return;
            }

            const idx = opts.values.indexOf(value);

            if (idx !== -1) {
                select_tab(idx);
            }
        },

        register_event_handlers,
    };

    return prototype;
}
