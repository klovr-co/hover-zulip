import type {Meta, StoryObj} from "@storybook/html";

import render_toast from "../templates/cofounder/components/toast.hbs";

import {component_story} from "./story_utils.ts";

type ToastArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Toast",
    parameters: {layout: "padded"},
} satisfies Meta<ToastArgs>;

export default meta;
type Story = StoryObj<ToastArgs>;

export const AllIntents: Story = {
    render: () =>
        component_story(
            [
                render_toast({
                    intent: "neutral",
                    message: "The message was moved to Product updates.",
                    title: "Message moved",
                    has_undo_button: true,
                    undo_button_text: "Undo",
                }),
                render_toast({
                    intent: "info",
                    message: "Your export is being prepared.",
                    title: "Export started",
                }),
                render_toast({
                    intent: "success",
                    message: "The workspace settings are up to date.",
                    title: "Changes saved",
                }),
                render_toast({
                    intent: "warning",
                    message: "Reconnect soon to keep receiving updates.",
                    title: "Connection is unstable",
                }),
                render_toast({
                    intent: "danger",
                    message: "We could not schedule the reminder. Try again.",
                    title: "Something went wrong",
                }),
            ].join(""),
            true,
        ),
};
