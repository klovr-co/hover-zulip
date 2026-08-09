import type {Message} from "./message_store.ts";

export const HOVER_AI_EMAIL = "hover-ai@hover.test";

export function is_generated_update(message: Pick<Message, "sender_email">): boolean {
    return message.sender_email === HOVER_AI_EMAIL;
}
