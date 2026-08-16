import {mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync} from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

import Handlebars from "handlebars";

const project_root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const templates_root = path.resolve(project_root, "web/templates");
const stories_root = path.resolve(project_root, "web/stories/generated");
const utility_path = path.resolve(project_root, "web/stories/template_story_utils.ts");

const helper_names = new Set([
    "and",
    "each",
    "eq",
    "if",
    "list_each",
    "lookup",
    "map_entries",
    "not",
    "numberFormat",
    "object_entries",
    "object_values",
    "or",
    "popover_hotkey_hints",
    "rendered_markdown",
    "t",
    "tooltip_hotkey_hints",
    "tr",
    "unless",
    "with",
]);

function set_path(target, parts, value, overwrite = false) {
    if (parts.length === 0) {
        return;
    }
    let cursor = target;
    const parent_parts = parts.slice(0, -1);
    for (const part of parent_parts) {
        if (
            typeof cursor[part] !== "object" ||
            cursor[part] === null ||
            Array.isArray(cursor[part])
        ) {
            cursor[part] = {};
        }
        cursor = cursor[part];
    }
    const leaf = parts.at(-1);
    if (overwrite || cursor[leaf] === undefined) {
        cursor[leaf] = value;
    }
}

function value_for_path(name) {
    if (name === "stream") {
        return {color: "#4f8394", name: "design", stream_id: 7};
    }
    if (name === "user" || name === "sender") {
        return {email: "ava@example.com", full_name: "Ava Rodriguez", user_id: 7};
    }
    if (name === "group") {
        return {id: 7, name: "Design team"};
    }
    if (name === "msg" || name === "message") {
        return {
            content: "A representative message for this UI state.",
            id: 7,
            message_reactions: [],
            reminders: [],
            sender_full_name: "Ava Rodriguez",
            sender_id: 7,
            url: "#narrow/near/7",
        };
    }
    if (name === "sub" || name === "settings_object") {
        return {is_muted: false, stream_id: 7};
    }
    if (/(?:color)$/u.test(name)) {
        return "#4f8394";
    }
    if (/(?:_id|^id)$/u.test(name)) {
        return 7;
    }
    if (/(?:url|href|link)$/u.test(name)) {
        return "#storybook";
    }
    if (/(?:count|number|unread)$/u.test(name)) {
        return 3;
    }
    if (
        /^(?:is_|has_|can_|should_|show_|allow_|enable_|disabled|embedded|archived|muted|guest|admin|owner|spectator|current|default)/u.test(
            name,
        )
    ) {
        return true;
    }
    if (/(?:time|date)$/u.test(name)) {
        return "10:45 AM";
    }
    if (/(?:email)$/u.test(name)) {
        return "ava@example.com";
    }
    return name.replaceAll("_", " ").replace(/^./u, (character) => character.toUpperCase());
}

function path_target(expression, contexts) {
    if (
        expression?.type !== "PathExpression" ||
        expression.data ||
        expression.original === "this"
    ) {
        return undefined;
    }
    const target = contexts.at(Math.max(0, contexts.length - 1 - expression.depth));
    const parts = expression.parts.filter((part) => part !== "this");
    return target === undefined || parts.length === 0 ? undefined : {parts, target};
}

function add_path(expression, contexts) {
    const target = path_target(expression, contexts);
    if (target === undefined || helper_names.has(expression.original)) {
        return;
    }
    set_path(target.target, target.parts, value_for_path(target.parts.at(-1)));
}

function add_collection(expression, contexts) {
    const target = path_target(expression, contexts);
    if (target === undefined) {
        return undefined;
    }
    const item = {
        custom_classes: "",
        disabled: false,
        icon: "check",
        intent: "primary",
        label: "Sample action",
        name: "Sample name",
        variant: "primary",
    };
    set_path(target.target, target.parts, [item], true);
    return item;
}

function visit_expression(expression, contexts) {
    if (expression?.type === "PathExpression") {
        add_path(expression, contexts);
        return;
    }
    if (expression?.type !== "SubExpression") {
        return;
    }
    for (const parameter of expression.params) {
        visit_expression(parameter, contexts);
    }
    const hash_pairs = expression.hash?.pairs ?? [];
    for (const pair of hash_pairs) {
        visit_expression(pair.value, contexts);
    }
    if (["object_entries", "object_values"].includes(expression.path.original)) {
        const object_parameter = path_target(expression.params[0], contexts);
        if (object_parameter !== undefined) {
            set_path(object_parameter.target, object_parameter.parts, {
                sample: {code: "sample", description: "Sample option"},
            });
        }
    }
}

