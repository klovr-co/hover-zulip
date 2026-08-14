import {$} from "jquery";

import render_hover_all_view_filters from "../templates/hover_all_view_filters.hbs";
import render_hover_module_view_filters from "../templates/hover_module_view_filters.hbs";

import * as hover_spaces from "./hover_spaces.ts";
import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";

let active_filter: {kind: "module" | "source"; key: string} | undefined;
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
    const $rows = $("#message_feed_container .cf-message-item");
    const context = current_context();
    const filter = active_filter;
    $rows.removeClass("cf-feed-filtered-out");
    if (context?.kind === "module") {
        if (!show_module_history) {
            $rows.filter("[data-cf-lineage='earlier']").addClass("cf-feed-filtered-out");
        }
        return;
    }
    if (context?.kind !== "all") {
        return;
    }
    if (filter === undefined) {
        $rows
            .filter("[data-cf-source-record], [data-cf-lineage='earlier']")
            .addClass("cf-feed-filtered-out");
        return;
    }
    $rows.each((_index, element) => {
        const matches_filter =
            filter.kind === "module"
                ? element.dataset["cfModuleKey"] === filter.key
                : (element.dataset["cfFilterSourceIds"]?.split(" ").includes(filter.key) ?? false);
        element.classList.toggle(
            "cf-feed-filtered-out",
            !matches_filter ||
                (filter.kind === "module" && element.dataset["cfLineage"] === "earlier"),
        );
    });
}

function refresh(): void {
    const context = current_context();
    $("[data-cf-feed-controls]").remove();
    document.body.classList.toggle("cf-space-feed--all", context?.kind === "all");
    document.body.classList.toggle("cf-space-feed--module", context?.kind === "module");
    active_filter = undefined;
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
    $("body").on("click", "[data-cf-feed-filter]", (event) => {
        const $button = $(event.currentTarget);
        const kind = $button.attr("data-cf-feed-filter");
        const key = $button.attr("data-cf-feed-filter-key");
        active_filter =
            (kind === "module" || kind === "source") && key !== undefined ? {kind, key} : undefined;
        $("[data-cf-feed-filter]")
            .removeClass("cf-feed-filter--selected")
            .attr("aria-pressed", "false");
        $button.addClass("cf-feed-filter--selected").attr("aria-pressed", "true");
        const label = $button.find(".cf-feed-filter__label").text().trim();
        $("[data-cf-feed-controls='all'] .cf-feed-controls__status").text(
            active_filter === undefined
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
    $("body").on("click", "[data-cf-feed-history]", (event) => {
        const $button = $(event.currentTarget);
        show_module_history = $button.attr("data-cf-feed-history") === "all";
        $("[data-cf-feed-history]")
            .removeClass("cf-feed-filter--selected")
            .attr("aria-pressed", "false");
        $button.addClass("cf-feed-filter--selected").attr("aria-pressed", "true");
        $("[data-cf-feed-controls='module'] .cf-feed-controls__status").text(
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
