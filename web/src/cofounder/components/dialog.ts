export function set_dialog_loading($dialog: JQuery, loading: boolean): void {
    const $buttons = $dialog.find(".cf-dialog__button");
    const $submit_button = $dialog.find(".cf-dialog__submit");

    $buttons.prop("disabled", loading);
    $submit_button.attr("aria-busy", String(loading));
}
