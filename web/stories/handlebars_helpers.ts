import Handlebars from "handlebars/runtime.js";

// Storybook renders the same precompiled templates as the application, but it
// does not start the entire Zulip client. Register the helpers this component
// catalogue uses so templates remain executable in isolation.
Handlebars.registerHelper({
    eq(a: unknown, b: unknown) {
        return a === b;
    },
    and(...args: unknown[]) {
        args.pop(); // Handlebars options
        if (args.length === 0) {
            return true;
        }
        const last = args.pop();
        for (const arg of args) {
            if (!arg || Handlebars.Utils.isEmpty(arg)) {
                return arg;
            }
        }
        return last;
    },
    or(...args: unknown[]) {
        args.pop(); // Handlebars options
        if (args.length === 0) {
            return false;
        }
        const last = args.pop();
        for (const arg of args) {
            if (arg && !Handlebars.Utils.isEmpty(arg)) {
                return arg;
            }
        }
        return last;
    },
    not(value: unknown) {
        return !value || Handlebars.Utils.isEmpty(value);
    },
    object_values(value: Record<string, unknown> | undefined): unknown[] {
        return Object.values(value ?? {});
    },
});

Handlebars.registerHelper(
    "t",
    function t(
        this: Record<string, unknown>,
        message: string,
        options: {hash?: Record<string, unknown>},
    ) {
        const normalized_message = message
            .trim()
            .split("\n")
            .map((line) => line.trim())
            .join(" ");
        const values = {...this, ...options.hash};

        return normalized_message.replaceAll(/\{([a-z_]+)\}/g, (placeholder, key: string) => {
            const value = values[key];
            return typeof value === "string" || typeof value === "number"
                ? String(value)
                : placeholder;
        });
    },
);

Handlebars.registerHelper(
    "tr",
    function tr(
        this: unknown,
        options: {
            fn: ((context: unknown) => string) & {
                partials?: Record<string, (context: unknown, options: unknown) => string>;
            };
        },
    ) {
        // Zulip's translation blocks can contain inline partials (for example,
        // keyboard keys and rich stream/topic labels). Storybook has no locale
        // catalog to substitute, so render the source block while retaining that
        // production markup.
        let translated = options.fn(this);
        const inline_partials = Object.entries(options.fn.partials ?? {});
        for (const [name, partial] of inline_partials) {
            const placeholder = new RegExp(`<${name}>([\\s\\S]*?)</${name}>`, "g");
            translated = translated.replace(placeholder, (_match, content: string) =>
                partial(this, {data: {"partial-block": () => content}}),
            );
        }
        return new Handlebars.SafeString(translated);
    },
);

Handlebars.registerHelper("map_entries", (value: unknown): unknown[] =>
    value instanceof Map ? [...value] : [],
);

Handlebars.registerHelper(
    "object_entries",
    (value: Record<string, unknown> | undefined): unknown[] => Object.entries(value ?? {}),
);

Handlebars.registerHelper(
    "rendered_markdown",
    (content: string) => new Handlebars.SafeString(content ?? ""),
);

Handlebars.registerHelper("numberFormat", (number: number) => number.toLocaleString());

Handlebars.registerHelper("lookup", (parent: unknown, property_name: unknown): unknown => {
    if (typeof property_name !== "string" || typeof parent !== "object" || parent === null) {
        return undefined;
    }
    return Reflect.get(parent, property_name);
});

Handlebars.registerHelper("tooltip_hotkey_hints", (...args: unknown[]) => {
    args.pop(); // Handlebars options
    const hints = args
        .map(String)
        .map((hotkey) => `<span class="tooltip-hotkey-hint">${hotkey}</span>`)
        .join("");
    return new Handlebars.SafeString(`<span class="tooltip-hotkey-hints">${hints}</span>`);
});

Handlebars.registerHelper(
    "list_each",
    function list_each(this: unknown, context: unknown, options: Handlebars.HelperOptions) {
        const items_html: string[] = [];
        let empty = false;
        const each_helper = Handlebars.helpers["each"];
        if (typeof each_helper !== "function") {
            return options.inverse(this);
        }
        each_helper.call(this, context, {
            ...options,
            fn(item_context: unknown, item_options?: Handlebars.RuntimeOptions) {
                items_html.push(options.fn(item_context, item_options));
                return "";
            },
            inverse(item_context: unknown, item_options?: Handlebars.RuntimeOptions) {
                empty = true;
                return options.inverse(item_context, item_options);
            },
        });
        if (empty) {
            return options.inverse(this);
        }
        return new Intl.ListFormat("en", {type: "conjunction"})
            .formatToParts(items_html)
            .map((part) =>
                part.type === "element"
                    ? part.value
                    : Handlebars.Utils.escapeExpression(part.value),
            )
            .join("");
    },
);

Handlebars.registerHelper("popover_hotkey_hints", (...args: unknown[]) => {
    args.pop(); // Handlebars options
    const hotkeys = args.map(String);
    const hints = hotkeys
        .map((hotkey) => `<span class="popover-menu-hotkey-hint">${hotkey}</span>`)
        .join("");
    return new Handlebars.SafeString(`<span class="popover-menu-hotkey-hints">${hints}</span>`);
});
