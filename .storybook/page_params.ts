// Storybook renders components without Zulip's server-generated #page-params
// element. Return conservative defaults for modules that read page parameters
// during import; individual stories provide richer state through their fixtures.
const default_page_params = {
    development_environment: true,
    is_node_test: true,
    is_spectator: false,
    page_type: "home",
    request_language: "en",
};

export const page_params = new Proxy(default_page_params, {
    get(target, property) {
        switch (property) {
            case "development_environment":
                return target.development_environment;
            case "is_node_test":
                return target.is_node_test;
            case "is_spectator":
                return target.is_spectator;
            case "page_type":
                return target.page_type;
            case "request_language":
                return target.request_language;
            default:
                return false;
        }
    },
});

export const page_params_parse_time = 0;
