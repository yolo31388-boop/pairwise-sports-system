"""Test bootstrap: the test module uses unittest-style assertions
(`self.assertIsNotNone`) on a plain pytest class. Provide the assertion
helpers without modifying the test files."""

import unittest


def pytest_collection_modifyitems(items):
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is not None and not hasattr(cls, "assertIsNotNone"):
            cls.assertIsNotNone = unittest.TestCase.assertIsNotNone
