import type {Meta, StoryObj} from "@storybook/html";

import render_message_controls from "../templates/message_controls.hbs";
import render_message_controls_failed from "../templates/message_controls_failed_msg.hbs";
import render_message_reactions from "../templates/message_reactions.hbs";

type MessageActionArgs = {
    compact: boolean;
};

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

function render_message_actions(args: MessageActionArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = `cf-theme storybook-cf-message-controls${args.compact ? " storybook-cf-message-controls--compact" : ""}`;
    canvas.innerHTML = `
        <header class="storybook-cf-message-controls__header">
            <div>
                <h2>Message actions &amp; reactions</h2>
                <p>Try the production controls, persistent reaction state, and narrow-touch geometry.</p>
            </div>
            <span>COFOUNDER</span>
        </header>
        <div class="storybook-cf-message-controls__grid">
            <article class="storybook-cf-message-controls__message" aria-labelledby="message-actions-available-title">
                <div class="storybook-cf-message-controls__identity">
                    <h3 id="message-actions-available-title">Ava Rodriguez</h3>
                    <time datetime="10:32">10:32 AM</time>
                    <div class="cf-message-actions">${render_message_controls({is_archived: false, msg: {locally_echoed: false, sent_by_me: false, starred: false}})}</div>
                </div>
                <p>The launch notes are ready for a final pass before we share them with the team.</p>
                ${render_message_reactions({is_archived: false, msg: {message_reactions: [reaction("thumbs up", "👍", "4", true), reaction("sparkles", "✨", "2")]}})}
            </article>
            <article class="storybook-cf-message-controls__message" aria-labelledby="message-actions-own-title">
                <div class="storybook-cf-message-controls__identity">
                    <h3 id="message-actions-own-title">You</h3>
                    <time datetime="10:45">10:45 AM</time>
                    <div class="cf-message-actions">${render_message_controls({is_archived: false, msg: {locally_echoed: false, sent_by_me: true, starred: true}})}</div>
                </div>
                <p>I’ll resolve the last two comments and post the approved version this afternoon.</p>
                ${render_message_reactions({is_archived: true, msg: {message_reactions: [reaction("check", "✅", "You", true)]}})}
            </article>
            <article class="storybook-cf-message-controls__message storybook-cf-message-controls__message--failed" aria-labelledby="message-actions-failed-title">
                <div class="storybook-cf-message-controls__identity">
                    <h3 id="message-actions-failed-title">Send failed</h3>
                    <span>Retry or dismiss</span>
                    <div class="cf-message-actions">${render_message_controls_failed()}</div>
                </div>
                <p>Your draft is safe. Check your connection, then retry the message.</p>
            </article>
            <p class="storybook-cf-message-controls__feedback" role="status" aria-live="polite"></p>
        </div>`;

    canvas
        .querySelector<HTMLElement>(".cf-message-actions__edit")
        ?.classList.add("cf-message-actions__edit--can-edit");

    const feedback = canvas.querySelector<HTMLElement>(".storybook-cf-message-controls__feedback");
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

        if (button.classList.contains("refresh-failed-message")) {
            button.classList.add("rotating");
            button.closest("article")?.setAttribute("aria-busy", "true");
            feedback.textContent = "Retry requested.";
            return;
        }

        if (button.classList.contains("remove-failed-message")) {
            button.closest("article")?.setAttribute("hidden", "");
            feedback.textContent = "Failed draft dismissed.";
            return;
        }

        feedback.textContent = `${button.getAttribute("aria-label") ?? "Action"} selected.`;
    });
    return canvas;
}

const meta = {
    title: "Cofounder/Messages/Actions and reactions",
    parameters: {layout: "fullscreen"},
    args: {compact: false},
    render: render_message_actions,
} satisfies Meta<MessageActionArgs>;

export default meta;
type Story = StoryObj<MessageActionArgs>;

export const StateGallery: Story = {};

export const NarrowTouch: Story = {
    args: {compact: true},
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
