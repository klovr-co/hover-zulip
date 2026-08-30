import * as z from "zod/mini";

export const hover_source_schema = z.object({
    id: z.number(),
    provider_key: z.string(),
    provider_name: z.string(),
    source_type: z.string(),
    display_name: z.string(),
    external_url: z.string(),
    supports_live_capture: z.boolean(),
    account_id: z.number(),
    account_display_name: z.string(),
});

export const hover_space_attachment_schema = z.object({
    id: z.number(),
    state: z.enum(["active", "detached"]),
    history_window: z.enum(["today", "last_30_days", "custom"]),
    history_timezone: z.string(),
    history_start_at: z.string(),
    custom_start_date: z.nullable(z.string()),
    destination_topic: z._default(z.string(), ""),
    can_browse_records: z.boolean(),
    evidence_deleted: z._default(z.boolean(), false),
    source: hover_source_schema,
    integration_routes: z.array(
        z.object({
            id: z.number(),
            state: z.literal("active"),
            bot_user_id: z.number(),
            bot_name: z.string(),
            stream_id: z.number(),
            topic_name: z._default(z.string(), ""),
            live_since: z.string(),
        }),
    ),
    generated_count: z._default(z.number(), 0),
});

export const hover_module_version_schema = z.object({
    id: z.number(),
    definition_key: z.string(),
    name: z.string(),
    description: z.string(),
    version: z.string(),
    output_type: z.string(),
    lookback_days: z.number(),
    destination_topic: z.string(),
    maximum_runtime_seconds: z.number(),
    navigation_icon: z.string(),
    navigation_order: z.number(),
    content_hash: z.string(),
    published_at: z.string(),
    requirements: z.array(
        z.object({
            id: z.number(),
            key: z.string(),
            capability: z.string(),
            minimum_count: z.number(),
            maximum_count: z.number(),
        }),
    ),
    supported_triggers: z.array(z.enum(["manual", "new_source", "schedule"])),
});

export const hover_module_installation_schema = z.object({
    id: z.number(),
    state: z.enum(["configured", "enabled", "disabled", "paused_detached"]),
    version_id: z.number(),
    definition_key: z.string(),
    name: z.string(),
    label: z._default(z.string(), ""),
    version: z.string(),
    output_type: z.string(),
    destination_topic: z.string(),
    summary_stream_id: z._default(z.nullable(z.number()), null),
    navigation_icon: z.string(),
    navigation_order: z.number(),
    content_hash: z.string(),
    activated_at: z.nullable(z.string()),
    processing_start_at: z.nullable(z.string()),
    activation_timezone: z.string(),
    policy_revision: z.number(),
    policy_hash: z.string(),
    predecessor_id: z.nullable(z.number()),
    latest_scheduled_failure: z._default(
        z.nullable(
            z.object({
                failure_code: z.string(),
                scheduled_for: z.nullable(z.string()),
                completed_at: z.nullable(z.string()),
            }),
        ),
        null,
    ),
    bindings: z.array(z.object({requirement_key: z.string(), attachment_id: z.number()})),
    triggers: z.array(
        z.object({
            kind: z.enum(["manual", "new_source", "schedule"]),
            cadence: z.nullable(z.enum(["daily", "weekly"])),
            local_time: z.nullable(z.string()),
            timezone: z.nullable(z.string()),
            debounce_seconds: z.nullable(z.number()),
            anchor_at: z._default(z.nullable(z.string()), null),
            interval_seconds: z._default(z.nullable(z.number()), null),
            next_due_at: z._default(z.nullable(z.string()), null),
        }),
    ),
    generated_count: z._default(z.number(), 0),
    inputs: z._default(
        z.array(
            z.object({
                stream_id: z.number(),
                topic_name: z.string(),
                kind: z.enum(["regular", "source"]),
                attachment_id: z.nullable(z.number()),
            }),
        ),
        [],
    ),
    member_ids: z._default(z.array(z.number()), []),
});

export const hover_topic_descriptor_schema = z.object({
    stream_id: z.number(),
    topic_name: z.string(),
    kind: z.enum(["source", "summary"]),
    source: z.optional(
        z.object({
            attachment_id: z.number(),
            provider_key: z.enum(["github", "posthog", "whatsapp"]),
            state: z.enum(["setup_required", "live", "paused", "error"]),
        }),
    ),
    summary: z.optional(
        z.object({
            installation_id: z.number(),
            schedule_label: z.string(),
            can_manage: z.boolean(),
        }),
    ),
});

export const hover_space_schema = z.object({
    id: z.number(),
    name: z.string(),
    description: z.string(),
    state: z.enum(["setup", "launched"]),
    category: z.object({id: z.number(), name: z.string()}),
    created_by_id: z.nullable(z.number()),
    stream_id: z.nullable(z.number()),
    attachments: z.array(hover_space_attachment_schema),
    administrators: z._default(z.array(z.object({user_id: z.number(), full_name: z.string()})), []),
    memberships: z._default(
        z.array(
            z.object({
                id: z.number(),
                user_id: z.number(),
                full_name: z.string(),
                role: z.enum(["contributor", "subscriber"]),
                is_administrator: z.boolean(),
            }),
        ),
        [],
    ),
    membership_suggestions: z._default(
        z.array(
            z.object({
                id: z.number(),
                user_id: z.number(),
                full_name: z.string(),
                suggested_role: z.enum(["contributor", "subscriber"]),
                state: z.literal("pending"),
                match_basis: z.enum(["verified_email", "verified_phone"]),
            }),
        ),
        [],
    ),
    module_installations: z._default(z.array(hover_module_installation_schema), []),
    module_catalog: z._default(z.array(hover_module_version_schema), []),
    topic_descriptors: z._default(z.array(hover_topic_descriptor_schema), []),
});

