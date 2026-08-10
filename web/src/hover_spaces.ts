import * as z from "zod/mini";

export const hover_space_schema = z.object({
    id: z.number(),
    name: z.string(),
    description: z.string(),
    state: z.enum(["setup", "launched"]),
    category: z.object({id: z.number(), name: z.string()}),
    created_by_id: z.nullable(z.number()),
    stream_id: z.nullable(z.number()),
});

export const hover_spaces_response_schema = z.object({
    spaces: z.array(hover_space_schema),
});

export type HoverSpace = z.infer<typeof hover_space_schema>;

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
    return [...spaces_by_id.values()].find((space) => space.stream_id === stream_id);
}

export function get_all(): HoverSpace[] {
    return [...spaces_by_id.values()].sort(
        (a, b) => a.category.name.localeCompare(b.category.name) || a.name.localeCompare(b.name),
    );
}

export function get_setup_spaces(): HoverSpace[] {
    return get_all().filter((space) => space.state === "setup");
}
