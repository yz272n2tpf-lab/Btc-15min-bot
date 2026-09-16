#!/usr/bin/env python3
from html.parser import HTMLParser
import unittest

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14


class Node:
    def __init__(self, tag, attrs, parent):
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
        suffix = ("#" + ident) if ident else ""
        if classes:
            suffix += "." + classes
        return f"{self.tag}{suffix}"


class TreeParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
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


def find_one(nodes, predicate, label):
    found = [n for n in nodes if predicate(n)]
    if len(found) != 1:
        raise AssertionError(f"{label}: expected exactly one node, found {len(found)}")
    return found[0]


class V15GeneratedDOMStructureAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = v14.build_dashboard()
        text = path.read_text(encoding="utf-8", errors="replace")
        parser = TreeParser()
        parser.feed(text)
        cls.parser = parser
        nodes = parser.nodes
        cls.final = find_one(nodes, lambda n: n.attrs.get("id") == "finalCard", "FINAL")
        cls.early = find_one(nodes, lambda n: "early-card" in n.classes, "EARLY")
        cls.timer = find_one(nodes, lambda n: "timer-card" in n.classes, "TIMER")
        cls.scalp = find_one(nodes, lambda n: n.attrs.get("id") == "scalpCard", "SCALP")

    def test_four_core_cards_share_one_parent(self):
        parents = [self.final.parent, self.early.parent, self.timer.parent, self.scalp.parent]
        signatures = [p.signature() if p else None for p in parents]
        self.assertTrue(all(p is parents[0] for p in parents), f"core-card parents differ: {signatures}")

    def test_all_four_are_real_card_nodes(self):
        for label, node in (
            ("FINAL", self.final), ("EARLY", self.early), ("TIMER", self.timer), ("SCALP", self.scalp),
        ):
            with self.subTest(label=label):
                self.assertIn("card", node.classes, node.signature())

    def test_parent_child_indexes_are_stable_and_distinct(self):
        parent = self.final.parent
        self.assertIsNotNone(parent)
        cards = [self.final, self.early, self.timer, self.scalp]
        indexes = [parent.children.index(c) for c in cards]
        self.assertEqual(len(set(indexes)), 4)
        self.assertTrue(all(i >= 0 for i in indexes))

    def test_single_timer_node(self):
        nodes = [n for n in self.parser.nodes if n.attrs.get("id") == "timerRemaining"]
        self.assertEqual(len(nodes), 1)


if __name__ == "__main__":
    unittest.main()
