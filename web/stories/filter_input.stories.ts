import type {Meta, StoryObj} from "@storybook/html";

import render_filter_input from "../templates/components/showroom/filter_input.hbs";

import {component_story} from "./story_utils.ts";

const meta = {
    title: "Components/Filter input",
    tags: ["autodocs"],
    render: () => component_story(render_filter_input()),
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const Default: Story = {};
