import type {Meta, StoryObj} from "@storybook/html";

import render_todos from "../templates/hover_todos_overlay.hbs";

type TodosArgs = {
    empty: boolean;
};

const todos = [
    {
        assignee: {full_name: "Priya Shah", user_id: 11},
        assignee_label: "Priya Shah",
        assignable_options: [{full_name: "Morgan Lee", user_id: 12}],
        due_label: "August 20, 2026",
        generated_item: {evidence_count: 3, evidence_url: "#sources"},
        id: 73,
        is_active: true,
        is_completed: false,
        latest_event: {
            actor: {full_name: "Aisha Rahman"},
            occurred_at: "August 13, 2026 at 10:18 AM",
        },
        source_hash: "#near/42",
        space: {name: "AIMTO Events"},
        state_label: "Active",
        state_tone: "accent",
        wording: "Publish the reviewed venue plan and confirm the delivery entrance.",
    },
    {
        assignee: {full_name: "Morgan Lee", user_id: 12},
        assignee_label: "Morgan Lee",
        assignable_options: [],
        due_label: "August 13, 2026",
        generated_item: {evidence_count: 0, evidence_url: null},
        id: 74,
        is_active: false,
        is_completed: true,
        latest_event: null,
        source_hash: "#near/43",
        space: {name: "Launch plan"},
        state_label: "Completed",
        state_tone: "success",
        wording: "Confirm the final catering count with the venue team.",
    },
];

function render_story(args: TodosArgs): string {
    return render_todos({empty: args.empty, todos: args.empty ? [] : todos});
}

const meta = {
    title: "Cofounder/Workflow/Todos",
    parameters: {layout: "fullscreen"},
    args: {empty: false},
    render: render_story,
} satisfies Meta<TodosArgs>;

export default meta;
type Story = StoryObj<TodosArgs>;

export const Home: Story = {};
export const Empty: Story = {args: {empty: true}};
export const NarrowTouch: Story = {
    parameters: {viewport: {defaultViewport: "mobile1"}},
};
