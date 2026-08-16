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
    render() {
        const canvas = globalThis.document.createElement("div");
        canvas.innerHTML = component_story(
            [
                render_toast({
                    intent: "neutral",
                    message: "The message was moved to Product updates.",
                    title: "Message moved",
                    has_undo_button: true,
                    undo_button_text: "Undo",
                }),
                render_toast({
                    intent: "brand",
                    message: "A new Cofounder review is ready.",
                    title: "Review ready",
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
        );

        for (const toast of canvas.querySelectorAll<HTMLElement>(".cf-toast")) {
            const title = toast.querySelector<HTMLElement>(".cf-toast__title");
            const close = toast.querySelector<HTMLButtonElement>(".cf-toast__close");
            if (title !== null && close !== null) {
                close.setAttribute(
                    "aria-label",
                    `Dismiss ${title.textContent?.trim() ?? "notification"} notification`,
                );
            }
        }

        canvas.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }
            const trigger = event.target.closest<HTMLButtonElement>(
                ".cf-toast__close, .cf-toast__undo",
            );
            const toast = trigger?.closest<HTMLElement>(".cf-toast");
            if (
                trigger === null ||
                trigger === undefined ||
                toast === null ||
                toast === undefined
            ) {
                return;
            }
            const controls = [...canvas.querySelectorAll<HTMLButtonElement>("button")];
            const trigger_index = controls.indexOf(trigger);
            const next_control = [
                ...controls.slice(trigger_index + 1),
                ...controls.slice(0, trigger_index).toReversed(),
            ].find((control) => !toast.contains(control));
            const move_focus = globalThis.document.activeElement === trigger;
            toast.addEventListener(
                "animationend",
                () => {
                    toast.remove();
                    if (move_focus) {
                        next_control?.focus();
                    }
                },
                {once: true},
            );
            toast.classList.add("cf-toast--leaving");
        });
        return canvas;
    },
};
