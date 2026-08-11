import type {Meta, StoryObj} from "@storybook/html";

import render_todo_widget from "../templates/widgets/todo_widget.hbs";
import render_todo_widget_example from "../templates/widgets/todo_widget_example.hbs";
import render_todo_widget_tasks from "../templates/widgets/todo_widget_tasks.hbs";

import {component_story} from "./story_utils.ts";

type TodoTask = {
    completed: boolean;
    desc?: string;
    key: string;
    task: string;
};

type TodoWidgetArgs = {
    all_tasks: TodoTask[];
    task_list_title: string;
};

function render_todo_widget_state(args: TodoWidgetArgs): HTMLElement {
    const wrapper = globalThis.document.createElement("div");
    wrapper.innerHTML = component_story(render_todo_widget());

    const widget = wrapper.querySelector<HTMLElement>(".todo-widget");
    if (widget === null) {
        throw new Error("Todo widget template did not render its root element.");
    }

    const title = widget.querySelector<HTMLElement>(".todo-task-list-title-header");
    const tasks = widget.querySelector<HTMLElement>("ul.todo-widget");
    if (title === null || tasks === null) {
        throw new Error("Todo widget template did not render its required regions.");
    }

    title.textContent = args.task_list_title;
    tasks.innerHTML = render_todo_widget_tasks({all_tasks: args.all_tasks});
    return wrapper;
}

const meta = {
    title: "Widgets/Todo",
    tags: ["autodocs"],
    args: {
        task_list_title: "Launch checklist",
        all_tasks: [
            {completed: true, key: "research", task: "Validate the release notes"},
            {
                completed: false,
                desc: "Include the new component catalogue",
                key: "demo",
                task: "Prepare demo",
            },
            {completed: false, key: "share", task: "Share the review link"},
        ],
    },
    render: render_todo_widget_state,
} satisfies Meta<TodoWidgetArgs>;

export default meta;
type Story = StoryObj<TodoWidgetArgs>;

export const Tasks: Story = {};

export const Example: Story = {
    render: () => component_story(render_todo_widget_example()),
};
