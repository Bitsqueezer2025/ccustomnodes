from __future__ import annotations
import bpy                                          # type: ignore
from bpy.types import Node, NodeSocket, Operator, NodeSocketFloat, NodeSocketInt, NodeSocketColor  # type: ignore

from . import ccn_utils as ccnu
from . import ColorHarmonyNodes as chn
import math

tree_id = None              # used to assign the created editor to the "update_callback" function

def update_tree_id(new_id):
    global tree_id
    tree_id = new_id
    print(tree_id)

# -------------------------------------------------------
def update_callback(self, context):
    global tree_id
    try:
        for tree in bpy.data.node_groups:
            if tree.bl_idname == tree_id:
                process_tree(tree)
            
            # for node in tree.nodes:
            #     if isinstance(node, chn.CCNHarmonyColorNode):
            #         node.load_color_wheel_icon()     # reload color wheel
            # for node in tree.nodes:
            #     if hasattr(node, 'update'):
            #         node.update()
            
        context.view_layer.update()
    except:
        pass
    

# -------------------------------------------------------
def process_tree(node_tree):
    global icon_id
    processed_nodes = set()
    
    # function to process the tree in the right order
    def process_node(node):
        if node in processed_nodes:
            return  # Node already processed
        
        # first process the linked parent node
        for input_socket in node.inputs:
            if input_socket.is_linked:
                linked_node = input_socket.links[0].from_node
                process_node(linked_node)  # recursive

        # if isinstance(node,chn.CCNHarmonyColorNode):
        #     node.load_color_wheel_icon()
        
        # no further or no links: now process the current node
        if hasattr(node, 'update'):
            node.update()  
        processed_nodes.add(node)
    
    # first process the nodes without input
    for node in node_tree.nodes:
        process_node(node)
        # if all(not input_socket.is_linked for input_socket in node.inputs):
        #     process_node(node)

# --- General Utility Function for Socket Values ---
def get_socket_value(socket: NodeSocket):
    """
    Retrieves the value from a socket, recursively following links (e.g., through Reroute nodes).
    It fetches the *actual* data value from the source of the link or the socket's default value.
    Converts the value to the expected type based on the target socket's type.
    """
    current_socket = socket
    
    # Traverse through linked sockets until we find the actual data source
    # or an unlinked socket
    while current_socket.is_linked:
        from_socket = current_socket.links[0].from_socket
        
        # If the 'from_socket' is an output of a Reroute node,
        # we need to go to its input to find the true source.
        # Otherwise, the from_socket itself is our next candidate.
        if hasattr(from_socket.node, 'bl_idname') and from_socket.node.bl_idname == 'NodeReroute':
            # A Reroute node's output socket doesn't hold a value directly.
            # Its value comes from its *single input socket*.
            # So, we set the current_socket to the Reroute's input socket
            # to continue tracing the connection backward.
            if from_socket.node.inputs[0].is_linked:
                current_socket = from_socket.node.inputs[0].links[0].from_socket
            else:
                # Reroute node's input is not linked, so it provides no value
                current_socket = None # Break the loop, effectively meaning no value
                break
        else:
            # If it's not a Reroute node, then this 'from_socket' is our actual source.
            current_socket = from_socket
            break # Found the source, exit the loop
            
    val = None
    if current_socket:
        # Now current_socket should be the source socket 
        if hasattr(current_socket, "default_value"):
            val = current_socket.default_value
   
    # --- Type Conversion based on Target Socket Type ---

    if val is not None:
        if isinstance(socket, (NodeSocketFloat, CCNCustomFloatSocket)):
            if isinstance(val, (tuple, list, bpy.types.bpy_prop_array)) and hasattr(val, '__len__') and len(val) > 0:
                # Take the first component if it's an array/tuple (e.g., from a vector or color output)
                return float(val[0])       #type: ignore 
            
            return float(val) if val is not None else 0.0
        
        elif isinstance(socket, (NodeSocketInt, NodeSocketFloat, chn.CCNAngleInputSocket)):
            if isinstance(val, (tuple, list, bpy.types.bpy_prop_array)) and hasattr(val, '__len__') and len(val) > 0:
                # Take the first component if it's an array/tuple (e.g., from a vector or color output)
                angle_value = max(1.0, min(180.0, val[0] if val[0] is not None else 1.0))
                return float(val[0])       #type: ignore 

            angle_value = max(1.0, min(180.0, val if val is not None else 1.0))
            return angle_value
        
        elif isinstance(socket, (NodeSocketColor, chn.CCNColorInputSocket)):
            if isinstance(val, (tuple, list, bpy.types.bpy_prop_array)):
                if len(val) == 3:
                    return (*val, 1.0) # Add default alpha
                elif len(val) == 4:
                    return tuple(val)
                return val if val is not None else (0.7,0.7,0.7,1)
        
        
        # elif isinstance(socket, NodeSocketInt) or isinstance(socket, CCNCustomIntegerSocket):
        #     return int(val) if val is not None else 0
    
    return val # Return for other socket types

