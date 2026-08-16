import type {Meta, StoryObj} from "@storybook/html";

import render_single_message from "../templates/single_message.hbs";

type MessageItemArgs = {
    narrow: boolean;
};

const avatar = (initials: string, color: string): string =>
    `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72"><rect width="72" height="72" rx="14" fill="${color}"/><text x="36" y="39" text-anchor="middle" dominant-baseline="middle" fill="white" font-family="system-ui" font-size="24" font-weight="650">${initials}</text></svg>`)}`;

const emoji_image = (glyph: string): string =>
    `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" font-size="22">${glyph}</text></svg>`)}`;

function reaction(emoji_name: string, glyph: string, vote_text: string, selected = false): object {
    return {
        emoji_alt_code: false,
        emoji_name,
        is_realm_emoji: true,
        label: `${emoji_name}, ${vote_text}`,
        local_id: `realm_emoji,${emoji_name}`,
        selected,
        url: emoji_image(glyph),
        vote_text,
    };
}

function message(data: {
    avatar: string;
    content: string;
    id: number;
    name: string;
    reactions?: object[];
    sender_is_bot?: boolean;
    sent_by_me?: boolean;
    show_slow_send_spinner?: boolean;
    time: string;
    unread?: boolean;
}): string {
    const locally_echoed = data.show_slow_send_spinner === true;
    return render_single_message({
        include_sender: true,
        message_list_id: 1,
        sender_is_bot: data.sender_is_bot ?? false,
        small_avatar_url: data.avatar,
        timestr: data.time,
        msg: {
            content: `<p>${data.content}</p>`,
            failed_request: false,
            id: data.id,
            is_stream: true,
            locally_echoed,
            message_reactions: data.reactions ?? [],
            reminders: [],
            sender_full_name: data.name,
            sender_id: data.id,
            sent_by_me: data.sent_by_me ?? false,
            show_slow_send_spinner: locally_echoed,
            starred: false,
            unread: data.unread ?? false,
            url: `#message-${data.id}`,
        },
    });
}

function render_message_items(args: MessageItemArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = `cf-theme storybook-cf-message-items${args.narrow ? " storybook-cf-message-items--narrow" : ""}`;
    canvas.innerHTML = `
        <header class="storybook-cf-message-items__header">
            <div>
                <p>COFOUNDER / PRODUCTION</p>
                <h2>Message rows</h2>
                <span>Real templates, stateful controls, and content behavior.</span>
            </div>
            <strong>${args.narrow ? "≤ 390 px" : "Desktop"}</strong>
        </header>
        <main class="storybook-cf-message-items__stage">
            <div class="message-list storybook-cf-message-items__stack" role="list">
                ${message({
                    avatar: avatar("AR", "#3768a6"),
                    content:
                        "The launch notes are ready for a final pass before we share them with the team.",
                    id: 41,
                    name: "Ava Rodriguez",
                    reactions: [
                        reaction("thumbs up", "👍", "4", true),
                        reaction("sparkles", "✨", "2"),
                    ],
                    time: "10:32 AM",
                    unread: true,
                })}
                ${message({
                    avatar: avatar("HB", "#57745d"),
                    content:
                        "I linked the evidence and marked the two assumptions that still need confirmation.",
                    id: 42,
                    name: "Hover Bot",
                    sender_is_bot: true,
                    time: "10:38 AM",
                })}
                ${message({
                    avatar: avatar("MC", "#8a5b47"),
                    content:
                        "I’ll resolve the last comments and post the approved version this afternoon.",
                    id: 43,
                    name: "Maxine Chen",
                    sent_by_me: true,
                    show_slow_send_spinner: true,
                    time: "Sending",
                })}
            </div>
        </main>
        <p class="storybook-cf-message-items__feedback" role="status" aria-live="polite"></p>`;

    canvas
        .querySelector<HTMLElement>(".cf-message-actions__edit")
        ?.classList.add("cf-message-actions__edit--can-edit");
    canvas
        .querySelector<HTMLElement>(".cf-message-item")
        ?.classList.add("storybook-cf-message-item--active");

    const feedback = canvas.querySelector<HTMLElement>(".storybook-cf-message-items__feedback");
    canvas.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }

        const button = event.target.closest<HTMLButtonElement>("button");
        if (!button || button.disabled || !feedback) {
            return;
        }

        if (button.classList.contains("cf-message-reaction")) {
            const selected = button.getAttribute("aria-pressed") !== "true";
            button.classList.toggle("cf-message-reaction--selected", selected);
            button.setAttribute("aria-pressed", String(selected));
            feedback.textContent = selected ? "Reaction added." : "Reaction removed.";
            return;
        }

        if (button.classList.contains("cf-message-actions__star-button")) {
            const selected = button.getAttribute("aria-pressed") !== "true";
            button.classList.toggle("cf-message-actions__star-button--selected", selected);
            button.setAttribute("aria-pressed", String(selected));
            button.setAttribute("aria-label", selected ? "Unstar message" : "Star message");
            feedback.textContent = selected ? "Message starred." : "Message unstarred.";
            return;
        }

        const label = button.getAttribute("aria-label") ?? button.textContent?.trim() ?? "Action";
        feedback.textContent = `${label} selected.`;
    });
    return canvas;
}

const meta = {
    title: "Cofounder/Messages/Production row",
    parameters: {layout: "fullscreen"},
    args: {narrow: false},
    render: render_message_items,
} satisfies Meta<MessageItemArgs>;

export default meta;
type Story = StoryObj<MessageItemArgs>;

export const StateGallery: Story = {};

export const NarrowTouch: Story = {
    args: {narrow: true},
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
