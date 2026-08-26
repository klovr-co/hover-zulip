import {$} from "jquery";

import render_hover_pipeline_draft_editor from "../templates/hover_pipeline_draft_editor.hbs";
import render_hover_pipeline_library from "../templates/hover_pipeline_library.hbs";
import render_hover_pipeline_library_content from "../templates/hover_pipeline_library_content.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as hover_pipeline_library from "./hover_pipeline_library.ts";
import type {
    HoverPipelineDraft,
    HoverPipelineDraftContract,
    HoverPipelineLibrary,
} from "./hover_pipeline_library.ts";
import {$t, $t_html} from "./i18n.ts";
import * as people from "./people.ts";
import {current_user} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";

type LibraryRequest = typeof channel.get;

let modal_is_open = false;

function trigger_label(trigger: string): string {
    const labels = new Map([
        ["manual", $t({defaultMessage: "Manual"})],
        ["new_source", $t({defaultMessage: "New source"})],
        ["schedule", $t({defaultMessage: "Schedule"})],
    ]);
    return labels.get(trigger) ?? trigger;
}

function user_name(user_id: number): string {
    return (
        people.maybe_get_user_by_id(user_id, true)?.full_name ??
        $t({defaultMessage: "Former teammate"})
    );
}

function status_box(): JQuery {
    return $("#hover_pipeline_library_status");
}

function show_parse_error(): void {
    ui_report.client_error(
        $t_html({
            defaultMessage:
                "The Pipeline Library returned an unexpected response. Refresh the library and try again.",
        }),
        status_box(),
    );
}

function set_busy($button: JQuery, busy: boolean): void {
    $button.prop("disabled", busy).toggleClass("is-busy", busy);
}

function people_context(user_ids: number[]): {user_id: number; full_name: string}[] {
    return user_ids.map((user_id) => ({user_id, full_name: user_name(user_id)}));
}

function render_library(library: HoverPipelineLibrary): void {
    const creator_ids = new Set(library.creator_user_ids);
    const eligible_creators = people
        .get_realm_active_human_users()
        .filter((person) => !person.is_guest && !creator_ids.has(person.user_id))
        .toSorted((a, b) => a.full_name.localeCompare(b.full_name));
    const definitions = hover_pipeline_library.visible_definitions().map((definition) => ({
        ...definition,
        definition_class: `hover-pipeline-library__definition${
            definition.archived ? " is-archived" : ""
        }`,
        latest_icon: definition.versions.at(-1)?.navigation_icon ?? "zulip-icon-bot",
        can_archive_definition: library.permissions.can_archive && !definition.archived,
        versions: definition.versions.map((version) => ({
            ...version,
            version_class: `hover-pipeline-library__version${
                version.archived ? " is-archived" : ""
            }`,
            state_class: `hover-pipeline-library__state ${
                version.archived ? "is-archived" : "is-immutable"
            }`,
            can_create_successor:
                library.permissions.can_create && !definition.archived && !version.archived,
            can_archive_version: library.permissions.can_archive && !version.archived,
            trigger_summary: version.supported_triggers
                .map((trigger) => trigger_label(trigger))
                .join(", "),
            requirement_summary:
                version.requirements.length === 0
                    ? $t({defaultMessage: "None"})
                    : version.requirements
                          .map(
                              (requirement) =>
                                  `${requirement.key} (${requirement.minimum_count}–${requirement.maximum_count})`,
                          )
                          .join(", "),
            published_label: new Date(version.published_at).toLocaleDateString(),
        })),
    }));
    const drafts = hover_pipeline_library.sorted_drafts().map((draft) => ({
        ...draft,
        is_published: draft.state === "published",
        author_name: user_name(draft.author_id),
        collaborator_count: draft.collaborator_user_ids.length,
        can_edit: hover_pipeline_library.can_edit_draft(draft, current_user.user_id),
    }));

    $("#hover_pipeline_library_root").html(
        render_hover_pipeline_library_content({
            ...library,
            creator_count: library.creator_user_ids.length,
            creators: people_context(library.creator_user_ids),
            eligible_creators,
            has_creators: library.creator_user_ids.length > 0,
            definitions,
            has_definitions: definitions.length > 0,
            drafts,
            has_drafts: drafts.length > 0,
        }),
    );
}

function accept_library_response(raw_data: unknown): HoverPipelineLibrary | undefined {
    const library = hover_pipeline_library.replace(raw_data);
    if (library === undefined) {
        show_parse_error();
        return undefined;
    }
    return library;
}

