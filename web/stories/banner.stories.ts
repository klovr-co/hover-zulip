import type {Meta, StoryObj} from "@storybook/html";

import render_banner from "../templates/components/banner.hbs";

import {component_story} from "./story_utils.ts";

type BannerButton = {
    label: string;
    variant: "primary" | "secondary" | "ghost" | "danger" | "success";
};

type BannerArgs = {
    buttons: BannerButton[];
    close_button: boolean;
    custom_classes?: string;
    intent: "neutral" | "brand" | "info" | "success" | "warning" | "danger";
    label: string;
    process?: string;
};

const meta = {
    title: "Cofounder/Components/Banner",
    tags: ["autodocs"],
    args: {
        buttons: [{label: "Review", variant: "secondary"}],
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

export const Navbar: Story = {
    args: {
        custom_classes: "navbar-alert-banner",
        label: "Your organization has a new policy update.",
        process: "organization-policy-update",
    },
};

export const Popup: Story = {
    args: {
        custom_classes: "popup-banner",
        intent: "success",
        label: "Your changes were saved.",
    },
};
