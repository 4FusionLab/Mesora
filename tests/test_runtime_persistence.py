import json
import unittest
from types import SimpleNamespace

from Mesora.dimensions.model import Dimension, EntityReference, KINDS, SchemaError, serialize
from Mesora.dimensions.persistence import GROUP, NAME, MAX_BYTES, PersistenceError, save
from Mesora.dimensions.runtime_persistence import load_state, save_state
class Attributes:
    def __init__(self):
        self.data = {}
        self.writes = 0

    def itemByName(self, group, name):
        return self.data.get((group, name))

    def add(self, group, name, value):
        self.writes += 1
        self.data[group, name] = SimpleNamespace(value=value)
        return self.data[group, name]


class RuntimePersistenceTest(unittest.TestCase):
    def setUp(self):
        self.design = SimpleNamespace(attributes=Attributes())

    def test_all_runtime_types_restore_references_settings_and_next_id(self):
        refs = (EntityReference('native', 'occurrence'), EntityReference('second'))
        items = [('m' + str(i), kind, refs[:count])
                 for i, (kind, count) in enumerate(KINDS.items(), 1)]
        offsets = {ident: i * .2 for i, (ident, _, _) in enumerate(items)}
        self.assertTrue(save_state(self.design, items, offsets, {'m2'}, False))
        restored = load_state(self.design)
        self.assertEqual(restored.items, items)
        self.assertEqual(restored.offsets, offsets)
        self.assertEqual(restored.hidden_ids, {'m2'})
        self.assertFalse(restored.visible)
        self.assertEqual(restored.next_id, 8)
        payload = self.design.attributes.itemByName(GROUP, NAME).value
        self.assertNotIn('value', json.loads(payload)['dimensions'][0])
        writes = self.design.attributes.writes
        self.assertFalse(save_state(self.design, items, offsets, {'m2'}, False))
        self.assertEqual(self.design.attributes.writes, writes)

    def test_legacy_uuid_references_migrate_without_geometry_or_data_loss(self):
        dimension = Dimension.create('distance', [EntityReference('a'), EntityReference('b', 'occ')])
        data = json.loads(serialize([dimension]))
        data['schema_version'] = 1
        self.design.attributes.add(GROUP, NAME, json.dumps(data))
        restored = load_state(self.design)
        self.assertEqual(restored.items, [(dimension.id, dimension.kind, dimension.references)])
        self.assertEqual(restored.next_id, 1)
        save_state(self.design, restored.items, restored.offsets, restored.hidden_ids, restored.visible)
        self.assertEqual(json.loads(self.design.attributes.itemByName(GROUP, NAME).value)['schema_version'], 2)

    def test_clear_round_trip_and_new_empty_document_is_not_modified(self):
        self.assertFalse(save_state(self.design, [], {}, set(), True))
        save_state(self.design, [('m12', 'radius', (EntityReference('a'),))], {}, set(), True)
        self.assertTrue(save_state(self.design, [], {}, set(), True))
        self.assertEqual(load_state(self.design).items, [])

    def test_unrecognized_settings_are_not_silently_destroyed(self):
        dimension = Dimension.create('radius', [EntityReference('a')], {'future_setting': 12})
        save(self.design, [dimension], True)
        payload = self.design.attributes.itemByName(GROUP, NAME).value
        with self.assertRaises(SchemaError):
            save_state(self.design, [], {}, set(), True)
        self.assertEqual(self.design.attributes.itemByName(GROUP, NAME).value, payload)

    def test_malformed_future_and_unknown_data_are_never_overwritten(self):
        valid = json.loads(serialize([Dimension('m1', 'radius', (EntityReference('a'),))]))
        variants = ['{broken', '{"schema_version":99}',
                    '{"schema_version":2,"schema_version":1}',
                    json.dumps(dict(valid, future_data=True))]
        for location, invalid in [('placement', {'offset': float('nan')}),
                                  ('placement', {'offset': True}),
                                  ('display', {'visible': 'yes'})]:
            candidate = json.loads(json.dumps(valid))
            candidate['dimensions'][0][location] = invalid
            variants.append(json.dumps(candidate))
        for payload in variants:
            with self.subTest(payload=payload):
                self.design.attributes.add(GROUP, NAME, payload)
                with self.assertRaises(SchemaError):
                    save_state(self.design, [], {}, set(), True)
                self.assertEqual(self.design.attributes.itemByName(GROUP, NAME).value, payload)

    def test_oversized_existing_data_is_preserved_and_other_document_is_isolated(self):
        payload = 'x' * (MAX_BYTES + 1)
        self.design.attributes.add(GROUP, NAME, payload)
        with self.assertRaises(PersistenceError):
            load_state(self.design)
        with self.assertRaises(PersistenceError):
            save_state(self.design, [], {}, set(), True)
        self.assertEqual(self.design.attributes.itemByName(GROUP, NAME).value, payload)
        self.assertEqual(load_state(SimpleNamespace(attributes=Attributes())).items, [])

    def test_duplicate_or_unknown_runtime_ids_and_invalid_settings_fail_closed(self):
        item = ('m1', 'radius', (EntityReference('a'),))
        for items, offsets, hidden in [([item, item], {}, set()),
                                       ([item], {'m2': 0}, set()),
                                       ([item], {}, {'m2'}),
                                       ([('m0', 'radius', item[2])], {}, set()),
                                       ([item], {'m1': float('inf')}, set())]:
            with self.subTest(items=items, offsets=offsets, hidden=hidden):
                with self.assertRaises(SchemaError):
                    save_state(self.design, items, offsets, hidden, True)
                self.assertIsNone(self.design.attributes.itemByName(GROUP, NAME))


if __name__ == '__main__':
    unittest.main()
