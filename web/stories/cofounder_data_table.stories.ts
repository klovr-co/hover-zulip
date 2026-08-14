import type {Meta, StoryObj} from "@storybook/html";

import render_icon from "../templates/cofounder/components/icon.hbs";
import render_active_users from "../templates/settings/active_user_list_admin.hbs";

function render_settings_table(): HTMLElement {
    const host = globalThis.document.createElement("div");
    host.className = "cf-theme";
    host.style.cssText =
        "box-sizing:border-box;width:min(960px,calc(100vw - 48px));margin:24px auto;";
    host.innerHTML = render_active_users({
        active_user_list_dropdown_widget_name: "active-user-filter",
        is_admin: true,
    });

    const dropdownValue = host.querySelector(".dropdown_widget_value");
    if (dropdownValue) {
        dropdownValue.textContent = "All members";
    }

    const rows = [
        ["Amina Yusuf", "amina@cofounder.test", "Owner", "Now"],
        ["Jon Bell", "jon@cofounder.test", "Administrator", "12 minutes ago"],
        ["Mei Lin", "mei@cofounder.test", "Member", "Yesterday"],
        ["Ravi Shah", "ravi@cofounder.test", "Guest", "4 days ago"],
    ];
    const body = host.querySelector("#admin_users_table");
    if (body) {
        body.innerHTML = rows
            .map(
                ([name, email, role, activity]) => `
                    <tr>
                        <td><strong>${name}</strong></td>
                        <td>${email}</td>
                        <td>${role}</td>
                        <td>${activity}</td>
                        <td>
                            <button type="button" class="cf-icon-button cf-icon-button--neutral" aria-label="Edit ${name}">
                                ${render_icon({compact: true, name: "edit"})}
                            </button>
                        </td>
                    </tr>`,
            )
            .join("");
    }

    return host;
}

const meta = {
    title: "Cofounder/Components/Data table",
    parameters: {layout: "fullscreen"},
    render: render_settings_table,
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const SettingsMembers: Story = {};