function load_library(): void {
    void channel.get({
        url: "/json/hover/pipeline-library",
        success(raw_data) {
            const library = accept_library_response(raw_data);
            if (library !== undefined) {
                render_library(library);
            }
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Could not open the Pipeline Library."}),
                xhr,
                status_box(),
            );
        },
    });
}

function mutate(
    request: LibraryRequest,
    url: string,
    data: Record<string, string> | undefined,
    $button: JQuery,
    success_continuation?: (library: HoverPipelineLibrary, raw_data: unknown) => void,
): void {
    set_busy($button, true);
    void request({
        url,
        ...(data !== undefined && {data}),
        success(raw_data) {
            set_busy($button, false);
            const library = accept_library_response(raw_data);
            if (library === undefined) {
                return;
            }
            if (success_continuation !== undefined) {
                success_continuation(library, raw_data);
            } else {
                render_library(library);
            }
        },
        error(xhr) {
            set_busy($button, false);
            ui_report.error(
                $t_html({defaultMessage: "The Pipeline Library could not save that change."}),
                xhr,
                status_box(),
            );
        },
    });
}

function json_text(value: unknown): string {
    return JSON.stringify(value, undefined, 2);
}

function editor_context(
    contract: HoverPipelineDraftContract,
    draft: HoverPipelineDraft | undefined,
): Record<string, unknown> {
    const library = hover_pipeline_library.get()!;
    const can_edit =
        draft === undefined
            ? library.permissions.can_create
            : hover_pipeline_library.can_edit_draft(draft, current_user.user_id);
    const can_manage_collaborators =
        draft !== undefined &&
        can_edit &&
        (library.permissions.can_manage_creators || draft.author_id === current_user.user_id);
    const collaborator_ids = new Set(draft?.collaborator_user_ids);
    const excluded_ids = new Set([draft?.author_id, ...collaborator_ids]);
    const eligible_collaborators = library.creator_user_ids
        .filter((user_id) => !excluded_ids.has(user_id))
        .map((user_id) => ({user_id, full_name: user_name(user_id)}))
        .toSorted((a, b) => a.full_name.localeCompare(b.full_name));

    return {
        is_new: draft === undefined,
        draft_id: draft?.id ?? "new",
        revision: draft?.revision,
        can_edit,
        can_manage_collaborators,
        contract,
        input_contract_text: json_text(contract.input_contract),
        output_template_text: json_text(contract.output_template),
        requirements_text: json_text(contract.requirements),
        integration_keys_text: contract.integration_keys.join(", "),
        supports_manual: contract.supported_triggers.includes("manual"),
        supports_schedule: contract.supported_triggers.includes("schedule"),
        collaborators: people_context(draft?.collaborator_user_ids ?? []).map((person) => ({
            ...person,
            can_remove: can_manage_collaborators,
        })),
        has_collaborators: (draft?.collaborator_user_ids.length ?? 0) > 0,
        eligible_collaborators,
    };
}

function open_editor(draft?: HoverPipelineDraft): void {
    const contract = draft?.contract ?? hover_pipeline_library.blank_contract();
    $("#hover_pipeline_library_root").html(
        render_hover_pipeline_draft_editor(editor_context(contract, draft)),
    );
    $("[data-pipeline-contract-fieldset]").prop(
        "disabled",
        draft === undefined
            ? !hover_pipeline_library.get()!.permissions.can_create
            : !hover_pipeline_library.can_edit_draft(draft, current_user.user_id),
    );
    $("#hover_pipeline_draft_form input[name='version']").prop("readonly", true);
    if (draft?.definition_id !== null && draft?.definition_id !== undefined) {
        $("#hover_pipeline_draft_form input[name='stable_key']").prop("readonly", true);
    }
    for (const trigger of contract.supported_triggers) {
        $<HTMLInputElement>(
            `#hover_pipeline_draft_form input[name='supported_trigger'][value='${trigger}']`,
        ).prop("checked", true);
    }
    $("#hover_pipeline_draft_form input[name='name']").trigger("focus");
}

function parse_json_field(name: string): unknown {
    const value = $<HTMLTextAreaElement>(`#hover_pipeline_draft_form [name='${name}']`).val();
    try {
        return JSON.parse(value ?? "");
    } catch {
        ui_report.client_error(
            $t_html({
                defaultMessage:
                    "Input contract, requirements, and output template must be valid JSON.",
            }),
            status_box(),
        );
        return undefined;
    }
}

