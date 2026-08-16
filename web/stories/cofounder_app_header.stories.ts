import type {Meta, StoryObj} from "@storybook/html";

import render_navbar from "../templates/navbar.hbs";

type AppHeaderArgs = {
    active_menu: "none" | "help" | "settings" | "personal";
    search_expanded: boolean;
};

const avatar = `data:image/svg+xml,${encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="100%" height="100%" rx="40" fill="#7584b5"/><text x="50%" y="53%" dominant-baseline="middle" text-anchor="middle" fill="white" font-family="sans-serif" font-size="29" font-weight="600">MA</text></svg>',
)}`;

function render_app_header(args: AppHeaderArgs): HTMLElement {
    const canvas = globalThis.document.createElement("div");
    canvas.className = "cf-theme storybook-app-header";
    canvas.innerHTML = render_navbar({
        embedded: false,
        realm_logo_url: avatar,
        user_avatar: avatar,
    });

    if (args.search_expanded) {
        canvas
            .querySelector<HTMLElement>(".cf-app-header__search")
            ?.classList.add("cf-app-header__search--expanded");
        canvas
            .querySelector<HTMLElement>(".cf-app-header__search-input")
            ?.setAttribute("contenteditable", "true");
    }

    if (args.active_menu !== "none") {
        const id =
            args.active_menu === "settings"
                ? "gear-menu"
                : args.active_menu === "personal"
                  ? "personal-menu"
                  : "help-menu";
        canvas.querySelector<HTMLElement>(`#${id}`)?.classList.add("cf-app-header__item--active");
    }

    return canvas;
}

const meta = {
    title: "Cofounder/Application Header",
    parameters: {layout: "fullscreen"},
    args: {active_menu: "none", search_expanded: false},
    render: render_app_header,
} satisfies Meta<AppHeaderArgs>;

export default meta;
type Story = StoryObj<AppHeaderArgs>;

export const Default: Story = {};

export const SearchExpanded: Story = {
    args: {search_expanded: true},
};

export const PersonalMenuActive: Story = {
    args: {active_menu: "personal"},
};
