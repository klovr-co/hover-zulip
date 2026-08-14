import {$} from "jquery";
import assert from "minimalistic-assert";

import * as buddy_data from "./buddy_data.ts";
import * as people from "./people.ts";

export function update_indicators(): void {
    $("[data-presence-indicator-user-id]").each(function () {
        const user_id = Number.parseInt($(this).attr("data-presence-indicator-user-id") ?? "", 10);
        const is_deactivated = !people.is_active_user_or_system_bot(user_id || 0);
        assert(!Number.isNaN(user_id));
        const user_circle_class = buddy_data.get_user_circle_class(user_id, is_deactivated);
        const $indicator = $(this);
        $indicator
            .removeClass(
                `
                user-circle-active zulip-icon-user-circle-active
                user-circle-idle zulip-icon-user-circle-idle
                user-circle-offline zulip-icon-user-circle-offline
            `,
            )
            .addClass(user_circle_class);
        if (!$indicator.hasClass("cf-presence-dot")) {
            $indicator.addClass(`zulip-icon-${user_circle_class}`);
        }
    });
}
