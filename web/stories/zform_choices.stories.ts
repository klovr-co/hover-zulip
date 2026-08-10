import type {Meta, StoryObj} from "@storybook/html";

import render_zform_choices from "../templates/widgets/zform_choices.hbs";

import {component_story} from "./story_utils.ts";

type ZFormChoice = {
    idx: number;
    long_name: string;
    short_name: string;
};

type ZFormChoicesArgs = {
    choices: ZFormChoice[];
    heading: string;
};

const meta = {
    title: "Widgets/Interactive form choices",
    tags: ["autodocs"],
    args: {
        heading: "Choose a response",
        choices: [
            {idx: 0, long_name: "Continue with the default settings", short_name: "Continue"},
            {idx: 1, long_name: "Open the settings panel first", short_name: "Configure"},
        ],
    },
    render: (args) => component_story(render_zform_choices(args)),
} satisfies Meta<ZFormChoicesArgs>;

export default meta;
type Story = StoryObj<ZFormChoicesArgs>;

export const Playground: Story = {};
