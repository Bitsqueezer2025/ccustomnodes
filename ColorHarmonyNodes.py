from __future__ import annotations
import bpy                                          # type: ignore
from bpy.types import Node, NodeSocket              # type: ignore
from typing import List, Tuple
import colorsys
import math
from PIL import Image, ImageDraw                    # type: ignore
from enum import Enum

import os
import tempfile

#------------------------------------------------------------------------------------------------------------------    
# Type Aliases

Point       = Tuple[float, float]   # TypeAlias for a 2D point (1 x/y-coordinate)
LineSegment = Tuple[Point, Point]   # TypeAlias for a line segment (2 x/y coordinates)

#------------------------------------------------------------------------------------------------------------------    
# constants and globals

# Flag to avoid loops in update
updating = False

COLORWHEEL_ICONSIZE             = 900
COLORWHEEL_SCALE                = 10
MARKER_SIZE                     = 20
MARKER_LINE_WIDTH               = 3
MARKER_LINE_COLOR               = (0,0,0)
LINE_WIDTH                      = 3
LINE_COLOR                      = (80,80,80)
MONOCHROMATIC_RADIUS_VALUES     = [0.8, 0.9, 1.0] # positions in percent

previous_harmony_type           = None          # to check the change of harmony type in the drop down

# Create a global preview collection for the color wheel icon
color_wheel_previews = bpy.utils.previews.new()
# cache the colorwheel image after creation to only generate it one time
cached_color_wheel_image = None

#------------------------------------------------------------------------------------------------------------------    
class Harmony(Enum):
    # harmony presets
    COMPLEMENTARY       = "COMPLEMENTARY"
    SPLIT_COMPLEMENTARY = "SPLIT_COMPLEMENTARY"
    ANALOGOUS           = "ANALOGOUS"
    TRIADIC             = "TRIADIC"
    TETRADIC_SQUARE     = "TETRADIC_SQUARE"
    TETRADIC_ANGLE      = "TETRADIC_ANGLE"
    MONOCHROMATIC       = "MONOCHROMATIC"

    #--------------------
    @staticmethod
    def get_preset_angle(harmony: 'Harmony') -> float:
        angle = 30.0
        match harmony:
            case Harmony.COMPLEMENTARY.value:
                angle = 180.0
            case Harmony.SPLIT_COMPLEMENTARY.value:
                angle = 30.0
            case Harmony.ANALOGOUS.value:
                angle = 30.0
            case Harmony.TRIADIC.value:
                angle = 120.0
            case Harmony.TETRADIC_SQUARE.value:
                angle = 90.0
            case Harmony.TETRADIC_ANGLE.value:
                angle = 90.0
            case Harmony.MONOCHROMATIC.value:
                angle = 0.0
        return angle

    #--------------------
    @staticmethod
    def get_num_color_pickers(harmony: 'Harmony') -> int:
        num_color_pickers = 1
        match harmony:
            case Harmony.COMPLEMENTARY.value:
                num_color_pickers = 2
            case Harmony.SPLIT_COMPLEMENTARY.value:
                num_color_pickers = 3
            case Harmony.ANALOGOUS.value:
                num_color_pickers = 3
            case Harmony.TRIADIC.value:
                num_color_pickers = 3
            case Harmony.TETRADIC_SQUARE.value:
                num_color_pickers = 4
            case Harmony.TETRADIC_ANGLE.value:
                num_color_pickers = 4
            case Harmony.MONOCHROMATIC.value:
                num_color_pickers = 3
        return num_color_pickers
    
    #--------------------
    @staticmethod
    def get_colors(node: CCNHarmonyColorNode, harmony: 'Harmony'):
        colors = []
        for i in range(Harmony.get_num_color_pickers(harmony)):
            output_name = f"Color {i + 1}"  # Dynamic Output-Name
            if output_name in node.outputs:
                colors.append(node.outputs[output_name].default_value)  # read the output value
        return colors        
    
    #--------------------
    @staticmethod
    def get_color_coordinates(node: CCNHarmonyColorNode, harmony: 'Harmony', radius, center) -> List[Tuple[float, float]]:
        """Returns a list of (x, y) coordinates for colors based on the given harmony type, radius, and center."""
        color_coords = []
        color_coords.append((center, center))   # always as index 0 if needed
        for i in range(Harmony.get_num_color_pickers(harmony)):
            output_name = f"Color {i + 1}"
            if output_name in node.outputs:
                color = node.outputs[output_name].default_value  # gets the output value
                x, y = HarmonyDraw.get_line_values(color, radius, center)  # calculate the coordinate
                color_coords.append((x, y))
        return color_coords

    #--------------------
    @staticmethod
    def get_line_indices(harmony: 'Harmony') -> List[Tuple[int, int]]:
        line_indices = []
        match harmony:
            case Harmony.COMPLEMENTARY.value:
                line_indices = [(1, 2)]
            case Harmony.SPLIT_COMPLEMENTARY.value | Harmony.ANALOGOUS.value:
                line_indices = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
            case Harmony.TRIADIC.value:
                line_indices = [(0, 1), (0, 2), (0, 3), (1, 2), (2, 3), (3, 1)]
            case Harmony.TETRADIC_SQUARE.value | Harmony.TETRADIC_ANGLE.value:
                line_indices = [(1, 2), (2, 3), (3, 4), (4, 1)]
            case Harmony.MONOCHROMATIC.value:
                line_indices = [(0, 1), (0, 2), (0, 3)]
        return line_indices
    
    #--------------------
    @staticmethod
    def get_line_coords(node: CCNHarmonyColorNode, harmony: 'Harmony', radius, center) -> List[LineSegment]:
        line_indices = Harmony.get_line_indices(harmony)
        color_coords = Harmony.get_color_coordinates(node, harmony, radius, center)
        
        line_coords = []
        for line_index in line_indices:
            line_coords.append((color_coords[line_index[0]], color_coords[line_index[1]]))
    
        return line_coords    
    

