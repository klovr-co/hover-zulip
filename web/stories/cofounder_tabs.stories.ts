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
    render() {
        const canvas = globalThis.document.createElement("div");
        canvas.innerHTML = component_story(
            render_tabs({
                aria_label: "Source views",
                custom_classes: "cf-tabs--fill",
                tabs: [
                    {id: 0, key: "overview", label: "Overview", selected: true},
                    {id: 1, key: "activity", label: "Activity"},
                    {id: 2, key: "permissions", label: "Permissions", disabled: true},
                ],
            }),
        );
        const tabs = [...canvas.querySelectorAll<HTMLButtonElement>(".cf-tabs__tab")];
        const select_tab = (tab: HTMLButtonElement): void => {
            if (tab.getAttribute("aria-disabled") === "true") {
                return;
            }
            for (const candidate of tabs) {
                const selected = candidate === tab;
                candidate.classList.toggle("cf-tabs__tab--selected", selected);
                candidate.setAttribute("aria-selected", String(selected));
                candidate.tabIndex = selected ? 0 : -1;
            }
            tab.focus();
        };

        for (const tab of tabs) {
            tab.addEventListener("click", () => {
                select_tab(tab);
            });
            tab.addEventListener("keydown", (event) => {
                if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
                    return;
                }
                const offset = event.key === "ArrowRight" ? 1 : -1;
                let index = tabs.indexOf(tab) + offset;
                while (index >= 0 && index < tabs.length) {
                    const candidate = tabs[index];
                    if (
                        candidate !== undefined &&
                        candidate.getAttribute("aria-disabled") !== "true"
                    ) {
                        event.preventDefault();
                        select_tab(candidate);
                        return;
                    }
                    index += offset;
                }
            });
        }
        return canvas;
    },
};
