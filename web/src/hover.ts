import type {Message} from "./message_store.ts";

export type SourceIntegration = {
    id: number | null;
    key: string;
    name: string;
    icon_class: string;
    count: number;
    url: string;
};

export function is_generated_update(message: Pick<Message, "hover_generated_item">): boolean {
    return message.hover_generated_item !== undefined;
}
