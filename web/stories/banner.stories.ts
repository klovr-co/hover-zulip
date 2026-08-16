import type {Meta, StoryObj} from "@storybook/html";

import render_banner from "../templates/components/banner.hbs";

import {component_story} from "./story_utils.ts";

type BannerButton = {
    label: string;
    variant: "primary" | "secondary" | "ghost" | "danger" | "success";
};

type BannerArgs = {
    buttons: BannerButton[];
    close_button: boolean;
    custom_classes?: string;
    intent: "neutral" | "brand" | "info" | "success" | "warning" | "danger";
    label: string;
    process?: string;
};

const meta = {
    title: "Cofounder/Components/Banner",
    tags: ["autodocs"],
    args: {
        buttons: [{label: "Review", variant: "secondary"}],
        close_button: true,
        intent: "info",
        label: "A new activity summary is ready to review.",
    },
    render: (args) => component_story(render_banner(args), true),
} satisfies Meta<BannerArgs>;

export default meta;
type Story = StoryObj<BannerArgs>;

function render_banner_playground(args: BannerArgs): HTMLElement {
    const host = globalThis.document.createElement("div");
    host.className = "storybook-banner-playground";
    host.innerHTML = component_story(render_banner(args), true);

    const component = host.querySelector<HTMLElement>(".storybook-component");
    const banner = host.querySelector<HTMLElement>(".cf-banner");
    if (component === null || banner === null) {
        return host;
    }

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-banner-playground__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");

    const restore = globalThis.document.createElement("button");
    restore.type = "button";
    restore.className = "cf-button cf-button--secondary storybook-banner-playground__restore";
    restore.textContent = "Show banner";
    restore.hidden = true;
    component.append(feedback, restore);

    host.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        if (target.closest(".storybook-banner-playground__restore") !== null) {
            banner.hidden = false;
            restore.hidden = true;
            feedback.textContent = "Banner restored.";
            banner.querySelector<HTMLElement>(".cf-banner__close")?.focus();
            return;
        }

        if (target.closest(".cf-banner__close") !== null) {
            banner.hidden = true;
            restore.hidden = false;
            feedback.textContent = "Banner dismissed.";
            restore.focus();
            return;
        }

        const action = target.closest<HTMLElement>(".cf-banner__actions button");
        if (action !== null) {
            const label = action.textContent?.trim() ?? "Action";
            feedback.textContent = `${label} requested.`;
        }
    });

    return host;
}

export const Playground: Story = {
    render: render_banner_playground,
};

const banner_intents = ["neutral", "brand", "info", "success", "warning", "danger"] as const;
const supported_banner_intents: readonly string[] = banner_intents;

const banner_intent_messages: Record<BannerArgs["intent"], string> = {
    brand: "Cofounder has a new activity summary.",
    danger: "The activity summary could not be published.",
    info: "A new activity summary is ready to review.",
    neutral: "No changes are needed.",
    success: "The activity summary was published.",
    warning: "Review the activity summary before sharing it.",
};

function intent_label(intent: BannerArgs["intent"]): string {
    return intent.charAt(0).toUpperCase() + intent.slice(1);
}

function is_banner_intent(value: string | undefined): value is BannerArgs["intent"] {
    return value !== undefined && supported_banner_intents.includes(value);
}

function render_banner_intents(args: BannerArgs): HTMLElement {
    const specimens = banner_intents
        .map((intent) => {
            const heading_id = `storybook-banner-intent-${intent}`;
            return `<section class="storybook-banner-intent" data-banner-intent="${intent}" aria-labelledby="${heading_id}">
                <h2 class="storybook-banner-intent__heading" id="${heading_id}">${intent_label(intent)}</h2>
                ${render_banner({...args, intent, label: banner_intent_messages[intent]})}
            </section>`;
        })
        .join("");
    const host = globalThis.document.createElement("div");
    host.className = "storybook-banner-intents";
    host.innerHTML = component_story(specimens, true);

    const component = host.querySelector<HTMLElement>(".storybook-component");
    if (component === null) {
        return host;
    }

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-banner-intents__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");
    component.append(feedback);

    for (const section of host.querySelectorAll<HTMLElement>(".storybook-banner-intent")) {
        const intent = section.dataset["bannerIntent"];
        if (!is_banner_intent(intent)) {
            continue;
        }
        const restore = globalThis.document.createElement("button");
        restore.type = "button";
        restore.className = "cf-button cf-button--secondary storybook-banner-intent__restore";
        restore.textContent = `Show ${intent} banner`;
        restore.hidden = true;
        section.append(restore);
    }

    host.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const section = target.closest<HTMLElement>(".storybook-banner-intent");
        if (section === null) {
            return;
        }
        const banner = section.querySelector<HTMLElement>(".cf-banner");
        const restore = section.querySelector<HTMLElement>(".storybook-banner-intent__restore");
        const intent = section.dataset["bannerIntent"];
        if (banner === null || restore === null || !is_banner_intent(intent)) {
            return;
        }

        if (target.closest(".storybook-banner-intent__restore") !== null) {
            banner.hidden = false;
            restore.hidden = true;
            feedback.textContent = `${intent_label(intent)} banner restored.`;
            banner.querySelector<HTMLElement>(".cf-banner__close")?.focus();
            return;
        }

        if (target.closest(".cf-banner__close") !== null) {
            banner.hidden = true;
            restore.hidden = false;
            feedback.textContent = `${intent_label(intent)} banner dismissed.`;
            restore.focus();
            return;
        }

        const action = target.closest<HTMLElement>(".cf-banner__actions button");
        if (action !== null) {
            feedback.textContent = `${intent_label(intent)}: ${action.textContent?.trim() ?? "Action"} requested.`;
        }
    });

    return host;
}

