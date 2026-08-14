import type {Meta, StoryObj} from "@storybook/html";

import render_menu_example from "./templates/cofounder_menu_example.hbs";

type MenuArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Menu",
    parameters: {layout: "padded"},
    render: () => render_menu_example(),
} satisfies Meta<MenuArgs>;

export default meta;
type Story = StoryObj<MenuArgs>;

export const Default: Story = {};
