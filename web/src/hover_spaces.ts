import * as z from "zod/mini";

import type {CofounderIconName} from "./cofounder/components/icon.ts";

const MODULE_NAVIGATION_ICONS: Readonly<Record<string, CofounderIconName>> = {
    conversation_digest: "file-text",
    decisions: "check",
    marketing_digest: "mail",
    progress_tracker: "bar-chart",
    signal_monitor: "activity",
    suggested_actions: "sparkles",
    topic_analysis: "bar-chart",
};

export function get_module_navigation_icon(definition_key: string): CofounderIconName {
    return MODULE_NAVIGATION_ICONS[definition_key] ?? "bot";
}

export function get_source_navigation_icon(provider_key: string): CofounderIconName {
    if (provider_key === "whatsapp") {
        return "phone";
    }
    if (provider_key === "github") {
        return "git-pull-request";
    }
    if (provider_key === "instagram") {
        return "image";
    }
    return "link-alt";
}

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
    destination_topic: z.string(),
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
    version: z.string(),
    output_type: z.string(),
    destination_topic: z.string(),
    navigation_icon: z.string(),
    navigation_order: z.number(),
    content_hash: z.string(),
    activated_at: z.nullable(z.string()),
    processing_start_at: z.nullable(z.string()),
    activation_timezone: z.string(),
    policy_revision: z.number(),
    policy_hash: z.string(),
    predecessor_id: z.nullable(z.number()),
    bindings: z.array(z.object({requirement_key: z.string(), attachment_id: z.number()})),
    triggers: z.array(
        z.object({
            kind: z.enum(["manual", "new_source", "schedule"]),
            cadence: z.nullable(z.enum(["daily", "weekly"])),
            local_time: z.nullable(z.string()),
            timezone: z.nullable(z.string()),
            debounce_seconds: z.nullable(z.number()),
        }),
    ),
    generated_count: z._default(z.number(), 0),
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
});

export const hover_spaces_response_schema = z.object({
    spaces: z.array(hover_space_schema),
});

export type HoverSpace = z.infer<typeof hover_space_schema>;
export type HoverSource = z.infer<typeof hover_source_schema>;

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
    return spaces_by_id.values().find((space) => space.stream_id === stream_id);
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
    icon_name: CofounderIconName;
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
                    icon_name: get_source_navigation_icon(source.provider_key),
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
    icon_name: CofounderIconName;
    topic: string;
    count: number;
}[] {
    return space.module_installations
        .filter((installation) => installation.state === "enabled")
        .toSorted((a, b) => a.navigation_order - b.navigation_order || a.id - b.id)
        .map((installation) => ({
            key: installation.definition_key,
            name: installation.name,
            icon_name: get_module_navigation_icon(installation.definition_key),
            topic: installation.destination_topic,
            count: installation.generated_count ?? 0,
        }));
}