export const AllIntents: Story = {
    render: render_banner_intents,
};

function render_navbar_banner(args: BannerArgs): HTMLElement {
    const host = globalThis.document.createElement("div");
    host.className = "storybook-navbar-banner";
    host.innerHTML = `<section class="storybook-navbar-banner__surface" aria-label="Workspace navigation banner example">
        <div class="storybook-navbar-banner__chrome" aria-hidden="true">
            <span class="storybook-navbar-banner__wordmark">Cofounder</span>
            <span class="storybook-navbar-banner__context">Workspace navigation</span>
        </div>
        <div class="banner-wrapper storybook-navbar-banner__boundary">${render_banner(args)}</div>
    </section>`;

    const banner = host.querySelector<HTMLElement>(".cf-banner");
    if (banner === null) {
        return host;
    }

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-navbar-banner__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");

    const restore = globalThis.document.createElement("button");
    restore.type = "button";
    restore.className = "cf-button cf-button--secondary storybook-navbar-banner__restore";
    restore.textContent = "Show navigation banner";
    restore.hidden = true;
    host.append(feedback, restore);

    host.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        if (target.closest(".storybook-navbar-banner__restore") !== null) {
            banner.hidden = false;
            restore.hidden = true;
            feedback.textContent = "Navigation banner restored.";
            banner.querySelector<HTMLElement>(".cf-banner__close")?.focus();
            return;
        }

        if (target.closest(".cf-banner__close") !== null) {
            banner.hidden = true;
            restore.hidden = false;
            feedback.textContent = "Navigation banner dismissed.";
            restore.focus();
            return;
        }

        const action = target.closest<HTMLElement>(".cf-banner__actions button");
        if (action !== null) {
            feedback.textContent = `${action.textContent?.trim() ?? "Action"} requested.`;
        }
    });

    return host;
}

export const Navbar: Story = {
    render: render_navbar_banner,
    args: {
        buttons: [{label: "Review policy", variant: "secondary"}],
        custom_classes: "navbar-alert-banner",
        label: "A workspace policy update is ready to review.",
        process: "organization-policy-update",
    },
};

function render_popup_banner(args: BannerArgs): HTMLElement {
    const host = globalThis.document.createElement("div");
    host.className = "storybook-popup-banner";
    host.innerHTML = `<section class="storybook-popup-banner__viewport" aria-label="Popup banner placement example">
        <div class="storybook-popup-banner__workspace" aria-hidden="true">
            <span>Application workspace</span>
        </div>
        <div class="cf-feedback-region storybook-popup-banner__region">
            <div class="cf-feedback-stack">${render_banner(args)}</div>
        </div>
    </section>`;

    const banner = host.querySelector<HTMLElement>(".cf-banner");
    if (banner === null) {
        return host;
    }

    const feedback = globalThis.document.createElement("p");
    feedback.className = "storybook-popup-banner__feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.setAttribute("aria-atomic", "true");

    const restore = globalThis.document.createElement("button");
    restore.type = "button";
    restore.className = "cf-button cf-button--secondary storybook-popup-banner__restore";
    restore.textContent = "Show popup banner";
    restore.hidden = true;
    host.append(feedback, restore);

    const finish_dismissal = (): void => {
        banner.hidden = true;
        banner.classList.remove("fade-out");
        restore.hidden = false;
        restore.focus();
    };

    host.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        if (target.closest(".storybook-popup-banner__restore") !== null) {
            banner.hidden = false;
            restore.hidden = true;
            feedback.textContent = "Popup banner restored.";
            banner.querySelector<HTMLElement>(".cf-banner__close")?.focus();
            return;
        }

        if (target.closest(".cf-banner__close") !== null) {
            feedback.textContent = "Popup banner dismissed.";
            banner.classList.add("fade-out");
            const duration = Number.parseFloat(
                globalThis.getComputedStyle(banner).animationDuration,
            );
            if (duration === 0) {
                finish_dismissal();
                return;
            }
            banner.addEventListener("animationend", finish_dismissal, {once: true});
        }
    });

    return host;
}

export const Popup: Story = {
    render: render_popup_banner,
    args: {
        buttons: [],
        custom_classes: "popup-banner",
        intent: "success",
        label: "Changes saved.",
        process: "changes-saved",
    },
};