#------------------------------------------------------------------------------------------------------------------    
class HarmonyDraw():

    #--------------------
    @staticmethod
    def get_angle_from_rgb(color): # <<<--- function from Victor Stepanov
        """Calculates the angle (in degrees, 0-360) of a color in the color wheel based on its RGB value."""
        r, g, b = [c / 255 for c in color[:3]]
        h, _, _ = colorsys.rgb_to_hsv(r, g, b)
        angle = h * 360
        return angle

    #--------------------
    @staticmethod
    def get_line_values(color, radius, center):
        angle = HarmonyDraw.get_angle_from_rgb(color)
        x = center + radius * math.cos(math.radians(angle))
        y = center + radius * math.sin(math.radians(angle))
        return x, y

    #--------------------
    @staticmethod
    def draw_marker(image, colors, radius, center):
        """Draws color markers for a list of colors on the color wheel image."""
        draw = ImageDraw.Draw(image)
        
        colors_rgb_pil = [tuple(int(c * 255) for c in color) for color in colors] # conversion in PIL RGB-Tuple (0-255)
        
        for color_rgb_pil in colors_rgb_pil:
            x, y = HarmonyDraw.get_line_values(color_rgb_pil, radius, center)
            draw.ellipse(
                [
                    x - MARKER_SIZE,
                    y - MARKER_SIZE,
                    x + MARKER_SIZE,
                    y + MARKER_SIZE,
                ],
                outline = MARKER_LINE_COLOR,
                width = MARKER_LINE_WIDTH,
                fill = color_rgb_pil,
            )
        return image

    #--------------------
    @staticmethod
    def draw_harmony(node: CCNHarmonyColorNode, image, harmony_type, radius, center):
        """Draws harmony elements (circles, lines) on the color wheel image based on harmony type and base colors."""
        draw = ImageDraw.Draw(image)
        
        for line_points in Harmony.get_line_coords(node, harmony_type, radius, center):
            draw.line(line_points, fill = LINE_COLOR, width = LINE_WIDTH)

        colors = Harmony.get_colors(node, harmony_type)

        if harmony_type != Harmony.MONOCHROMATIC.value:
            image = HarmonyDraw.draw_marker(image, colors , radius, center)
        else:
            radius_values = MONOCHROMATIC_RADIUS_VALUES
            reversed_colors = colors[::-1]
            for i, color in enumerate(reversed_colors):
                print("Color ", color, i)
                image = HarmonyDraw.draw_marker(image, [color], radius * radius_values[i], center)

        return image


#------------------------------------------------------------------------------------------------------------------    
def rgb_to_hsv(rgba):
    """Converts RGBA color (0.0-1.0 range) to HSV color (0.0-1.0 range)."""
    rgb = rgba[:3]   # Get the RGB values only
    alpha = rgba[3]  # Get the alpha value
    hsv = colorsys.rgb_to_hsv(*rgb) # convert the RGB part only
    return hsv + (alpha,)  # Add the alpha value back


#----------------------
def hsv_to_rgb(hsva):
    """Converts HSVA color (0.0-1.0 range) to RGB color (0.0-1.0 range)."""
    hsv = hsva[:3]   # Get the HSV values only
    alpha = hsva[3]  # Get the alpha value
    rgb = colorsys.hsv_to_rgb(*hsv) # convert the HSV part only
    return rgb + (alpha,)  # Add the alpha value back

