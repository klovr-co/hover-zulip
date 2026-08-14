import {$} from "jquery";

import * as cofounder_toast from "./cofounder/components/toast.ts";

$("body").on("click", ".cf-feedback-stack .cf-toast__close", function () {
    cofounder_toast.dismiss($(this).closest(".cf-toast"));
});
