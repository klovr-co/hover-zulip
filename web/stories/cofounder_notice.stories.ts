import type {Meta, StoryObj} from "@storybook/html";

import render_notice_example from "./templates/cofounder_notice_example.hbs";

type NoticeArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Notice",
    parameters: {layout: "padded"},
    render: () => render_notice_example(),
} satisfies Meta<NoticeArgs>;

export default meta;
type Story = StoryObj<NoticeArgs>;

export const Default: Story = {};
