import render_member_list_entry from "../templates/stream_settings/stream_member_list_entry.hbs";

import * as ListWidget from "./list_widget.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import {current_user} from "./state_data.ts";
import * as user_sort from "./user_sort.ts";

export type MemberRemovalAction = "remove" | "unsubscribe";

type RenderMemberOptions = {
    can_remove: boolean;
    removal_action: MemberRemovalAction;
};

export function render_member(person: User, options: RenderMemberOptions): string {
    return render_member_list_entry({
        name: person.full_name,
        user_id: person.user_id,
        is_current_user: person.user_id === current_user.user_id,
        email: person.delivery_email,
        can_remove_subscribers: options.can_remove,
        for_user_group_members: options.removal_action === "remove",
        img_src: people.small_avatar_url_for_person(person),
    });
}

export function create({
    $container,
    $scroll_container,
    $filter,
    $parent_container,
    user_ids,
    name,
    can_remove = false,
    removal_action = "remove",
}: {
    $container: JQuery;
    $scroll_container: JQuery;
    $filter?: JQuery<HTMLInputElement>;
    $parent_container?: JQuery;
    user_ids: number[];
    name?: string;
    can_remove?: boolean;
    removal_action?: MemberRemovalAction;
}): ListWidgetType<User, User> {
    const users = people.get_users_from_ids(user_ids);
    people.sort_but_pin_current_user_on_top(users);
    $container.empty();

    return ListWidget.create($container, users, {
        ...(name && {name}),
        get_item: ListWidget.default_get_item,
        modifier_html(person) {
            return render_member(person, {can_remove, removal_action});
        },
        ...($filter && {
            filter: {
                $element: $filter,
                predicate(person: User, value: string) {
                    return people.build_person_matcher(value)(person);
                },
            },
        }),
        ...($parent_container && {$parent_container}),
        sort_fields: {
            email: user_sort.sort_email,
            id: user_sort.sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
        },
        $simplebar_container: $scroll_container,
    });
}
