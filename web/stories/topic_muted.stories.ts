import type {Meta, StoryObj} from "@storybook/html";

import render_topic_muted from "../templates/topic_muted.hbs";

import {component_story} from "./story_utils.ts";

type TopicMutedArgs = {
    stream: string;
    topic: string;
};

function render_topic_muted_notification(args: TopicMutedArgs): HTMLElement {
    const wrapper = globalThis.document.createElement("div");
    wrapper.innerHTML = component_story(render_topic_muted());

    const stream = wrapper.querySelector<HTMLElement>(".stream");
    const topic = wrapper.querySelector<HTMLElement>(".topic");
    if (stream !== null) {
        stream.textContent = args.stream;
    }
    if (topic !== null) {
        topic.textContent = args.topic;
    }
    return wrapper;
}

const meta = {
    title: "States/Muted topic",
    tags: ["autodocs"],
    args: {
        stream: "design",
        topic: "Homepage redesign",
    },
    render: render_topic_muted_notification,
} satisfies Meta<TopicMutedArgs>;

export default meta;
type Story = StoryObj<TopicMutedArgs>;

export const Default: Story = {};

export const ReleasePlanning: Story = {
    args: {
        stream: "engineering",
        topic: "Release planning",
    },
};
