// Storybook renders components without Zulip's server-generated #page-params
// element. Return conservative defaults for modules that read page parameters
// during import; individual stories provide richer state through their fixtures.
export const page_params = new Proxy(
    {
        development_environment: true,
        is_node_test: true,
        is_spectator: false,
        page_type: "home",
        request_language: "en",
    },
    {
        get(target, property) {
            return property in target ? Reflect.get(target, property) : false;
        },
    },
);

export const page_params_parse_time = 0;