# -------------------------------------------------------
def get_all_target_nodes_from_socket(output_socket, visited_sockets=None, collected_nodes=None):
    if visited_sockets is None:
        visited_sockets = set()
    if collected_nodes is None:
        collected_nodes = set()

    if output_socket in visited_sockets:
        return collected_nodes
    visited_sockets.add(output_socket)

    node_tree = output_socket.node.id_data

    for link in node_tree.links:
        if link.from_socket == output_socket and not link.is_muted:
            to_socket = link.to_socket
            to_node = to_socket.node

            if to_node.type == 'REROUTE':
                reroute_output = to_node.outputs[0]
                get_all_target_nodes_from_socket(reroute_output, visited_sockets, collected_nodes)
            else:
                collected_nodes.add(to_node)

    return collected_nodes

# -------------------------------------------------------
def handle_muted_node(node):
    """
    Implements Blender-like bypass behavior for muted nodes.
    Each output will receive the value from the corresponding input if available,
    or fall back to input[0], or finally to 0.
    """
    #print(f"[Muted] Node '{node.name}' is bypassed.")

    for i, output_socket in enumerate(node.outputs):
        value = 0  # Fallback value

        # Prefer corresponding input socket
        if i < len(node.inputs) and node.inputs[i].is_linked:
            value = get_socket_value(node.inputs[i])

        # Fallback to input[0] if it's linked
        elif len(node.inputs) > 0 and node.inputs[0].is_linked:
            value = get_socket_value(node.inputs[0])

        output_socket.default_value = value
     #   print(f" → Output[{i}] = {value}")

# # -------------------------------------------------------
# class CCNMessageOperator(bpy.types.Operator):
#     bl_idname = "ccn.message"
#     bl_label = "Message"

#     message: bpy.props.StringProperty() # type: ignore

#     def execute(self, context):
#         self.report({'INFO'}, self.message)
#         return {'FINISHED'}
    
#     def invoke(self, context, event):
#         wm = context.window_manager
#         return wm.invoke_props_dialog(self)    

# # -------------------------------------------------------
# class CCNSimplePopupOperator(bpy.types.Operator):
#     bl_idname = "ccn.simple_popup"
#     bl_label = "Info Popup"

#     message: bpy.props.StringProperty() # type: ignore

#     def execute(self, context):
#         return {'FINISHED'}

#     def invoke(self, context, event):
#         def draw(self, context):
#             layout = self.layout
#             layout.label(text=self.message)

#         self.draw = draw
#         context.window_manager.invoke_popup(self, width=600)
#         return {'RUNNING_MODAL'}

# -------------------------------------------------------
class CCNUpdateNode(Node):
    '''A node that refreshes the Node-Tree on button click'''
    bl_idname = 'CCNCustomUpdateNodeType'
    bl_label = 'Update Node'
    bl_icon = 'FILE_REFRESH'

    def init(self, context):
        self.use_custom_color = True  # activates user-defined colors
        self.color = (0.6, 0.6, 0.0)

    def draw_buttons(self, context, layout):
        # add refresh button
        layout.operator("ccn.refresh_node_tree", text="Refresh Tree")

