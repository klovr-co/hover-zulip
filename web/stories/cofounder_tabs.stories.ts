import type {Meta, StoryObj} from "@storybook/html";

import render_tabs from "../templates/cofounder/components/tabs.hbs";

import {component_story} from "./story_utils.ts";

type TabsArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Tabs",
    parameters: {layout: "padded"},
} satisfies Meta<TabsArgs>;

export default meta;
type Story = StoryObj<TabsArgs>;

export const States: Story = {
    render: () =>
        component_story(
            render_tabs({
                aria_label: "Source views",
                custom_classes: "cf-tabs--fill",
                tabs: [
                    {id: 0, key: "overview", label: "Overview", selected: true},
                    {id: 1, key: "activity", label: "Activity"},
                    {id: 2, key: "permissions", label: "Permissions", disabled: true},
                ],
            }),
        ),
};
