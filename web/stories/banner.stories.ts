import type {Meta, StoryObj} from "@storybook/html";

import render_banner from "../templates/components/banner.hbs";

import {component_story} from "./story_utils.ts";

type BannerButton = {
    intent?: BannerArgs["intent"];
    label: string;
    variant: "solid" | "subtle" | "text";
};

type BannerArgs = {
    buttons: BannerButton[];
    close_button: boolean;
    intent: "neutral" | "brand" | "info" | "success" | "warning" | "danger";
    label: string;
};

const meta = {
    title: "Components/Banner",
    tags: ["autodocs"],
    args: {
        buttons: [{label: "Review", variant: "subtle"}],
        close_button: true,
        intent: "info",
        label: "A new activity summary is ready to review.",
    },
    render: (args) => component_story(render_banner(args), true),
} satisfies Meta<BannerArgs>;

export default meta;
type Story = StoryObj<BannerArgs>;

export const Playground: Story = {};

export const AllIntents: Story = {
    render: (args) =>
        component_story(
            (["neutral", "brand", "info", "success", "warning", "danger"] as const)
                .map((intent) => render_banner({...args, intent}))
                .join(""),
            true,
        ),
};