# -------------------------------------------------------
class CCNRefreshOperator(Operator):
    '''Operator to refresh the Node-Tree'''
    bl_idname = "ccn.refresh_node_tree"
    bl_label = "Refresh Node-Tree"

    def execute(self, context):
        update_callback(self, bpy.context)
        #self.report({'INFO'}, "Node-Tree refreshed")
        return {'FINISHED'}

# -------------------------------------------------------
class CCNObjectSelectorNode(Node):
    '''A node with an object selector'''
    bl_idname = 'CCNCustomObjectSelectorNodeType'
    bl_label = 'Object Selector'

    # PointerProperty for object selection
    selected_object: bpy.props.PointerProperty( # type: ignore
                                               name="Object",
                                               type=bpy.types.Object,
                                               description="Select an object from the scene",
                                               update = update_callback)

    def init(self, context):
        # Outputs for location (x, y, z)
        self.outputs.new('CCNCustomFloatSocket', "X Location")
        self.outputs.new('CCNCustomFloatSocket', "Y Location")
        self.outputs.new('CCNCustomFloatSocket', "Z Location")

        # Outputs for dimensions (x, y, z)
        self.outputs.new('CCNCustomFloatSocket', "X Dimension")
        self.outputs.new('CCNCustomFloatSocket', "Y Dimension")
        self.outputs.new('CCNCustomFloatSocket', "Z Dimension")

    def update(self):
        if self.mute:
            handle_muted_node(self)
            return  
                
        # check if an object is selected
        if self.selected_object:
            obj = self.selected_object
            if not obj or obj.name not in bpy.data.objects:
                return
            # update location values
            self.outputs["X Location"].default_value = obj.location.x
            self.outputs["Y Location"].default_value = obj.location.y
            self.outputs["Z Location"].default_value = obj.location.z

            # update dimension values
            self.outputs["X Dimension"].default_value = obj.dimensions.x
            self.outputs["Y Dimension"].default_value = obj.dimensions.y
            self.outputs["Z Dimension"].default_value = obj.dimensions.z
        else:
            # if no object is selected, set the default to 0
            for output in self.outputs:
                output.default_value = 0.0

    def draw_buttons(self, context, layout):
        layout.prop(self, "selected_object", text="Select Object")
        # show output values
        if not self.selected_object:
            layout.label(text="No object selected")

