from __future__ import annotations
import bpy                                          # type: ignore
from bpy.types import Node, NodeSocket, Operator    # type: ignore

from . import ccn_utils as ccnu
from . import ColorHarmonyNodes as chn

tree_id = None              # used to assign the created editor to the "update_callback" function

def update_tree_id(new_id):
    global tree_id
    tree_id = new_id
    print(tree_id)

# -------------------------------------------------------
def update_callback(self, context):
    global tree_id
    for tree in bpy.data.node_groups:
        if tree.bl_idname == tree_id:
            process_tree(tree)
            
            # for node in tree.nodes:
            #     if isinstance(node, chn.CCNHarmonyColorNode):
            #         node.load_color_wheel_icon()     # reload color wheel
            # for node in tree.nodes:
            #     if hasattr(node, 'update'):
            #         node.update()
    bpy.context.view_layer.update()

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
        self.report({'INFO'}, "Node-Tree refreshed")
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
        if self.selected_object:
            layout.label(text=f"X Location: {self.outputs['X Location'].default_value:.2f}")
            layout.label(text=f"Y Location: {self.outputs['Y Location'].default_value:.2f}")
            layout.label(text=f"Z Location: {self.outputs['Z Location'].default_value:.2f}")
            layout.label(text=f"X Dimension: {self.outputs['X Dimension'].default_value:.2f}")
            layout.label(text=f"Y Dimension: {self.outputs['Y Dimension'].default_value:.2f}")
            layout.label(text=f"Z Dimension: {self.outputs['Z Dimension'].default_value:.2f}")
        else:
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
            for axis in ["X", "Y", "Z"]:
                location_socket = self.inputs[f"{axis} Location"]
                socket = self.inputs[f"{axis} Location"]
                if socket.is_linked:
                    linked_socket = socket.links[0].from_socket
                    setattr(obj.location, axis.lower(), linked_socket.default_value)
                else:
                    location_socket.default_value = getattr(obj.location, axis.lower())

            # update dimension values
            socket = self.inputs["X Dimension"]
            if socket.is_linked:
                linked_socket = socket.links[0].from_socket
                obj.dimensions.x = linked_socket.default_value
            else:
                self.inputs["X Dimension"].default_value = obj.dimensions.x

            socket = self.inputs["Y Dimension"]
            if socket.is_linked:
                linked_socket = socket.links[0].from_socket
                obj.dimensions.y = linked_socket.default_value
            else:
                self.inputs["Y Dimension"].default_value = obj.dimensions.y

            socket = self.inputs["Z Dimension"]
            if socket.is_linked:
                linked_socket = socket.links[0].from_socket
                obj.dimensions.z = linked_socket.default_value
            else:
                self.inputs["Z Dimension"].default_value = obj.dimensions.z

            if self.inputs["Object Color"].is_linked:
                self.value_color_property = self.inputs["Object Color"].links[0].from_socket.default_value
            else:
                self.value_color_property = self.inputs["Object Color"].default_value  # Manual input value

            self.assign_material_to_object(obj, self.value_color_property)

    def draw_buttons(self, context, layout):
        layout.prop(self, "selected_object", text="Select Object")

        layout.label(text="Location Values:")
        for axis in ["X", "Y", "Z"]:
            socket = self.inputs[f"{axis} Location"]
            if socket.is_linked:
                linked_socket = socket.links[0].from_socket
                value = linked_socket.default_value
            else:
                value = socket.default_value
            layout.label(text=f"{axis} Location: {value:.2f}")

        layout.label(text="Dimension Values:")
        for axis in ["X", "Y", "Z"]:
            socket = self.inputs[f"{axis} Dimension"]
            if socket.is_linked:
                linked_socket = socket.links[0].from_socket
                value = linked_socket.default_value
            else:
                value = socket.default_value
            layout.label(text=f"{axis} Dimension: {value:.2f}")

# -------------------------------------------------------

class CCNCustomFloatSocket(NodeSocket):
    bl_idname = "CCNCustomFloatSocket"
    bl_label = "Custom Float Socket"

    _is_updating = False
    
    default_value: bpy.props.FloatProperty(# type: ignore
                                           name = "Value"
                                          ,default = 0.0
                                          ,update = lambda self, context: self.call_node_update(context)
                                          )

    def call_node_update(self, context):
        if CCNCustomFloatSocket._is_updating:
            return
        
        try:
            CCNCustomFloatSocket._is_updating = True
            if self.node and hasattr(self.node, "update"):            
                self.node.update()
        finally:
            CCNCustomFloatSocket._is_updating = False

    def draw(self, context, layout, node, text):
        is_output_socket = False
        socket_value = self.default_value
        
        for output_socket in self.node.outputs:
            if output_socket == self:
                is_output_socket = True
                break

        if self.is_linked:
            if not is_output_socket:
                for input_socket in self.node.inputs:
                    if input_socket == self:
                        socket_value = input_socket.links[0].from_socket.default_value
                        break
        
        layout.label(text=f"{text}: {socket_value:.2f}")        

    def draw_color(self, context, node):
        return (0.5, 0.7, 1.0, 1.0)  # Farbcode für Float-Sockets

