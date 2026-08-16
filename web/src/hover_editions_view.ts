import {$} from "jquery";
import * as z from "zod/mini";

import render_hover_editions_view from "../templates/hover_editions_view.hbs";

import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as recent_view_ui from "./recent_view_ui.ts";

const edition_item_schema = z.object({
    title: z.string(),
    detail: z.string(),
    update: z.object({
        message_id: z.number(),
        space_name: z.string(),
        topic: z.string(),
        url: z.string(),
        evidence_url: z.nullable(z.string()),
    }),
});
const edition_base = {
    title: z.string(),
    covered_end: z.string(),
    published_at: z.string(),
    all_clear: z.boolean(),
};
const morning_edition_schema = z.object({
    ...edition_base,
    edition: z.literal("morning"),
    sections: z.object({
        urgency: z.array(edition_item_schema),
        unresolved_carryover: z.array(edition_item_schema),
        guidance: z.array(edition_item_schema),
    }),
});
const end_of_day_edition_schema = z.object({
    ...edition_base,
    edition: z.literal("end_of_day"),
    sections: z.object({
        meaningful_movement: z.array(edition_item_schema),
        completed_work: z.array(edition_item_schema),
        carryover: z.array(edition_item_schema),
        delegated_dependencies: z.array(edition_item_schema),
        tomorrow_preview: z.array(edition_item_schema),
    }),
});
const response_schema = z.object({
    sync_status: z.enum(["current", "degraded", "empty"]),
    editions: z.object({
        morning: z.nullable(morning_edition_schema),
        end_of_day: z.nullable(end_of_day_edition_schema),
    }),
});
type EditionItem = z.infer<typeof edition_item_schema>;
type EditionsResponse = z.infer<typeof response_schema>;
type EditionKind = "morning" | "end_of_day";
type ViewMode = "all" | "focus";

const tab_ids: Record<EditionKind, string> = {
    morning: "cf-edition-tab-morning",
    end_of_day: "cf-edition-tab-end-of-day",
};
const panel_ids: Record<EditionKind, string> = {
    morning: "cf-edition-panel-morning",
    end_of_day: "cf-edition-panel-end-of-day",
};

const empty_response: EditionsResponse = {
    sync_status: "empty",
    editions: {morning: null, end_of_day: null},
};
let response = empty_response;
let selected_edition: EditionKind = "morning";
let view_mode: ViewMode = "all";
let slide_index = 0;
let visible = false;
let loaded = false;
let loading = false;
let status = "";
let show_retry = false;
let status_is_error = false;
let request: JQuery.jqXHR<unknown> | undefined;
let request_generation = 0;

const morning_sections = [
    ["urgency", $t({defaultMessage: "A good place to start"})],
    ["unresolved_carryover", $t({defaultMessage: "Carryover"})],
    ["guidance", $t({defaultMessage: "Suggested next step"})],
] as const;
const end_of_day_sections = [
    ["meaningful_movement", $t({defaultMessage: "Meaningful movement"})],
    ["completed_work", $t({defaultMessage: "Completed"})],
    ["carryover", $t({defaultMessage: "Carryover"})],
    ["delegated_dependencies", $t({defaultMessage: "Waiting safely"})],
    ["tomorrow_preview", $t({defaultMessage: "Tomorrow"})],
] as const;

function display_date(timestamp: string): string {
    return new Intl.DateTimeFormat(undefined, {dateStyle: "long"}).format(new Date(timestamp));
}

function section_data(): {key: string; label: string; items: EditionItem[]}[] {
    const edition = response.editions[selected_edition];
    if (edition === null) {
        return [];
    }
    if (edition.edition === "morning") {
        return morning_sections.map(([key, label]) => ({
            key,
            label,
            items: edition.sections[key],
        }));
    }
    return end_of_day_sections.map(([key, label]) => ({
        key,
        label,
        items: edition.sections[key],
    }));
}

