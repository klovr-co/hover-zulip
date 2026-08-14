export const COFOUNDER_BUTTON_VARIANTS = [
    "primary",
    "secondary",
    "ghost",
    "danger",
    "success",
] as const;

export type CofounderButtonVariant = (typeof COFOUNDER_BUTTON_VARIANTS)[number];

export function set_button_variant($button: JQuery, variant: CofounderButtonVariant): void {
    const variant_pattern = COFOUNDER_BUTTON_VARIANTS.join("|");
    const variant_regex = new RegExp(`cf-button--(${variant_pattern})`);
    const current_variant = $button.attr("class")?.match(variant_regex)?.[0];

    if (current_variant === undefined) {
        return;
    }

    $button.removeClass(current_variant);
    $button.addClass(`cf-button--${variant}`);
}