function draft_form_data(draft?: HoverPipelineDraft): Record<string, string> | undefined {
    const $form = $("#hover_pipeline_draft_form");
    const form = $form[0];
    if (form instanceof HTMLFormElement && !form.checkValidity()) {
        form.reportValidity();
        return undefined;
    }
    const input_contract = parse_json_field("input_contract");
    const requirements = parse_json_field("requirements");
    const output_template = parse_json_field("output_template");
    if (
        input_contract === undefined ||
        requirements === undefined ||
        output_template === undefined
    ) {
        return undefined;
    }
    const supported_triggers = Array.from(
        $<HTMLInputElement>("#hover_pipeline_draft_form input[name='supported_trigger']:checked"),
        (element) => element.value,
    );
    if (supported_triggers.length === 0) {
        ui_report.client_error(
            $t_html({defaultMessage: "Choose at least one supported trigger."}),
            status_box(),
        );
        return undefined;
    }
    const text = (name: string): string =>
        $<HTMLInputElement | HTMLTextAreaElement>(`#hover_pipeline_draft_form [name='${name}']`)
            .val()!
            .trim();
    const integer = (name: string): string => JSON.stringify(Math.trunc(Number(text(name))));

    return {
        ...(draft !== undefined && {revision: JSON.stringify(draft.revision)}),
        stable_key: text("stable_key"),
        name: text("name"),
        description: text("description"),
        version: text("version"),
        input_contract: JSON.stringify(input_contract),
        lookback_days: integer("lookback_days"),
        runtime_key: text("runtime_key"),
        prompt_key: text("prompt_key"),
        integration_keys: JSON.stringify(
            text("integration_keys")
                .split(",")
                .map((key) => key.trim())
                .filter(Boolean),
        ),
        output_type: text("output_type"),
        output_template: JSON.stringify(output_template),
        maximum_runtime_seconds: integer("maximum_runtime_seconds"),
        destination_topic: text("destination_topic"),
        navigation_icon: text("navigation_icon"),
        navigation_order: integer("navigation_order"),
        requirements: JSON.stringify(requirements),
        supported_triggers: JSON.stringify(supported_triggers),
    };
}

function current_draft(): HoverPipelineDraft | undefined {
    const draft_id = Number($(".hover-pipeline-editor").attr("data-draft-id"));
    return hover_pipeline_library.get()?.drafts.find((draft) => draft.id === draft_id);
}

