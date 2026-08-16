import type {Meta, StoryObj} from "@storybook/html";

import render_notice_example from "./templates/cofounder_notice_example.hbs";

type NoticeArgs = Record<string, never>;

const meta = {
    title: "Cofounder/Components/Notice",
    parameters: {layout: "padded"},
    render() {
        const host = globalThis.document.createElement("section");
        host.className = "cf-theme storybook-notice-story";
        host.innerHTML = render_notice_example();

        const feedback = globalThis.document.createElement("p");
        feedback.className = "storybook-notice-story__feedback";
        feedback.setAttribute("role", "status");
        feedback.setAttribute("aria-live", "polite");
        host.append(feedback);

        host.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }

            const close = event.target.closest<HTMLButtonElement>(".cf-notice__close");
            if (close) {
                const notice = close.closest<HTMLElement>(".cf-notice");
                if (notice) {
                    notice.hidden = true;
                    feedback.textContent = "Review notice dismissed.";
                    host.querySelector<HTMLButtonElement>(
                        ":scope .cf-notice:not([hidden]) .cf-notice__action",
                    )?.focus();
                }
                return;
            }

            const action = event.target.closest<HTMLButtonElement>(".cf-notice__action");
            if (!action) {
                return;
            }
            const notice = action.closest<HTMLElement>(".cf-notice");
            const content = notice?.querySelector<HTMLElement>(".cf-notice__content");
            if (notice?.id === "cofounder-notice-review") {
                if (content) {
                    content.textContent = "Source review opened.";
                }
                feedback.textContent = "Source review opened.";
                return;
            }
            if (content) {
                content.textContent = "The source was published.";
            }
            action.textContent = "Published";
            action.disabled = true;
            feedback.textContent = "Source published.";
        });

        return host;
    },
} satisfies Meta<NoticeArgs>;

export default meta;
type Story = StoryObj<NoticeArgs>;

export const Default: Story = {};
