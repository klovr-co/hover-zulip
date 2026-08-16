type Template = (
    context: Record<string, unknown>,
    options?: {data?: Record<string, unknown>},
) => string;

const sample_stream = {
    color: "#2297df",
    invite_only: false,
    is_archived: false,
    is_web_public: false,
    name: "design",
    stream_id: 7,
};

const channel_group_setting_labels = {
    can_add_subscribers_group: "Who can add subscribers",
    can_administer_channel_group: "Who can administer this channel",
    can_create_topic_group: "Who can start topics",
    can_delete_any_message_group: "Who can delete any message",
    can_delete_own_message_group: "Who can delete their own messages",
    can_move_messages_out_of_channel_group: "Who can move messages out of this channel",
    can_move_messages_within_channel_group: "Who can move messages within this channel",
    can_remove_subscribers_group: "Who can remove subscribers",
    can_resolve_topics_group: "Who can resolve topics",
    can_send_message_group: "Who can send messages",
    can_subscribe_group: "Who can subscribe to this channel",
};

const user_group_setting_labels = {
    can_add_members_group: "Who can add members",
    can_join_group: "Who can join this group",
    can_leave_group: "Who can leave this group",
    can_manage_group: "Who can manage this group",
    can_mention_group: "Who can mention this group",
    can_remove_members_group: "Who can remove members",
};

const organization_group_setting_labels = {
    can_access_all_users_group: "Who can access all users",
    can_add_custom_emoji_group: "Who can add custom emoji",
    can_add_subscribers_group: "Who can add subscribers",
    can_create_bots_group: "Who can create bots",
    can_create_groups: "Who can create groups",
    can_create_private_channel_group: "Who can create private channels",
    can_create_public_channel_group: "Who can create public channels",
    can_create_spaces_group: "Who can create spaces",
    can_create_web_public_channel_group: "Who can create web-public channels",
    can_create_write_only_bots_group: "Who can create incoming webhooks",
    can_delete_any_message_group: "Who can delete any message",
    can_delete_own_message_group: "Who can delete their own messages",
    can_invite_users_group: "Who can invite users",
    can_manage_all_groups: "Who can manage all groups",
    can_manage_billing_group: "Who can manage billing",
    can_mention_many_users_group: "Who can use wildcard mentions",
    can_move_messages_between_channels_group: "Who can move messages between channels",
    can_move_messages_between_topics_group: "Who can move messages between topics",
    can_resolve_topics_group: "Who can resolve topics",
    can_set_delete_message_policy_group: "Who can set message deletion policy",
    can_set_topics_policy_group: "Who can configure topic policy",
    can_summarize_topics_group: "Who can summarize topics",
    create_multiuse_invite_group: "Who can create reusable invitations",
    direct_message_initiator_group: "Who can initiate direct messages",
    direct_message_permission_group: "Who can send direct messages",
    workplace_users_group: "Members included in this workplace",
};

const sample_message = {
    content: "The updated component library is ready for review.",
    display_recipient: "design",
    failed_request: false,
    id: 42,
    is_stream: true,
    locally_echoed: false,
    match_content: "The updated component library is ready for review.",
    message_reactions: [],
    reminders: [],
    sender_email: "ava@example.com",
    sender_full_name: "Ava Rodriguez",
    sender_id: 7,
    show_slow_send_spinner: false,
    status_emoji_info: undefined,
    unread: true,
    url: "#narrow/channel/7-design/topic/Homepage-redesign/near/42",
};

const settings_labels = {
    automatically_follow_topics_policy: "Automatically follow topics",
    default_language_settings_label: "Language",
    email_address_visibility: "Who can see my email address",
    enter_sends: "Enter sends a message",
    fluid_layout_width: "Use the full browser width",
    hide_ai_features: "Hide AI features",
    high_contrast_mode: "Use high contrast mode",
    receives_typing_notifications: "Show typing notifications",
    send_private_typing_notifications: "Send typing notifications in direct messages",
    translate_emoticons: "Convert emoticons to emoji",
    twenty_four_hour_time: "Time format",
    web_escape_navigates_to_home_view: "Escape key navigates to the home view",
    web_inbox_show_channel_folders: "Show channel folders in Inbox",
    web_left_sidebar_unreads_count_summary: "Show unread count summaries",
};