function bind_events(): void {
    const $root = $("#hover_pipeline_library_root");
    $root.on("click", "[data-pipeline-create-draft]", () => {
        open_editor();
    });
    $root.on("click", "[data-pipeline-back]", () => {
        const library = hover_pipeline_library.get();
        if (library !== undefined) {
            render_library(library);
        }
    });
    $root.on("click", "[data-pipeline-open-draft]", (event) => {
        const draft_id = Number($(event.currentTarget).attr("data-pipeline-open-draft"));
        const draft = hover_pipeline_library.get()?.drafts.find((item) => item.id === draft_id);
        if (draft !== undefined) {
            open_editor(draft);
        }
    });
    $root.on("submit", "[data-pipeline-grant-creator]", (event) => {
        event.preventDefault();
        const user_id = Number($<HTMLSelectElement>("#hover_pipeline_creator_user").val());
        if (!Number.isSafeInteger(user_id) || user_id <= 0) {
            return;
        }
        mutate(
            channel.post,
            "/json/hover/pipeline-library/creators",
            {user_id: JSON.stringify(user_id)},
            $<HTMLButtonElement>("[data-pipeline-grant-creator] button[type='submit']"),
        );
    });
    $root.on("click", "[data-pipeline-revoke-creator]", (event) => {
        const user_id = Number($(event.currentTarget).attr("data-pipeline-revoke-creator"));
        mutate(
            channel.del,
            `/json/hover/pipeline-library/creators/${user_id}`,
            undefined,
            $<HTMLButtonElement>("[data-pipeline-revoke-creator]"),
        );
    });
    $root.on("submit", "#hover_pipeline_draft_form", (event) => {
        event.preventDefault();
        const draft = current_draft();
        const data = draft_form_data(draft);
        if (data === undefined) {
            return;
        }
        const $button = $(event.currentTarget).find("button[type='submit']");
        mutate(
            draft === undefined ? channel.post : channel.patch,
            draft === undefined
                ? "/json/hover/pipeline-library/drafts"
                : `/json/hover/pipeline-library/drafts/${draft.id}`,
            data,
            $button,
            (library, raw_data) => {
                const returned_draft = hover_pipeline_library.draft_from_mutation(raw_data);
                const saved =
                    returned_draft ?? library.drafts.find((item) => item.id === draft?.id);
                if (saved === undefined) {
                    show_parse_error();
                    return;
                }
                open_editor(saved);
                ui_report.success(
                    $t_html({defaultMessage: "Private draft saved."}),
                    status_box(),
                    3000,
                );
            },
        );
    });
    $root.on("click", "[data-pipeline-add-collaborator]", (_event) => {
        const draft = current_draft();
        const user_id = Number($<HTMLSelectElement>("#hover_pipeline_collaborator_user").val());
        if (draft === undefined || !Number.isSafeInteger(user_id) || user_id <= 0) {
            return;
        }
        mutate(
            channel.post,
            `/json/hover/pipeline-library/drafts/${draft.id}/collaborators`,
            {user_id: JSON.stringify(user_id)},
            $<HTMLButtonElement>("[data-pipeline-add-collaborator]"),
            (library, raw_data) => {
                const updated =
                    hover_pipeline_library.draft_from_mutation(raw_data) ??
                    library.drafts.find((item) => item.id === draft.id);
                if (updated !== undefined) {
                    open_editor(updated);
                }
            },
        );
    });
    $root.on("click", "[data-pipeline-remove-collaborator]", (event) => {
        const draft = current_draft();
        const user_id = Number($(event.currentTarget).attr("data-pipeline-remove-collaborator"));
        if (draft === undefined) {
            return;
        }
        mutate(
            channel.del,
            `/json/hover/pipeline-library/drafts/${draft.id}/collaborators/${user_id}`,
            undefined,
            $<HTMLButtonElement>("[data-pipeline-remove-collaborator]"),
            (library, raw_data) => {
                const updated =
                    hover_pipeline_library.draft_from_mutation(raw_data) ??
                    library.drafts.find((item) => item.id === draft.id);
                if (updated !== undefined) {
                    open_editor(updated);
                }
            },
        );
    });
    $root.on("click", "[data-pipeline-publish]", () => {
        const draft = current_draft();
        if (draft === undefined) {
            return;
        }
        const data = draft_form_data(draft);
        if (data === undefined) {
            return;
        }
        const $button = $<HTMLButtonElement>("[data-pipeline-publish]");
        mutate(
            channel.patch,
            `/json/hover/pipeline-library/drafts/${draft.id}`,
            data,
            $button,
            (library, raw_data) => {
                const saved =
                    hover_pipeline_library.draft_from_mutation(raw_data) ??
                    library.drafts.find((item) => item.id === draft.id);
                if (saved === undefined) {
                    show_parse_error();
                    return;
                }
                mutate(
                    channel.post,
                    `/json/hover/pipeline-library/drafts/${draft.id}/publish`,
                    {revision: JSON.stringify(saved.revision)},
                    $button,
                );
            },
        );
    });
    $root.on("click", "[data-pipeline-create-successor]", (event) => {
        const version_id = Number($(event.currentTarget).attr("data-pipeline-create-successor"));
        mutate(
            channel.post,
            `/json/hover/pipeline-library/versions/${version_id}/successor`,
            undefined,
            $<HTMLButtonElement>("[data-pipeline-create-successor]"),
            (library, raw_data) => {
                const successor =
                    hover_pipeline_library.draft_from_mutation(raw_data) ??
                    library.drafts.find(
                        (draft) =>
                            draft.based_on_version_id === version_id && draft.state === "draft",
                    );
                if (successor === undefined) {
                    show_parse_error();
                    return;
                }
                open_editor(successor);
            },
        );
    });
    $root.on("click", "[data-pipeline-archive-definition]", (event) => {
        const definition_id = Number(
            $(event.currentTarget).attr("data-pipeline-archive-definition"),
        );
        mutate(
            channel.post,
            `/json/hover/pipeline-library/definitions/${definition_id}/archive`,
            undefined,
            $<HTMLButtonElement>("[data-pipeline-archive-definition]"),
        );
    });
    $root.on("click", "[data-pipeline-archive-version]", (event) => {
        const version_id = Number($(event.currentTarget).attr("data-pipeline-archive-version"));
        mutate(
            channel.post,
            `/json/hover/pipeline-library/versions/${version_id}/archive`,
            undefined,
            $<HTMLButtonElement>("[data-pipeline-archive-version]"),
        );
    });
}

export function open(): void {
    if (current_user.is_guest || modal_is_open) {
        return;
    }
    hover_pipeline_library.clear();
    modal_is_open = true;
    dialog_widget.launch({
        id: "hover-pipeline-library-modal",
        modal_title_text: $t({defaultMessage: "Pipeline Library"}),
        modal_content_html: render_hover_pipeline_library(),
        hide_footer: true,
        always_visible_scrollbar: true,
        on_hidden() {
            modal_is_open = false;
            hover_pipeline_library.clear();
        },
        post_render() {
            bind_events();
            load_library();
        },
    });
}
