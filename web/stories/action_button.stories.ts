import type {Meta, StoryObj} from "@storybook/html";

import render_action_button from "../templates/components/action_button.hbs";

import {component_story} from "./story_utils.ts";

type ActionButtonArgs = {
    disabled: boolean;
    icon?: string;
    intent: "neutral" | "brand" | "info" | "success" | "warning" | "danger";
    label: string;
    variant: "solid" | "subtle" | "text";
};

const meta = {
    title: "Components/Action button",
    tags: ["autodocs"],
    args: {
        disabled: false,
        icon: "plus",
        intent: "brand",
        label: "Create space",
        variant: "solid",
    },
    argTypes: {
        icon: {control: "text"},
    },
    render: (args) => component_story(render_action_button(args)),
} satisfies Meta<ActionButtonArgs>;

export default meta;
type Story = StoryObj<ActionButtonArgs>;

export const Playground: Story = {};

export const Variants: Story = {
    render: (args) =>
        component_story(
            (["solid", "subtle", "text"] as const)
                .map((variant) => render_action_button({...args, variant}))
                .join(""),
        ),
};

export const Disabled: Story = {
    args: {disabled: true},
};
