# This file is part of Hypothesis, which may be found at
# https://github.com/HypothesisWorks/hypothesis/
#
# Most of this work is copyright (C) 2013-2020 David R. MacIver
# (david@drmaciver.com), but it contains contributions by others. See
# CONTRIBUTING.rst for a full list of people who may hold copyright, and
# consult the git log if you need to determine who owns an individual
# contribution.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at https://mozilla.org/MPL/2.0/.
#
# END HEADER

from collections import defaultdict

from hypothesis.internal.conjecture.junkdrawer import LazySequenceCopy, pop_random


def prefix_selection_order(prefix):
    """Select choices starting from ``prefix```,
    preferring to move left then wrapping around
    to the right."""

    def selection_order(depth, n):
        if depth < len(prefix):
            i = prefix[depth]
            if i >= n:
                i = n - 1
            yield from range(i, -1, -1)
            yield from range(n - 1, i, -1)
        else:
            yield from range(n - 1, -1, -1)

    return selection_order


def random_selection_order(random):
    """Select choices uniformly at random."""

    def selection_order(depth, n):
        pending = LazySequenceCopy(range(n))
        while True:
            # This will never be called with pending empty because
            # at that point the node is exhausted.
            yield pop_random(random, pending)

    return selection_order


class Chooser:
    """A source of nondeterminism for use in shrink passes."""

    def __init__(self, tree, selection_order):
        self.__selection_order = selection_order
        self.__tree = tree
        self.__node_trail = [tree.root]
        self.__choices = []
        self.__finished = False

    def choose(self, values, condition=lambda x: True):
        """Return some element of values satisfying the condition
        that will not lead to an exhausted branch, or raise DeadBranch
        if no such element exist".
        """
        assert not self.__finished
        node = self.__node_trail[-1]
        if node.live_child_count is None:
            node.live_child_count = len(values)
            node.n = len(values)

        assert node.live_child_count > 0 or len(values) == 0

        for i in self.__selection_order(len(self.__choices), len(values)):
            if node.live_child_count == 0:
                break
            if not node.children[i].exhausted:
                v = values[i]
                if condition(v):
                    self.__choices.append(i)
                    self.__node_trail.append(node.children[i])
                    return v
                else:
                    node.children[i] = DeadNode
                    node.live_child_count -= 1
        assert node.live_child_count == 0
        raise DeadBranch()

    def finish(self):
        """Record the decisions made in the underlying tree and return
        a prefix that can be used for the next Chooser to be used."""
        self.__finished = True
        assert len(self.__node_trail) == len(self.__choices) + 1

        result = tuple(self.__choices)

        self.__node_trail[-1].live_child_count = 0
        while len(self.__node_trail) > 1 and self.__node_trail[-1].exhausted:
            self.__node_trail.pop()
            assert len(self.__node_trail) == len(self.__choices)
            i = self.__choices.pop()
            target = self.__node_trail[-1]
            target.children[i] = DeadNode
            target.live_child_count -= 1

        return result


class ChoiceTree:
    """Records sequences of choices made during shrinking so that we
    can track what parts of a pass has run. Used to create Chooser
    objects that are the main interface that a pass uses to make
    decisions about what to do.
    """

    def __init__(self):
        self.root = TreeNode()

    @property
    def exhausted(self):
        return self.root.exhausted

    def step(self, selection_order, f):
        assert not self.exhausted

        chooser = Chooser(self, selection_order)
        try:
            f(chooser)
        except DeadBranch:
            pass
        return chooser.finish()


class TreeNode:
    def __init__(self):
        self.children = defaultdict(TreeNode)
        self.live_child_count = None
        self.n = None

    @property
    def exhausted(self):
        return self.live_child_count == 0


DeadNode = TreeNode()
DeadNode.live_child_count = 0


class DeadBranch(Exception):
    pass