#----------------------
def get_dynamic_radius(saturation, value):
    """Calculates the dynamic radius for marker and lines based on saturation and value."""
    inner_radius = COLORWHEEL_ICONSIZE * 0.136
    outer_radius = COLORWHEEL_ICONSIZE * 0.455
    value = value / 255 # normalize to values between 0 and 1
    
    if saturation == 0:
        dynamic_radius = inner_radius * value
    else:
        value_weight = 0.5
        saturation_weight = 0.5

        # Weighted sum of normalized factors (value and reversed saturation)
        radius_factor = (1.0 - value) * value_weight + saturation * saturation_weight
        dynamic_radius = inner_radius + (outer_radius - inner_radius) * radius_factor # linear interpolation with weighted factor

    return dynamic_radius

#----------------------
def get_harmony_colors(harmony_color_node: CCNHarmonyColorNode) -> List:
    """
    Calculates harmony colors based on the base color (HSV), harmony type, and optional angle and length parameters.

    Returns:
        list: List of HSV color tuples (Hue, Saturation, Value) in the range 0.0-1.0, representing the harmony colors.
        Returns an empty list if the harmony type is unknown or no harmony colors are defined.
    """
    harmony_colors_hsv = []  # Initialize empty list for harmony colors
    
    harmony_type    = harmony_color_node.color_harmony_type
    angle           = harmony_color_node.angle
    base_color_rgb  = harmony_color_node.base_color
    base_color_hsv  = rgb_to_hsv(base_color_rgb) # Convert base color to HSV
    
    base_hue, base_saturation, base_value, base_alpha = base_color_hsv  # Unpack HSV values of the base color

    match harmony_type:
        case Harmony.COMPLEMENTARY.value:
            # Complementary Harmony: 1 color (complementary color)
            harmony_hue = (base_hue + 0.5) % 1.0  # Complementary hue is 180° (0.5 in 0.0-1.0 range) opposite
            harmony_colors_hsv = [(harmony_hue, base_saturation, base_value, base_alpha)]  # List with only the complementary color

        case Harmony.SPLIT_COMPLEMENTARY.value:
            # Split Complementary Harmony: 2 colors (split complementary colors)
            angle_fraction = angle / 360.0  # Convert angle to 0.0-1.0 range
            harmony_hue1 = ((base_hue + 0.5 - angle_fraction) % 1.0)  # -angle degrees from complementary hue
            harmony_hue2 = ((base_hue + 0.5 + angle_fraction) % 1.0)  # +angle degrees from complementary hue
            harmony_colors_hsv = [(harmony_hue1, base_saturation, base_value, base_alpha),
                                  (harmony_hue2, base_saturation, base_value, base_alpha)]  # List with both split complementary colors

        case Harmony.ANALOGOUS.value:
            # Analogous Harmony: 2 colors (adjacent colors)
            angle_fraction = angle / 360.0  # Convert angle to 0.0-1.0 range
            harmony_hue1 = ((base_hue - angle_fraction) % 1.0)  # -angle degrees from base hue
            harmony_hue2 = ((base_hue + angle_fraction) % 1.0)  # +angle degrees from base hue
            harmony_colors_hsv = [(harmony_hue1, base_saturation, base_value, base_alpha),
                                  (harmony_hue2, base_saturation, base_value, base_alpha)]  # List with both analogous colors

        case Harmony.TRIADIC.value:
            # Triadic Harmony: 2 colors (equilateral triangle in the color wheel)
            angle_fraction = angle / 360.0  # Convert angle to 0.0-1.0 range
            harmony_hue1 = ((base_hue - angle_fraction) % 1.0)  # -angle degrees from base hue
            harmony_hue2 = ((base_hue + angle_fraction) % 1.0)  # +angle degrees from base hue
            harmony_colors_hsv = [(harmony_hue1, base_saturation, base_value, base_alpha),
                                  (harmony_hue2, base_saturation, base_value, base_alpha)]  # List with both triadic colors

        case Harmony.TETRADIC_SQUARE.value:
            # Tetradic (Square) Harmony: 3 colors (square in the color wheel)
            harmony_hue1 = (base_hue + 1/4) % 1.0  # +90 degrees from base hue
            harmony_hue2 = (base_hue + 0.5) % 1.0  # +180 degrees from base hue
            harmony_hue3 = (base_hue + 3/4) % 1.0  # +270 degrees from base hue
            harmony_colors_hsv = [(harmony_hue1, base_saturation, base_value, base_alpha),
                                  (harmony_hue2, base_saturation, base_value, base_alpha),
                                  (harmony_hue3, base_saturation, base_value, base_alpha)]  # List with all tetradic colors

        case Harmony.TETRADIC_ANGLE.value:
            # Tetradic (Square) Harmony: 3 colors (square in the color wheel)
            angle_fraction = angle / 360.0  # Convert angle to 0.0-1.0 range
            
            harmony_hue1 = (base_hue - angle_fraction) % 1.0  # +90 degrees from base hue
            harmony_hue2 = (base_hue + angle_fraction) % 1.0  # +180 degrees from base hue
            harmony_hue3 = (harmony_hue1 - angle_fraction) % 1.0  # +270 degrees from base hue
            harmony_colors_hsv = [(harmony_hue1, base_saturation, base_value, base_alpha),
                                  (harmony_hue2, base_saturation, base_value, base_alpha),
                                  (harmony_hue3, base_saturation, base_value, base_alpha)]  # List with all tetradic colors

        case Harmony.MONOCHROMATIC.value:
            # Monochromatic Harmony: 2 colors (variations of the base color in saturation)
            if base_saturation > 0.0:
                harmony_saturation1 = max(0, base_saturation - 0.2)  # Reduce saturation by 0.2 (min 0.0)
                harmony_saturation2 = max(0, base_saturation - 0.4)  # Reduce saturation by 0.4 (min 0.0)
                harmony_colors_hsv = [(base_hue, harmony_saturation1, base_value, base_alpha), 
                                      (base_hue, harmony_saturation2, base_value, base_alpha)]  # List with both monochromatic colors
            else:
                harmony_value1 = max(0, base_value - 0.2)  # Reduce saturation by 0.2 (min 0.0)
                harmony_value2 = max(0, base_value - 0.4)  # Reduce saturation by 0.4 (min 0.0)
                harmony_colors_hsv = [(0.0, 0.0, harmony_value1, base_alpha),
                                      (0.0, 0.0, harmony_value2, base_alpha)]  # List with both monochromatic colors

        case _:
            print(f"Unknown harmony type: {harmony_type}") 
            return []  # Return empty list if harmony type is unknown

    return harmony_colors_hsv  # Return the list of harmony colors (HSV tuples)

