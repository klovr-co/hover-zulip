import type {Message} from "./message_store.ts";

export const HOVER_AI_EMAIL = "hover-ai@hover.test";

export type SourceIntegration = {
    key: "whatsapp" | "github" | "instagram";
    name: string;
    icon_class: string;
    count: number;
    url?: string;
};

export function is_generated_update(message: Pick<Message, "sender_email">): boolean {
    return message.sender_email === HOVER_AI_EMAIL;
}

export function get_source_integrations(rendered_content: string): SourceIntegration[] {
    const integrations: SourceIntegration[] = [];
    const whatsapp_count = rendered_content.match(/<strong>WhatsApp\b/g)?.length ?? 0;
    const github_url = rendered_content.match(/href="(https:\/\/github\.com\/[^"]+)"/)?.[1];
    const instagram_url = rendered_content.match(
        /href="(https:\/\/www\.instagram\.com\/[^"]+)"/,
    )?.[1];

    if (whatsapp_count > 0) {
        integrations.push({
            key: "whatsapp",
            name: "WhatsApp",
            icon_class: "fa fa-whatsapp",
            count: whatsapp_count,
        });
    }
    if (github_url !== undefined) {
        integrations.push({
            key: "github",
            name: "GitHub",
            icon_class: "fa fa-github",
            count: 1,
            url: github_url,
        });
    }
    if (instagram_url !== undefined) {
        integrations.push({
            key: "instagram",
            name: "Instagram",
            icon_class: "fa fa-instagram",
            count: 1,
            url: instagram_url,
        });
    }

    return integrations;
}