export const hover_spaces_response_schema = z.object({
    spaces: z.array(hover_space_schema),
});

export type HoverSpace = z.infer<typeof hover_space_schema>;
export type HoverSource = z.infer<typeof hover_source_schema>;
export type HoverTopicDescriptor = z.infer<typeof hover_topic_descriptor_schema>;

let spaces_by_id = new Map<number, HoverSpace>();

export function initialize(params: {hover_spaces: HoverSpace[]}): void {
    spaces_by_id = new Map(params.hover_spaces.map((space) => [space.id, space]));
}

export function upsert(space: HoverSpace): void {
    spaces_by_id.set(space.id, space);
}

export function remove(space_id: number): void {
    spaces_by_id.delete(space_id);
}

export function clear(): void {
    spaces_by_id.clear();
}

export function get_by_id(space_id: number): HoverSpace | undefined {
    return spaces_by_id.get(space_id);
}

export function get_by_stream_id(stream_id: number): HoverSpace | undefined {
    return spaces_by_id
        .values()
        .find(
            (space) =>
                space.stream_id === stream_id ||
                (space.module_installations ?? []).some(
                    (installation) => installation.summary_stream_id === stream_id,
                ) ||
                (space.topic_descriptors ?? []).some(
                    (descriptor) =>
                        descriptor.kind === "summary" && descriptor.stream_id === stream_id,
                ),
        );
}

export function parent_stream_id(stream_id: number): number {
    return get_by_stream_id(stream_id)?.stream_id ?? stream_id;
}

export function is_summary_stream(stream_id: number): boolean {
    const space = get_by_stream_id(stream_id);
    return (
        space !== undefined &&
        space.stream_id !== stream_id &&
        ((space.module_installations ?? []).some(
            (installation) => installation.summary_stream_id === stream_id,
        ) ||
            (space.topic_descriptors ?? []).some(
                (descriptor) => descriptor.kind === "summary" && descriptor.stream_id === stream_id,
            ))
    );
}

export function get_topic_descriptor(
    stream_id: number,
    topic_name: string,
): HoverTopicDescriptor | undefined {
    const space = get_by_stream_id(stream_id);
    return space?.topic_descriptors?.find(
        (descriptor) =>
            descriptor.stream_id === stream_id &&
            descriptor.topic_name.toLocaleLowerCase() === topic_name.toLocaleLowerCase(),
    );
}

export function get_descriptors_for_parent(stream_id: number): HoverTopicDescriptor[] {
    return get_by_stream_id(stream_id)?.topic_descriptors ?? [];
}

export function get_all(): HoverSpace[] {
    return spaces_by_id
        .values()
        .toArray()
        .toSorted(
            (a, b) =>
                a.category.name.localeCompare(b.category.name) || a.name.localeCompare(b.name),
        );
}

export function get_setup_spaces(): HoverSpace[] {
    return get_all().filter((space) => space.state === "setup");
}

export function get_sidebar_sources(space: HoverSpace): {
    key: string;
    source_key: string;
    name: string;
    detail: string;
    icon_class: string;
    is_external: boolean;
    url?: string;
    attachment_id: number;
    can_browse_records: boolean;
    is_history_retained: boolean;
}[] {
    return space.attachments
        .map((attachment) => ({
            attachment_id: attachment.id,
            can_browse_records: attachment.can_browse_records,
            is_history_retained: attachment.state === "detached",
            source: attachment.source,
            integration_routes: attachment.integration_routes,
        }))
        .map(
            ({
                attachment_id,
                can_browse_records,
                is_history_retained,
                source,
                integration_routes,
            }) => {
                const is_external = !can_browse_records && source.external_url !== "";
                return {
                    key: source.provider_key,
                    source_key: String(source.id),
                    name: source.display_name,
                    detail:
                        integration_routes.length > 0
                            ? `${source.provider_name} · Live since ${new Date(integration_routes[0]!.live_since).toLocaleDateString()}`
                            : `${source.account_display_name} · ${source.source_type}`,
                    icon_class:
                        source.provider_key === "whatsapp" ? "fa fa-whatsapp" : "fa fa-plug",
                    is_external,
                    ...(is_external && {url: source.external_url}),
                    attachment_id,
                    can_browse_records,
                    is_history_retained,
                };
            },
        );
}

export function get_sidebar_modules(space: HoverSpace): {
    key: string;
    name: string;
    icon: string;
    topic: string;
    count: number;
}[] {
    return space.module_installations
        .filter((installation) => installation.state === "enabled")
        .toSorted((a, b) => a.navigation_order - b.navigation_order || a.id - b.id)
        .map((installation) => ({
            key: installation.definition_key,
            name: installation.name,
            icon: installation.navigation_icon,
            topic: installation.destination_topic,
            count: installation.generated_count ?? 0,
        }));
}
