import assert from "minimalistic-assert";

import * as activity from "./activity.ts";
import * as people from "./people.ts";
import * as pm_list from "./pm_list.ts";
import * as presence from "./presence.ts";
import type {PresenceInfoFromEvent} from "./presence.ts";
import {realm} from "./state_data.ts";
import * as util from "./util.ts";

export function initialize(): void {
    function get_full_presence_list_update(): void {
        activity.send_presence_to_server(redraw);
    }

    const active_ping_interval_ms = realm.server_presence_ping_interval_seconds * 1000;
    util.call_function_periodically(get_full_presence_list_update, active_ping_interval_ms);

    // Let the server know we're here. The initial presence data already came
    // from page parameters, so this first request does not need a redraw.
    activity.send_presence_to_server();
}

export function update_presence_info(info: PresenceInfoFromEvent): void {
    const presence_entry = Object.entries(info)[0];
    assert(presence_entry !== undefined);
    const [user_id_string, presence_info] = presence_entry;
    const user_id = Number.parseInt(user_id_string, 10);

    // Presence events can reference users that this client cannot access.
    const person = people.maybe_get_user_by_id(user_id, true);
    if (person === undefined || person.is_inaccessible_user) {
        return;
    }

    presence.update_info_from_event(user_id, presence_info);
    pm_list.update_private_messages();
}

export function redraw(): void {
    pm_list.update_private_messages();
}
