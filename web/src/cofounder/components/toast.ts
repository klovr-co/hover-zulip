export function dismiss($toast: JQuery): void {
    $toast.addClass("cf-toast--leaving");
    setTimeout(() => {
        $toast.remove();
    }, 180);
}
