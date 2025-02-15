"""Manages a Trackable object graph."""
# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
import collections
import weakref

from tensorflow.python.trackable import base
from tensorflow.python.trackable import converter
from tensorflow.python.util import object_identity


class TrackableView(object):
  """Gathers and serializes a trackable view."""

  def __init__(self, root):
    """Configure the trackable view.

    Args:
      root: A `Trackable` object whose variables (including the variables of
        dependencies, recursively) should be saved. May be a weak reference.
    """
    # TrackableView should never contain a strong reference to root, since it
    # may result in a cycle:
    #   root -> deferred dependencies -> CheckpointPosition
    #   -> CheckpointRestoreCoordinator -> TrackableView -> root
    self._root_ref = (root if isinstance(root, weakref.ref)
                      else weakref.ref(root))

  def children(self, obj, save_type=base.SaveType.CHECKPOINT, **kwargs):
    """Returns all child trackables attached to obj.

    Args:
      obj: A `Trackable` object.
      save_type: A string, can be 'savedmodel' or 'checkpoint'.
      **kwargs: kwargs to use when retrieving the object's children.

    Returns:
      Dictionary of all children attached to the object with name to trackable.
    """
    # pylint: disable=protected-access
    obj._maybe_initialize_trackable()
    children = {}
    for name, ref in obj._trackable_children(save_type, **kwargs).items():
      ref = converter.convert_to_trackable(ref, parent=obj)
      children[name] = ref
    return children

  @property
  def root(self):
    if isinstance(self._root_ref, weakref.ref):
      derefed = self._root_ref()
      assert derefed is not None
      return derefed
    else:
      return self._root_ref

  def all_nodes(self):
    """Returns a list of all nodes from self.root using a breadth first traversal."""
    return self._all_nodes_with_paths()[0]

  def _all_nodes_with_paths(self):
    """Returns a list of all nodes and its paths from self.root using a breadth first traversal."""
    bfs_sorted = []
    to_visit = collections.deque([self.root])
    node_paths = object_identity.ObjectIdentityDictionary()
    node_paths[self.root] = ()
    while to_visit:
      current_trackable = to_visit.popleft()
      bfs_sorted.append(current_trackable)
      for name, dependency in self.children(current_trackable).items():
        if dependency not in node_paths:
          node_paths[dependency] = (
              node_paths[current_trackable] +
              (base.TrackableReference(name, dependency),))
          to_visit.append(dependency)
    return bfs_sorted, node_paths
