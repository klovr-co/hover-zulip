type Template = (
    context: Record<string, unknown>,
    options?: {data?: Record<string, unknown>},
) => string;

const dedicated_fixtures: Record<string, Record<string, unknown>> = {
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
};

function generic_fixture(
    template_path: string,
    inferred_fixture: Record<string, unknown>,
): Record<string, unknown> {
    const dedicated_fixture = dedicated_fixtures[template_path];
    const overrides =
        dedicated_fixture === undefined
            ? inferred_fixture
            : {...inferred_fixture, ...dedicated_fixture};
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
    if (typeof value !== "object" || value === null) {
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
    } catch (error) {
        wrapper.classList.add("storybook-template-story-error");
        const message = error instanceof Error ? error.message : String(error);
        wrapper.textContent = `${template_path} needs a dedicated fixture: ${message}`;
    }

    return wrapper;
}
