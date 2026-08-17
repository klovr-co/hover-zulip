"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");

const hover_request_id = zrequire("hover_request_id");

const request_id = hover_request_id.generate();
assert.match(request_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
assert.notEqual(hover_request_id.generate(), request_id);
