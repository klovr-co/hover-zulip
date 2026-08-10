import type {Meta, StoryObj} from "@storybook/html";

import {component_story} from "./story_utils.ts";
import render_input_wrapper from "./templates/input_wrapper_example.hbs";

type InputWrapperArgs = {
    icon?: string;
    input_button_icon?: string;
    input_type?: string;
    placeholder: string;
    value: string;
};

const meta = {
    title: "Components/Input wrapper",
    tags: ["autodocs"],
    args: {
        icon: "search",
        input_button_icon: "close",
        input_type: "filter-input",
        placeholder: "Filter activity",
        value: "",
    },
    render: (args) => component_story(render_input_wrapper(args)),
} satisfies Meta<InputWrapperArgs>;

export default meta;
type Story = StoryObj<InputWrapperArgs>;

export const Playground: Story = {};

export const Filled: Story = {
    args: {value: "Research"},
};
