import type {Meta, StoryObj} from "@storybook/html";

import render_demo_organization_add_email_modal from "../templates/demo_organization_add_email_modal.hbs";

type DemoOrganizationEmailArgs = {
    delivery_email: string;
    full_name: string;
};

function render_demo_organization_email(args: DemoOrganizationEmailArgs): string {
    return `<div class="storybook-component storybook-demo-email-modal">${render_demo_organization_add_email_modal(
        {
            ...args,
            email_address_visibility_values: {
                everybody: {code: "1", description: "Everyone"},
                members: {code: "2", description: "Members of this organization"},
            },
        },
    )}</div>`;
}

const meta = {
    title: "Forms/Demo organization delivery email",
    tags: ["autodocs"],
    args: {
        delivery_email: "ava@example.com",
        full_name: "Ava Rodriguez",
    },
    render: render_demo_organization_email,
} satisfies Meta<DemoOrganizationEmailArgs>;

export default meta;
type Story = StoryObj<DemoOrganizationEmailArgs>;

export const Default: Story = {};

export const TeamOnly: Story = {
    args: {
        delivery_email: "design@example.com",
        full_name: "Design team",
    },
};