function render({
    focus_carousel = false,
    focus_panel = false,
    focus_status = false,
    focus_tab,
}: {
    focus_carousel?: boolean;
    focus_panel?: boolean;
    focus_status?: boolean;
    focus_tab?: EditionKind;
} = {}): void {
    if (!visible) {
        return;
    }
    const edition = response.editions[selected_edition];
    const sections = section_data().map((section) => ({
        ...section,
        has_items: section.items.length > 0,
    }));
    const slides = sections.flatMap((section) =>
        section.items.map((item) => ({...item, section_label: section.label})),
    );
    slide_index = Math.min(slide_index, Math.max(slides.length - 1, 0));
    const current_slide = slides[slide_index];
    $("#cf-editions-view").html(
        render_hover_editions_view({
            status,
            show_retry,
            loading,
            selected_morning: selected_edition === "morning",
            selected_end_of_day: selected_edition === "end_of_day",
            morning_aria_selected: selected_edition === "morning" ? "true" : "false",
            end_of_day_aria_selected: selected_edition === "end_of_day" ? "true" : "false",
            morning_tabindex: selected_edition === "morning" ? "0" : "-1",
            end_of_day_tabindex: selected_edition === "end_of_day" ? "0" : "-1",
            active_tab_id: tab_ids[selected_edition],
            active_panel_id: panel_ids[selected_edition],
            panel_aria_busy: loading ? "true" : "false",
            status_aria_live: status_is_error ? "assertive" : "polite",
            status_class: status_is_error
                ? "cf-edition-status cf-edition-status--error"
                : "cf-edition-status",
            status_role: status_is_error ? "alert" : "status",
            inactive_tab_id: tab_ids[selected_edition === "morning" ? "end_of_day" : "morning"],
            inactive_panel_id: panel_ids[selected_edition === "morning" ? "end_of_day" : "morning"],
            focus_mode: view_mode === "focus",
            all_mode: view_mode === "all",
            edition,
            edition_marker:
                selected_edition === "morning"
                    ? $t({defaultMessage: "Morning"})
                    : $t({defaultMessage: "End of day"}),
            display_date: edition === null ? "" : display_date(edition.covered_end),
            sections,
            has_items: slides.length > 0,
            current_slide,
            slide_number: slides.length === 0 ? 0 : slide_index + 1,
            slide_count: slides.length,
            can_go_previous: slide_index > 0,
            can_go_next: slide_index + 1 < slides.length,
        }),
    );
    if (focus_carousel && view_mode === "focus" && current_slide !== undefined) {
        $(".cf-edition-carousel").trigger("focus");
    } else if (focus_tab !== undefined) {
        $(`#${tab_ids[focus_tab]}`).trigger("focus");
    } else if (focus_status) {
        $(".cf-edition-status").trigger("focus");
    } else if (focus_panel) {
        $(`#${panel_ids[selected_edition]}`).trigger("focus");
    }
}

function select_edition(edition: EditionKind, {focus_tab = false} = {}): void {
    selected_edition = edition;
    slide_index = 0;
    render({...(focus_tab && {focus_tab: edition})});
}

function load({focus_status = false}: {focus_status?: boolean} = {}): void {
    request?.abort();
    request_generation += 1;
    const generation = request_generation;
    loading = true;
    status = $t({defaultMessage: "Preparing your latest edition…"});
    show_retry = false;
    status_is_error = false;
    render({focus_status});
    request = channel.get({
        url: "/json/hover/personal-editions",
        success(raw_data) {
            if (generation !== request_generation) {
                return;
            }
            response = response_schema.parse(raw_data);
            loaded = true;
            loading = false;
            status_is_error = false;
            show_retry = response.sync_status === "degraded";
            status =
                response.sync_status === "degraded"
                    ? $t({defaultMessage: "Showing the latest available edition. You can retry."})
                    : response.editions.morning === null && response.editions.end_of_day === null
                      ? $t({
                            defaultMessage:
                                "Your first edition will appear after confirmed Space updates arrive.",
                        })
                      : "";
            if (response.editions[selected_edition] === null) {
                const other: EditionKind =
                    selected_edition === "morning" ? "end_of_day" : "morning";
                if (response.editions[other] !== null) {
                    selected_edition = other;
                }
            }
            render({focus_panel: focus_status});
        },
        error(_xhr, error_type) {
            if (generation !== request_generation || error_type === "abort") {
                return;
            }
            loading = false;
            show_retry = true;
            status_is_error = true;
            status = $t({defaultMessage: "Your edition could not be loaded. Try again."});
            render({focus_status});
        },
    });
}

