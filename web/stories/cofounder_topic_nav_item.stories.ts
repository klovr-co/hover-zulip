import type {Meta, StoryObj} from "@storybook/html";

import render_more_topics from "../templates/more_topics.hbs";
import render_topic_list_item from "../templates/topic_list_item.hbs";
import render_topic_list_new_topic from "../templates/topic_list_new_topic.hbs";

import {component_story} from "./story_utils.ts";

type TopicNavItemArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Topic navigation item",
    parameters: {layout: "padded"},
} satisfies Meta<TopicNavItemArgs>;

export default meta;
type Story = StoryObj<TopicNavItemArgs>;

function topic({
    contains_unread_mention = false,
    is_active_topic = false,
    is_followed = false,
    is_muted = false,
    is_zero = false,
    name,
    resolved = false,
    unread,
}: {
    contains_unread_mention?: boolean;
    is_active_topic?: boolean;
    is_followed?: boolean;
    is_muted?: boolean;
    is_zero?: boolean;
    name: string;
    resolved?: boolean;
    unread: number;
}): string {
    return render_topic_list_item({
        contains_unread_mention,
        is_active_topic,
        is_empty_string_topic: false,
        is_followed,
        is_muted,
        is_unmuted_or_followed: is_followed,
        is_zero,
        stream_id: 7,
        topic_display_name: name,
        topic_name: `${resolved ? "✔ " : ""}${name}`,
        topic_resolved_prefix: resolved ? "✔ " : "",
        unread,
        url: `#narrow/channel/7-product-design/topic/${name.toLowerCase().replaceAll(" ", "-")}`,
    });
}

export const States: Story = {
    render() {
        const canvas = globalThis.document.createElement("div");
        canvas.innerHTML = component_story(`
            <nav class="storybook-cf-nav-states storybook-cf-topic-nav-states" aria-label="Product design topics">
                <p class="storybook-cf-nav-states__label">Product design</p>
                <ul id="stream_filters" class="filters storybook-cf-nav-states__list storybook-cf-nav-states__list--topics">
                    <li class="narrow-filter stream-expanded storybook-cf-nav-states__item">
                        <ul class="topic-list topic-list-has-topics">
                            ${topic({name: "Launch plan", unread: 12})}
                            ${topic({
                                contains_unread_mention: true,
                                is_active_topic: true,
                                name: "Research notes",
                                unread: 3,
                            })}
                            ${topic({is_followed: true, name: "Design critique", unread: 5})}
                            ${topic({name: "Decision log", resolved: true, unread: 1})}
                            ${topic({is_muted: true, is_zero: true, name: "Archive", unread: 0})}
                            ${render_more_topics({
                                more_topics_have_unread_mention_messages: true,
                                more_topics_unread_count_muted: false,
                                more_topics_unreads: 7,
                            })}
                            ${render_topic_list_new_topic({stream_id: 7})}
                        </ul>
                    </li>
                </ul>
                <p class="storybook-cf-nav-states__feedback" role="status" aria-live="polite" aria-atomic="true"></p>
            </nav>
        `);
        const feedback = canvas.querySelector<HTMLElement>(".storybook-cf-nav-states__feedback");
        canvas.addEventListener("click", (event) => {
            if (!(event.target instanceof Element) || feedback === null) {
                return;
            }
            const action = event.target.closest<HTMLButtonElement>(".cf-topic-nav__action");
            if (action !== null) {
                feedback.textContent = `${action.getAttribute("aria-label") ?? "Topic action"} opened.`;
                action.focus();
                return;
            }
            const topic_link = event.target.closest<HTMLAnchorElement>(".cf-topic-nav__main");
            if (topic_link !== null) {
                event.preventDefault();
                for (const row of canvas.querySelectorAll<HTMLElement>(".cf-topic-nav")) {
                    row.classList.remove("cf-topic-nav--selected", "active-sub-filter");
                    row.querySelector(".cf-topic-nav__main")?.removeAttribute("aria-current");
                }
                const row = topic_link.closest<HTMLElement>(".cf-topic-nav");
                row?.classList.add("cf-topic-nav--selected", "active-sub-filter");
                topic_link.setAttribute("aria-current", "page");
                const label = row?.querySelector(".cf-topic-nav__label-inner")?.textContent?.trim();
                feedback.textContent = `${label ?? "Topic"} selected.`;
                topic_link.focus();
                return;
            }
            const utility_link = event.target.closest<HTMLAnchorElement>(
                ".cf-topic-nav-action__main",
            );
            if (utility_link !== null) {
                event.preventDefault();
                const label =
                    utility_link.textContent?.trim().replaceAll(/\s+/g, " ") ?? "Topic action";
                feedback.textContent = `${label} opened.`;
                utility_link.focus();
            }
        });
        return canvas;
    },
};