# -------------------------------------------------------
class CCNObjectTargetNode(Node):
    '''A node to set input values to an object'''
    bl_idname = 'CCNCustomObjectTargetNodeType'
    bl_label = 'Object Target'

    # PointerProperty for object selection
    selected_object: bpy.props.PointerProperty( # type: ignore
                                               name = "Object",
                                               type = bpy.types.Object,
                                               description = "Select an object from the scene which should be changed",
                                               update = update_callback)

    def init(self, context):
        # Inputs for location (x, y, z)
        self.inputs.new('CCNCustomFloatSocket', "X Location")
        self.inputs.new('CCNCustomFloatSocket', "Y Location")
        self.inputs.new('CCNCustomFloatSocket', "Z Location")

        # inputs for dimensions (x, y, z)
        self.inputs.new('CCNCustomFloatSocket', "X Dimension")
        self.inputs.new('CCNCustomFloatSocket', "Y Dimension")
        self.inputs.new('CCNCustomFloatSocket', "Z Dimension")
        
        # input for color
        self.inputs.new('CCNColorInputSocket', "Object Color")

    def assign_material_to_object(self, obj, color):
        # check if the material already exists
        mat_name = f"Material_{obj.name}"
        if mat_name not in bpy.data.materials:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
        else:
            mat = bpy.data.materials[mat_name]

        # set base color to the material
        bsdf_node = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf_node:
            # Ensure the color value is a 4-tuple (RGBA)
            if len(color) == 3:
                color = (*color, 1.0) # Add alpha if RGB
            elif len(color) != 4:
                # Fallback for unexpected color formats
                color = (0.7, 0.7, 0.7, 1.0)
            bsdf_node.inputs["Base Color"].default_value = color
        else:
            print(f"No Principled BSDF found in material {mat.name}")

        # assign the material to the object
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

    def update(self):        
        if self.selected_object:
            obj = self.selected_object

            try: # during registration bpy.data is not accessible
                if not obj or obj.name not in bpy.data.objects:
                    return
            except AttributeError:
                return

            # update location values
            for axis_idx, axis_name in enumerate(["X", "Y", "Z"]):
                location_socket = self.inputs[f"{axis_name} Location"]
                # Use get_socket_value to properly retrieve and convert the value
                location_val = get_socket_value(location_socket)
                if location_val is not None:
                    setattr(obj.location, axis_name.lower(), location_val)
                else:
                    # If not linked, set the default value of the socket to the object's current location
                    location_socket.default_value = getattr(obj.location, axis_name.lower())

            # Update dimension values via obj.scale
            dimensions_data = [
                ("X Dimension", 0, 'x'),
                ("Y Dimension", 1, 'y'),
                ("Z Dimension", 2, 'z')
            ]

            # Get the scene's unit scale (meters per Blender unit in UI)
            scene_unit_scale = bpy.context.scene.unit_settings.scale_length

            for dim_name, axis_idx, axis_char in dimensions_data:
                dimension_socket = self.inputs[dim_name]
                # desired_dim_val from socket is in "Blender Units" (what user sees in UI without suffix)
                desired_dim_val = get_socket_value(dimension_socket)
                
                if desired_dim_val is not None:
                    # Always clamp desired_dim_val to be non-negative (for safety and visual consistency if UI doesn't clamp)
                    desired_dim_val = max(0.0, desired_dim_val)

                    # Convert desired input dimension from Blender Units to Meters
                    desired_dim_val_in_meters = desired_dim_val * scene_unit_scale

                    # Determine the object's base dimension (when its scale is 1.0) in meters
                    current_obj_dim_blender_units = getattr(obj.dimensions, axis_char)
                    current_obj_scale = getattr(obj.scale, axis_char)

                    # Initialize with a fallback for cases where calculation isn't possible (e.g., scale is 0)
                    # For most standard objects (like default cube, empty), their base dimension is 2.0 BU at scale 1.0.
                    # So, if we can't calculate, we assume a base of 2.0 BU.
                    current_base_dim_in_meters = 1.0 * scene_unit_scale 

                    if current_obj_scale > 0: # Only calculate if current scale is not zero to prevent ZeroDivisionError
                        # Calculate the base dimension in Blender Units: current_displayed_dim / current_scale
                        # Then convert to meters
                        current_base_dim_in_meters = (current_obj_dim_blender_units / current_obj_scale) * scene_unit_scale
                        
                    # Prevent division by zero if base dimension is effectively zero (e.g., from an extremely small initial object)
                    current_base_dim_in_meters = max(0.0001, current_base_dim_in_meters)

                    # Calculate the new scale factor
                    new_scale = desired_dim_val_in_meters / current_base_dim_in_meters
                    setattr(obj.scale, axis_char, new_scale)
                    
                    if current_obj_scale == 0:
                        bpy.context.view_layer.update()
                        current_obj_dim_blender_units = getattr(obj.dimensions, axis_char)
                        if current_obj_dim_blender_units != desired_dim_val and current_obj_dim_blender_units > 0:
                            correction_factor = desired_dim_val / current_obj_dim_blender_units
                            current_obj_scale = getattr(obj.scale, axis_char)
                            setattr(obj.scale, axis_char, current_obj_scale * correction_factor)                            
                                                
                else:
                    # If not linked, update the default value of the socket to reflect the current object dimension (in Blender Units)
                    dimension_socket.default_value = max(0.0, getattr(obj.dimensions, axis_char))


            # Update object color
            color_socket = self.inputs["Object Color"]
            color_val = get_socket_value(color_socket)

            if color_val:
                self.assign_material_to_object(obj, color_val)

            #bpy.context.view_layer.update()

            if self.inputs["Object Color"].is_linked:
                self.value_color_property = self.inputs["Object Color"].links[0].from_socket.default_value
            else:
                self.value_color_property = self.inputs["Object Color"].default_value  # Manual input value

            self.assign_material_to_object(obj, self.value_color_property)

    def draw_buttons(self, context, layout):
        layout.prop(self, "selected_object", text="Select Object")

    
