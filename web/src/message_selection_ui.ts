import {$} from "jquery";

export function update_selected_message_row(
    $row: JQuery,
    highlight_as_notification: boolean,
): void {
    $(".selected_message").removeClass("selected_message");
    $(".notification-highlighted-message").removeClass("notification-highlighted-message");
    $row.addClass("selected_message");
    if (highlight_as_notification) {
        $row.addClass("notification-highlighted-message");
    }
}
