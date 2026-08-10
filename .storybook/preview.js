import "@fontsource-variable/open-sans";
import "source-code-pro/source-code-pro.css";
import "source-sans/source-sans-3VF.css";

import "../web/icons/zulip-icons.font.cjs";
import "../web/stories/handlebars_helpers.ts";
import "../web/styles/app_components.css";
import "../web/styles/app_variables.css";
import "../web/styles/banners.css";
import "../web/styles/buttons.css";
import "../web/styles/inputs.css";
import "../web/styles/left_sidebar.css";
import "../web/styles/message_header.css";
import "../web/styles/message_row.css";
import "../web/styles/modal.css";
import "../web/styles/popovers.css";
import "../web/styles/right_sidebar.css";
import "../web/styles/zulip.css";
import "../web/styles/widgets.css";
import "../web/stories/storybook.css";

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