const settings_object = {
    automatically_follow_topics_policy: 1,
    color_scheme: 1,
    default_language: "en",
    email_address_visibility: 1,
    enter_sends: true,
    fluid_layout_width: false,
    hide_ai_features: false,
    high_contrast_mode: false,
    receives_typing_notifications: true,
    send_private_typing_notifications: true,
    translate_emoticons: true,
    twenty_four_hour_time: false,
    web_animate_image_previews: "always",
    web_escape_navigates_to_home_view: true,
    web_font_size_px: 15,
    web_inbox_show_channel_folders: true,
    web_left_sidebar_unreads_count_summary: true,
    web_line_height_percent: 120,
};

const sample_message_context = {
    has_hover_disputed_details: false,
    has_hover_revisions: false,
    has_hover_source_integrations: false,
    hover_response_clarification_required: false,
    is_hidden: false,
    is_hover_generated_update: false,
    is_hover_response: false,
    is_hover_review: false,
    is_hover_review_request: false,
    is_hover_suggested_action: false,
    include_sender: true,
    is_archived: false,
    is_stream: true,
    message_id: sample_message.id,
    message_list_id: "main",
    msg: sample_message,
    sender_is_bot: false,
    should_add_guest_indicator_for_sender: false,
    small_avatar_url: "/static/images/logo/zulip-icon-circle.svg",
    status_message: "",
    timestr: "10:42 AM",
};

const sample_recipient_row = {
    all_visibility_policies: {
        FOLLOWED: "FOLLOWED",
        INHERIT: "INHERIT",
        MUTED: "MUTED",
        UNMUTED: "UNMUTED",
    },
    date_html: "Today",
    display_recipient: sample_stream.name,
    is_archived: false,
    is_empty_string_topic: false,
    is_stream: true,
    recipient_bar_color: "#dceef7",
    stream_id: sample_stream.stream_id,
    stream_name: sample_stream.name,
    stream_privacy_icon_color: "#1f2933",
    stream_url: "#narrow/channel/7-design",
    topic: "Homepage redesign",
    topic_display_name: "Homepage redesign",
    topic_links: [],
    topic_url: "#narrow/channel/7-design/topic/Homepage-redesign",
    visibility_policy: "INHERIT",
};

function family_fixture(template_path: string): Record<string, unknown> {
    const common_fixture: Record<string, unknown> = {
        class: "",
        display_value: "Members",
        full_name: "Ava Rodriguez",
        group: {description: "Product design team", id: 3, name: "Design"},
        is_archived: false,
        is_stream: true,
        message_id: sample_message.id,
        message_list_id: "main",
        msg: sample_message,
        pm_with_url: false,
        prefix: "user_",
        realm: {},
        search_val: "",
        stream: sample_stream,
        sub: sample_stream,
        timezone: "Asia/Kuala_Lumpur",
    };

    if (template_path.startsWith("settings/") || template_path === "settings_tab.hbs") {
        return {
            ...common_fixture,
            automatically_follow_topics_policy: settings_object.automatically_follow_topics_policy,
            color_scheme_values: {
                automatic: {code: 0, description: "Automatic"},
                dark: {code: 2, description: "Dark"},
                light: {code: 1, description: "Light"},
            },
            default_language_settings_label: settings_labels.default_language_settings_label,
            admin_settings_label: settings_labels,
            attachment: {
                create_time_str: "Today",
                id: 17,
                message_ids: [42],
                name: "design-review.pdf",
                path_id: "design-review.pdf",
                size_str: "1.2 MB",
            },
            current_user: {email: "ava@example.com", full_name: "Ava Rodriguez", user_id: 7},
            custom_stream_specific_notification_settings: [],
            disabled_notification_settings: {},
            enter_sends: settings_object.enter_sends,
            for_realm_settings: false,
            general_settings: [],
            group_setting_labels: organization_group_setting_labels,
            is_admin: true,
            notification_settings: {
                desktop_notification_settings: [],
                email_notification_settings: [],
                mobile_notification_settings: [],
            },
            page_params: {two_fa_enabled: true, two_fa_enabled_user: false},
            realm_enable_read_receipts: true,
            realm_invite_required: false,
            realm_want_advertise_in_communities_directory: false,
            send_private_typing_notifications: settings_object.send_private_typing_notifications,
            settings_label: settings_labels,
            settings_object,
            settings_render_only: {},
            translate_emoticons: settings_object.translate_emoticons,
            twenty_four_hour_time: settings_object.twenty_four_hour_time,
            twenty_four_hour_time_values: {
                twelve_hour: {description: "12-hour clock", value: false},
                twenty_four_hour: {description: "24-hour clock", value: true},
            },
            web_escape_navigates_to_home_view: settings_object.web_escape_navigates_to_home_view,
            web_left_sidebar_unreads_count_summary:
                settings_object.web_left_sidebar_unreads_count_summary,
            workplace_users_group: {description: "Everyone in this organization", id: 1},
        };
    }

    if (template_path.startsWith("stream_settings/")) {
        return {
            ...common_fixture,
            channel_folder_widget_name: "channel_folder",
            check_default_stream: false,
            empty_string_topic_display_name: "(no topic)",
            group_setting_labels: channel_group_setting_labels,
            is_admin: true,
            is_owner: true,
            is_stream_edit: true,
            stream_topics_policy_values: {
                all: {code: "allow_empty_topic", description: "Topics are optional"},
                required: {code: "require_topics", description: "Topics are required"},
            },
        };
    }

    if (template_path.startsWith("user_group_settings/")) {
        return {
            ...common_fixture,
            all_group_setting_labels: {group: user_group_setting_labels},
            can_manage_group: {direct_members: [], direct_subgroups: []},
            date_created_string: "August 12, 2026",
            group_assigned_realm_permissions: [],
            group_assigned_stream_permissions: [],
            group_assigned_user_group_permissions: [],
            group_has_no_permissions: true,
            group_has_no_realm_permissions: true,
            group_setting_labels: user_group_setting_labels,
            max_user_group_name_length: 100,
        };
    }

    if (
        template_path.includes("message") ||
        template_path === "cofounder_generated_update_visual_fixture.hbs"
    ) {
        return {
            ...common_fixture,
            ...sample_message_context,
        };
    }

    return common_fixture;
}

