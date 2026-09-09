# -*- coding: utf-8 -*-
"""Find tables and rebuild them.

Three signals do the work.  Drawn cell borders say where the columns are and
which band is a header.  A wide blank inside a line marks a cell boundary.
And the leftmost reliably-filled column tells a real row apart from a line that
merely wrapped, which geometry alone cannot: both look like a short line.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .inline import render, tidy
from .reader import GAP, YTOL


@dataclass
class Table:
    header: list
    rows: list
    warnings: list = field(default_factory=list)
    #: Text of spanning rows that ended up labelling nothing.  Kept so it can be
    #: written out beside the table instead of vanishing.
    orphans: list = field(default_factory=list)

    def to_markdown(self) -> str:
        if not self.rows:
            return ""
        keep = [c for c in range(len(self.header))
                if self.header[c] or any(r[c] for r in self.rows)]
        if not keep:
            return ""

        def line(cells):
            body = " | ".join((cells[c] or " ").replace("|", "\\|") for c in keep)
            return "| " + body + " |"

        return "\n".join([line(self.header), "|" + "---|" * len(keep)]
                         + [line(r) for r in self.rows])


def cluster(values, tol=3.0):
    values, groups = sorted(values), []
    for v in values:
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [g[0] for g in groups]


def bands_of(lines):
    """Group lines that sit on the same baseline."""
    out = []
    for line in lines:
        if out and abs(line.yc - out[-1][0].yc) <= YTOL:
            out[-1].append(line)
        else:
            out.append([line])
    return out


def line_cells(line):
    """Split one line into cells wherever a cell-sized gap appears."""
    runs = [r for r in line.runs if not r.blank]
    if not runs:
        return []
    cells, current = [], [runs[0]]
    for prev, run in zip(runs, runs[1:]):
        if run.x0 - prev.x1 > GAP:
            cells.append(current)
            current = [run]
        else:
            current.append(run)
    cells.append(current)
    return cells


def band_starts(band):
    return cluster([c[0].x0 for line in band for c in line_cells(line)])


def find_regions(bands, rules, margin, breaks=frozenset()):
    """Seed on bands holding two or more cells, then take in the neighbouring
    single-cell bands that are wrapped continuations.  Prose starts at the page
    margin and cells do not, which keeps a paragraph from being swallowed.

    `breaks` are band indices a table can never span -- a caption announces the
    next table, so two tables with a caption between them stay separate.
    """
    starts = [band_starts(b) for b in bands]
    multi = [len(s) >= 2 for s in starts]
    at_margin = [bool(s) and abs(s[0] - margin) <= 1.5 for s in starts]
    for i in breaks:                       # a hard stop behaves like prose
        multi[i] = False
        at_margin[i] = True

    seeds, i = [], 0
    while i < len(bands):
        if not multi[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(bands):
            if multi[j + 1]:
                j += 1
                continue
            k = j + 1
            while k < len(bands) and not multi[k] and not at_margin[k]:
                k += 1
            if k < len(bands) and multi[k] and not at_margin[k]:
                j = k
            else:
                break
        seeds.append([i, j])
        i = j + 1

    regions = []
    for lo, hi in seeds:
        seed_cols = [c for c in cluster([x for t in range(lo, hi + 1)
                                         for x in starts[t]])
                     if abs(c - margin) > 1.5]
        if len(seed_cols) < 2:
            continue

        def continues(t, ref, downward, _cols=seed_cols):
            if multi[t] or not starts[t] or at_margin[t]:
                return False
            if abs(bands[t][0].yc - bands[ref][0].yc) > 22:
                return False
            if downward:
                # Below the last row, a line reaching across the columns is a
                # note about the table, not the tail of a wrapped cell.
                width = max(l.x1 for l in bands[t]) - min(l.x0 for l in bands[t])
                crossed = sum(1 for c in _cols if starts[t][0] + 2 < c
                              < min(l.x0 for l in bands[t]) + width - 2)
                if crossed >= 2:
                    return False
            return any(abs(starts[t][0] - c) <= 2.5 for c in _cols)

        while lo - 1 >= 0 and continues(lo - 1, lo, False):
            lo -= 1
        while hi + 1 < len(bands) and continues(hi + 1, hi, True):
            hi += 1
        idx = list(range(lo, hi + 1))
        if len(idx) < 2:
            continue

        top = min(bands[t][0].yc for t in idx)
        bottom = max(bands[t][0].yc for t in idx)
        ys = [y for y in rules if top - 16 <= y <= bottom + 10]
        # An unruled block of aligned text is an example list, not a table.
        if not any(len(rules[y]) > 2 for y in ys):
            continue
        cols = sorted({x for y in ys if len(rules[y]) > 2 for x in rules[y]})
        regions.append({"bands": idx, "cols": cols, "rules": ys})
    return regions


def build(bands, region, links, resolve) -> Table:
    cols, ys, idx = region["cols"], region["rules"], region["bands"]
    ncol = len(cols)

    def column_of(x):
        c = 0
        for i, edge in enumerate(cols):
            if x >= edge - 2:
                c = i
        return c

    rows = []
    for i in idx:
        buckets = [[] for _ in range(ncol)]
        spans_columns = False
        for line in bands[i]:
            for cell in line_cells(line):
                x0, x1 = cell[0].x0, cell[-1].x1
                if any(x0 + 2 < e < x1 - 2 for e in cols):
                    spans_columns = True
                buckets[column_of(x0)].extend(cell)
        text = [tidy(render(b, links, resolve)) if b else "" for b in buckets]
        if spans_columns and sum(1 for t in text if t) == 1:
            rows.append(["span", next(t for t in text if t)])
        else:
            rows.append(["row", text])

    body = [v for kind, v in rows if kind == "row"]
    key = next((c for c in range(ncol)
                if body and sum(1 for r in body if r[c]) / len(body) >= 0.6), None)
    ycs = [bands[i][0].yc for i in idx]

    def ruled(n):
        return n > 0 and any(ycs[n - 1] < y < ycs[n] for y in ys)

    for n, entry in enumerate(rows):
        kind, v = entry
        if kind != "row" or not any(v) or ruled(n):
            continue
        if key is not None:
            wrapped = (not v[key]) or (ncol > 1 and
                                       not any(v[c] for c in range(ncol) if c != key))
        else:
            wrapped = sum(1 for t in v if t) < 2
        if wrapped:
            entry[0] = "cont"

    merged = []
    for kind, v in rows:
        if kind == "cont" and merged and merged[-1][0] == "row":
            for c, cell in enumerate(v):
                if cell:
                    merged[-1][1][c] = (merged[-1][1][c] + " " + cell).strip()
        elif kind == "cont":
            merged.append(["row", list(v)])          # nothing above to join onto
        else:
            merged.append([kind, list(v) if kind == "row" else v])

    header_present = bool(ys) and any(bands[i][0].yc < min(ys) - 2 for i in idx)
    return _assemble(merged, header_present)


def _assemble(rows, header_present) -> Table:
    spanning = any(k == "span" for k, _ in rows)
    header, data, group = None, [], ""
    used, pending, orphans = False, None, []
    for kind, value in rows:
        if kind == "span":
            if pending is not None and not used:
                orphans.append(pending)      # laboured nothing; keep it anyway
            group = value.replace("**", "").replace("_", "").strip()
            pending, used = value, False
            continue
        if kind != "row":
            continue
        used = True
        cells = ([group] if spanning else []) + list(value)
        if header is None and header_present:
            header = cells
        else:
            data.append(cells)
    if pending is not None and not used:
        orphans.append(pending)
    if not data:
        return Table([], [], orphans=orphans)

    width = max(len(r) for r in data)
    if header:
        width = max(width, len(header))
    data = [r + [""] * (width - len(r)) for r in data]
    header = [""] * width if header is None else header + [""] * (width - len(header))

    # Recover rowspans: leading columns hold sparse group labels, so carry them
    # down.  A blank in a densely filled column is a real blank and stays blank.
    for c in range(width):
        if sum(1 for r in data if r[c]) / len(data) >= 0.6:
            break
        for r in range(1, len(data)):
            if not data[r][c]:
                data[r][c] = data[r - 1][c]

    table = Table(header, data, orphans=orphans)
    trailing = sum(1 for r in data if r and r[-1].rstrip().endswith(","))
    if trailing:
        table.warnings.append(
            f"{trailing}개 행이 쉼표로 끝납니다 — 다음 행과 원래 한 행일 수 있습니다")
    return table
