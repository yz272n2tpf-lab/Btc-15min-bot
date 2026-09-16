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
        cls.left = cls.final.parent
        cls.right = cls.timer.parent
        cls.primary = cls.left.parent if cls.left is not None else None

    def test_final_and_early_share_left_stack(self):
        self.assertIsNotNone(self.left)
        self.assertIs(self.early.parent, self.left)
        self.assertIn("left-stack", self.left.classes, self.left.signature())
        self.assertEqual(self.left.children.index(self.final), 0)
        self.assertEqual(self.left.children.index(self.early), 1)

    def test_timer_and_scalp_share_right_stack(self):
        self.assertIsNotNone(self.right)
        self.assertIs(self.scalp.parent, self.right)
        self.assertIn("right-stack", self.right.classes, self.right.signature())
        self.assertEqual(self.right.children.index(self.timer), 0)
        self.assertEqual(self.right.children.index(self.scalp), 1)

    def test_left_and_right_stacks_share_primary_grid(self):
        self.assertIsNotNone(self.primary)
        self.assertIs(self.right.parent, self.primary)
        self.assertEqual(self.primary.tag, "section")
        self.assertIn("primary-grid", self.primary.classes, self.primary.signature())
        self.assertNotEqual(self.primary.children.index(self.left), self.primary.children.index(self.right))

    def test_all_four_are_real_card_nodes(self):
        for label, node in (
            ("FINAL", self.final), ("EARLY", self.early), ("TIMER", self.timer), ("SCALP", self.scalp),
        ):
            with self.subTest(label=label):
                self.assertIn("card", node.classes, node.signature())

    def test_stack_hierarchy_is_exactly_two_levels_for_core_cards(self):
        self.assertIs(self.final.parent.parent, self.primary)
        self.assertIs(self.early.parent.parent, self.primary)
        self.assertIs(self.timer.parent.parent, self.primary)
        self.assertIs(self.scalp.parent.parent, self.primary)

    def test_single_timer_node(self):
        nodes = [n for n in self.parser.nodes if n.attrs.get("id") == "timerRemaining"]
        self.assertEqual(len(nodes), 1)


if __name__ == "__main__":
    unittest.main()
