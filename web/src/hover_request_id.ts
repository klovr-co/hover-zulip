export function generate(): string {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    // RFC 9562 UUIDv4: set the version and variant bits explicitly.
    bytes[6] = 0x40 + (bytes[6]! % 0x10);
    bytes[8] = 0x80 + (bytes[8]! % 0x40);
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex
        .slice(6, 8)
        .join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}
