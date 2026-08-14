export const COFOUNDER_MENU_ITEM_SELECTOR = [
    ".cf-menu__action:not([aria-disabled='true']):not(:disabled)",
    ".cf-menu [role='menuitemradio']:not([aria-disabled='true'])",
].join(", ");

export function get_menu_items($root: JQuery): JQuery {
    return $root.find(COFOUNDER_MENU_ITEM_SELECTOR);
}

export function focus_first_menu_item($items: JQuery | undefined, index = 0): void {
    if (!$items) {
        return;
    }

    $items.eq(index).expectOne().trigger("focus");
}

export function menu_items_handle_keyboard(key: string, $items?: JQuery): void {
    if (!$items) {
        return;
    }

    const index = $items.index($items.filter(":focus"));

    if (key === "enter") {
        $items.eq(index).trigger("click");
        return;
    }

    const focused_item_has_focus_ring =
        index !== -1 && document.activeElement?.matches(":focus-visible") === true;
    if (
        !focused_item_has_focus_ring &&
        index !== -1 &&
        document.activeElement instanceof HTMLElement
    ) {
        document.activeElement.blur();
    }
    const navigation_index = focused_item_has_focus_ring ? index : -1;

    if (key === "down_arrow" || key === "vim_down") {
        [...$items]
            .slice(navigation_index === -1 ? 0 : navigation_index + 1)
            .find((item) => item.getClientRects().length)
            ?.focus();
    } else if (key === "up_arrow" || key === "vim_up") {
        [...$items]
            .slice(0, navigation_index === -1 ? $items.length : navigation_index)
            .findLast((item) => item.getClientRects().length)
            ?.focus();
    }
}
