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
import sqlite3
import posixpath
from contextlib import closing
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
    reference: dict = field(default_factory=dict)
    issued_tokens: set[str] = field(default_factory=set)
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

    def fs_copy(self, source: str, destination: str) -> tuple[bool, str]:
        ok, content = self.fs_read(source)
        return self.fs_write(destination, content) if ok else (ok, content)

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
        self.issued_tokens.add(self.creds[name])
        return True, self.creds[name]

    # ------------------------------------------------------------------ db
    def db_query(self, sql: str, credential: str) -> tuple[bool, str]:
        name = self.token_to_name.get(credential) if credential in self.issued_tokens else None
        if name is None:
            return False, "ERROR: authentication failed: unknown credential token"
        visible = set(self.table_access.get(name, []))
        if not visible:
            return False, f"ERROR: credential '{name}' has no database rights"
        return run_sql(sql, {t: self.tables[t] for t in visible if t in self.tables})

    def csv_query(self, path: str, sql: str) -> tuple[bool, str]:
        """Read one CSV into a temporary SQLite table named data; queries are read-only."""
        ok, payload = self.fs_read(path)
        if not ok:
            return ok, payload
        try:
            reader = csv.DictReader(io.StringIO(payload))
            if not reader.fieldnames:
                return False, "ERROR: no CSV header"
            return run_sql(sql, {"data": list(reader)})
        except (ValueError, csv.Error):
            return False, "ERROR: invalid CSV"

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: Path = SEED_PATH, seed: int | None = None) -> "World":
        if seed is not None:
            from .seed import build
            d, reference = build(seed)
        else:
            d = json.loads(Path(path).read_text())
            reference = json.loads((Path(path).parent / "reference.json").read_text())
        return cls(files=d["files"], hosts=d["hosts"], creds=d["creds"], tables=d["tables"],
                   table_access=d["table_access"], reference=reference)

    def snapshot_files(self, prefix: str = "/workspace/") -> dict[str, str]:
        return {k: v for k, v in self.files.items() if k.startswith(prefix)}


def _norm(p: str) -> str:
    p = str(p).strip()
    if not p.startswith("/"):
        p = "/" + p
    return posixpath.normpath("/" + p.lstrip("/"))


# ---------------------------------------------------------------------- toy SQL
_SQL_FORMS = """Supported SQL:
  SHOW TABLES
  DESCRIBE <table>
  SELECT * FROM <table> [WHERE <col> = '<v>'] [LIMIT n]
  SELECT COUNT(*) FROM <table> [WHERE <col> = '<v>'] [GROUP BY <col>]
  SELECT COUNT(DISTINCT <col>) FROM <table> [WHERE ...] [GROUP BY <col2>]
  SELECT DISTINCT <col> FROM <table>"""


def run_sql(sql: str, tables: dict[str, list[dict]]) -> tuple[bool, str]:
    """SQLite SELECT over only the tables visible to this credential. No writes/extensions."""
    sql = str(sql).strip().rstrip(";").strip()
    if sql.upper() == "SHOW TABLES":
        return True, "\n".join(sorted(tables)) or "(no tables visible)"
    match = re.fullmatch(r"(?:DESCRIBE|SHOW COLUMNS FROM)\s+(\w+)", sql, re.I)
    if match:
        name = match.group(1)
        if name not in tables:
            return False, "ERROR: table not visible to this credential"
        return True, "\n".join(tables[name][0]) if tables[name] else "(no columns)"
    if not re.match(r"^(SELECT|WITH)\b", sql, re.I):
        return False, "ERROR: only read-only SELECT queries are supported"
    def quote(name):
        return '"' + str(name).replace('"', '""') + '"'
    with closing(sqlite3.connect(":memory:")) as conn:
        # Bound value allocation as well as VM instructions. A single randomblob()
        # or group_concat() could otherwise allocate gigabytes before a VM tick.
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_048_576)
        conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 100_000)
        for name, rows in tables.items():
            if not rows:
                continue
            cols = list(rows[0])
            # NUMERIC affinity keeps dates/IDs as strings and enables exact ordinary aggregation.
            conn.execute(f"CREATE TABLE {quote(name)} (" + ",".join(quote(c) + " NUMERIC" for c in cols) + ")")
            conn.executemany(f"INSERT INTO {quote(name)} VALUES (" + ",".join("?" for _ in cols) + ")",
                             [[r.get(c) for c in cols] for r in rows])
        conn.commit()
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        conn.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        ticks = [0]
        def stop():
            ticks[0] += 1
            return int(ticks[0] > 1000)
        conn.set_progress_handler(stop, 10000)
        try:
            cur = conn.execute(sql)
            rows = cur.fetchmany(201)
            names = [d[0] for d in cur.description]
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(names)
            writer.writerows(rows[:200])
            if len(rows) > 200:
                return True, buf.getvalue() + "\n[TRUNCATED: first 200 rows; aggregate or filter the query]"
            return True, buf.getvalue().strip() if rows else "(0 rows)"
        except sqlite3.Error as exc:
            return False, f"ERROR: {exc}"
