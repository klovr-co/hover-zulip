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
    const body = host.querySelector<HTMLTableSectionElement>("#admin_users_table");
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

        const sortableHeaders = [...host.querySelectorAll<HTMLTableCellElement>("th[data-sort]")];
        const syncSortState = (activeHeader: HTMLTableCellElement): void => {
            for (const header of sortableHeaders) {
                header.classList.toggle("active", header === activeHeader);
                if (header !== activeHeader) {
                    header.classList.remove("descend");
                }
                header.setAttribute(
                    "aria-sort",
                    header === activeHeader
                        ? header.classList.contains("descend")
                            ? "descending"
                            : "ascending"
                        : "none",
                );
            }
        };
        const sortByHeader = (header: HTMLTableCellElement): void => {
            if (header.classList.contains("active")) {
                header.classList.toggle("descend");
            }
            syncSortState(header);
            const sortedRows = [...body.rows].toSorted((left, right) => {
                const leftValue = left.cells[header.cellIndex]?.textContent?.trim() ?? "";
                const rightValue = right.cells[header.cellIndex]?.textContent?.trim() ?? "";
                return leftValue.localeCompare(rightValue, undefined, {
                    numeric: true,
                    sensitivity: "base",
                });
            });
            if (header.classList.contains("descend")) {
                sortedRows.reverse();
            }
            body.append(...sortedRows);
        };
        for (const header of sortableHeaders) {
            header.tabIndex = 0;
            header.addEventListener("click", () => {
                sortByHeader(header);
            });
            header.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") {
                    return;
                }
                event.preventDefault();
                sortByHeader(header);
            });
        }
        const activeHeader = sortableHeaders.find((header) => header.classList.contains("active"));
        if (activeHeader) {
            syncSortState(activeHeader);
        }
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
