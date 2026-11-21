"""Stamp both pytest evidence files with the invocation and original node ID."""

from uuid import uuid4

import pytest


RUN_ID_KEY = pytest.StashKey[str]()
RUN_PROPERTY = "proofscope_run_id"
NODE_PROPERTY = "proofscope_nodeid"


def pytest_configure(config):
    """Use one invocation marker across the controller and workers (issue #8)."""
    if hasattr(config, "workerinput"):
        config.stash[RUN_ID_KEY] = config.workerinput[RUN_PROPERTY]
    else:
        config.stash[RUN_ID_KEY] = uuid4().hex


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    """Pass the controller marker to an xdist worker before collection (issue #8)."""
    node.workerinput[RUN_PROPERTY] = node.config.stash[RUN_ID_KEY]


def pytest_collection_modifyitems(config, items):
    """Keep pytest's full identity alongside the JUnit name (issue #8)."""
    for item in items:
        item.user_properties.extend([
            (RUN_PROPERTY, config.stash[RUN_ID_KEY]),
            (NODE_PROPERTY, item.nodeid),
        ])
