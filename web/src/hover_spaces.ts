import * as z from "zod/mini";

export const hover_source_schema = z.object({
    id: z.number(),
    provider_key: z.string(),
    source_type: z.string(),
    display_name: z.string(),
    account_id: z.number(),
    account_display_name: z.string(),
});

export const hover_space_attachment_schema = z.object({
    id: z.number(),
    state: z.literal("active"),
    history_window: z.enum(["today", "last_30_days", "custom"]),
    history_timezone: z.string(),
    history_start_at: z.string(),
    custom_start_date: z.nullable(z.string()),
    source: hover_source_schema,
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
});

export const hover_spaces_response_schema = z.object({
    spaces: z.array(hover_space_schema),
});

export type HoverSpace = z.infer<typeof hover_space_schema>;
export type HoverSource = z.infer<typeof hover_source_schema>;

export const pilot_ai_modules = [
    {key: "conversation_digest", name: "Conversation Digest", icon: "zulip-icon-align-left"},
    {key: "progress_tracker", name: "Progress Tracker", icon: "zulip-icon-trending-up"},
    {key: "suggested_actions", name: "Suggested Actions", icon: "zulip-icon-sparkles"},
    {key: "decisions", name: "Decisions", icon: "zulip-icon-check-circle"},
    {key: "marketing_digest", name: "Marketing Digest", icon: "zulip-icon-megaphone"},
    {key: "topic_analysis", name: "Topic Analysis", icon: "zulip-icon-chart-bar"},
] as const;

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
    icon_class: string;
    is_external: false;
}[] {
    return space.attachments.map(({source}) => ({
        key: source.provider_key,
        source_key: String(source.id),
        name: source.display_name,
        detail: `${source.account_display_name} · ${source.source_type}`,
        icon_class: source.provider_key === "whatsapp" ? "fa fa-whatsapp" : "fa fa-plug",
        is_external: false,
    }));
}
