import type {Meta, StoryObj} from "@storybook/html";

import render_membership_banner from "../templates/components/membership_banner.hbs";

import {component_story} from "./story_utils.ts";

type MembershipBannerArgs = {
    error_message: string;
    intent: "success" | "danger";
};

const meta = {
    title: "Components/Membership banner",
    tags: ["autodocs"],
    args: {
        error_message: "Added three people to the Design team.",
        intent: "success",
    },
    render: (args) => component_story(render_membership_banner(args), true),
} satisfies Meta<MembershipBannerArgs>;

export default meta;
type Story = StoryObj<MembershipBannerArgs>;

export const Success: Story = {};

export const Error: Story = {
    args: {
        error_message: "Some members could not be added. Check their access and try again.",
        intent: "danger",
    },
};
