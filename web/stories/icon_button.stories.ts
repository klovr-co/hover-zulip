import type {Meta, StoryObj} from "@storybook/html";

import render_icon_button from "../templates/components/icon_button.hbs";

import {component_story} from "./story_utils.ts";

type IconButtonArgs = {
    disabled: boolean;
    icon: string;
    intent: "neutral" | "brand" | "info" | "success" | "warning" | "danger";
    squared: boolean;
};

const meta = {
    title: "Components/Icon button",
    tags: ["autodocs"],
    args: {
        disabled: false,
        icon: "close",
        intent: "neutral",
        squared: false,
    },
    render: (args) => component_story(render_icon_button(args)),
} satisfies Meta<IconButtonArgs>;

export default meta;
type Story = StoryObj<IconButtonArgs>;

export const Playground: Story = {};

export const Square: Story = {
    args: {squared: true},
};

export const Disabled: Story = {
    args: {disabled: true},
};