const dedicated_fixtures: Record<string, Record<string, unknown>> = {
    "popovers/user_card/user_card_popover.hbs": {
        pm_with_url: "#narrow/dm/7",
    },
    "invite_user_modal.hbs": {
        default_welcome_message_custom_text: "Welcome! We’re glad you’re here.",
        development_environment: false,
        expires_in_options: [
            {default: true, description: "10 days", value: 10},
            {default: false, description: "30 days", value: 30},
        ],
        invite_as_options: {
            admin: {code: 200, description: "Administrator"},
            guest: {code: 600, description: "Guest"},
            member: {code: 400, description: "Member"},
            moderator: {code: 300, description: "Moderator"},
            owner: {code: 100, description: "Owner"},
        },
        time_choices: [
            {default: true, description: "10 days", value: 10},
            {default: false, description: "30 days", value: 30},
        ],
        user_has_email_set: true,
    },
    "muted_user_ui_row.hbs": {
        muted_user: {
            avatar_url: "/static/images/logo/zulip-icon-circle.svg",
            email: "muted@example.com",
            full_name: "Muted user",
            user_id: 11,
        },
    },
    "popovers/buddy_list_popover.hbs": {
        can_invite_users: true,
        display_style_options: {
            compact: {code: 1, description: "Compact"},
            detailed: {code: 2, description: "Detailed"},
        },
    },
    "popovers/emoji/emoji_popover_emoji.hbs": {
        emoji_dict: {
            emoji_code: "1f44d",
            emoji_name: "thumbs_up",
            name: "thumbs up",
            reaction_type: "unicode_emoji",
        },
        index: 0,
        section: "People",
        type: "unicode_emoji",
    },
    "popovers/emoji/emoji_showcase.hbs": {
        emoji_dict: {
            emoji_code: "1f44d",
            emoji_name: "thumbs_up",
            name: "thumbs up",
            reaction_type: "unicode_emoji",
        },
    },
    "popovers/left_sidebar_menu_popover.hbs": {
        web_channel_default_view: 1,
        web_channel_default_view_values: {
            top_topics: {code: 1, description: "Top topics"},
            all_topics: {code: 2, description: "All topics"},
        },
        web_stream_unreads_count_display_policy: 1,
        web_stream_unreads_count_display_policy_values: {
            all: {code: 1, description: "All unread messages"},
            mentions: {code: 2, description: "Mentions only"},
        },
    },
    "settings/admin_export_consent_list.hbs": {
        export_consent: {
            consent: "Approved",
            full_name: "Ava Rodriguez",
            img_src: "/static/images/logo/zulip-icon-circle.svg",
            user_id: 7,
        },
    },
    "settings/admin_emoji_list.hbs": {
        emoji: {
            can_delete_emoji: true,
            display_name: "party parrot",
            is_overriding_default: false,
            name: "party_parrot",
            source_url: "/static/images/logo/zulip-icon-circle.svg",
        },
    },
    "settings/admin_export_list.hbs": {
        realm_export: {date_created: "Today", id: 17, status: "Complete"},
    },
    "settings/admin_invites_list.hbs": {
        invite: {email: "new.member@example.com", id: 17, invited_by: "Ava Rodriguez"},
    },
    "settings/admin_linkifier_list.hbs": {
        can_drag: true,
        can_modify: true,
        linkifier: {
            id: 17,
            pattern: "#(?<id>[0-9]+)",
            url_format_string: "https://issues.example.com/%(id)s",
        },
    },
    "settings/admin_playground_list.hbs": {
        can_modify: true,
        playground: {
            id: 17,
            name: "TypeScript",
            pygments_language: "typescript",
            url_prefix: "https://play.example.com",
        },
    },
    "settings/admin_profile_field_list.hbs": {
        can_modify: true,
        profile_field: {display_name: "Team", field_type: 2, hint: "Your primary team", id: 17},
    },
    "settings/admin_realm_domains_list.hbs": {
        realm_domain: {allow_subdomains: true, domain: "example.com"},
    },
    "settings/alert_word_settings_item.hbs": {
        alert_word: {word: "launch"},
    },
    "settings/organization_settings_admin.hbs": {
        default_avatar_source_values: {
            generated: {code: "G", description: "Generated avatar"},
            gravatar: {code: "U", description: "Gravatar"},
        },
        gif_rating_policy_options: {
            all: {code: 0, description: "All GIFs"},
            moderate: {code: 1, description: "Moderate content"},
        },
        realm_available_video_chat_providers: {
            jitsi: {id: 1, name: "Jitsi Meet"},
        },
    },
    "user_topic_ui_row.hbs": {
        is_empty_string_topic: false,
        topic_display_name: "Homepage redesign",
        user_topic: {
            date_updated_str: "Today",
            stream: "design",
            stream_id: 7,
            topic: "Homepage redesign",
            visibility_policy: 1,
        },
        user_topic_visibility_policy_values: {
            followed: {code: 1, description: "Followed"},
            muted: {code: 2, description: "Muted"},
        },
        visibility_policy: 1,
    },
    "compose_banner/topic_moved_banner.hbs": {
        is_empty_string_topic: false,
        narrow_url: "#narrow/channel/7-design/topic/Homepage-redesign",
        old_stream: sample_stream,
        orig_topic: "Homepage redesign",
    },
    "cofounder_generated_update_visual_fixture.hbs": {
        generated: {
            ...sample_message_context,
            hover_module_name: "Project update",
            hover_source_context: "Design workspace",
            hover_state: "approved",
            is_hover_generated_update: true,
        },
        ordinary: sample_message_context,
    },
    "message_group.hbs": {
        message_groups: [
            {
                ...sample_recipient_row,
                invite_only: false,
                is_web_public: false,
                message_containers: [sample_message_context],
                message_group_id: "message-group-design",
                pm_with_url: false,
            },
        ],
        message_list_id: "main",
        use_match_properties: false,
    },
    "popovers/color_picker_popover.hbs": {
        ...sample_recipient_row,
        stream_color: "#2297df",
        stream_color_palette: [
            ["#2297df", "#76ce90", "#e79ab5", "#f4ae55"],
            ["#7e5fd1", "#5ec7c7", "#c2a45f", "#8c9ab8"],
        ],
    },
    "presence_rows.hbs": {
        presence_rows: [
            {
                href: "#narrow/dm/7-ava",
                name: "Ava Rodriguez",
                num_unread: 2,
                profile_picture: "/static/images/logo/zulip-icon-circle.svg",
                status_emoji_info: undefined,
                status_text: "Reviewing the design system",
                user_circle_class: "user-circle-active",
                user_id: 7,
                user_list_style: {WITH_AVATAR: true, WITH_STATUS: false},
            },
        ],
    },
    "report_message_modal.hbs": {
        message_container_data: sample_message_context,
        recipient_row_data: sample_recipient_row,
    },
    "components/membership_banner.hbs": {
        additions: {
            already_added_members: [],
            ignored_deactivated_groups: [],
            ignored_deactivated_users: [],
            newly_added_members: [
                {
                    type: "user",
                    user: {email: "ava@example.com", full_name: "Ava Rodriguez", user_id: 7},
                },
            ],
        },
        already_added_member_count: 0,
        already_added_subgroups_count: 0,
        already_added_user_count: 0,
        ignored_deactivated_groups_count: 0,
        ignored_deactivated_member_count: 0,
        ignored_deactivated_users_count: 0,
        intent: "success",
        newly_added_member_count: 1,
        newly_added_subgroups_count: 0,
        newly_added_user_count: 1,
        total_member_count_exceeds_five: false,
    },
    "confirm_dialog/confirm_reset_stream_notifications.hbs": {
        sub: {
            color: "#4f8394",
            is_archived: false,
            is_web_public: false,
            name: "design",
            stream_id: 7,
            stream_weekly_traffic: 3,
        },
    },
    "dropdown_list.hbs": {
        item: {
            bold_current_selection: true,
            description: "Use this value for the current workspace setting.",
            name: "Design",
            unique_id: 7,
        },
    },
    "inbox_view/inbox_folder_with_channels.hbs": {
        all_visibility_policies: {
            FOLLOWED: "FOLLOWED",
            INHERIT: "INHERIT",
            MUTED: "MUTED",
            UNMUTED: "UNMUTED",
        },
        has_unread_mention: false,
        header_id: "inbox-folder-design",
        is_collapsed: false,
        is_header_visible: true,
        name: "Design",
        stream_rows: [
            {
                stream_key: "inbox-stream-design",
                stream_row: {
                    column_indexes: {
                        ACTION_MENU: 3,
                        FULL_ROW: 0,
                        TOPIC_VISIBILITY: 2,
                        UNREAD_COUNT: 1,
                    },
                    is_archived: false,
                    is_collapsed: false,
                    is_hidden: false,
                    is_muted: false,
                    is_stream: true,
                    mention_in_unread: false,
                    stream_color: "#4f8394",
                    stream_header_color: "#eef6f7",
                    stream_id: 7,
                    stream_name: "design",
                    unread_count: 3,
                },
                topic_rows: [
                    {
                        all_visibility_policies: {
                            FOLLOWED: "FOLLOWED",
                            INHERIT: "INHERIT",
                            MUTED: "MUTED",
                            UNMUTED: "UNMUTED",
                        },
                        column_indexes: {
                            ACTION_MENU: 3,
                            FULL_ROW: 0,
                            TOPIC_VISIBILITY: 2,
                            UNREAD_COUNT: 1,
                        },
                        is_empty_string_topic: false,
                        is_hidden: false,
                        is_topic: true,
                        stream_archived: false,
                        stream_id: 7,
                        topic_display_name: "Homepage redesign",
                        topic_name: "Homepage redesign",
                        topic_url: "#narrow/channel/7/topic/Homepage%20redesign",
                        unread_count: 3,
                        visibility_policy: "INHERIT",
                    },
                ],
            },
        ],
        unread_count: 3,
    },
    "inbox_view/inbox_stream_container.hbs": {
        stream_key: "inbox-stream-design",
        stream_row: {
            column_indexes: {ACTION_MENU: 3, FULL_ROW: 0, TOPIC_VISIBILITY: 2, UNREAD_COUNT: 1},
            is_archived: false,
            is_collapsed: false,
            is_hidden: false,
            is_muted: false,
            is_stream: true,
            mention_in_unread: false,
            stream_color: "#4f8394",
            stream_header_color: "#eef6f7",
            stream_id: 7,
            stream_name: "design",
            unread_count: 3,
        },
        topic_rows: [
            {
                all_visibility_policies: {
                    FOLLOWED: "FOLLOWED",
                    INHERIT: "INHERIT",
                    MUTED: "MUTED",
                    UNMUTED: "UNMUTED",
                },
                column_indexes: {ACTION_MENU: 3, FULL_ROW: 0, TOPIC_VISIBILITY: 2, UNREAD_COUNT: 1},
                is_empty_string_topic: false,
                is_hidden: false,
                is_topic: true,
                stream_archived: false,
                stream_id: 7,
                topic_display_name: "Homepage redesign",
                topic_name: "Homepage redesign",
                topic_url: "#narrow/channel/7/topic/Homepage%20redesign",
                unread_count: 3,
                visibility_policy: "INHERIT",
            },
        ],
    },
    "draft_table_body.hbs": {
        context: {
            narrow_drafts: [],
            narrow_drafts_header: undefined,
            other_drafts: [
                {
                    content: "Outline the empty and loading states before the review.",
                    draft_id: 17,
                    is_empty_string_topic: false,
                    is_stream: true,
                    recipient_bar_color: "#4f8394",
                    stream_id: 7,
                    stream_name: "design",
                    stream_privacy_icon_color: "#ffffff",
                    time_stamp: "10:45 AM",
                    topic_display_name: "Homepage redesign",
                },
            ],
        },
    },
    "demo_organization_add_email_modal.hbs": {
        delivery_email: "ava@example.com",
        email_address_visibility_values: {
            everybody: {code: "1", description: "Everyone"},
            members: {code: "2", description: "Members of this organization"},
        },
        full_name: "Ava Rodriguez",
    },
    "settings/edit_custom_profile_field_form.hbs": {
        profile_field_info: {
            choices: [
                {is_existing_choice: true, text: "Engineering"},
                {is_existing_choice: true, text: "Design"},
                {new_empty_choice_row: true, text: ""},
            ],
            display_in_profile_summary: true,
            editable_by_user: true,
            hint: "Choose the team you work with most closely.",
            id: 7,
            is_dropdown_field: true,
            name: "Team",
            required: false,
            valid_to_display_in_summary: true,
            valid_to_use_for_user_matching: true,
        },
        realm_default_external_accounts: {},
    },
    "settings/preferences_information.hbs": {
        for_realm_settings: false,
        full_name: "Ava Rodriguez",
        prefix: "user_",
        profile_picture: "/static/images/logo/zulip-icon-circle.svg",
        settings_label: {
            fluid_layout_width: "Use the full browser width",
            hide_ai_features: "Hide AI features",
            receives_typing_notifications: "Show typing notifications",
            web_inbox_show_channel_folders: "Show channel folders in Inbox",
            high_contrast_mode: "Use high contrast mode",
        },
        settings_object: {
            fluid_layout_width: true,
            hide_ai_features: false,
            receives_typing_notifications: true,
            web_inbox_show_channel_folders: true,
            high_contrast_mode: false,
        },
        settings_render_only: {},
        user_list_style_values: {
            compact: {code: 1, description: "Name and status emoji"},
            detailed: {code: 2, description: "Name, emoji, and status text"},
            profile: {code: 3, description: "Profile picture and status"},
        },
        web_animate_image_previews_values: {
            always: {code: "always", description: "Always"},
            never: {code: "never", description: "Never"},
        },
    },
    "stream_settings/announce_stream_checkbox.hbs": {
        new_stream_announcements_stream_sub: {
            color: "#2297df",
            name: "announcements",
            stream_id: 9,
        },
    },
    "message_moved_widget_body.hbs": {
        is_empty_string_topic: false,
        new_location_url: "#narrow/channel/7/topic/Launch.20planning",
        new_topic_display_name: "Launch planning",
        stream: {
            color: "#2297df",
            invite_only: false,
            is_archived: false,
            is_web_public: false,
            name: "product",
            stream_id: 7,
        },
    },
    "stream_settings/stream_creation_form.hbs": {
        ask_to_announce_stream: true,
        channel_privacy_widget_name: "new_channel_privacy",
        check_default_stream: false,
        empty_string_topic_display_name: "(no topic)",
        group_setting_labels: {
            ...channel_group_setting_labels,
        },
        is_admin: true,
        is_owner: true,
        max_stream_description_length: 1024,
        max_stream_name_length: 60,
        new_stream_announcements_stream_sub: {
            color: "#2297df",
            name: "announcements",
            stream_id: 9,
        },
        prefix: "id_new_",
        stream_topics_policy_values: {
            all: {code: "allow_empty_topic", description: "Topics are optional"},
            required: {code: "require_topics", description: "Topics are required"},
        },
    },
    "user_group_settings/user_group_creation_form.hbs": {
        all_group_setting_labels: {
            group: user_group_setting_labels,
        },
        max_user_group_name_length: 100,
    },
};

