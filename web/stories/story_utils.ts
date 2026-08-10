export function component_story(content: string, vertical = false): string {
    const direction = vertical ? " storybook-component-stack-vertical" : "";
    return `<div class="storybook-component"><div class="storybook-component-stack${direction}">${content}</div></div>`;
}
