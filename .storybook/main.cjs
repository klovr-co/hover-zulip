"use strict";

const fs = require("node:fs");
const path = require("node:path");

const Handlebars = require("handlebars");

const root = process.cwd();
const known_helpers = [
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
];

const templates_root = path.join(root, "web", "templates");

function find_partial_dependencies(source, template_path) {
    const dependencies = new Map();
    const visit = (node) => {
        if (node === null || typeof node !== "object") {
            return;
        }
        if (node.type === "PartialStatement" || node.type === "PartialBlockStatement") {
            const partial_name = node.name?.original;
            // `@partial-block` and named inline partials are provided by the
            // calling template, not the filesystem.
            if (partial_name !== undefined && partial_name !== "@partial-block") {
                const candidates = [
                    path.resolve(path.dirname(template_path), `${partial_name}.hbs`),
                    path.resolve(templates_root, `${partial_name}.hbs`),
                ];
                const partial_path = candidates.find((candidate) => fs.existsSync(candidate));
                if (partial_path !== undefined) {
                    dependencies.set(partial_name, partial_path);
                }
            }
        }
        for (const value of Object.values(node)) {
            if (Array.isArray(value)) {
                for (const item of value) {
                    visit(item);
                }
            } else {
                visit(value);
            }
        }
    };

    visit(Handlebars.parse(source));
    return dependencies;
}

module.exports = {
    framework: "@storybook/html-vite",
    // This is a focused Cofounder verification harness, not the former
    // generated template catalog. The two named screen fixtures render the
    // production Cofounder banner and conversation trees but retain their
    // historical filenames for now.
    stories: [
        "../web/stories/cofounder*.stories.ts",
        "../web/stories/banner.stories.ts",
        "../web/stories/conversation_screen.stories.ts",
    ],
    addons: ["@storybook/addon-a11y"],
    // Production templates use both root-relative `/images/...` paths and
    // `/static/images/...` paths. Serve the repository assets at both mounts
    // so Storybook exercises the real template markup without broken media.
    staticDirs: ["../static", {from: "../static", to: "/static"}],
    viteFinal(vite_config) {
        vite_config.resolve = {
            ...vite_config.resolve,
            alias: {
                ...vite_config.resolve?.alias,
                [path.join(root, "web", "src", "base_page_params.ts")]: path.join(
                    root,
                    ".storybook",
                    "page_params.ts",
                ),
            },
        };
        vite_config.define = {
            ...vite_config.define,
            DEVELOPMENT: "false",
        };
        vite_config.css = {
            ...vite_config.css,
            postcss: path.join(root, "web", "postcss.config.js"),
        };
        vite_config.plugins ??= [];
        vite_config.plugins.push({
            name: "zulip-handlebars",
            enforce: "pre",
            resolveId(source, importer) {
                if (
                    source === "./base_page_params.ts" &&
                    importer?.startsWith(path.join(root, "web", "src"))
                ) {
                    return path.join(root, ".storybook", "page_params.ts");
                }
                return undefined;
            },
            transform(source, id) {
                if (!id.endsWith(".hbs")) {
                    return undefined;
                }
                const partial_dependencies = find_partial_dependencies(source, id);
                const template = Handlebars.precompile(source, {
                    knownHelpers: Object.fromEntries(known_helpers.map((helper) => [helper, true])),
                    knownHelpersOnly: true,
                    strict: true,
                    explicitPartialContext: true,
                    preventIndent: true,
                });
                const partial_imports = partial_dependencies
                    .entries()
                    .map(
                        ([partial_name, partial_path], index) =>
                            `import partial_${index} from ${JSON.stringify(partial_path)};\n` +
                            `Handlebars.registerPartial(${JSON.stringify(partial_name)}, partial_${index});`,
                    )
                    .toArray()
                    .join("\n");
                return {
                    // Application templates resolve partials at build time. Do
                    // the same in curated Cofounder stories so production
                    // component trees render instead of a missing-partial error.
                    code: `import Handlebars from "handlebars/runtime";\n${partial_imports}\nexport default Handlebars.template(${template});`,
                    map: null,
                };
            },
        });
        return vite_config;
    },
};
