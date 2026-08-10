import {$} from "jquery";

import render_hover_all_view_filters from "../templates/hover_all_view_filters.hbs";

import * as hover_spaces from "./hover_spaces.ts";
import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";

let active_filter_class: string | undefined;
let observer: MutationObserver | undefined;

function current_space(): hover_spaces.HoverSpace | undefined {
    const stream_id = narrow_state.stream_id();
    if (stream_id === undefined || narrow_state.topic() !== undefined) {
        return undefined;
    }
    return hover_spaces.get_by_stream_id(stream_id);
}

function apply_filter(): void {
    const $rows = $("#message_feed_container .message_row");
    const filter_class = active_filter_class;
    $rows.removeClass("hover-all-filtered-out");
    if (filter_class === undefined) {
        $rows
            .filter(".hover-raw-source-record, .hover-lineage-earlier")
            .addClass("hover-all-filtered-out");
        return;
    }
    $rows.each((_index, element) => {
        element.classList.toggle(
            "hover-all-filtered-out",
            !element.classList.contains(filter_class),
        );
    });
}

function refresh(): void {
    const space = current_space();
    $(".hover-all-view-filters").remove();
    document.body.classList.toggle("hover-space-all-view", space !== undefined);
    active_filter_class = undefined;
    if (space === undefined) {
        return;
    }
    const modules = hover_spaces.get_sidebar_modules(space);
    const sources = hover_spaces.get_sidebar_sources(space).map((source) => ({
        ...source,
        count:
            space.attachments.find((attachment) => attachment.id === source.attachment_id)
                ?.generated_count ?? 0,
    }));
    $("#message_feed_container").prepend(
        $(render_hover_all_view_filters({space_name: space.name, modules, sources})),
    );
    apply_filter();
}

export function initialize(): void {
    $(window).on("hashchange", () => setTimeout(refresh, 0));
    $("body").on("click", ".hover-all-filter", (event) => {
        const $button = $(event.currentTarget);
        const kind = $button.attr("data-hover-filter");
        const key = $button.attr("data-hover-filter-key");
        active_filter_class =
            kind === "module" && key !== undefined
                ? `hover-module--${key}`
                : kind === "source" && key !== undefined
                  ? `hover-source-id--${key}`
                  : undefined;
        $(".hover-all-filter").removeClass("is-active").attr("aria-pressed", "false");
        $button.addClass("is-active").attr("aria-pressed", "true");
        const label = $button.clone().children().remove().end().text().trim();
        $(".hover-all-view-filters__status").text(
            active_filter_class === undefined
                ? $t({
                      defaultMessage:
                          "Showing teammate posts and the latest meaningful state of every enabled Module.",
                  })
                : $t(
                      {
                          defaultMessage:
                              "Showing {label} updates from the same native Space history.",
                      },
                      {label},
                  ),
        );
        apply_filter();
    });
    observer = new MutationObserver(() => {
        if (current_space() !== undefined) {
            apply_filter();
        }
    });
    const feed = document.querySelector("#message_feed_container");
    if (feed !== null) {
        observer.observe(feed, {childList: true, subtree: true});
    }
    setTimeout(refresh, 0);
}