function generic_fixture(
    template_path: string,
    inferred_fixture: Record<string, unknown>,
): Record<string, unknown> {
    const dedicated_fixture = dedicated_fixtures[template_path];
    const shared_fixture = family_fixture(template_path);
    const overrides =
        dedicated_fixture === undefined
            ? {...inferred_fixture, ...shared_fixture}
            : {...inferred_fixture, ...shared_fixture, ...dedicated_fixture};
    const fixture = safe_fixture(overrides);
    if (!is_record(fixture)) {
        throw new Error("Storybook template fixtures must be records");
    }
    return fixture;
}

function is_record(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safe_fixture(
    value: unknown,
    cache = new WeakMap<object, unknown>(),
    root_fixture?: unknown,
): unknown {
    // Compiled Handlebars performs nested lookups as separate property reads.
    // Wrapping only the root fixture therefore leaves values passed to partials
    // vulnerable to `lookupProperty(undefined, ...)`. Recursively proxy every
    // record and array so the same safe behavior survives those boundaries.
    if (value === null || value === undefined) {
        return value;
    }

    if (typeof value !== "object") {
        // Preserve native truthiness. In particular, wrapping `false` or `0`
        // in an object makes Handlebars render branches that production skips.
        return value;
    }

    const cached = cache.get(value);
    if (cached !== undefined) {
        return cached;
    }

    const fixture = new Proxy(value, {
        get(target, key, receiver) {
            if (key === Symbol.toPrimitive || key === "toString" || key === "valueOf") {
                return () => "";
            }
            // Handlebars uses this optional protocol to detect values that
            // intentionally bypass escaping. An unknown fixture field is not
            // HTML-safe content, and therefore must not pretend to implement it.
            if (key === "toHTML") {
                return undefined;
            }
            if (Reflect.has(target, key)) {
                return safe_fixture(
                    Reflect.get(target, key, receiver),
                    cache,
                    root_fixture ?? fixture,
                );
            }
            // Partials can receive a nested record while still referencing
            // state supplied by their parent template (for example, enums).
            return root_fixture ?? fixture;
        },
        getOwnPropertyDescriptor(target, key) {
            return (
                Reflect.getOwnPropertyDescriptor(target, key) ?? {
                    configurable: true,
                    enumerable: false,
                    value: undefined,
                    writable: false,
                }
            );
        },
        has() {
            // Handlebars' strict lookup uses the `in` operator. Treat
            // unknown keys as empty fixture data rather than throwing,
            // while curated values above remain real representative data.
            return true;
        },
    });
    cache.set(value, fixture);
    return fixture;
}

export function render_template_story(
    template_path: string,
    template: Template,
    inferred_fixture: Record<string, unknown>,
): HTMLElement {
    const wrapper = globalThis.document.createElement("section");
    wrapper.className = "storybook-template-story";

    try {
        wrapper.innerHTML = template(generic_fixture(template_path, inferred_fixture), {
            // Standalone block partials have no calling template to provide
            // this value. A parent-supplied block replaces it in normal use.
            data: {"partial-block": () => ""},
        });
        for (const image of wrapper.querySelectorAll("img")) {
            const source = image.getAttribute("src") ?? "";
            if (["#storybook", "Img src", "User avatar", "Avatar", "Image"].includes(source)) {
                image.src = "/static/images/logo/zulip-icon-circle.svg";
            } else if (source === "../images/giphy/GIPHY_attribution.png") {
                image.src = "/static/images/interactive-bot/giphy/powered-by-giphy.png";
            } else if (source.includes("generated/emoji/images/emoji/unicode/1f44d.png")) {
                image.src = "/static/images/logo/zulip-icon-circle.svg";
            }
        }
    } catch (error) {
        wrapper.classList.add("storybook-template-story-error");
        const message = error instanceof Error ? error.message : String(error);
        wrapper.textContent = `${template_path} needs a dedicated fixture: ${message}`;
    }

    return wrapper;
}
