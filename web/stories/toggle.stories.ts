import type {Meta, StoryObj} from "@storybook/html";

import * as components from "../src/components.ts";

type ToggleArgs = {
    selected: number;
};

const values = [
    {key: "all", label: "All"},
    {key: "unread", label: "Unread"},
    {key: "mentioned", label: "Mentioned"},
];

function render_toggle(args: ToggleArgs): HTMLElement {
    const wrapper = globalThis.document.createElement("div");
    const toggle = components.toggle({selected: args.selected, values});
    wrapper.append(toggle.get().get(0)!);
    return wrapper;
}

const meta = {
    title: "Components/Toggle",
    tags: ["autodocs"],
    args: {
        selected: 0,
    },
    argTypes: {
        selected: {
            control: {min: 0, max: values.length - 1, step: 1, type: "range"},
        },
    },
    render: render_toggle,
} satisfies Meta<ToggleArgs>;

export default meta;
type Story = StoryObj<ToggleArgs>;

export const Playground: Story = {};

export const Mentioned: Story = {
    args: {selected: 2},
};
