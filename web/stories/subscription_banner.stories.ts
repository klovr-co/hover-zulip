import type {Meta, StoryObj} from "@storybook/html";

import render_subscription_banner from "../templates/components/subscription_banner.hbs";

import {component_story} from "./story_utils.ts";

type SubscriptionBannerArgs = {
    error_message: string;
    intent: "success" | "danger";
};

const meta = {
    title: "Components/Subscription banner",
    tags: ["autodocs"],
    args: {
        error_message: "Subscribed three people to #design.",
        intent: "success",
    },
    render: (args) => component_story(render_subscription_banner(args), true),
} satisfies Meta<SubscriptionBannerArgs>;

export default meta;
type Story = StoryObj<SubscriptionBannerArgs>;

export const Success: Story = {};

export const Error: Story = {
    args: {
        error_message:
            "Some people could not be subscribed. Check their permissions and try again.",
        intent: "danger",
    },
};