function visit_program(program, contexts) {
    for (const statement of program.body) {
        if (statement.type === "MustacheStatement") {
            add_path(statement.path, contexts);
            for (const parameter of statement.params) {
                visit_expression(parameter, contexts);
            }
            const hash_pairs = statement.hash?.pairs ?? [];
            for (const pair of hash_pairs) {
                visit_expression(pair.value, contexts);
            }
            continue;
        }
        if (statement.type !== "BlockStatement") {
            continue;
        }
        const name = statement.path.original;
        for (const parameter of statement.params) {
            visit_expression(parameter, contexts);
        }
        const hash_pairs = statement.hash?.pairs ?? [];
        for (const pair of hash_pairs) {
            visit_expression(pair.value, contexts);
        }
        if (name === "each" || name === "list_each") {
            const item = add_collection(statement.params[0], contexts);
            visit_program(statement.program, item === undefined ? contexts : [...contexts, item]);
        } else if (name === "with") {
            const target = path_target(statement.params[0], contexts);
            const child = {};
            if (target !== undefined) {
                set_path(target.target, target.parts, child);
            }
            visit_program(statement.program, [...contexts, child]);
        } else {
            visit_program(statement.program, contexts);
        }
        if (statement.inverse !== undefined) {
            visit_program(statement.inverse, contexts);
        }
    }
}

function inferred_fixture(template_path) {
    const fixture = {};
    visit_program(Handlebars.parse(readFileSync(template_path, "utf8")), [fixture]);
    return fixture;
}

function list_templates(directory) {
    return readdirSync(directory, {withFileTypes: true}).flatMap((entry) => {
        const entry_path = path.resolve(directory, entry.name);
        if (entry.isDirectory()) {
            return list_templates(entry_path);
        }
        return entry.name.endsWith(".hbs") ? [entry_path] : [];
    });
}

function import_path(from_directory, to_file) {
    const relative_path = path.relative(from_directory, to_file).split(path.sep).join("/");
    return relative_path.startsWith(".") ? relative_path : `./${relative_path}`;
}

function title_segment(segment) {
    return segment
        .split(/[-_]/u)
        .filter(Boolean)
        .map((word) => word[0].toUpperCase() + word.slice(1))
        .join(" ");
}

function generate_story(template_path) {
    const template_relative_path = path
        .relative(templates_root, template_path)
        .split(path.sep)
        .join("/");
    const story_path = path.resolve(
        stories_root,
        `${template_relative_path.slice(0, -".hbs".length)}.stories.ts`,
    );
    const story_directory = path.dirname(story_path);
    const title = `Catalogue/${template_relative_path
        .slice(0, -".hbs".length)
        .split("/")
        .map((segment) => title_segment(segment))
        .join("/")}`;
    const fixture = JSON.stringify(inferred_fixture(template_path), undefined, 4);

    mkdirSync(story_directory, {recursive: true});
    writeFileSync(
        story_path,
        `/* This file is generated by tools/generate_storybook_template_catalog.mjs. */\n\n` +
            `import type {Meta, StoryObj} from "@storybook/html";\n\n` +
            `import render_template from "${import_path(story_directory, template_path)}";\n` +
            `import {render_template_story} from "${import_path(story_directory, utility_path)}";\n\n` +
            `const fixture = ${fixture};\n\n` +
            `const meta = {\n` +
            `    title: ${JSON.stringify(title)},\n` +
            `    render: () => render_template_story(${JSON.stringify(template_relative_path)}, render_template, fixture),\n` +
            `} satisfies Meta;\n\n` +
            `export default meta;\n` +
            `type Story = StoryObj;\n\n` +
            `export const Default: Story = {};\n`,
    );
}

rmSync(stories_root, {force: true, recursive: true});
const template_paths = list_templates(templates_root).toSorted((a, b) => a.localeCompare(b));
for (const template_path of template_paths) {
    generate_story(template_path);
}
