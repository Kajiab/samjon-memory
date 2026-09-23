"""Server-rendered Resolver Debug Portal pages.

Rendered behind the existing Portal HTTP Basic admin. Pages render only and
never touch SQLite or repositories directly; handlers call ResolverService
methods (the Resolver application-service boundary).
"""

import html as _html


def _e(value):
    return _html.escape(str(value) if value is not None else "")


_NAV = [
    ("Resolver Dashboard", "/portal/resolver/"),
    ("Query Debug", "/portal/resolver/query"),
    ("Projection Status", "/portal/resolver/projection"),
    ("Rebuild Controls", "/portal/resolver/rebuild"),
]


def _header(active):
    items = []
    for label, href in _NAV:
        cls = ' class="active"' if href == active else ""
        items.append('<a href="%s"%s>%s</a>' % (href, cls, _e(label)))
    nav = " | ".join(items)
    return (
        '<header><div class="nav"><strong>Resolver Debug</strong> | '
        + nav
        + ' | <a href="/portal/">Core Portal</a></div></header>'
    )


_CSS = (
    'body{font-family:sans-serif;margin:0;background:#f6f6f6;color:#1a1a1a}'
    'header{background:#1e3a5f;color:#fff;padding:8px 12px}'
    '.nav a{color:#cfe3ff;margin-right:10px;text-decoration:none}'
    '.nav a.active{color:#fff;font-weight:bold}'
    'main{padding:16px;max-width:1000px}'
    'table{border-collapse:collapse;width:100%;background:#fff}'
    'th,td{border:1px solid #ccc;padding:6px 8px;text-align:left;font-size:13px}'
    'th{background:#eef2f7}'
    'form{background:#fff;padding:12px;border:1px solid #ddd;margin:12px 0}'
    'label{margin-right:12px}'
    '.mono{font-family:monospace;font-size:12px}'
    '.msg{background:#e0f2e9;border:1px solid #b7dfcb;padding:8px;margin:10px 0}'
    '.err{background:#fdecea;border:1px solid #e6b4a9;padding:8px;margin:10px 0}'
    'a.cancel{margin-left:20px}'
)


def page(title, body, active):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>' + _e(title) + '</title><style>' + _CSS + '</style></head><body>'
        + _header(active)
        + '<main>' + body + '</main></body></html>'
    )


def _dl(data):
    rows = "".join(
        '<tr><th>%s</th><td class="mono">%s</td></tr>' % (_e(k), _e(v))
        for k, v in data
    )
    return "<table>" + rows + "</table>"


def dashboard(data):
    r = data.get("readiness", {})
    rows = [
        ("status", r.get("status")),
        ("resolver schema version", data.get("schema_version")),
        ("projection built", r.get("projection_built")),
        ("database available", r.get("database_available")),
        ("fts5 available", r.get("fts5_available")),
        ("active build id", data.get("last_full_build_id")),
        ("projected at", data.get("projected_at")),
        ("snapshot checksum", data.get("snapshot_checksum")),
        ("memories / collections / sections", data.get("counts")),
        ("fresh / stale / missing / orphaned", data.get("freshness_summary")),
    ]
    body = "<h2>Resolver Dashboard</h2>" + _dl(rows)
    builds = "".join(
        '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (_e(b.get("build_id")), _e(b.get("build_type")),
           _e(b.get("status")), _e(b.get("entity_id")))
        for b in data.get("recent_builds", [])
    )
    body += ('<h3>Recent builds</h3><table><tr><th>build id</th><th>type</th>'
             '<th>status</th><th>entity</th></tr>' + builds + "</table>")
    return page("Resolver Dashboard", body, "/portal/resolver/")


def query_page(form, result):
    q = form.get("query", "")
    target = form.get("target", "auto") or "auto"
    scope = form.get("scope", "")
    cid = form.get("collection_id", "")
    allow = ' checked' if str(form.get("allow_stale", "")) == "1" else ""
    neighbors = form.get("neighbor_items", "0")
    budget = form.get("context_budget", "0")
    opts = "".join(
        '<option%s>%s</option>' % (' selected' if target == t else "", t)
        for t in ("auto", "memory", "collection")
    )
    f = (
        '<form method="get" action="/portal/resolver/query">'
        '<label>query <input name="query" value="%s"></label>' % _e(q)
        + '<label>target <select name="target">' + opts + '</select></label>'
        + '<label>scope <input name="scope" value="%s"></label>' % _e(scope)
        + '<label>collection <input name="collection_id" value="%s"></label>' % _e(cid)
        + '<label>allow_stale <input type="checkbox" name="allow_stale" value="1"%s></label>' % allow
        + '<label>neighbors <input name="neighbor_items" value="%s"></label>' % _e(neighbors)
        + '<label>budget <input name="context_budget" value="%s"></label>' % _e(budget)
        + '<button type="submit">Search</button>'
        + '<a class="cancel" href="/portal/resolver/">Cancel</a></form>'
    )
    body = "<h2>Query Debug</h2>" + f
    if result is None:
        return page("Query Debug", body, "/portal/resolver/query")
    head = [
        ("result type", result.get("result_type")),
        ("resolved target", result.get("resolved_target")),
        ("count", result.get("count")),
        ("total", result.get("total")),
        ("incomplete", result.get("incomplete")),
        ("projection freshness", result.get("projection_freshness")),
    ]
    body += _dl(head)
    rows = "".join(
        '<tr><td>%s</td><td class="mono">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (_e(r.get("result_type")), _e(r.get("identity")), _e(r.get("score")),
           _e(r.get("match_reasons")), _e(r.get("projection_freshness")),
           _e(r.get("context")))
        for r in result.get("results", [])
    )
    body += ('<h3>Results</h3><table><tr><th>type</th><th>identity</th><th>score</th>'
             '<th>match reasons</th><th>freshness</th><th>context</th></tr>'
             + rows + "</table>")
    return page("Query Debug", body, "/portal/resolver/query")
