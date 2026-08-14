"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {run_test} = require("./lib/test.cjs");

const cofounder_styles_directory = path.join(__dirname, "../styles/cofounder");
const component_styles_directory = path.join(__dirname, "../styles/cofounder/components");

function read_component_styles() {
    return fs
        .readdirSync(component_styles_directory)
        .filter((file_name) => file_name.endsWith(".css"))
        .toSorted()
        .map((file_name) => ({
            file_name,
            source: fs.readFileSync(path.join(component_styles_directory, file_name), "utf8"),
        }));
}

function read_cofounder_styles() {
    return [
        ...read_component_styles(),
        ...["app.css", "design-system.css"].map((file_name) => ({
            file_name,
            source: fs.readFileSync(path.join(cofounder_styles_directory, file_name), "utf8"),
        })),
    ];
}

run_test("Cofounder custom properties resolve within owned styles", () => {
    const styles = read_cofounder_styles();
    const defined_properties = new Set(
        styles.flatMap(({source}) =>
            source
                .matchAll(/^\s*(--cf-[\w-]+)\s*:/gm)
                .map(([, property]) => property)
                .toArray(),
        ),
    );
    const unresolved_properties = [];

    for (const {file_name, source} of styles) {
        for (const match of source.matchAll(/var\((--cf-[\w-]+)([^)]*)\)/g)) {
            const [, property, remainder] = match;
            const has_fallback = remainder.includes(",");

            if (!has_fallback && !defined_properties.has(property)) {
                unresolved_properties.push(`${file_name}: ${property}`);
            }
        }
    }

    assert.deepEqual(unresolved_properties, []);
});

run_test("Cofounder styles do not depend on legacy design tokens", () => {
    for (const {file_name, source} of read_cofounder_styles()) {
        assert.doesNotMatch(source, /--ds-[\w-]+/, file_name);
    }
});
