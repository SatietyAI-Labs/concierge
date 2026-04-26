// Concierge dashboard frontend shim — SSE bridge for live updates.
//
// Per Day 10 alignment: SSE for the Pending Requests Inbox new-request
// highlight; 5-10s HTMX polling fallback for non-event-driven counters
// (Health/Stats bar, see partials/health_bar.html).
//
// Why a shim instead of vendoring htmx-ext-sse: a single EventSource
// + htmx.ajax() call is ~10 lines and avoids a second vendored asset.
// The shim opens once at page load (not per partial render — the
// EventSource persists across HTMX swaps because index.html owns it,
// not the partials).
//
// Future event types (scanner-run-complete, install-complete) layer on
// here as additional addEventListener calls.

(function () {
    "use strict";

    function bridgeNewRequestEvents() {
        if (typeof EventSource === "undefined" || typeof htmx === "undefined") {
            return;
        }
        var source = new EventSource("/ui/events");
        source.addEventListener("new_request", function () {
            // A pending request just landed; refresh the inbox partial.
            // The /partials/pending-inbox endpoint owns the rendering;
            // we just signal "go fetch".
            htmx.ajax("GET", "/partials/pending-inbox", {
                target: "#pending-inbox",
                swap: "outerHTML",
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bridgeNewRequestEvents);
    } else {
        bridgeNewRequestEvents();
    }
})();
