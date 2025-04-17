from __future__ import annotations
from bpy.utils import register_class                # type: ignore
from bpy.utils import unregister_class              # type: ignore
import nodeitems_utils                              # type: ignore

# Import modules
from . import ccn_utils           as ccnu \
             ,ColorHarmonyNodes   as chn \
             ,ObjectUtilityNodes  as oun


# ---------------------------------------------------------------------------------------
classes = [oun.CCNDynamicInputNode, oun.CCNAddDynamicInputOperator, oun.CCNCustomFloatSocket,
           oun.CCNNumberNode, oun.CCNNumberOperatorNode, oun.CCNOutputNode,
           oun.CCNColorGeneratorNode, oun.CCNObjectSelectorNode, oun.CCNUpdateNode,
           oun.CCNRefreshOperator, oun.CCNObjectTargetNode,
           chn.CCNColorOutputSocket, chn.CCNColorInputSocket, chn.CCNAngleInputSocket,
           chn.CCNHarmonyColorNode]

# ------------------------------------------------
def register():
    try:
        unregister()  # Deregistrierung aller vorherigen Klassen
    except Exception as e:
        print(f"Error during unregistering: {e}")
            
    # Register all classes
    for cls in classes:
        try:
            register_class(cls)
        except ValueError:
            print(f"{cls.__name__} is already registered, skipping...")

    node_manager = ccnu.CCNNodeEditorManager()
    node_editor  = node_manager.add_editor("Object Utility Nodes", icon="NODETREE", force_overwrite=True)
    tree_id = node_editor.bl_idname
    oun.update_tree_id(tree_id)
    
    # create dictionary
    category_dict = {
        "Math"  : [oun.CCNNumberNode, oun.CCNDynamicInputNode, oun.CCNNumberOperatorNode],
        "Object": [oun.CCNObjectSelectorNode, oun.CCNObjectTargetNode],
        "Color" : [oun.CCNColorGeneratorNode, chn.CCNHarmonyColorNode],
        "Output": [oun.CCNOutputNode],
        "Tools" : [oun.CCNUpdateNode]
    }

    # create categories and nodes
    node_editor.create_categories_from_dict(category_dict, force_overwrite=True)    

# ------------------------------------------------
def unregister():
    chn.cleanup_color_wheel_previews()

    # Unregister all classes
    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            print(f"Class {cls.__name__} was not registered.")


