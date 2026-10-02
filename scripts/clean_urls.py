#!/usr/bin/env python3
"""The one rule that turns a URL path into the file that answers it.

/industries/mining is served by industries/mining.html. That rewrite happens at
the edge, in a CloudFront function, because the site is static objects in S3
and the only way to drop the extension from a URL is to put it back on before
the request reaches the bucket.

WHY THE RULE ALSO LIVES HERE. Every local check serves site/ with Python's own
static handler, which knows nothing about the edge. Without this the checks
would validate a site that does not exist: either they resolve .html paths the
site no longer links, or they 404 on the clean paths it does. Both happened.

So the rule is written once, in both languages, and a test asserts the two
agree on a table of paths. If the edge function changes and this does not, that
test fails rather than the site.

The test for "this is a page" is whether the LAST SEGMENT contains a dot. That
leaves /data/x.json, /catalog.json, /llms.txt, /og/x.png and the Parquet
exports alone, and it is why the check is on the segment rather than the whole
path: /industries/mining has a dot in neither.
"""
from __future__ import annotations

EDGE_FUNCTION = "infra/cdn/clean-urls.js"          # the other copy of this rule


def to_path(uri: str) -> str:
    """The object path a request URI should be served from.

    Mirrors infra/cdn/clean-urls.js exactly. Returns the URI unchanged when it
    already names a file, so it is safe to call on anything.
    """
    if uri == "/":
        return uri
    if uri.endswith("/"):
        uri = uri[:-1]
        if not uri:
            return "/"
    last = uri[uri.rfind("/") + 1:]
    if "." not in last:
        return uri + ".html"
    return uri


def install(handler_cls):
    """Return a handler subclass that applies the rule before serving.

    Used by the local servers the checks run against, so a check sees what a
    reader sees.
    """
    class CleanURLHandler(handler_cls):
        def translate_path(self, path):                       # noqa: D102
            query = ""
            if "?" in path:
                path, _, query = path.partition("?")
            if "#" in path:
                path, _, _ = path.partition("#")
            return super().translate_path(to_path(path) + (f"?{query}" if query else ""))

    return CleanURLHandler
