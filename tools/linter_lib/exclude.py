# Exclude some directories and files from lint checking
EXCLUDED_FILES = [
    # Standalone design prototypes intentionally use CDN dependencies and inline styles.
    "designs/stitch/cofounder-inspired-web-design",
    # Third-party code that doesn't match our style
    "web/third",
    # Static design references are not production application assets.
    "designs/stitch",
]

PUPPET_CHECK_RULES_TO_EXCLUDE = [
    "--no-documentation-check",
    "--no-80chars-check",
]
