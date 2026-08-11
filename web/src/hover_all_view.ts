import {$} from "jquery";

import render_hover_all_view_filters from "../templates/hover_all_view_filters.hbs";
import render_hover_module_view_filters from "../templates/hover_module_view_filters.hbs";

import * as hover_spaces from "./hover_spaces.ts";
import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";

let active_filter_class: string | undefined;
let show_module_history = false;
let observer: MutationObserver | undefined;

type HoverModule = ReturnType<typeof hover_spaces.get_sidebar_modules>[number];
type HoverViewContext =
    | {kind: "all"; space: hover_spaces.HoverSpace}
    | {kind: "module"; space: hover_spaces.HoverSpace; module: HoverModule};

function current_context(): HoverViewContext | undefined {
    const stream_id = narrow_state.stream_id();
    if (stream_id === undefined) {
        return undefined;
    }
    const space = hover_spaces.get_by_stream_id(stream_id);
    if (space === undefined) {
        return undefined;
    }
    const topic = narrow_state.topic();
    if (topic === undefined) {
        return {kind: "all", space};
    }
    const module = hover_spaces
        .get_sidebar_modules(space)
        .find((candidate) => candidate.topic.toLocaleLowerCase() === topic.toLocaleLowerCase());
    return module === undefined ? undefined : {kind: "module", space, module};
}

function apply_filter(): void {
    const $rows = $("#message_feed_container .message_row");
    const context = current_context();
    const filter_class = active_filter_class;
    $rows.removeClass("hover-all-filtered-out");
    if (context?.kind === "module") {
        if (!show_module_history) {
            $rows.filter(".hover-lineage-earlier").addClass("hover-all-filtered-out");
        }
        return;
    }
    if (context?.kind !== "all") {
        return;
    }
    if (filter_class === undefined) {
        $rows
            .filter(".hover-raw-source-record, .hover-lineage-earlier")
            .addClass("hover-all-filtered-out");
        return;
    }
    $rows.each((_index, element) => {
        element.classList.toggle(
            "hover-all-filtered-out",
            !element.classList.contains(filter_class) ||
                (filter_class.startsWith("hover-module--") &&
                    element.classList.contains("hover-lineage-earlier")),
        );
    });
}

function refresh(): void {
    const context = current_context();
    $(".hover-all-view-filters, .hover-module-view-filters").remove();
    document.body.classList.toggle("hover-space-all-view", context?.kind === "all");
    document.body.classList.toggle("hover-space-module-view", context?.kind === "module");
    active_filter_class = undefined;
    show_module_history = false;
    if (context === undefined) {
        return;
    }
    const {space} = context;
    if (context.kind === "module") {
        $("#message_feed_container").prepend(
            $(
                render_hover_module_view_filters({
                    space_name: space.name,
                    module_name: context.module.name,
                }),
            ),
        );
        apply_filter();
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
    $("body").on("click", ".hover-module-history-filter", (event) => {
        const $button = $(event.currentTarget);
        show_module_history = $button.attr("data-hover-history") === "all";
        $(".hover-module-history-filter").removeClass("is-active").attr("aria-pressed", "false");
        $button.addClass("is-active").attr("aria-pressed", "true");
        $(".hover-module-view-filters__status").text(
            show_module_history
                ? $t({
                      defaultMessage:
                          "Showing the complete chronological Module history, including earlier insight states.",
                  })
                : $t({
                      defaultMessage:
                          "Showing the latest state of each insight. Earlier updates remain in Full history.",
                  }),
        );
        apply_filter();
    });
    observer = new MutationObserver(() => {
        if (current_context() !== undefined) {
            apply_filter();
        }
    });
    const feed = document.querySelector("#message_feed_container");
    if (feed !== null) {
        observer.observe(feed, {childList: true, subtree: true});
    }
    setTimeout(refresh, 0);
}
