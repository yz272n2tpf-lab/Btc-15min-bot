#!/usr/bin/env python3
from html.parser import HTMLParser
import json

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14


class Node:
    _next = 0

    def __init__(self, tag, attrs, parent):
        self.index = Node._next
        Node._next += 1
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []
        if parent is not None:
            parent.children.append(self)

    @property
    def classes(self):
        return set(str(self.attrs.get("class") or "").split())

    def signature(self):
        ident = self.attrs.get("id")
        classes = ".".join(sorted(self.classes))
        out = self.tag
        if ident:
            out += "#" + str(ident)
        if classes:
            out += "." + classes
        return out


class Parser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        Node._next = 0
        self.root = Node("document", [], None)
        self.stack = [self.root]
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.nodes.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.nodes.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return


def one(nodes, pred, label):
    found = [n for n in nodes if pred(n)]
    if len(found) != 1:
        return {"label": label, "count": len(found), "node": None}
    n = found[0]
    ancestry = []
    p = n.parent
    while p is not None and p.tag != "document":
        ancestry.append({
            "index": p.index,
            "signature": p.signature(),
            "child_count": len(p.children),
            "card_child_count": sum(1 for c in p.children if "card" in c.classes),
        })
        p = p.parent
    return {
        "label": label,
        "count": 1,
        "node": {
            "index": n.index,
            "signature": n.signature(),
            "parent_index": n.parent.index if n.parent else None,
            "parent_signature": n.parent.signature() if n.parent else None,
            "index_in_parent": n.parent.children.index(n) if n.parent else None,
            "ancestry": ancestry,
        },
    }


def report():
    path = v14.build_dashboard()
    text = path.read_text(encoding="utf-8", errors="replace")
    p = Parser()
    p.feed(text)
    targets = {
        "FINAL": one(p.nodes, lambda n: n.attrs.get("id") == "finalCard", "FINAL"),
        "EARLY": one(p.nodes, lambda n: "early-card" in n.classes, "EARLY"),
        "TIMER": one(p.nodes, lambda n: "timer-card" in n.classes, "TIMER"),
        "SCALP": one(p.nodes, lambda n: n.attrs.get("id") == "scalpCard", "SCALP"),
    }
    nodes = {k: v.get("node") for k, v in targets.items()}
    all_present = all(v is not None for v in nodes.values())

    final_parent = nodes["FINAL"]["parent_index"] if nodes["FINAL"] else None
    early_parent = nodes["EARLY"]["parent_index"] if nodes["EARLY"] else None
    timer_parent = nodes["TIMER"]["parent_index"] if nodes["TIMER"] else None
    scalp_parent = nodes["SCALP"]["parent_index"] if nodes["SCALP"] else None

    by_index = {n.index: n for n in p.nodes}
    left = by_index.get(final_parent)
    right = by_index.get(timer_parent)
    primary = left.parent if left is not None else None

    layout_shape_ok = bool(
        all_present
        and final_parent == early_parent
        and timer_parent == scalp_parent
        and final_parent != timer_parent
        and left is not None
        and right is not None
        and "left-stack" in left.classes
        and "right-stack" in right.classes
        and primary is not None
        and right.parent is primary
        and primary.tag == "section"
        and "primary-grid" in primary.classes
        and nodes["FINAL"]["index_in_parent"] == 0
        and nodes["EARLY"]["index_in_parent"] == 1
        and nodes["TIMER"]["index_in_parent"] == 0
        and nodes["SCALP"]["index_in_parent"] == 1
    )

    return {
        "version": "BTC15_DASHBOARD_DOM_STRUCTURE_REPORT_V15",
        "targets": targets,
        "layout_shape_ok": layout_shape_ok,
        "layout_shape": {
            "left_stack_index": left.index if left else None,
            "left_stack_signature": left.signature() if left else None,
            "right_stack_index": right.index if right else None,
            "right_stack_signature": right.signature() if right else None,
            "primary_grid_index": primary.index if primary else None,
            "primary_grid_signature": primary.signature() if primary else None,
            "primary_grid_child_count": len(primary.children) if primary else None,
        },
        "all_four_cards_share_one_parent": bool(
            all_present and len({final_parent, early_parent, timer_parent, scalp_parent}) == 1
        ),
        "timer_remaining_count": text.count('id="timerRemaining"'),
        "v14_marker_present": v14.MARKER in text,
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2, sort_keys=True))