# -------------------------------------------------------
class CCNCustomFloatSocket(NodeSocket):
    bl_idname = "CCNCustomFloatSocket"
    bl_label = "Custom Float Socket"

    default_value: bpy.props.FloatProperty(# type: ignore
                                           name = "Value"
                                          ,default = 0.0
                                          ,update = lambda self, context: self.call_node_update(context)
                                          )

    def call_node_update(self, context):
        try:
            is_output_socket = any(self == sock for sock in self.node.outputs)
            is_input_socket  = any(self == sock for sock in self.node.inputs)            

            #print(f"Socket 'call_node_update': {self.name}")

            # If OUTPUT: Collect all direct target nodes and update them
            if is_output_socket:
                target_nodes = get_all_target_nodes_from_socket(self)
                for node in target_nodes:
                    if hasattr(node, 'update'):
                        #print(f" → Updating target node: {node.name}")
                        node.update()
                
            if is_input_socket:
                if self.node and hasattr(self.node, "update"):            
                    self.node.update()
        except:
            pass

    def draw(self, context, layout, node, text):
        is_output_socket = any(self == sock for sock in self.node.outputs)
        is_input_socket  = any(self == sock for sock in self.node.inputs)

        if self.is_linked:
            # If linked, only show the current value            
            linked_value = get_socket_value(self)
            
            label_text = f"{text}: {linked_value:.2f}" if linked_value is not None else f"{text}"
            layout.label(text=label_text)
        else:
            if is_output_socket:
                # outputs are read-only
                layout.label(text=f"{text}: {self.default_value:.2f}")
            else:
                # inputs without links are changeable
                layout.prop(self, "default_value", text = text)

    def draw_color(self, context, node):
        return (0.7, 0.7, 0.7, 1)  # Color Code for Float-Sockets

# -------------------------------------------------------
class CCNCustomIntegerSocket(NodeSocket):
    bl_idname = "CCNCustomIntegerSocket"
    bl_label = "Custom Integer Socket"

    _is_updating = False

    # for checks if the input noodle comes from an allowed value
    is_invalid_link_type: bpy.props.BoolProperty(default=False) # type: ignore
    
    default_value: bpy.props.IntProperty(# type: ignore
                                         name = "Value"
                                        ,default = 0
                                        ,update = lambda self, context: self.call_node_update(context)
                                        )

    def call_node_update(self, context):
        try:
            is_output_socket = any(self == sock for sock in self.node.outputs)
            is_input_socket  = any(self == sock for sock in self.node.inputs)            

            #print(f"Socket 'call_node_update': {self.name}")

            # If OUTPUT: Collect all direct target nodes and update them
            if is_output_socket:
                target_nodes = get_all_target_nodes_from_socket(self)
                for node in target_nodes:
                    if hasattr(node, 'update'):
                        #print(f" → Updating target node: {node.name}")
                        node.update()
                
            if is_input_socket:
                if self.node and hasattr(self.node, "update"):            
                    self.node.update()
        except:
            pass

    def draw(self, context, layout, node, text):
        is_output_socket = any(self == sock for sock in self.node.outputs)
        is_input_socket  = any(self == sock for sock in self.node.inputs)

        if self.is_linked:
            # If linked, only show the current value
            linked_value = get_socket_value(self)

            label_text = f"{text}: {int(linked_value)}" if linked_value is not None else f"{text}" # type:ignore
            layout.label(text=label_text)
        else:
            if is_output_socket:
                # outputs are read-only
                layout.label(text=f"{text}: {int(self.default_value)}")
            else:
                # inputs without links are changeable
                layout.prop(self, "default_value", text = text)

    def draw_color(self, context, node):                
        return (0.38, 0.62, 0.38, 1.0)  # Color Code for Integer-Sockets

