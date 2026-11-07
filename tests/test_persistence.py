import unittest
from types import SimpleNamespace

from dimensions.model import Dimension, EntityReference, SchemaError
from dimensions.persistence import GROUP, NAME, load, save


class Attributes:
    def __init__(self):
        self.data = {}

    def itemByName(self, group, name):
        return self.data.get((group, name))

    def add(self, group, name, value):
        self.data[group, name] = SimpleNamespace(value=value)
        return self.data[group, name]


class PersistenceTest(unittest.TestCase):
    def test_document_isolation_and_clear_round_trip(self):
        first, second = SimpleNamespace(attributes=Attributes()), SimpleNamespace(attributes=Attributes())
        dim = Dimension.create('radius', [EntityReference('reference')])
        save(first, [dim], True)
        self.assertEqual(load(first), ([dim], True))
        self.assertEqual(load(second), ([], True))
        save(first, [], False)
        self.assertEqual(load(first), ([], False))

    def test_corrupt_data_fails_without_writing(self):
        design = SimpleNamespace(attributes=Attributes())
        design.attributes.add(GROUP, NAME, '{bad json')
        with self.assertRaises(SchemaError):
            load(design)
        with self.assertRaises(SchemaError):
            save(design, [], True)
        self.assertEqual(design.attributes.itemByName(GROUP, NAME).value, '{bad json')