# -------------------------------------------------------
class CCNNumberNode(Node):
    '''To enter a number to be used as output'''
    bl_idname = 'CCNNumberNodeType'
    bl_label = "Number"

    number: bpy.props.FloatProperty(# type: ignore
                                    name="Number"
                                   ,default = 0.0
                                   ,update = update_callback)

    def init(self, context):
        self.outputs.new('NodeSocketFloat', "Number Output")

    @classmethod
    def poll(cls, context):
        return True
    
    def update(self):
        output_socket = self.outputs[0]
        output_socket.default_value = self.number

    def draw_buttons(self, context, layout):
        layout.prop(self, "number")

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
                                     ,update = update_callback)

    def init(self, context):
        self.inputs.new('CCNCustomFloatSocket', "Input A")  # Standard-Sockets for tests
        self.inputs.new('CCNCustomFloatSocket', "Input B")
        self.outputs.new('CCNCustomFloatSocket', "Result")

    @classmethod
    def poll(cls, context):
        return True
    
    def process(self):
        if self.inputs[0].is_linked:
            input_a = self.inputs[0].links[0].from_socket.default_value
        else:
            input_a = self.inputs[0].default_value
        
        # Check Input B
        if self.inputs[1].is_linked:
            input_b = self.inputs[1].links[0].from_socket.default_value
        else:
            input_b = self.inputs[1].default_value
        
        result = 0.0

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
                                    update = update_callback
                                   )

    def init(self, context):
        self.use_custom_color = True  # activates user-defined colors
        self.color = (0.2, 0.6, 1.0)
        self.inputs.new('NodeSocketColor', "Label Color")
        self.inputs.new('NodeSocketColor', "Value Color")
        self.inputs.new('NodeSocketFloat', "Input")

    def assign_material_to_text(self, obj, color):
        # check if the material already exists
        mat_name = f"Material_{obj.name}"
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

    def update(self):
        # check if inputs are available and set standard values
        if self.inputs[0].is_linked:
            self.label_color = self.inputs[0].links[0].from_socket.default_value
        else:
            self.label_color = self.inputs[0].default_value  # Manual input value

        if self.inputs[1].is_linked:
            self.value_color_property = self.inputs[1].links[0].from_socket.default_value
        else:
            self.value_color_property = self.inputs[1].default_value  # Manual input value
            
        # get the input value from the socket
        if self.inputs[2].is_linked:
            result_value = self.inputs[2].links[0].from_socket.default_value
        else:
            result_value = 0  # Fallback value if no result is connected

        # text for result and label
        label_text = self.label if self.label.strip() else "Result"
        result_text = f"{result_value:.2f}"

        # Create or modify the label text object
        if "LabelText" not in bpy.data.objects:
            bpy.ops.object.text_add(location=(10, 0, 0))
            label_obj = bpy.context.object
            label_obj.name = "LabelText"
        else:
            label_obj = bpy.data.objects["LabelText"]
        label_obj.data.body = label_text

        if label_obj:
            x_pos = label_obj.location.x + label_obj.dimensions.x + 0.5           
        else:
            x_pos = 0.0

        # create or modify the result text
        if "ResultText" not in bpy.data.objects:
            bpy.ops.object.text_add(location=(x_pos, 0, 0))
            result_obj = bpy.context.object
            result_obj.name = "ResultText"
        else:
            result_obj = bpy.data.objects["ResultText"]
            result_obj.location.x = x_pos
        result_obj.data.body = result_text

        self.assign_material_to_text(label_obj, self.label_color)
        self.assign_material_to_text(result_obj, self.value_color_property)
        
        bpy.context.view_layer.update()

    def draw_buttons(self, context, layout):
        layout.prop(self, "label", text="Label")

class CCNColorGeneratorNode(Node):
    '''Generates harmonic colors based on a base color'''
    bl_idname = 'CCNColorGeneratorNodeType'
    bl_label  = "Color Generator"

    base_color: bpy.props.FloatVectorProperty(# type: ignore
                                              name = "Base Color"
                                             ,subtype = 'COLOR'
                                             ,size = 4
                                             ,default = (1.0, 0.0, 0.0, 1.0)
                                             ,min = 0.0, max = 1.0
                                             ,description="Base color for generating harmonic colors"
                                             ,update = update_callback
                                             )

    def init(self, context):
        self.outputs.new('NodeSocketColor', "Color 1")
        self.outputs.new('NodeSocketColor', "Color 2")

    def calculate_complementary(self, color):
        # Ensure the color has 4 components (RGBA)
        if len(color) == 3:  # If only RGB is present
            color = (*color, 1.0)  # Add a default Alpha value

        # Calculate the complementary color
        return (1.0 - color[0], 1.0 - color[1], 1.0 - color[2], color[3])  # Alpha remains unchanged


    def update(self):
        # Color 1: base color from property base_color
        base_color = self.base_color # tuple(self.base_color[:3]) + (1.0,)  # Add Alpha (1.0)
        
        # Color 2: Calculate complementary color
        complementary_color = self.calculate_complementary(base_color)

        # Set outputs
        self.outputs[0].default_value = base_color  # Set Color 1 to base_color
        self.outputs[1].default_value = complementary_color  # Set Color 2 to complementary color

    def draw_buttons(self, context, layout):
        layout.prop(self, "base_color", text="Base Color")