#------------------------------------------------------------------------------------------------------------------    
def update_dynamic_color_wheel(self, context):  # self, context are needed because this is called from the property change
    """Clears the old dynamic icon and loads a new one to update the UI, and updates color picker values."""
    global updating
    global previous_harmony_type
    
    if updating: # Loop test
        return # return to avoid loop

    updating = True # set Loop flag

    if hasattr(self, "update"):
        self.update()

    updating = False # reset Loop-Flag

#------------------------------------------------------------------------------------------------------------------
class CCNColorOutputSocket(NodeSocket):
    bl_idname = "CCNColorOutputSocket"
    bl_label = "Color"

    default_value: bpy.props.FloatVectorProperty(# type: ignore
                                                 name = "Color"
                                                ,subtype = "COLOR"
                                                ,size = 4
                                                ,min = 0.0
                                                ,max = 1.0
                                                ,default = (0.3, 0.3, 0.3, 1.0)
                                                ,update = update_dynamic_color_wheel
                                                )

    def draw(self, context, layout, node, text):
        row = layout.row()
        col = row.column()
        col.label(text="RGBA")
        col = row.column()
        col.scale_y = 0.6
        col.prop(self, "default_value", text="")  

    def draw_color(self, context, node):
        return self.default_value  # return the color of the socket itself

#------------------------------------------------------------------------------------------------------------------
class CCNColorRGBOutputSocket(NodeSocket):
    bl_idname = "CCNColorRGBOutputSocket"
    bl_label = "Color"

    default_value: bpy.props.FloatVectorProperty(# type: ignore
                                                 name = "Color"
                                                ,subtype = "COLOR"
                                                ,size = 3
                                                ,min = 0.0
                                                ,max = 1.0
                                                ,default = (0.3, 0.3, 0.3)
                                                ,update = update_dynamic_color_wheel
                                                )

    def draw(self, context, layout, node, text):
        row = layout.row()
        col = row.column()
        col.label(text="RGB")
        col = row.column()
        col.scale_y = 0.6
        col.prop(self, "default_value", text="")  

    def draw_color(self, context, node):
        return (*self.default_value, 1.0)  # return the color of the socket itself

#------------------------------------------------------------------------------------------------------------------
class CCNColorInputSocket(NodeSocket):
    bl_idname = "CCNColorInputSocket"
    bl_label = "Color Input"

    default_value: bpy.props.FloatVectorProperty( # type: ignore
                                                 name = "Base Color"
                                                ,subtype = "COLOR"
                                                ,size = 4
                                                ,min = 0.0
                                                ,max = 1.0
                                                ,default = (0.3, 0.3, 0.3, 1.0)
                                                ,update = lambda self, context: self.call_node_update()
                                                )

    def call_node_update(self):
        if hasattr(self.node, "update"):
            self.node.update()

    def draw(self, context, layout, node, text):
        if not self.is_linked:
            layout.prop(self, "default_value", text=text)
        else:
            layout.label(text=text)

    def draw_color(self, context, node):
        return self.default_value