# -------------------------------------------------------
class CCNNumberNode(Node):
    '''To enter a number to be used as output'''
    bl_idname = 'CCNNumberNodeType'
    bl_label = "Number"

    number: bpy.props.FloatProperty(# type: ignore
                                    name="Number"
                                   ,default = 0.0
                                   ,update = lambda self, context: self.update())

    def init(self, context):
        self.outputs.new('CCNCustomFloatSocket', "Number Output")

    @classmethod
    def poll(cls, context):
        return True
    
    def update(self):
        if self.mute:
            handle_muted_node(self)
            return  
                
        output_socket = self.outputs[0]
        output_socket.default_value = self.number

    def draw_buttons(self, context, layout):
        layout.prop(self, "number")

# -------------------------------------------------------
class CCNIntegerNumberNode(Node):
    '''To enter an integer number to be used as output'''
    bl_idname = 'CCNIntegerNumberNodeType'
    bl_label = "Integer Number"

    integer_number: bpy.props.IntProperty(# type: ignore
                                          name="Integer Number"
                                         ,default = 0
                                         ,update = lambda self, context: self.update())

    def init(self, context):
        self.outputs.new('CCNCustomIntegerSocket', "Integer Output")

    @classmethod
    def poll(cls, context):
        return True
    
    def update(self):
        if self.mute:
            handle_muted_node(self)
            return  
                
        output_socket = self.outputs[0]
        output_socket.default_value = self.integer_number

    def draw_buttons(self, context, layout):
        layout.prop(self, "integer_number")

# -------------------------------------------------------
class CCNDynamicInputNode(Node):
    '''Node with dynamically added inputs'''
    bl_idname = 'CCNDynamicInputNodeType'
    bl_label = "Dynamic Input"

    def init(self, context):
        # Initial input and output
        self.inputs.new('CCNCustomFloatSocket', "Input 1")
        self.outputs.new('CCNCustomFloatSocket', "Total Sum")
        self.outputs.new('CCNCustomFloatSocket', "Total Product")

    def call_node_update(self):
        if hasattr(self.node, "update"):
            self.node.update()
        if self.node.id_data:
            self.node.id_data.update_tag()

    def update(self):
        if self.mute:
            handle_muted_node(self)
            return  
                
        # Update outputs based on inputs
        total_sum = 0.0
        total_product = 1.0
        
        for socket in self.inputs:            
            if socket.is_linked:
                # get value from source socket
                link = socket.links[0]
                source_socket = link.from_socket
                if hasattr(source_socket, 'default_value'):
                    total_sum += source_socket.default_value
                    total_product *= source_socket.default_value
            else:
                # get value from local socket value
                if hasattr(socket, 'default_value'):
                    total_sum += socket.default_value
                    total_product *= socket.default_value

        self.outputs[0].default_value = total_sum
        self.outputs[1].default_value = total_product

    def draw_buttons(self, context, layout):
        # "+" Button to add a new input
        op = layout.operator("node.add_dynamic_input", text="Add Input", icon='ADD')
        op.node_name = self.name

# -------------------------------------------------------
class CCNAddDynamicInputOperator(Operator):
    '''Add a new input to the dynamic node'''
    bl_idname = "node.add_dynamic_input"
    bl_label = "Add Dynamic Input"

    node_name: bpy.props.StringProperty() #type: ignore
    
    @classmethod
    def poll(cls, context):
        return context.active_node is not None

    def execute(self, context):
        global tree_id

        # Find the current node editor
        node_tree = None
        for tree in bpy.data.node_groups:
            if tree.bl_idname == tree_id:
                node_tree = tree
                break
        
        if not node_tree:
            return {'CANCELLED'}

        # find the specific node which contains the button
        node_name = getattr(self, 'node_name', None)
        if node_name:
            node = node_tree.nodes.get(node_name)
            if node and hasattr(node, "inputs"):
                input_count = len(node.inputs) + 1
                node.inputs.new('CCNCustomFloatSocket', f"Input {input_count}")
                node.update()
            return {'FINISHED'}

        return {'CANCELLED'}


