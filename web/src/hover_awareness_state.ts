export type AwarenessSurface = "for_you" | "team_pulse";

let current_surface: AwarenessSurface | undefined;

export function get_surface(): AwarenessSurface | undefined {
    return current_surface;
}

export function set_surface(surface: AwarenessSurface): void {
    current_surface = surface;
}

export function clear(): void {
    current_surface = undefined;
}
