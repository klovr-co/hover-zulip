import "@fontsource-variable/open-sans";
import "source-code-pro/source-code-pro.css";
import "source-sans/source-sans-3VF.css";

// `zulip-icons.font.cjs` configures the build-time font generator.  It is not
// browser code, so importing it here makes Vite execute `module.exports` in
// the preview iframe and prevents Storybook from bootstrapping.
import "../web/stories/handlebars_helpers.ts";
import "../web/styles/app_components.css";
import "../web/styles/app_variables.css";
import "../web/styles/banners.css";
import "../web/styles/buttons.css";
import "../web/styles/compose.css";
import "../web/styles/recent_view.css";
import "../web/styles/inputs.css";
import "../web/styles/left_sidebar.css";
import "../web/styles/message_header.css";
import "../web/styles/message_row.css";
import "../web/styles/modal.css";
import "../web/styles/popovers.css";
import "../web/styles/right_sidebar.css";
import "../web/styles/zulip.css";
import "../web/styles/widgets.css";
import "../web/styles/cofounder/components/foundations.css";
import "../web/styles/cofounder/components/icon.css";
import "../web/styles/cofounder/components/dropdown-trigger.css";
import "../web/styles/cofounder/components/presence-dot.css";
import "../web/styles/cofounder/components/icon-button.css";
import "../web/styles/cofounder/components/button.css";
import "../web/styles/cofounder/components/banner.css";
import "../web/styles/cofounder/components/notice.css";
import "../web/styles/cofounder/components/toast.css";
import "../web/styles/cofounder/components/tabs.css";
import "../web/styles/cofounder/components/nav-item.css";
import "../web/styles/cofounder/components/channel-nav-item.css";
import "../web/styles/cofounder/components/topic-nav-item.css";
import "../web/styles/cofounder/components/topic-nav-action.css";
import "../web/styles/cofounder/components/dm-nav-item.css";
import "../web/styles/cofounder/components/dm-nav-action.css";
import "../web/styles/cofounder/components/dm-section-header.css";
import "../web/styles/cofounder/components/conversation-header.css";
import "../web/styles/cofounder/components/message.css";
import "../web/styles/cofounder/components/message-actions.css";
import "../web/styles/cofounder/components/message-reactions.css";
import "../web/styles/cofounder/components/source-actions.css";
import "../web/styles/cofounder/components/space-navigation.css";
import "../web/styles/cofounder/components/space-workbench.css";
import "../web/styles/cofounder/components/feed-controls.css";
import "../web/styles/cofounder/components/generated-update.css";
import "../web/styles/cofounder/components/source-view.css";
import "../web/styles/cofounder/components/evidence-dialog.css";
import "../web/styles/cofounder/components/editions-view.css";
import "../web/styles/cofounder/components/connected-accounts.css";
import "../web/styles/cofounder/components/todo-workflow.css";
import "../web/styles/cofounder/components/review-workflow.css";
import "../web/styles/cofounder/components/composer.css";
import "../web/styles/cofounder/components/data-table.css";
import "../web/styles/cofounder/components/conversation-list.css";
import "../web/styles/cofounder/components/settings-shell.css";
import "../web/styles/cofounder/components/two-pane-shell.css";
import "../web/styles/cofounder/components/form-field.css";
import "../web/styles/cofounder/components/search-field.css";
import "../web/styles/cofounder/components/copy-field.css";
import "../web/styles/cofounder/components/help-link.css";
import "../web/styles/cofounder/components/surface.css";
import "../web/styles/cofounder/components/status.css";
import "../web/styles/cofounder/components/dialog.css";
import "../web/styles/cofounder/components/menu.css";
import "../web/styles/cofounder/components/user-identity.css";
import "../web/styles/cofounder/components/people-sidebar.css";
import "../web/styles/cofounder/components/app-header-search.css";
import "../web/styles/cofounder/components/app-header.css";
import "../web/styles/cofounder/components/awareness-view.css";
import "../web/styles/cofounder/components/global-search.css";
import "../web/styles/cofounder/design-system.css";
import "../web/styles/cofounder/app.css";
import "../web/stories/storybook.css";

// The production app enables the Cofounder system from realm state. Storybook
// has no realm bootstrap, so provide the same host and foundation theme classes
// for every curated story while keeping component CSS identical to production.
globalThis.document.body.classList.add("hover-enabled", "cf-theme");

export default {
    parameters: {
        a11y: {
            element: "#storybook-root",
        },
        controls: {
            expanded: true,
        },
        layout: "padded",
    },
};