# -------------------------------------------------------
class CCNNumberOperatorNode(Node):
    bl_idname = 'CCNNumberOperatorNodeType'
    bl_label = "Number Operator"

    operations = [
        ('ADD', "Add", "Addition"),
        ('SUB', "Subtract", "Subtraction"),
        ('MUL', "Multiply", "Multiplication"),
        ('DIV', "Divide", "Division"),
    ]
    operation: bpy.props.EnumProperty(# type: ignore
                                      name = "Operation"
                                     ,items = operations
                                     ,default = 'ADD'
                                     ,update = lambda self, context: self.update())

    def init(self, context):
        self.inputs.new('CCNCustomFloatSocket', "Input A")
        self.inputs.new('CCNCustomFloatSocket', "Input B")
        self.outputs.new('CCNCustomFloatSocket', "Result")

    @classmethod
    def poll(cls, context):
        return True
    
    def process(self):
        input_a = 0.0
        input_b = 0.0        

        input_a = get_socket_value(self.inputs[0])
        input_b = get_socket_value(self.inputs[1])        
        
        result = 0.0
        
        if input_a is not None and input_b is not None \
            and isinstance(input_a, (float, int)) \
            and isinstance(input_b, (float, int)):
            if self.operation == 'ADD':
                result = input_a + input_b
            elif self.operation == 'SUB':
                result = input_a - input_b
            elif self.operation == 'MUL':
                result = input_a * input_b
            elif self.operation == 'DIV':
                result = input_a / input_b if input_b != 0 else 0.0

        self.outputs[0].default_value = result
        return result

    def update(self):
        if self.mute:
            handle_muted_node(self)
            return  
                
        result = self.process()
        output_socket = self.outputs[0]
        output_socket.default_value = result

    def draw_buttons(self, context, layout):
        layout.prop(self, "operation", text="Operation")

# -------------------------------------------------------
class CCNOutputNode(Node):
    '''3D Scene Output for a result value with a custom label text'''
    bl_idname = 'CCNOutputNodeType'
    bl_label = "3D View Output"

    # Label-Property for user-defined text
    label: bpy.props.StringProperty(# type: ignore
                                    name = "Label",
                                    default = "Result",
                                    description = "Label text to display in the 3D scene",
                                    update = lambda self, context: self.update()
                                   )

    def init(self, context):
        self.use_custom_color = True  # activates user-defined colors
        self.color = (0.2, 0.6, 1.0)
        self.inputs.new('NodeSocketColor', "Label Color")
        self.inputs.new('NodeSocketColor', "Value Color")
        self.inputs.new('CCNCustomFloatSocket', "Input")
        self.inputs.new('CCNCustomFloatSocket', "X Pos")
        self.inputs.new('CCNCustomFloatSocket', "Y Pos")
        self.inputs.new('CCNCustomFloatSocket', "Z Pos")
        self.inputs.new('CCNCustomFloatSocket', "X Offset")
        self.inputs.new('CCNCustomFloatSocket', "Y Offset")
        self.inputs.new('CCNCustomFloatSocket', "Z Offset")
        

    def assign_material_to_text(self, obj, color):
        # check if the material already exists
        mat_name = f"{self.name}_{obj.name}_Material"

        if mat_name not in bpy.data.materials:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
        else:
            mat = bpy.data.materials[mat_name]

        # set base color to the material
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color

        # assign the material to the object
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        mat.node_tree.update_tag()

    def get_input_value(self, name):
        if name in self.inputs and self.inputs[name].is_linked:
            return self.inputs[name].links[0].from_socket.default_value
        elif name in self.inputs:
            return self.inputs[name].default_value
        return 0.0

    def update(self):        
        if self.mute:
            handle_muted_node(self)
            return  
                
        label_text = self.label.strip() or "Result"

        # get the color values and the value to display either from local or linked socket
        label_color  = self.inputs[0].links[0].from_socket.default_value if self.inputs[0].is_linked else self.inputs[0].default_value
        value_color  = self.inputs[1].links[0].from_socket.default_value if self.inputs[1].is_linked else self.inputs[1].default_value
        result_value = self.inputs[2].links[0].from_socket.default_value if self.inputs[2].is_linked else self.inputs[2].default_value

        x_pos = self.get_input_value("X Pos") + self.get_input_value("X Offset")
        y_pos = self.get_input_value("Y Pos") + self.get_input_value("Y Offset")
        z_pos = self.get_input_value("Z Pos") + self.get_input_value("Z Offset")

        # === PARENT-EMPTY (Container for both texts)
        parent_name = f"OutputGroup_{self.name}"
        if parent_name not in bpy.data.objects:
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
            empty = bpy.context.object
            empty.empty_display_size = 0.01
            parent_obj = bpy.context.object
            parent_obj.name = parent_name
        else:
            parent_obj = bpy.data.objects[parent_name]

        if parent_obj:
            parent_obj.location = (x_pos, y_pos, z_pos)

        # === LABEL-TEXT
        label_name = f"LabelText_{self.name}"
        if label_name not in bpy.data.objects:
            bpy.ops.object.text_add(location=(0, 0, 0))
            label_obj = bpy.context.object
            label_obj.name = label_name
            if not parent_obj is self:
                label_obj.parent = parent_obj
        else:
            label_obj = bpy.data.objects[label_name]
        
        label_obj.data.body = label_text
        label_obj.data.align_x = 'LEFT'
        label_obj.data.align_y = 'BOTTOM'
        label_obj.location = (0, 0, 0)

        bb = label_obj.bound_box
        min_x = min([v[0] for v in bb])
        max_x = max([v[0] for v in bb])
        label_width_local = max_x - min_x

        # === RESULT-TEXT
        result_name = f"ResultText_{self.name}"
        if result_name not in bpy.data.objects:
            bpy.ops.object.text_add(location=(0, 0, 0))
            result_obj = bpy.context.object
            result_obj.name = result_name
            if not parent_obj is self:
                result_obj.parent = parent_obj
        else:
            result_obj = bpy.data.objects[result_name]
        
        result_obj.data.body = f"{result_value:.2f}"
        result_obj.data.align_x = 'LEFT'
        result_obj.data.align_y = 'BOTTOM'
        #result_obj.location = (label_obj.dimensions.x + 0.7, 0, 0)
        result_obj.location = (label_width_local + 0.5, 0, 0)

        self.assign_material_to_text(label_obj, label_color)
        self.assign_material_to_text(result_obj, value_color)

        bpy.context.view_layer.update()


    def draw_buttons(self, context, layout):
        layout.prop(self, "label", text="Label")

