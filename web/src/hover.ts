import type {Message} from "./message_store.ts";

export type SourceIntegration = {
    id: number | null;
    key: string;
    name: string;
    count: number;
    url: string;
};

export function normalize_source_integrations(
    sources: readonly SourceIntegration[],
): SourceIntegration[] {
    return sources.map(({id, key, name, count, url}) => ({id, key, name, count, url}));
}

export function is_generated_update(message: Pick<Message, "hover_generated_item">): boolean {
    return message.hover_generated_item !== undefined;
}
