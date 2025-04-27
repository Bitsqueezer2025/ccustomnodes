from __future__ import annotations
import bpy                                          # type: ignore
from bpy.utils import register_class                # type: ignore
from bpy.utils import unregister_class              # type: ignore
import nodeitems_utils                              # type: ignore

# Import modules
from . import ccn_utils           as ccnu \
             ,ColorHarmonyNodes   as chn \
             ,ObjectUtilityNodes  as oun

class CCN_MT_geometry_add_harmony_menu(bpy.types.Menu):
    bl_idname = "CCN_MT_geometry_add_harmony_menu"
    bl_label  = "Harmony Color Nodes"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'ShaderNodeTree' # 'GeometryNodeTree' to put it into Geometry Node Editor

    def draw(self, context):
        layout = self.layout
        layout.operator("node.add_node", text="Harmony Color Node").type = "CCNHarmonyColorNodeType"
# ---------------------------------------------------------------------------------------
classes = [oun.CCNDynamicInputNode, oun.CCNAddDynamicInputOperator, oun.CCNCustomFloatSocket,
           oun.CCNNumberNode, oun.CCNNumberOperatorNode, oun.CCNOutputNode,
           oun.CCNColorGeneratorNode, oun.CCNObjectSelectorNode, oun.CCNUpdateNode,
           oun.CCNRefreshOperator, oun.CCNObjectTargetNode,
           chn.CCNColorOutputSocket, chn.CCNColorInputSocket, chn.CCNAngleInputSocket,
           chn.CCNColorRGBOutputSocket, chn.CCNHarmonyColorNode, chn.CCN_OT_GenerateHarmonyShader,
           CCN_MT_geometry_add_harmony_menu,
           chn.CCNAutoShaderGeneratorNode, chn.CCN_OT_GenerateMaterials]
           #oun.CCNMessageOperator, oun.CCNSimplePopupOperator]

# ---------------------------------------------------------------------------------------
def add_harmony_node_menu(self, context):
    layout = self.layout
    layout.menu("CCN_MT_geometry_add_harmony_menu", text="Color Tools")

# ------------------------------------------------
def register():
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
        "Math"      : [oun.CCNNumberNode, oun.CCNDynamicInputNode, oun.CCNNumberOperatorNode],
        "Object"    : [oun.CCNObjectSelectorNode, oun.CCNObjectTargetNode],
        "Color"     : [oun.CCNColorGeneratorNode, chn.CCNHarmonyColorNode],
        "Material"  : [chn.CCNAutoShaderGeneratorNode],
        "Output"    : [oun.CCNOutputNode],
        "Tools"     : [oun.CCNUpdateNode]
    }

    # create categories and nodes
    node_editor.create_categories_from_dict(category_dict, force_overwrite=True)   
    # adds the harmony color node to the standard Shader Editor
    bpy.types.NODE_MT_add.append(add_harmony_node_menu) 

# ------------------------------------------------
def unregister():
    chn.cleanup_color_wheel_previews()

    # Unregister all classes
    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            print(f"Class {cls.__name__} was not registered.")

    bpy.types.NODE_MT_add.remove(add_harmony_node_menu)

