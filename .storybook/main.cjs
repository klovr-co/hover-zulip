"use strict";

const path = require("node:path");

const root = process.cwd();
const app_styles = path.join(root, "web", "styles");

module.exports = {
    framework: "@storybook/html-webpack5",
    stories: ["../web/stories/**/*.stories.ts"],
    addons: ["@storybook/addon-essentials", "@storybook/addon-a11y"],
    staticDirs: ["../static"],
    webpackFinal(webpack_config) {
        const existing_rules = webpack_config.module?.rules ?? [];
        const is_css_rule = (rule) => rule.test instanceof RegExp && rule.test.test(".css");

        webpack_config.module = {
            ...webpack_config.module,
            rules: [
                ...existing_rules.filter(
                    (rule) => typeof rule === "object" && rule !== null && !is_css_rule(rule),
                ),
                {
                    test: /\.hbs$/,
                    loader: "handlebars-loader",
                    options: {
                        ignoreHelpers: true,
                        knownHelpers: [
                            "eq",
                            "and",
                            "or",
                            "not",
                            "t",
                            "tr",
                            "map_entries",
                            "object_entries",
                            "object_values",
                            "rendered_markdown",
                            "numberFormat",
                            "tooltip_hotkey_hints",
                            "popover_hotkey_hints",
                            "list_each",
                        ],
                        precompileOptions: {
                            knownHelpersOnly: true,
                            strict: true,
                            explicitPartialContext: true,
                        },
                        preventIndent: true,
                        // Generated static assets are served by Zulip rather than bundled;
                        // keeping their URLs intact lets Storybook compile every template.
                        inlineRequires: /^(\.\.\/)+images\//,
                    },
                },
                {
                    test: /\.css$/,
                    include: app_styles,
                    use: ["style-loader", "css-loader", "postcss-loader"],
                },
                {
                    test: /\.css$/,
                    exclude: app_styles,
                    use: ["style-loader", "css-loader"],
                },
                {
                    test: /\.font\.cjs$/,
                    use: [
                        "style-loader",
                        {
                            loader: "css-loader",
                            options: {url: false},
                        },
                        {
                            loader: "webfonts-loader",
                            options: {
                                fileName: "fonts/[fontname].[ext]",
                                publicPath: "",
                            },
                        },
                    ],
                    type: "javascript/auto",
                },
            ],
        };

        return webpack_config;
    },
};
