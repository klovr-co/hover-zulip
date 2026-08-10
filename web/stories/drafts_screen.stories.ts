import type {Meta, StoryObj} from "@storybook/html";

import render_draft_table_body from "../templates/draft_table_body.hbs";

type DraftsArgs = {
    show_drafts: boolean;
};

const sample_draft = {
    content: "Outline the empty and loading states before the review.",
    draft_id: 17,
    is_empty_string_topic: false,
    is_stream: true,
    recipient_bar_color: "#4f8394",
    stream_id: 7,
    stream_name: "design",
    stream_privacy_icon_color: "#ffffff",
    time_stamp: "10:45 AM",
    topic_display_name: "Homepage redesign",
};

function render_drafts_screen(args: DraftsArgs): string {
    return render_draft_table_body({
        context: {
            narrow_drafts: [],
            narrow_drafts_header: undefined,
            other_drafts: args.show_drafts ? [sample_draft] : [],
        },
    });
}

const meta = {
    title: "Screens/Drafts",
    tags: ["autodocs"],
    args: {show_drafts: true},
    render: render_drafts_screen,
} satisfies Meta<DraftsArgs>;

export default meta;
type Story = StoryObj<DraftsArgs>;

export const WithDraft: Story = {};
export const Empty: Story = {args: {show_drafts: false}};
