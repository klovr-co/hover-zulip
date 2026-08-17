import * as z from "zod/mini";

export const hover_pipeline_trigger_schema = z.enum(["manual", "new_source", "schedule"]);

export const hover_pipeline_requirement_schema = z.object({
    key: z.string(),
    capability: z.string(),
    minimum_count: z.number(),
    maximum_count: z.number(),
});

export const hover_pipeline_public_version_schema = z.object({
    id: z.number(),
    definition_key: z.string(),
    name: z.string(),
    description: z.string(),
    version: z.string(),
    output_type: z.string(),
    destination_topic: z.string(),
    navigation_icon: z.string(),
    navigation_order: z.number(),
    content_hash: z.string(),
    published_at: z.string(),
    lookback_days: z.number(),
    maximum_runtime_seconds: z.number(),
    archived: z.boolean(),
    requirements: z.array(hover_pipeline_requirement_schema),
    supported_triggers: z.array(hover_pipeline_trigger_schema),
});

export const hover_pipeline_definition_schema = z.object({
    id: z.number(),
    stable_key: z.string(),
    name: z.string(),
    description: z.string(),
    archived: z.boolean(),
    versions: z.array(hover_pipeline_public_version_schema),
});

export const hover_pipeline_draft_contract_schema = z.object({
    stable_key: z.string(),
    name: z.string(),
    description: z.string(),
    version: z.string(),
    input_contract: z.unknown(),
    lookback_days: z.number(),
    runtime_key: z.string(),
    prompt_key: z.string(),
    integration_keys: z.array(z.string()),
    output_type: z.string(),
    output_template: z.unknown(),
    maximum_runtime_seconds: z.number(),
    destination_topic: z.string(),
    navigation_icon: z.string(),
    navigation_order: z.number(),
    requirements: z.array(hover_pipeline_requirement_schema),
    supported_triggers: z.array(hover_pipeline_trigger_schema),
});

export const hover_pipeline_draft_schema = z.object({
    id: z.number(),
    definition_id: z.nullable(z.number()),
    based_on_version_id: z.nullable(z.number()),
    author_id: z.number(),
    collaborator_user_ids: z.array(z.number()),
    revision: z.number(),
    state: z.enum(["draft", "published"]),
    published_version_id: z.nullable(z.number()),
    date_updated: z.string(),
    contract: hover_pipeline_draft_contract_schema,
});

export const hover_pipeline_library_response_schema = z.object({
    definitions: z.array(hover_pipeline_definition_schema),
    drafts: z.array(hover_pipeline_draft_schema),
    creator_user_ids: z.array(z.number()),
    permissions: z.object({
        can_create: z.boolean(),
        can_manage_creators: z.boolean(),
        can_archive: z.boolean(),
    }),
});

const hover_pipeline_draft_mutation_response_schema = z.object({
    draft: hover_pipeline_draft_schema,
});

export type HoverPipelineLibrary = z.output<typeof hover_pipeline_library_response_schema>;
export type HoverPipelineDefinition = z.output<typeof hover_pipeline_definition_schema>;
export type HoverPipelinePublicVersion = z.output<typeof hover_pipeline_public_version_schema>;
export type HoverPipelineDraft = z.output<typeof hover_pipeline_draft_schema>;
export type HoverPipelineDraftContract = z.output<typeof hover_pipeline_draft_contract_schema>;

let library: HoverPipelineLibrary | undefined;

export function replace(raw_data: unknown): HoverPipelineLibrary | undefined {
    const result = hover_pipeline_library_response_schema.safeParse(raw_data);
    if (!result.success) {
        return undefined;
    }
    library = result.data;
    return library;
}

export function get(): HoverPipelineLibrary | undefined {
    return library;
}

export function draft_from_mutation(raw_data: unknown): HoverPipelineDraft | undefined {
    const result = hover_pipeline_draft_mutation_response_schema.safeParse(raw_data);
    return result.success ? result.data.draft : undefined;
}

export function clear(): void {
    library = undefined;
}

export function visible_definitions(): HoverPipelineDefinition[] {
    if (library === undefined) {
        return [];
    }
    const current_library = library;
    return current_library.definitions
        .filter((definition) => current_library.permissions.can_archive || !definition.archived)
        .map((definition) => ({
            ...definition,
            versions: definition.versions.filter(
                (version) => current_library.permissions.can_archive || !version.archived,
            ),
        }))
        .filter(
            (definition) =>
                current_library.permissions.can_archive || definition.versions.length > 0,
        )
        .toSorted(
            (a, b) => a.name.localeCompare(b.name) || a.stable_key.localeCompare(b.stable_key),
        );
}

export function sorted_drafts(): HoverPipelineDraft[] {
    return [...(library?.drafts ?? [])].toSorted(
        (a, b) =>
            b.date_updated.localeCompare(a.date_updated) ||
            a.contract.name.localeCompare(b.contract.name),
    );
}

export function can_edit_draft(draft: HoverPipelineDraft, user_id: number): boolean {
    if (library === undefined || draft.state !== "draft") {
        return false;
    }
    return (
        library.permissions.can_manage_creators ||
        (library.permissions.can_create &&
            (draft.author_id === user_id || draft.collaborator_user_ids.includes(user_id)))
    );
}

export function blank_contract(): HoverPipelineDraftContract {
    return {
        stable_key: "",
        name: "",
        description: "",
        version: "1.0.0",
        input_contract: {type: "source_records"},
        lookback_days: 7,
        runtime_key: "",
        prompt_key: "",
        integration_keys: [],
        output_type: "generated_update",
        output_template: {format: "markdown"},
        maximum_runtime_seconds: 300,
        destination_topic: "",
        navigation_icon: "zulip-icon-bot",
        navigation_order: 100,
        requirements: [
            {key: "source", capability: "records_read", minimum_count: 1, maximum_count: 1},
        ],
        supported_triggers: ["manual"],
    };
}
