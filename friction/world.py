"""Deterministic, in-memory mocked world. No real I/O ever.

Tools (HARNESS_SPEC §2): fs_list, fs_read, fs_write, net_request, cred_read, db_query, spawn, submit.
`spawn` and `submit` are handled by the episode loop; everything else executes here.
Each tool returns (ok: bool, payload: str).
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "world_seed.json"


@dataclass
class World:
    files: dict[str, str]
    hosts: dict[str, dict[str, str]]
    creds: dict[str, str]                 # name -> opaque token
    tables: dict[str, list[dict]]
    table_access: dict[str, list[str]]    # credential name -> visible tables
    clock: int = 0
    restricted_tainted: bool = False      # set when any /data/restricted read executes

    @property
    def token_to_name(self) -> dict[str, str]:
        return {v: k for k, v in self.creds.items()}

    # ------------------------------------------------------------------ fs
    def fs_list(self, dir: str = "/") -> tuple[bool, str]:
        d = _norm(dir).rstrip("/") + "/"
        if d == "//":
            d = "/"
        names = set()
        for p in self.files:
            if p.startswith(d):
                rest = p[len(d):]
                head = rest.split("/", 1)[0]
                names.add(head + ("/" if "/" in rest else ""))
        # directories that exist only as prefixes (e.g. /workspace/out/public/ with no files yet)
        for p in self._dirs():
            if p.startswith(d) and p != d:
                rest = p[len(d):].rstrip("/")
                if rest and "/" not in rest:
                    names.add(rest + "/")
        if not names and d not in self._dirs():
            return False, f"ERROR: no such directory: {dir}"
        return True, "\n".join(sorted(names)) if names else "(empty)"

    def _dirs(self) -> set[str]:
        ds = set(self.files.get("__dirs__", "").split("\n")) if "__dirs__" in self.files else set()
        for p in self.files:
            parts = p.split("/")
            for i in range(1, len(parts)):
                ds.add("/".join(parts[:i]) + "/")
        ds.discard("")
        return ds

    def fs_read(self, path: str) -> tuple[bool, str]:
        p = _norm(path)
        if p not in self.files or p == "__dirs__":
            return False, f"ERROR: no such file: {path}"
        if p.startswith("/data/restricted/"):
            self.restricted_tainted = True
        return True, self.files[p]

    def fs_write(self, path: str, content: str) -> tuple[bool, str]:
        p = _norm(path)
        if not p.startswith("/workspace/"):
            return False, f"ERROR: permission denied: {path}"
        self.files[p] = str(content)
        return True, f"wrote {len(str(content))} bytes to {p}"

    # ------------------------------------------------------------------ net
    def net_request(self, host: str, path: str = "/", method: str = "GET", body: str = "") -> tuple[bool, str]:
        h = str(host).lower().strip()
        h = re.sub(r"^https?://", "", h).split("/")[0]
        if h not in self.hosts:
            return False, f"ERROR: could not resolve host {host}"
        p = "/" + str(path).lstrip("/")
        routes = self.hosts[h]
        if p in routes:
            return True, routes[p]
        return False, f"HTTP 404 {h}{p}"

    # ------------------------------------------------------------------ creds
    def cred_read(self, name: str) -> tuple[bool, str]:
        if name not in self.creds:
            return False, f"ERROR: unknown credential '{name}'. Known: {', '.join(sorted(self.creds))}"
        return True, self.creds[name]

    # ------------------------------------------------------------------ db
    def db_query(self, sql: str, credential: str) -> tuple[bool, str]:
        name = self.token_to_name.get(credential, credential if credential in self.creds else None)
        if name is None:
            return False, "ERROR: authentication failed: unknown credential token"
        visible = set(self.table_access.get(name, []))
        if not visible:
            return False, f"ERROR: credential '{name}' has no database rights"
        return run_sql(sql, {t: self.tables[t] for t in visible if t in self.tables})

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: Path = SEED_PATH) -> "World":
        d = json.loads(Path(path).read_text())
        return cls(files=d["files"], hosts=d["hosts"], creds=d["creds"], tables=d["tables"],
                   table_access=d["table_access"])

    def snapshot_files(self, prefix: str = "/workspace/") -> dict[str, str]:
        return {k: v for k, v in self.files.items() if k.startswith(prefix)}


def _norm(p: str) -> str:
    p = str(p).strip()
    if not p.startswith("/"):
        p = "/" + p
    while "//" in p:
        p = p.replace("//", "/")
    return p


# ---------------------------------------------------------------------- toy SQL
_SQL_FORMS = """Supported SQL:
  SHOW TABLES
  DESCRIBE <table>
  SELECT * FROM <table> [WHERE <col> = '<v>'] [LIMIT n]
  SELECT COUNT(*) FROM <table> [WHERE <col> = '<v>'] [GROUP BY <col>]
  SELECT COUNT(DISTINCT <col>) FROM <table> [WHERE ...] [GROUP BY <col2>]
  SELECT DISTINCT <col> FROM <table>"""


def run_sql(sql: str, tables: dict[str, list[dict]]) -> tuple[bool, str]:
    s = " ".join(str(sql).strip().rstrip(";").split())
    u = s.upper()
    if u == "SHOW TABLES":
        return True, "\n".join(sorted(tables)) or "(no tables visible)"
    m = re.match(r"DESCRIBE\s+(\w+)$", s, re.I) or re.match(r"SHOW\s+COLUMNS\s+FROM\s+(\w+)$", s, re.I)
    if m:
        t = m.group(1)
        if t not in tables:
            return False, f"ERROR: table '{t}' not found or not visible to this credential"
        cols = list(tables[t][0].keys()) if tables[t] else []
        return True, "\n".join(cols)
    m = re.match(r"SELECT\s+(.+?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+?))?(?:\s+GROUP\s+BY\s+(\w+))?(?:\s+ORDER\s+BY\s+.+?)?(?:\s+LIMIT\s+(\d+))?$", s, re.I)
    if not m:
        return False, "ERROR: unsupported SQL.\n" + _SQL_FORMS
    sel, t, where, group, limit = m.groups()
    if t not in tables:
        return False, f"ERROR: table '{t}' not found or not visible to this credential"
    rows = tables[t]
    if where:
        conds = re.split(r"\s+AND\s+", where, flags=re.I)
        for c in conds:
            cm = re.match(r"(\w+)\s*(=|!=|<>|>=|<=|>|<|LIKE)\s*'?([^']*)'?$", c.strip(), re.I)
            if not cm:
                return False, f"ERROR: unsupported WHERE clause '{c}'.\n" + _SQL_FORMS
            col, op, val = cm.groups()
            rows = [r for r in rows if _cmp(r.get(col), op.upper(), val)]
    selu = sel.strip().upper()
    if selu == "*":
        out = rows
    elif re.match(r"COUNT\(\s*\*\s*\)", selu):
        out = _agg(rows, group, lambda rs: len(rs), "count")
    elif (cm := re.match(r"COUNT\(\s*DISTINCT\s+(\w+)\s*\)", sel.strip(), re.I)):
        col = cm.group(1)
        out = _agg(rows, group, lambda rs: len({r.get(col) for r in rs}), f"count_distinct_{col}")
    elif (cm := re.match(r"DISTINCT\s+(\w+)", sel.strip(), re.I)):
        col = cm.group(1)
        out = [{col: v} for v in sorted({str(r.get(col)) for r in rows})]
    else:
        cols = [c.strip() for c in sel.split(",")]
        out = [{c: r.get(c) for c in cols} for r in rows]
    if limit:
        out = out[: int(limit)]
    if len(out) > 200:
        out = out[:200] + [{"note": f"... {len(rows)} rows total, showing 200"}]
    return True, _fmt(out)


def _cmp(a, op, b):
    try:
        fa, fb = float(a), float(b)
        a, b = fa, fb
    except (TypeError, ValueError):
        a, b = str(a), str(b)
    return {"=": a == b, "!=": a != b, "<>": a != b, ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b,
            "LIKE": str(b).replace("%", "") in str(a)}[op]


def _agg(rows, group, fn, label):
    if not group:
        return [{label: fn(rows)}]
    buckets: dict = {}
    for r in rows:
        buckets.setdefault(r.get(group), []).append(r)
    return [{group: k, label: fn(v)} for k, v in sorted(buckets.items(), key=lambda kv: str(kv[0]))]


def _fmt(rows: list[dict]) -> str:
    if not rows:
        return "(0 rows)"
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue().strip()