# -------------------------------------------------------
class CCNColorGeneratorNode(Node):
    '''Generates harmonic complementary color based on a base color'''
    bl_idname = 'CCNColorGeneratorNodeType'
    bl_label  = "Color Generator"

    base_color: bpy.props.FloatVectorProperty(# type: ignore
                                              name = "Base Color"
                                             ,subtype = 'COLOR'
                                             ,size = 4
                                             ,default = (1.0, 0.0, 0.0, 1.0)
                                             ,min = 0.0, max = 1.0
                                             ,description="Base color for generating complementary color"
                                             ,update = lambda self, context: self.update()
                                             )

    def init(self, context):
        self.outputs.new('CCNColorOutputSocket', "Color 1")
        self.outputs.new('CCNColorOutputSocket', "Color 2")

    def calculate_complementary(self, color):
        # Ensure the color has 4 components (RGBA)
        if len(color) == 3:  # If only RGB is present
            color = (*color, 1.0)  # Add a default Alpha value

        # Calculate the complementary color
        return (1.0 - color[0], 1.0 - color[1], 1.0 - color[2], color[3])  # Alpha remains unchanged


    def update(self):
        if self.mute:
            handle_muted_node(self)
            return  
                
        # Color 1: base color from property base_color
        base_color = self.base_color # tuple(self.base_color[:3]) + (1.0,)  # Add Alpha (1.0)
        
        # Color 2: Calculate complementary color
        complementary_color = self.calculate_complementary(base_color)

        # Set outputs
        self.outputs[0].default_value = base_color  # Set Color 1 to base_color
        self.outputs[1].default_value = complementary_color  # Set Color 2 to complementary color

    def draw_buttons(self, context, layout):
        layout.prop(self, "base_color", text="Base Color")