def projection_page(data, fil):
    et_filter = fil.get("entity_type", "")
    fr_filter = fil.get("freshness", "")
    opts_type = "".join(
        '<option%s>%s</option>' % (' selected' if et_filter == t else "", t)
        for t in ("", "memory", "collection")
    )
    opts_fr = "".join(
        '<option%s>%s</option>' % (' selected' if fr_filter == t else "", t)
        for t in ("", "fresh", "stale", "missing", "orphaned")
    )
    filt = (
        '<form method="get" action="/portal/resolver/projection">'
        '<label>entity type <select name="entity_type">' + opts_type + '</select></label>'
        '<label>freshness <select name="freshness">' + opts_fr + '</select></label>'
        '<button type="submit">Filter</button>'
        '<a class="cancel" href="/portal/resolver/">Cancel</a></form>'
    )
    body = "<h2>Projection Status</h2>" + filt
    body += "<p>total %s | showing %s</p>" % (_e(data.get("total")), _e(data.get("count")))
    rows = "".join(
        '<tr><td>%s</td><td class="mono">%s</td><td>%s</td><td class="mono">%s</td>'
        '<td>%s</td><td class="mono">%s</td><td>%s</td>'
        '<td><a href="/portal/resolver/evidence?entity_type=%s&amp;entity_id=%s">view</a></td></tr>'
        % (_e(e["entity_type"]), _e(e["entity_id"]), _e(e["core_version"]),
           _e(e["core_checksum"]), _e(e["projected_core_version"]),
           _e(e["projected_core_checksum"]), _e(e["freshness"]),
           _e(e["entity_type"]), _e(e["entity_id"]))
        for e in data.get("entries", [])
    )
    body += ('<table><tr><th>entity type</th><th>entity id</th><th>core ver</th>'
             '<th>core checksum</th><th>proj ver</th><th>proj checksum</th>'
             '<th>freshness</th><th></th></tr>' + rows + "</table>")
    return page("Projection Status", body, "/portal/resolver/projection")


def rebuild_page(build, status, message):
    body = "<h2>Rebuild Controls</h2>"
    if message:
        body += '<div class="msg">%s</div>' % _e(message)
    body += _dl([
        ("in progress", status.get("in_progress")),
        ("last build id", status.get("last_build_id")),
        ("last build status", status.get("last_build_status")),
        ("projected at", status.get("projected_at")),
        ("snapshot checksum", status.get("snapshot_checksum")),
    ])
    body += (
        '<h3>Full rebuild</h3>'
        '<form method="post" action="/portal/resolver/rebuild">'
        '<label>type <b>full</b></label>'
        '<label>type <b>rebuild</b> to confirm <input name="confirmation" required></label>'
        '<button type="submit">Run full rebuild</button>'
        '<a class="cancel" href="/portal/resolver/rebuild">Cancel</a></form>'
    )
    body += (
        '<h3>Selective rebuild</h3>'
        '<form method="post" action="/portal/resolver/rebuild/selective">'
        '<label>entity_type <select name="entity_type"><option>memory</option>'
        '<option>collection</option></select></label>'
        '<label>entity_id <input name="entity_id" required></label>'
        '<label>type <b>rebuild</b> to confirm <input name="confirmation" required></label>'
        '<button type="submit">Run selective rebuild</button>'
        '<a class="cancel" href="/portal/resolver/rebuild">Cancel</a></form>'
    )
    builds = "".join(
        '<tr><td>%s</td><td>%s</td><td>%s</td><td class="mono">%s</td><td>%s</td></tr>'
        % (_e(b.get("build_id")), _e(b.get("build_type")), _e(b.get("status")),
           _e(b.get("error_code")), _e(b.get("entity_id")))
        for b in build.get("recent_builds", [])
    )
    body += ('<h3>Build history (rollback/failure evidence)</h3>'
             '<table><tr><th>build id</th><th>type</th><th>status</th><th>error</th>'
             '<th>entity</th></tr>' + builds + "</table>")
    return page("Rebuild Controls", body, "/portal/resolver/rebuild")


def evidence_page(data):
    auth = data.get("authoritative")
    proj = data.get("projected")
    body = "<h2>Evidence Viewer</h2>"
    body += _dl([
        ("entity type", data.get("entity_type")),
        ("entity id", data.get("entity_id")),
        ("freshness", data.get("freshness")),
        ("provenance", data.get("provenance")),
        ("authoritative source", data.get("authoritative_source")),
    ])
    body += "<h3>Authoritative (CoreService)</h3>"
    body += _dl(sorted(auth.items())) if auth else "<p>not in Core</p>"
    body += "<h3>Projected identity (Resolver snapshot)</h3>"
    body += _dl(sorted(proj.items())) if proj else "<p>no projection</p>"
    body += '<p><a href="/portal/resolver/projection">Back to Projection Status</a></p>'
    return page("Evidence Viewer", body, "")