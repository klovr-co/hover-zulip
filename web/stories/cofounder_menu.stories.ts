import type {Meta, StoryObj} from "@storybook/html";
import {$} from "jquery";

import {
    focus_first_menu_item,
    get_menu_items,
    menu_items_handle_keyboard,
} from "../src/cofounder/components/menu.ts";

import render_menu_example from "./templates/cofounder_menu_example.hbs";

type MenuArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Menu",
    parameters: {layout: "padded"},
    render() {
        const wrapper = globalThis.document.createElement("div");
        wrapper.innerHTML = render_menu_example();
        const host = wrapper.firstElementChild;
        if (!(host instanceof HTMLElement)) {
            throw new TypeError("The Cofounder menu story must render an element");
        }
        const $items = get_menu_items($(host));
        host.addEventListener("keydown", (event) => {
            const key = {
                ArrowDown: "down_arrow",
                ArrowUp: "up_arrow",
                Enter: "enter",
                j: "vim_down",
                k: "vim_up",
            }[event.key];
            if (key === undefined) {
                return;
            }
            event.preventDefault();
            menu_items_handle_keyboard(key, $items);
        });
        globalThis.requestAnimationFrame(() => {
            focus_first_menu_item($items);
        });
        return host;
    },
} satisfies Meta<MenuArgs>;

export default meta;
type Story = StoryObj<MenuArgs>;

export const Default: Story = {};
