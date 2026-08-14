import type {Meta, StoryObj} from "@storybook/html";

import render_dialog from "../templates/dialog_widget.hbs";
import render_source_results from "../templates/hover_source_discovery_results.hbs";
import render_space_setup from "../templates/hover_space_setup_modal.hbs";
import render_copy_email from "../templates/stream_settings/copy_email_address_modal.hbs";
import render_edit_folder from "../templates/stream_settings/edit_channel_folder_modal.hbs";

function render_open_dialog(args: {
    content: string;
    id: string;
    submitLabel: string;
    title: string;
}): string {
    return render_dialog({
        close_on_overlay_click: true,
        id: args.id,
        modal_content_html: args.content,
        modal_exit_button_text: "Close",
        modal_submit_button_text: args.submitLabel,
        modal_submit_button_variant: "primary",
        modal_title_text: args.title,
        modal_unique_id: `${args.id}-story`,
    })
        .replace(
            "micromodal cf-theme cf-dialog-root",
            "micromodal cf-theme cf-dialog-root modal--open",
        )
        .replace('aria-hidden="true"', 'aria-hidden="false"');
}

const meta = {
    title: "Cofounder/Settings/Dialogs",
    parameters: {layout: "fullscreen"},
} satisfies Meta;

export default meta;
type Story = StoryObj;

export const ChannelEmailAddress: Story = {
    render: () =>
        render_open_dialog({
            content: render_copy_email({
                email_address: "design.4e2f7c@example.hover.app",
                tags: [
                    {description: "The sender's email address", name: "show-sender"},
                    {
                        description: "Email footers (for example, signatures)",
                        name: "include-footer",
                    },
                    {description: "Quoted original email in replies", name: "include-quotes"},
                    {description: "Use HTML encoding", name: "prefer-html"},
                ],
            }),
            id: "copy_email_address_modal",
            submitLabel: "Generate email address",
            title: "Generate channel email address",
        }),
};

export const ManageChannelFolder: Story = {
    render: () =>
        render_open_dialog({
            content: render_edit_folder({
                can_manage_folder: true,
                description: "Planning and delivery channels for the product team.",
                folder_id: 4,
                max_channel_folder_description_length: 200,
                max_channel_folder_name_length: 60,
                name: "Product",
            }),
            id: "edit_channel_folder",
            submitLabel: "Save changes",
            title: "Manage channel folder",
        }),
};

export const SpaceSetup: Story = {
    render() {
        const source = {
            account_display_name: "Community operations",
            display_name: "Mentors & Volunteers",
            icon_name: "phone",
            provider_key: "whatsapp",
            source_ref: "wa-community-planning",
            source_type: "group",
        };
        const attachment = {icon_name: source.icon_name, id: 41, source};
        const results = render_source_results({
            has_more: true,
            has_sources: true,
            sources: [
                source,
                {
                    account_display_name: "Product organization",
                    display_name: "Research repository",
                    icon_name: "link-alt",
                    provider_key: "workspace",
                    source_ref: "workspace-research",
                    source_type: "workspace",
                },
            ],
        });
        const content = render_space_setup({
            accounts: [{display_name: "Community operations", id: 3, provider_name: "WhatsApp"}],
            eligible_users: [{full_name: "Amina Niyonkuru", user_id: 14}],
            has_accounts: true,
            has_attachments: true,
            has_eligible_users: true,
            has_module_catalog: true,
            has_module_installations: true,
            launch_ready: false,
            launch_requirements: [
                {icon_name: "check", label: "At least one active Source", met: true},
                {icon_name: "check", label: "At least one confirmed teammate", met: true},
                {
                    icon_name: "warning",
                    label: "No pending teammate suggestions",
                    met: false,
                },
                {icon_name: "check", label: "No paused Module bindings", met: true},
            ],
            module_catalog: [
                {
                    attachments: [attachment],
                    description:
                        "Creates a concise daily view of decisions, follow-ups, and unanswered questions.",
                    destination_topic: "Daily brief",
                    icon_name: "file-text",
                    id: 22,
                    is_installed: false,
                    name: "Conversation Digest",
                    supports_manual: true,
                    supports_new_source: true,
                    supports_schedule: true,
                    version: "1.4",
                },
            ],
            space: {
                attachments: [attachment],
                category: {name: "Community"},
                description: "Coordinate the people and evidence needed for the next launch.",
                membership_suggestions: [
                    {full_name: "Maya Chen", suggested_role: "subscriber", user_id: 10},
                ],
                memberships: [
                    {
                        full_name: "Ava Rodriguez",
                        is_administrator: true,
                        role: "contributor",
                        user_id: 7,
                    },
                    {
                        full_name: "Jordan Lee",
                        is_administrator: false,
                        role: "subscriber",
                        user_id: 8,
                    },
                ],
                module_installations: [
                    {id: 19, name: "Suggested Actions", state: "enabled", version: "2.1"},
                ],
                name: "Community launch",
            },
        })
            .replace(
                '<div id="cf-source-discovery-results"></div>',
                () => `<div id="cf-source-discovery-results">${results}</div>`,
            )
            .replace(
                /<div\s+id="cf-source-preview"\s+class="cf-space-workbench__source-preview hide"\s+aria-live="polite"\s*><\/div>/,
                '<div id="cf-source-preview" class="cf-space-workbench__source-preview" aria-live="polite"><span class="cf-space-workbench__preview-label">Verified preview</span><strong>Mentors &amp; Volunteers</strong><small>Community operations · WhatsApp · group</small></div>',
            );

        return render_open_dialog({
            content,
            id: "cf-space-setup-dialog",
            submitLabel: "Attach Source",
            title: "Space Setup",
        });
    },
};
