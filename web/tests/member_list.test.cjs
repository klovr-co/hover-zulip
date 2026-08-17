"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const ada = {
    user_id: 2,
    full_name: "Ada Lovelace",
    delivery_email: "ada@example.com",
};
const grace = {
    user_id: 1,
    full_name: "Grace Hopper",
    delivery_email: "grace@example.com",
};

let create_options;
const list_widget_result = {};
mock_esm("../src/list_widget", {
    create($container, users, options) {
        assert.equal($container, list_container);
        assert.deepEqual(users, [grace, ada]);
        create_options = options;
        return list_widget_result;
    },
    generic_sort_functions() {
        return {full_name_alphabetic: "alphabetic-sort"};
    },
});

mock_esm("../src/people", {
    get_users_from_ids(user_ids) {
        assert.deepEqual(user_ids, [2, 1]);
        return [ada, grace];
    },
    sort_but_pin_current_user_on_top(users) {
        users.reverse();
    },
    small_avatar_url_for_person(person) {
        return `/avatar/${person.user_id}`;
    },
    build_person_matcher(value) {
        return (person) => person.full_name.toLowerCase().includes(value.toLowerCase());
    },
});

mock_esm("../src/state_data", {
    current_user: {user_id: 1},
});

const email_sort = () => 0;
const user_id_sort = () => 0;
mock_esm("../src/user_sort", {
    sort_email: email_sort,
    sort_user_id: user_id_sort,
});

const member_list = zrequire("member_list");

const list_container = {
    empty_called: false,
    empty() {
        this.empty_called = true;
    },
};
const scroll_container = {};
const filter = {};
const parent_container = {};

run_test("create reusable member list", ({mock_template}) => {
    mock_template("stream_settings/stream_member_list_entry.hbs", false, (data) =>
        JSON.stringify(data),
    );

    const result = member_list.create({
        $container: list_container,
        $scroll_container: scroll_container,
        $filter: filter,
        $parent_container: parent_container,
        user_ids: [2, 1],
        name: "test_members",
        can_remove: true,
        removal_action: "unsubscribe",
    });

    assert.equal(result, list_widget_result);
    assert.equal(list_container.empty_called, true);
    assert.equal(create_options.name, "test_members");
    assert.equal(create_options.$simplebar_container, scroll_container);
    assert.equal(create_options.$parent_container, parent_container);
    assert.equal(create_options.filter.$element, filter);
    assert.equal(create_options.filter.predicate(ada, "love"), true);
    assert.equal(create_options.filter.predicate(ada, "hopper"), false);
    assert.equal(email_sort(), 0);
    assert.equal(user_id_sort(), 0);
    assert.deepEqual(create_options.sort_fields, {
        email: email_sort,
        id: user_id_sort,
        full_name_alphabetic: "alphabetic-sort",
    });

    assert.deepEqual(JSON.parse(create_options.modifier_html(grace)), {
        name: "Grace Hopper",
        user_id: 1,
        is_current_user: true,
        email: "grace@example.com",
        can_remove_subscribers: true,
        for_user_group_members: false,
        img_src: "/avatar/1",
    });
});

run_test("render member for a removable user-group row", ({mock_template}) => {
    mock_template("stream_settings/stream_member_list_entry.hbs", false, (data) =>
        JSON.stringify(data),
    );

    assert.deepEqual(
        JSON.parse(
            member_list.render_member(ada, {
                can_remove: true,
                removal_action: "remove",
            }),
        ),
        {
            name: "Ada Lovelace",
            user_id: 2,
            is_current_user: false,
            email: "ada@example.com",
            can_remove_subscribers: true,
            for_user_group_members: true,
            img_src: "/avatar/2",
        },
    );
});
