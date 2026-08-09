import type {Message} from "./message_store.ts";

export const HOVER_AI_EMAIL = "hover-ai@hover.test";
export const AIMTO_SPACE_NAME = "AIMTO Events";
export const AIMTO_SUMMARY_TOPIC = "Summary";

export type AttachedSource = {
    key: "whatsapp" | "github" | "instagram";
    name: string;
    detail: string;
    icon_class: string;
    url: string;
    is_external: boolean;
};

export type SourceIntegration = {
    key: "whatsapp" | "github" | "instagram";
    name: string;
    icon_class: string;
    count: number;
    url?: string;
};

export function get_aimto_attached_sources(summary_url: string): AttachedSource[] {
    return [
        {
            key: "whatsapp",
            name: "Mentors & Volunteers",
            detail: "WhatsApp group",
            icon_class: "fa fa-whatsapp",
            url: summary_url,
            is_external: false,
        },
        {
            key: "whatsapp",
            name: "Resident Lounge",
            detail: "WhatsApp group",
            icon_class: "fa fa-whatsapp",
            url: summary_url,
            is_external: false,
        },
        {
            key: "whatsapp",
            name: "500 volunteers",
            detail: "WhatsApp group",
            icon_class: "fa fa-whatsapp",
            url: summary_url,
            is_external: false,
        },
        {
            key: "github",
            name: "learnaimto",
            detail: "GitHub repository",
            icon_class: "fa fa-github",
            url: "https://github.com/ashvinpraveen/learnaimto",
            is_external: true,
        },
        {
            key: "instagram",
            name: "@aimto_26",
            detail: "Instagram account",
            icon_class: "fa fa-instagram",
            url: "https://www.instagram.com/aimto_26/",
            is_external: true,
        },
    ];
}

export function is_generated_update(message: Pick<Message, "sender_email">): boolean {
    return message.sender_email === HOVER_AI_EMAIL;
}

export function get_source_integrations(rendered_content: string): SourceIntegration[] {
    const integrations: SourceIntegration[] = [];
    const whatsapp_count = rendered_content.matchAll(/<strong>WhatsApp\b/g).toArray().length;
    const github_url = /href="(https:\/\/github\.com\/[^"]+)"/.exec(rendered_content)?.[1];
    const instagram_url = /href="(https:\/\/www\.instagram\.com\/[^"]+)"/.exec(
        rendered_content,
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

export function get_source_context(rendered_content: string): string {
    const integrations = get_source_integrations(rendered_content);
    const source_count = integrations.reduce((total, integration) => total + integration.count, 0);

    if (source_count > 1) {
        return `Across ${source_count} sources`;
    }

    const whatsapp_name = /<strong>WhatsApp · ([^<]+)<\/strong>/.exec(rendered_content)?.[1];
    if (whatsapp_name !== undefined) {
        return `From ${whatsapp_name.replace(/ \(AIMTO excerpts\)$/, "").replaceAll("&amp;", "&")}`;
    }

    const linked_source_name = /<a [^>]*>(?:GitHub|Instagram) · ([^<]+)<\/a>/.exec(
        rendered_content,
    )?.[1];
    if (linked_source_name !== undefined) {
        return `From ${linked_source_name}`;
    }

    return "Source-backed update";
}
