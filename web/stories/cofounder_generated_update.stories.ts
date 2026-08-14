import type {Meta, StoryObj} from "@storybook/html";

import render_details from "../templates/hover_generated_details_modal.hbs";

type GeneratedUpdateArgs = {
    history: boolean;
    narrow: boolean;
};

const history = [
    {
        display_time: "August 13, 2026 at 10:38 AM",
        is_current: true,
        state: "active",
        title: "Approved venue plan",
        url: "#current",
    },
    {
        display_time: "August 12, 2026 at 4:18 PM",
        is_current: false,
        state: "superseded",
        title: "Venue plan awaiting access confirmation",
        url: "#earlier",
    },
];

function render_generated_update(args: GeneratedUpdateArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = `cf-theme storybook-component${args.narrow ? " cf-generated-details-story--narrow" : ""}`;
    canvas.innerHTML = render_details({
        history,
        module: {name: "Operations brief", version: "v6"},
        presentation: {
            display_generated_at: "August 13, 2026 at 10:37 AM",
            display_occurred_at: "August 13, 2026 at 10:32 AM",
            display_published_at: "August 13, 2026 at 10:38 AM",
            importance: "high",
            label: "Venue plan",
            run_reference: "run-42-a9f3",
            state: "active",
            state_tone: "success",
        },
        show_history: args.history,
    });
    return canvas;
}

const meta = {
    title: "Cofounder/Workflow/Generated updates",
    args: {history: false, narrow: false},
    render: render_generated_update,
} satisfies Meta<GeneratedUpdateArgs>;

export default meta;
type Story = StoryObj<GeneratedUpdateArgs>;

export const Details: Story = {};
export const History: Story = {args: {history: true}};
export const NarrowTouch: Story = {args: {history: true, narrow: true}};
