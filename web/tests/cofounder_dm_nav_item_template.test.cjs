"use strict";

const assert = require("node:assert/strict");

const render_more_pms = require("../templates/more_pms.hbs");
const render_pm_list_item = require("../templates/pm_list_item.hbs");

const {run_test} = require("./lib/test.cjs");

function conversation(overrides = {}) {
    return {
        has_unread_mention: false,
        is_active: false,
        is_bot: false,
        is_current_user: false,
        is_group: false,
        is_zero: false,
        recipients: "Alex Lee",
        status_emoji_info: undefined,
        unread: 4,
        url: "#narrow/dm/7-alex-lee",
        user_circle_class: "user-circle-active",
        user_ids_string: "7",
        ...overrides,
    };
}

run_test("direct-message row renders the Cofounder navigation contract", () => {
    const html = render_pm_list_item(conversation({has_unread_mention: true, is_active: true}));

    assert.match(
        html,
        /class="cf-dm-nav dm-list-item bottom_left_row cf-dm-nav--selected active-sub-filter/,
    );
    assert.match(html, /class="cf-dm-nav__main dm-box dm-user-status"/);
    assert.match(html, /aria-current="page"/);
    assert.match(html, /class="cf-dm-nav__presence-dot user-circle-active"/);
    assert.match(html, /class="cf-dm-nav__label-text conversation-partners-list">Alex Lee/);
    assert.match(
        html,
        /class="cf-dm-nav__mention unread_mention_info" aria-label="translated: Mentioned you">@/,
    );
    assert.match(
        html,
        /class="cf-dm-nav__badge unread_count" aria-label="translated: Unread messages: 4">4/,
    );
    assert.doesNotMatch(html, /zulip-icon/);
});

run_test("group, bot, self, and empty DM states stay in the typed contract", () => {
    const group = render_pm_list_item(
        conversation({
            is_group: true,
            recipients: "Jamie Morris, Taylor Smith",
            user_circle_class: undefined,
            user_ids_string: "8,9",
        }),
    );
    assert.match(group, /M16 21v-2a4 4/);
    assert.doesNotMatch(group, /user-circle-active/);

    const bot = render_pm_list_item(conversation({is_bot: true, recipients: "Build bot"}));
    assert.match(bot, /class="cf-dm-nav__bot" role="img"/);
    assert.match(bot, /<rect x="4" y="7" width="16"/);

    const self = render_pm_list_item(
        conversation({is_current_user: true, is_zero: true, unread: 0}),
    );
    assert.match(self, /zero-dm-unreads/);
    assert.match(self, /class="cf-dm-nav__self my_user_status">translated: \(you\)/);
    assert.match(self, /cf-dm-nav__badge unread_count zero_count/);
});

run_test("more-conversations row is a native Cofounder action", () => {
    const html = render_more_pms({more_conversations_unread_count: 8});

    assert.match(html, /id="show-more-direct-messages" class="cf-dm-nav-action/);
    assert.match(html, /<button type="button" class="cf-dm-nav-action__main dm-name">/);
    assert.match(html, /class="cf-dm-nav-action__label">translated: More conversations/);
    assert.match(
        html,
        /class="cf-dm-nav-action__badge unread_count" aria-label="translated: Unread messages: 8">8/,
    );
    assert.doesNotMatch(html, /<a|zulip-icon/);
});
