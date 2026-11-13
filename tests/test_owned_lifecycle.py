"""Reproduce Undo's actual-group/tracked-group mismatch through real cleanup."""
import types
import unittest
from unittest.mock import Mock, patch
import test_visibility_lifecycle as lifecycle


class Groups:
    def __init__(self): self.values = []
    @property
    def count(self): return len(self.values)
    def item(self, index): return self.values[index]


class Group:
    def __init__(self, collection, ident, deletes=True):
        self.collection, self.id, self.deletes = collection, ident, deletes
        self.isValid = True
        collection.values.append(self)
    def deleteMe(self):
        if not self.deletes: return False
        self.collection.values.remove(self)
        self.isValid = False
        return True


class OwnedLifecycleTest(unittest.TestCase):
    tearDown = lifecycle.LifecycleTest.tearDown

    def setUp(self):
        lifecycle.LifecycleTest.setUp(self)
        self.ownership_patch.stop()  # Exercise the actual renderer ownership API.
        self.owned_collection_patch.stop()
        self.groups = Groups()
        self.state.design = types.SimpleNamespace(rootComponent=types.SimpleNamespace(customGraphicsGroups=self.groups))
        self.m.UI.messageBox = Mock()
        self.prefix = self.m.renderer.OWNERSHIP_PREFIX

    def test_refresh_reconciles_undo_revived_group_before_render_preserving_foreign(self):
        old_wrapper = Group(self.groups, self.prefix + 'm1')
        old_wrapper.deleteMe()
        revived = Group(self.groups, old_wrapper.id)  # Fusion returns a fresh wrapper.
        self.assertIsNot(old_wrapper, revived)
        foreign = Group(self.groups, 'other.addin.graphics')
        self.state.groups = []
        self.state.items = [('m1', 'radius', ('edge',))]
        def render(*args, **kwargs):
            self.assertFalse(revived.isValid, 'Undo-restored group must be removed before adding its replacement')
            return Group(self.groups, self.prefix + 'new')
        with patch.object(self.m, 'resolve', return_value=object()), \
                patch.object(self.m.renderer, 'render', side_effect=render), \
                patch.object(self.m, 'geometry_fingerprint', return_value=('current',)):
            self.assertEqual(self.state.refresh(), [])
        self.assertEqual(len(self.state.groups), 1)
        self.assertEqual(len(self.m.renderer.owned_groups(self.state.design)), 1)
        self.assertEqual(self.groups.count, 2)
        self.assertTrue(foreign.isValid)
        self.assertIn(self.state.groups[0], self.groups.values)

    def test_execute_preserves_staged_groups_and_foreign_but_removes_revived(self):
        revived = Group(self.groups, self.prefix + 'undo-restored')
        foreign = Group(self.groups, 'foreign')
        row = types.SimpleNamespace(id='m1', kind='radius', entities=('edge',), visible=True)
        context = types.SimpleNamespace(clear_preview=Mock(), visible=True,
                                        batch=types.SimpleNamespace(rows=[row], next_id=2))
        created = []
        def render(*args, **kwargs):
            group = Group(self.groups, self.prefix + 'staged')
            created.append(group)
            return group
        with patch.object(self.m, 'current_state', return_value=self.state), \
                patch.object(self.m, 'reference_for', side_effect=lambda entity: entity), \
                patch.object(self.m, 'resolve', side_effect=lambda design, ref: ref), \
                patch.object(self.m.renderer, 'render', side_effect=render), \
                patch.object(self.m, 'geometry_fingerprint', return_value=('current',)):
            self.m.Execute('add', context).notify(None)
        self.assertFalse(revived.isValid)
        self.assertTrue(foreign.isValid)
        self.assertEqual(self.state.groups, created)
        self.assertTrue(created[0].isValid)
        self.assertEqual(self.groups.count, 2)
        self.assertEqual(len(self.m.renderer.owned_groups(self.state.design)), 1)

    def test_save_cleans_revived_owned_group_even_when_runtime_tracks_none(self):
        revived = Group(self.groups, self.prefix + 'revived')
        foreign = Group(self.groups, 'foreign')
        self.assertEqual(self.state.groups, [])
        args = types.SimpleNamespace(document=self.doc, isOperationCancelled=False)
        with patch.object(self.m, 'geometry_fingerprint', return_value=('saved',)):
            self.m.DocumentEvent('saving').notify(args)
        self.assertFalse(args.isOperationCancelled)
        self.assertFalse(revived.isValid)
        self.assertTrue(foreign.isValid)
        self.assertEqual(self.groups.values, [foreign])
        self.assertTrue(self.state.removed_for_save)

    def test_save_cleanup_failure_retains_revived_group_cancels_then_retry_succeeds(self):
        revived = Group(self.groups, self.prefix + 'revived', deletes=False)
        foreign = Group(self.groups, 'foreign')
        args = types.SimpleNamespace(document=self.doc, isOperationCancelled=False)
        self.m.DocumentEvent('saving').notify(args)
        self.assertTrue(args.isOperationCancelled)
        self.assertEqual(self.state.groups, [revived])
        self.assertTrue(revived.isValid)
        revived.deletes = True
        retry = types.SimpleNamespace(document=self.doc, isOperationCancelled=False)
        with patch.object(self.m, 'geometry_fingerprint', return_value=('saved',)):
            self.m.DocumentEvent('saving').notify(retry)
        self.assertFalse(retry.isOperationCancelled)
        self.assertEqual(self.state.groups, [])
        self.assertEqual(self.groups.values, [foreign])
        self.assertTrue(self.state.removed_for_save)

    def test_unchanged_metadata_and_geometry_reconcile_undo_restored_wrapper(self):
        previous = Group(self.groups, self.prefix + 'before-no-op-edit')
        previous.deleteMe()
        revived = Group(self.groups, previous.id)
        foreign = Group(self.groups, 'foreign')
        invalid_tracked = types.SimpleNamespace(id=self.prefix + 'after-no-op-edit', isValid=False)
        self.state.items = [('m1', 'radius', ('edge',))]
        self.state.groups = [invalid_tracked]
        self.state.fingerprint = ('unchanged',)
        self.state.restore_requested = False
        def render(*args, **kwargs):
            self.assertFalse(revived.isValid)
            return Group(self.groups, self.prefix + 'reconciled')
        with patch.object(self.m, 'resolve', return_value=object()), \
                patch.object(self.m, 'geometry_fingerprint', return_value=('unchanged',)), \
                patch.object(self.m.renderer, 'render', side_effect=render):
            self.m.UpdateDimensions().notify(None)
        self.assertFalse(revived.isValid, 'Unchanged metadata must not bypass restored-group reconciliation')
        self.assertEqual(len(self.state.groups), 1)
        self.assertTrue(self.state.groups[0].isValid)
        self.assertEqual(self.m.renderer.owned_groups(self.state.design), self.state.groups)
        self.assertTrue(foreign.isValid)
        self.assertEqual(self.groups.count, 2)

    def test_after_save_equal_empty_owned_and_tracked_sets_do_not_redraw(self):
        foreign = Group(self.groups, 'foreign')
        self.state.items = [('m1', 'radius', ('edge',))]
        self.state.groups = []
        self.state.fingerprint = ('saved',)
        self.state.removed_for_save = True
        self.state.restore_requested = False
        with patch.object(self.m, 'geometry_fingerprint', return_value=('saved',)), \
                patch.object(self.m.renderer, 'render') as render:
            self.m.UpdateDimensions().notify(None)
        render.assert_not_called()
        self.assertEqual(self.state.groups, [])
        self.assertEqual(self.groups.values, [foreign])
        self.assertTrue(self.state.removed_for_save)

    def test_empty_definitions_still_remove_untracked_owned_group(self):
        revived = Group(self.groups, self.prefix + 'revived-with-empty-definitions')
        foreign = Group(self.groups, 'foreign')
        self.state.items = []
        self.state.groups = []
        self.state.restore_requested = False
        self.state.fingerprint = ('empty',)
        with patch.object(self.m, 'geometry_fingerprint', return_value=('empty',)), \
                patch.object(self.m.renderer, 'render') as render:
            self.m.UpdateDimensions().notify(None)
        self.assertFalse(revived.isValid)
        self.assertEqual(self.groups.values, [foreign])
        render.assert_not_called()