#------------------------------------------------------------------------------------------------------------------    
class CCNAngleInputSocket(NodeSocket):
    bl_idname = "CCNAngleInputSocket"
    bl_label = "Float Input"

    default_value: bpy.props.FloatProperty( # type: ignore
                                            name = "Angle"
                                           ,default = 30.0
                                           ,min = 0.0 
                                           ,max = 180.0 
                                           ,update = lambda self, context: self.call_node_update()
                                          )

    def call_node_update(self):
        if hasattr(self.node, "update"):
            self.node.update()

    def draw(self, context, layout, node, text):
        if not self.is_linked:
            layout.prop(self, "default_value", text=text)
        else:
            link = self.links[0]
            if link:
                source_socket = link.from_socket
                if hasattr(source_socket, "default_value"):
                    angle_value = max(1.0, min(180.0, source_socket.default_value))
                    layout.label(text=f"{text}: {angle_value:.2f}")
                else:
                    layout.label(text=text)            

    def draw_color(self, context, node):
        return (0.5, 0.7, 1.0, 1.0)


#------------------------------------------------------------------------------------------------------------------    
class CCNHarmonyColorNode(Node):
    '''Node for generating harmonic colors'''
    bl_idname = 'CCNHarmonyColorNodeType'
    bl_label = 'Harmony Color'
    bl_icon = 'COLOR'
    bl_width_default = 300

    color_harmony_type: bpy.props.EnumProperty( # type: ignore
                                               name = "",
                                               description = "The color harmony which you want to visualize",
                                               items = [(harmony.value, harmony.name.replace('_', ' ').title(), f"{harmony.name.replace('_', ' ').title()} Harmony") for harmony in Harmony], 
                                               default = Harmony.COMPLEMENTARY.value, 
                                               update = update_dynamic_color_wheel
                                              )
    previous_harmony_type: bpy.props.StringProperty( # type: ignore
                                                    name = "Previous Harmony Type",
                                                    default = ""
                                                   )

    auto_link: bpy.props.BoolProperty( # type: ignore
                                      name = "",
                                      description = "If enabled, generated Shader RGB Nodes will be linked to material settings, if available." \
                                                    "These are ""Base Color"", ""Coat"", ""Emission"", ""Specular""",
                                      default = False,
                                      update = update_dynamic_color_wheel
                                     )

    base_color: bpy.props.FloatVectorProperty(#type: ignore
                                              name = '', subtype = 'COLOR_GAMMA', 
                                              size = 4, min = 0.0, max = 1.0, default = (1.0, 0.0, 0.0, 1.0),
                                              description = "Only this color can be changed, the other colors will be calculated using " \
                                                            "the selected harmony",
                                              update = update_dynamic_color_wheel
                                             )

    angle: bpy.props.FloatProperty(# type: ignore
                                   name="Angle",
                                   min=1.0, max=180.0,
                                   default=30.0,
                                   description="Angle for color harmony",
                                   update = update_dynamic_color_wheel                                              
                                  )
    
    icon_id: bpy.props.IntProperty(default=-1)  # type: ignore

    def init(self, context):
        # Inputs: Base color and angle
        self.inputs.new('CCNColorInputSocket', "Base Color")
        self.inputs.new('CCNAngleInputSocket', "Angle")
        self.previous_harmony_type = self.color_harmony_type
        
        # Outputs: up to five colors
        for i in range(1,5):
            self.outputs.new("CCNColorOutputSocket", f"Color {i}")
        
        for i in range(1,5):
            self.outputs.new("CCNColorRGBOutputSocket", f"ColorRGB {i}")            

    def update(self):
        angle_reset = False
        
        harmony_type = self.color_harmony_type
        if self.previous_harmony_type != harmony_type:   # reset the angle/length properties if the harmony type was changed
            self.angle = Harmony.get_preset_angle(harmony_type)
            angle_reset = True
            self.previous_harmony_type = harmony_type        
        
        # update the harmonic colors
        if self.inputs["Angle"].is_linked:
            # get the value from the linked node
            link = self.inputs["Angle"].links[0]  # get the connection
            source_socket = link.from_socket      # get the source socket

            # try to get the right value from the source node
            if hasattr(source_socket, "default_value"):
                self.angle = max(1.0, min(180.0, source_socket.default_value))
        else:
            if not angle_reset:
                self.angle = self.inputs["Angle"].default_value
                
        if self.inputs["Base Color"].is_linked:
            link = self.inputs["Base Color"].links[0]
            source_socket = link.from_socket
            #source_node = link.from_node

            if hasattr(source_socket, "default_value"):
                self.base_color = source_socket.default_value
        else:                
            self.base_color = self.inputs["Base Color"].default_value

        harmonic_colors_rgb = [] # list of harmonic colors
        harmony_colors_hsv = get_harmony_colors(self)

        # convert the hsv colors back to rgb
        harmonic_colors_rgb = [hsv_to_rgb(hsv_color) for hsv_color in harmony_colors_hsv]

        # Set outputs
        # base color to Color 1 always:
        if f"Color 1" in self.outputs:
            self.outputs[f"Color 1"].default_value = self.base_color

        if f"ColorRGB 1" in self.outputs:
            self.outputs[f"ColorRGB 1"].default_value = self.base_color[:3]
        for i, color in enumerate(harmonic_colors_rgb):
            # Color 1 is always the base value
            if f"Color {i + 2}" in self.outputs:
                self.outputs[f"Color {i + 2}"].default_value = color

            if f"ColorRGB {i + 2}" in self.outputs:
                self.outputs[f"ColorRGB {i + 2}"].default_value = color[:3]
        self.load_color_wheel_icon()

    
    def draw_buttons(self, context, layout):
        layout.prop(self, "color_harmony_type", text="Harmony")

        if self.color_harmony_type in [Harmony.SPLIT_COMPLEMENTARY.value
                                      ,Harmony.ANALOGOUS.value
                                      ,Harmony.TRIADIC.value
                                      ,Harmony.TETRADIC_ANGLE.value]:
            temp_angle = Harmony.get_preset_angle(self.color_harmony_type)
            layout.label(text=f"{temp_angle:.2f}° preset angle)")
            layout.label(text=f"Angle setting is active!")

        if context.space_data.tree_type == 'ShaderNodeTree':
            layout.operator("node.generate_harmony_shader", text="Generate Harmony Colors", icon='NODE').node_name = self.name
            layout.prop(self, "auto_link", text="Auto Link")

        if self.icon_id != -1:
            layout.template_icon(icon_value = self.icon_id, scale = COLORWHEEL_SCALE)
        else:
            layout.label(text="Icon Color Wheel Image not available!")

    #----------------------
    def generate_base_color_wheel(self):
        """Generates and returns the base color wheel without harmony elements."""
        global cached_color_wheel_image  # Zugriff auf die globale Variable für den Cache

        if cached_color_wheel_image is None:
            width, height = COLORWHEEL_ICONSIZE, COLORWHEEL_ICONSIZE
            center_x, center_y = width // 2, height // 2
            radius = min(center_x, center_y) * 0.95
            wheel_radius = radius
             
            # generate the color wheel image if it is not in the cache
            image = Image.new("RGBA", (width, height), (0,0,0, 0)) # Black RGBA image
            draw = ImageDraw.Draw(image)

            # 1.1 Draw Color Wheel Base (using PIL ImageDraw)
            for angle in range(361):
                radians = math.radians(angle)
                hue = angle / 360.0

                # draw several circles for color steps to white
                num_radius_steps = 50 # number of steps. Higher values gets finer results but calculation time increases.
                for radius_step in range(num_radius_steps, 0, -1):
                    radial_factor = radius_step / num_radius_steps # Normalized radial factor (0.0 centre, 1.0 outer ring)
                    # Reduce saturation 
                    saturation = radial_factor 
                    value = 1.0 - radial_factor

                    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
                    color_rgb_pil = tuple(int(c * 255) for c in (r, g, b))

                    start_angle = angle
                    end_angle = angle + 1
                    current_radius = (wheel_radius * radial_factor + wheel_radius * 0.45) * 0.7

                    # Pieslice for current step
                    draw.pieslice((center_x - current_radius
                                  ,center_y - current_radius
                                  ,center_x + current_radius
                                  ,center_y + current_radius)
                                  ,start_angle, end_angle, fill = color_rgb_pil)

            spacer_ring_radius_factor = 0.3
            spacer_ring_inner_radius = wheel_radius * spacer_ring_radius_factor # radius of the transparent disc

            # transparent ring between colors and greyscales
            draw.ellipse((center_x - spacer_ring_inner_radius,
                          center_y - spacer_ring_inner_radius,
                          center_x + spacer_ring_inner_radius,
                          center_x + spacer_ring_inner_radius),
                          fill=None, outline=(0, 0, 0, 0))

            num_grayscale_steps = 15 
            inner_radius_factor = 0.29
            inner_radius = wheel_radius * inner_radius_factor

            for grayscale_step in range(num_grayscale_steps, 0, -1): # loop for grayscales
                radial_factor = grayscale_step / num_grayscale_steps # Normalized radial factor (1.0 inner ring, 0.0 centre)
                value = radial_factor
                saturation = 0.0
                hue = 0.0

                r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
                color_rgb_pil = tuple(int(c * 255) for c in (r, g, b))

                current_radius = (inner_radius * radial_factor)

                # draw greyscale from white to black
                draw.ellipse((center_x - current_radius,
                              center_y - current_radius,
                              center_x + current_radius,
                              center_y + current_radius),
                              fill=color_rgb_pil)
                
            cached_color_wheel_image = image # save color wheel to cache        
        return cached_color_wheel_image

    # ---------------------
    def load_color_wheel_icon(self):
        """Generates the harmonic color wheel dynamically using PIL and returns the icon_id."""
        global color_wheel_previews
        global cached_color_wheel_image
        
        icon_key = self.name # Unique key for the dynamic icon
        temp_filepath = os.path.join(tempfile.gettempdir(), f"{self.name}_icon.png")
        
        # reload a copy from cache to not use the reference to the cached picture
        base_image = self.generate_base_color_wheel() 
        image = base_image.copy()
                                  
        # 2. Draw Harmony Elements (Markers, Lines) using draw_harmony function
        base_color_rgb_pil     = tuple(int(c * 255) for c in self.base_color) # PIL RGB-Tuple 0 - 255
        base_color_hsv         = rgb_to_hsv(base_color_rgb_pil) # HSV-Tuple 0.0 - 1.0
        dynamic_radius         = get_dynamic_radius(base_color_hsv[1], base_color_hsv[2])
        
        # draw markers and lines
        image_with_harmony = HarmonyDraw.draw_harmony(self, image
                                                     ,self.color_harmony_type
                                                     ,dynamic_radius
                                                     ,image.width // 2)

        # 3. Save PIL Image to temporary file and load as Blender Preview Icon        
        image_with_harmony.save(temp_filepath) # Save PIL image to temporary file
        
        if color_wheel_previews is None:
            color_wheel_previews = bpy.utils.previews.new()
        
        if icon_key in color_wheel_previews:
            del color_wheel_previews[icon_key]
        
        try:
            icon = color_wheel_previews.load(icon_key, temp_filepath, 'IMAGE')
            _dummy = icon.image_size[0] + icon.image_size[1]
        except Exception as e:
            print(f"Error loading color wheel image: {e}")
            return -1

        self.icon_id = color_wheel_previews[icon_key].icon_id
        return self.icon_id # Icon ID

# ---------------------------------------------------------------------------------------
class CCN_OT_GenerateHarmonyShader(bpy.types.Operator):
    """Creates four RGBA shader nodes which are usable as input for the shader editor color values.
    Auto link to four color values of the material if this option is enabled."""
    bl_idname = "node.generate_harmony_shader"
    bl_label = "Generate Harmony Shader Colors"

    node_name: bpy.props.StringProperty() # type: ignore
    
    def execute(self, context):
        node = context.space_data.edit_tree.nodes.get(self.node_name)
        if not node:
            self.report({'WARNING'}, f"Node '{self.node_name}' not found.")
            return {'CANCELLED'}

        mat = bpy.context.object.active_material
        if not mat or not mat.use_nodes:
            self.report({'WARNING'}, "No active material with nodes.")
            return {'CANCELLED'}

        nt = mat.node_tree
        nodes = nt.nodes

        created_nodes = []
        y_pos = 400

        frame = None
        frame_name = f"Frame_{node.name}"

        for n in nodes:
            if n.type == 'FRAME' and n.name == frame_name:
                frame = n
                break

        if not frame:
            frame = nodes.new(type='NodeFrame')
            frame.label = node.name
            frame.name = frame_name
            frame.location = (-400, y_pos + 100)
            frame.color = (0.2, 0.5, 1.0) # light blue
            frame.use_custom_color = True

        for i in range(1, 5):
            output_name = f"Color {i}"
            if output_name in node.outputs:
                color = node.outputs[output_name].default_value
                node_label = f"{node.name}_Color{i}"

                existing_node = None
                for n in nodes:
                    if n.type == 'RGB' and n.label == node_label:
                        existing_node = n
                        break

                if existing_node:
                    rgb_node = existing_node
                    rgb_node.outputs[0].default_value = color
                else:
                    rgb_node = nodes.new(type="ShaderNodeRGB")
                    rgb_node.location = (-300, y_pos)
                    rgb_node.outputs[0].default_value = color
                    rgb_node.label = node_label
                    rgb_node.width = 180
                    rgb_node.parent = frame
                    y_pos -= 180

                created_nodes.append(rgb_node)                

        # Auto-Link if active
        if getattr(node, "auto_link", False):
            target_node = None
            for n in nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    target_node = n
                    break

            if target_node:
                links = nt.links
                input_names = ["Base Color", "Specular Tint", "Coat Tint", "Emission Color", ]
                for rgb_node, input_name in zip(created_nodes, input_names):
                    if input_name in target_node.inputs:
                        links.new(rgb_node.outputs[0], target_node.inputs[input_name])

        self.report({'INFO'}, f"{len(created_nodes)} Harmony Shader Colors generated!")        
        return {'FINISHED'}


# ---------------------------------------------------------------------------------------
class CCN_OT_GenerateMaterials(bpy.types.Operator):
    bl_idname = "node.generate_materials"
    bl_label = "Generate & Assign Materials"

    node_name: bpy.props.StringProperty() # type: ignore

    @classmethod
    def poll(cls, context):
        return isinstance(context.active_node, CCNAutoShaderGeneratorNode)

    def execute(self, context):
        node = context.space_data.edit_tree.nodes.get(self.node_name)
        if not node:
            self.report({'WARNING'}, f"Node '{self.node_name}' not found.")
            return {'CANCELLED'}

        generated_names = []

        for i, socket in enumerate(node.inputs):
            if not isinstance(socket, CCNColorInputSocket):
                continue

            if socket.is_linked:
                from_socket = socket.links[0].from_socket
                color = getattr(from_socket, "default_value", (0.0, 0.0, 0.0, 1.0))
            else:
                color = socket.default_value

            mat_name = f"CCNMat_{node.name}_{i+1}"
            mat = bpy.data.materials.get(mat_name)
            if not mat:
                mat = bpy.data.materials.new(name = mat_name)
                mat.use_nodes = True

            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                if len(color) == 3:
                    color = (*color, 1.0)   # add alpha value if the color is RGB instead of RGBA
                bsdf.inputs["Base Color"].default_value = color

            generated_names.append(mat_name)

            # assign the material
            target_obj = getattr(node, f"obj{i+1}", None)
            if target_obj and target_obj.type == 'MESH':
                if mat.name not in target_obj.data.materials:
                    target_obj.data.materials.append(mat)
                target_obj.active_material = mat

        node.update_material_names(generated_names)
        self.report({'INFO'}, f"{len(generated_names)} Materials generated and assigned.")
        return {'FINISHED'}



# ---------------------------------------------------------------------------------------
class CCNAutoShaderGeneratorNode(Node):
    '''Node to create up to four materials from the input colors and assign it to selected objects'''
    bl_idname = "CCNAutoShaderGeneratorNodeType"
    bl_label = "Auto Shader Generator"
    bl_icon = "MATERIAL"

    # material names
    mat1: bpy.props.StringProperty(name="Material 1")     # type: ignore
    mat2: bpy.props.StringProperty(name="Material 2")     # type: ignore
    mat3: bpy.props.StringProperty(name="Material 3")     # type: ignore
    mat4: bpy.props.StringProperty(name="Material 4")     # type: ignore

    # object assignment
    obj1: bpy.props.PointerProperty(type=bpy.types.Object)     # type: ignore
    obj2: bpy.props.PointerProperty(type=bpy.types.Object)     # type: ignore
    obj3: bpy.props.PointerProperty(type=bpy.types.Object)     # type: ignore
    obj4: bpy.props.PointerProperty(type=bpy.types.Object)     # type: ignore

    def init(self, context):
        for i in range(4):
            self.inputs.new("CCNColorInputSocket", f"Color {i+1}")

    def update(self):
        for i, socket in enumerate(self.inputs):
            mat_name = f"CCNMat_{self.name}_{i+1}"
            mat = bpy.data.materials.get(mat_name)
            
            if not mat:          
                continue
            
            if socket.is_linked:
                from_socket = socket.links[0].from_socket
                color = getattr(from_socket, "default_value", (0.0, 0.0, 0.0, 1.0))
            else:
                color = socket.default_value            

            if mat.use_nodes:  # Sicherstellen, dass Nodes aktiviert sind
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    if len(color) == 3:
                        color = (*color, 1.0)   # Falls RGB, füge Alpha hinzu
                    bsdf.inputs["Base Color"].default_value = color
            
            # assign the material
            target_obj = getattr(self, f"obj{i+1}", None)
            if target_obj and target_obj.type == 'MESH':
                if mat.name not in target_obj.data.materials:
                    target_obj.data.materials.append(mat)
                target_obj.active_material = mat

    def draw_buttons(self, context, layout):
        layout.operator("node.generate_materials", text="Generate & Assign").node_name = self.name
        
        col = layout.column(align=True)
        col.label(text="Assign To Objects:")
        col.prop(self, "obj1", text="Object 1")
        col.prop(self, "obj2", text="Object 2")
        col.prop(self, "obj3", text="Object 3")
        col.prop(self, "obj4", text="Object 4")

        col.separator()
        col.label(text="Materials:")
        for mat in [self.mat1, self.mat2, self.mat3, self.mat4]:
            if mat:
                col.label(text=mat, icon="CHECKMARK")
            else:
                col.label(text="Not yet generated!", icon="ERROR")


    def update_material_names(self, names):
        self.mat1, self.mat2, self.mat3, self.mat4 = (names + [""] * 4)[:4]
        
# ---------------------------------------------------------------------------------------
def cleanup_color_wheel_previews():
    global color_wheel_previews
    if color_wheel_previews is not None:
        bpy.utils.previews.remove(color_wheel_previews)
        color_wheel_previews = None

