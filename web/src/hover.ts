import type {Message} from "./message_store.ts";

export const HOVER_AI_EMAIL = "hover-ai@hover.test";

const SOURCE_LOGOS = {
    whatsapp:
        '<span class="hover-source-logo hover-source-logo--whatsapp" aria-hidden="true"><i class="fa fa-whatsapp"></i></span>',
    github: '<span class="hover-source-logo hover-source-logo--github" aria-hidden="true"><i class="fa fa-github"></i></span>',
    instagram:
        '<span class="hover-source-logo hover-source-logo--instagram" aria-hidden="true"><i class="fa fa-instagram"></i></span>',
};

export function is_generated_update(message: Pick<Message, "sender_email">): boolean {
    return message.sender_email === HOVER_AI_EMAIL;
}

export function add_source_logos(rendered_content: string): string {
    return rendered_content
        .replace(
            /<li>(\s*)(<strong>WhatsApp\b)/g,
            `<li>$1${SOURCE_LOGOS.whatsapp}$2`,
        )
        .replace(
            /<li>(\s*)(<a\b[^>]*href="https:\/\/github\.com\/)/g,
            `<li>$1${SOURCE_LOGOS.github}$2`,
        )
        .replace(
            /<li>(\s*)(<a\b[^>]*href="https:\/\/www\.instagram\.com\/)/g,
            `<li>$1${SOURCE_LOGOS.instagram}$2`,
        );
}