function move_slide(change: number): void {
    if (view_mode !== "focus") {
        return;
    }
    slide_index = Math.max(
        0,
        Math.min(
            slide_index + change,
            section_data().flatMap((section) => section.items).length - 1,
        ),
    );
    render({focus_carousel: true});
}

export function show(): void {
    visible = true;
    inbox_ui.hide();
    recent_view_ui.hide();
    $(
        "#cf-source-view, #cf-awareness-view, #cf-global-search-view, #message_feed_container, #compose",
    ).hide();
    $("#cf-editions-view").show();
    left_sidebar_navigation_area.select_top_left_corner_item(".top_left_daily_brief");
    if (!loaded) {
        load();
    } else {
        render();
    }
}

export function hide(): void {
    if (!visible) {
        return;
    }
    visible = false;
    request?.abort();
    request_generation += 1;
    $("#cf-editions-view").hide();
    $("#message_feed_container, #compose").show();
}

export function handle_access_change(): void {
    loaded = false;
    if (visible) {
        load();
    }
}

export function initialize(): void {
    $("body").on("click", ".cf-edition-tab", (event) => {
        const edition = $(event.currentTarget).attr("data-edition");
        if (edition !== "morning" && edition !== "end_of_day") {
            return;
        }
        select_edition(edition, {focus_tab: true});
    });
    $("body").on("keydown", ".cf-edition-tab", (event) => {
        const edition = $(event.currentTarget).attr("data-edition");
        if (edition !== "morning" && edition !== "end_of_day") {
            return;
        }
        let next_edition: EditionKind;
        switch (event.key) {
            case "ArrowLeft":
            case "ArrowRight": {
                next_edition = edition === "morning" ? "end_of_day" : "morning";
                break;
            }
            case "Home": {
                next_edition = "morning";
                break;
            }
            case "End": {
                next_edition = "end_of_day";
                break;
            }
            default: {
                return;
            }
        }
        event.preventDefault();
        select_edition(next_edition, {focus_tab: true});
    });
    $("body").on("click", "#cf-edition-focus-view", () => {
        view_mode = "focus";
        slide_index = 0;
        render({focus_carousel: true});
    });
    $("body").on("click", "#cf-edition-view-all", () => {
        view_mode = "all";
        render();
        $("#cf-edition-focus-view").trigger("focus");
    });
    $("body").on("click", "#cf-edition-previous", () => {
        move_slide(-1);
    });
    $("body").on("click", "#cf-edition-next", () => {
        move_slide(1);
    });
    $("body").on("keydown", ".cf-edition-carousel", (event) => {
        if (event.key === "ArrowLeft") {
            event.preventDefault();
            move_slide(-1);
        } else if (event.key === "ArrowRight") {
            event.preventDefault();
            move_slide(1);
        }
    });
    $("body").on("click", "#cf-edition-retry", () => {
        load({focus_status: true});
    });
}

export const test = {
    load,
    move_slide,
    reset(): void {
        response = empty_response;
        selected_edition = "morning";
        view_mode = "all";
        slide_index = 0;
        visible = false;
        loaded = false;
        loading = false;
        status = "";
        show_retry = false;
        status_is_error = false;
        request = undefined;
        request_generation = 0;
    },
};
