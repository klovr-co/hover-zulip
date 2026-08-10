import type {Meta, StoryObj} from "@storybook/html";

import render_poll_widget from "../templates/widgets/poll_widget.hbs";
import render_poll_widget_example from "../templates/widgets/poll_widget_example.hbs";
import render_poll_widget_results from "../templates/widgets/poll_widget_results.hbs";

import {component_story} from "./story_utils.ts";

type PollOption = {
    count: number;
    current_user_vote?: boolean;
    key: string;
    names?: string;
    option: string;
};

type PollWidgetArgs = {
    options: PollOption[];
    question: string;
};

function render_poll_widget_state(args: PollWidgetArgs): HTMLElement {
    const wrapper = globalThis.document.createElement("div");
    wrapper.innerHTML = component_story(render_poll_widget());

    const widget = wrapper.querySelector<HTMLElement>(".poll-widget");
    if (widget === null) {
        throw new Error("Poll widget template did not render its root element.");
    }

    const question = widget.querySelector<HTMLElement>(".poll-question-header");
    const results = widget.querySelector<HTMLElement>("ul.poll-widget");
    if (question === null || results === null) {
        throw new Error("Poll widget template did not render its required regions.");
    }

    question.textContent = args.question;
    results.innerHTML = render_poll_widget_results({options: args.options});
    return wrapper;
}

const meta = {
    title: "Widgets/Poll",
    tags: ["autodocs"],
    args: {
        question: "Where should the next team offsite be?",
        options: [
            {count: 12, key: "lisbon", names: "Ava, Sam, and 10 others", option: "Lisbon"},
            {
                count: 9,
                current_user_vote: true,
                key: "tokyo",
                names: "You and 8 others",
                option: "Tokyo",
            },
            {count: 4, key: "remote", option: "Remote"},
        ],
    },
    render: render_poll_widget_state,
} satisfies Meta<PollWidgetArgs>;

export default meta;
type Story = StoryObj<PollWidgetArgs>;

export const Results: Story = {};

export const NewPoll: Story = {
    render: () => component_story(render_poll_widget_example()),
};
