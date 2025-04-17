from __future__ import annotations
import bpy                                          # type: ignore
from bpy.types import NodeTree, Node, NodeSocket    # type: ignore
from bpy.utils import register_class                # type: ignore
from bpy.utils import unregister_class              # type: ignore
import nodeitems_utils                              # type: ignore
from typing import List  
from nodeitems_utils import NodeCategory, NodeItem  # type: ignore
from nodeitems_utils import register_node_categories    # type: ignore
from nodeitems_utils import unregister_node_categories  # type: ignore
from bpy.props import (StringProperty,              # type: ignore
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       CollectionProperty,
                       EnumProperty,
                       PointerProperty
                       )

# ---------------------------------------------------------------------------------------
class CCNNodeCategory:
    # ------------------------------------------------
    def __init__(self, name: str, node_editor: CCNNodeEditor, items = None, force_overwrite: bool = False):
        self.label = name
        self.identifier = self.get_idname_from_label(name)
        self.tree_type = node_editor.bl_idname
        self.force_overwrite = force_overwrite

        self.create_items_list(items)
        self.create_dynamic_category_class()

    # ------------------------------------------------
    def create_items_list(self, items):
        if items is None:
            self.items = lambda context: []  # Empty callable
        elif callable(items):
            self.items = items  # already submitted as callable
        else:
            def items_gen(context):
                for item in items:
                    if item.poll is None or context is None or item.poll(context):
                        yield item
            self.items = items_gen  # Dynamic generator        

    # ------------------------------------------------
    def create_dynamic_category_class(self):
        self.category_class = type(
            f"{self.identifier}",
            (CCNNodeCategory,),
            {
                "identifier": self.identifier,
                "name": self.label,
                "items": self.items,
                "poll": classmethod(lambda cls, context: context.space_data.tree_type == self.tree_type),
            },
        )

    # ------------------------------------------------
    def add_nodes(self, *node_classes):
        """
        Add one or more nodes to the current category and reregisters the category
        """
        self.unregister()

        if callable(self.items):
            current_items = list(self.items(None))  # get the current items list
        else:
            current_items = self.items

        for node_class in node_classes:
            # check if the node is already in the list
            if not any(item.nodetype == node_class.bl_idname for item in current_items):
                current_items.append(NodeItem(node_class.bl_idname))

        # update the items list as new callable
        self.items = lambda context: current_items

        self.create_dynamic_category_class()
        self.register()

    # ------------------------------------------------
    @classmethod
    def get_idname_from_label(cls, label: str) -> str:
        return f"CCN_CAT_{label.replace(' ', '_').upper()}"

    # ------------------------------------------------
    def register(self):
        try:
            if self.force_overwrite:
                unregister_class(self.category_class)  # Remove previously registered class
        except:
            pass
        
        try:
            nodeitems_utils.register_node_categories(self.identifier, [self.category_class])
            print(f"Category '{self.identifier}' successfully registered.")
        except Exception as e:
            print(f"Error registering category '{self.identifier}': {e}")

    # ------------------------------------------------
    def unregister(self, remove_dynamic_class: bool = False):
        try:
            nodeitems_utils.unregister_node_categories(self.identifier)
            if remove_dynamic_class:
                self.category_class = None
            print(f"Category '{self.identifier}' successfully unregistered.")
        except Exception as e:
            print(f"Error unregistering category '{self.identifier}': {e}")
            pass  

# ---------------------------------------------------------------------------------------
class CCNNodeEditor:
    # ------------------------------------------------
    def __init__(self, name: str, icon: str = 'NODETREE', force_overwrite:bool = False):
        """
        Initializes a new node editor manager.

        Parameters:
        - name: The display name of the node tree editor.
        - icon: The icon to use for the node tree in Blender.
        - force_overwrite: If True, any registered class with the same bl_idname will be overwritten (unregistered)
        """
        self.name = name
        self.bl_icon = icon
        self.bl_idname = self.get_idname_from_label(self.name)
        self.bl_label = self.name
        self.force_overwrite = force_overwrite
        self.categories = []    # List to track all registered category classes
        # Dynamically generate a NodeTree class
        self.editor_class = type(
            f"{self.name.replace(' ', '')}NodeTree",  # Dynamic class name
            (NodeTree,),  # Base class is NodeTree
            {
                'bl_idname': self.bl_idname,  # Unique identifier for the node tree
                'bl_label':  self.bl_label,   # Display label in Blender
                'bl_icon':   self.bl_icon,    # Icon for the node tree
            }
        )
    
    # ------------------------------------------------
    @classmethod
    def get_idname_from_label(cls, label: str) -> str:
        return f"CCN_NodeEditor{label.replace(' ', '')}NodeTreeType"
    
    # ------------------------------------------------
    def get_or_create_category(self, category_name):
        """
        Retrieves an existing category or creates a new one.
        """
        for category in self.categories:
            if category.label == category_name and category.tree_type == self.bl_idname:
                return category

        # create a new category if it was not found above
        new_category = CCNNodeCategory(name = category_name,node_editor = self)
        self.categories.append(new_category)
        new_category.register()
        return new_category
        
    # ------------------------------------------------
    def add_categories(self, *category_names: str | List[str], force_overwrite: bool = False) -> List[CCNNodeCategory]:
        category_list = []
        
        if len(category_names) == 1 and isinstance(category_names[0], list):
            category_names = category_names[0]  # unpack the list

        for category_name in category_names:
            existing_category = next((c for c in self.categories if c.label == category_name), None)
            if existing_category:
                if force_overwrite:
                    existing_category.unregister()
                    self.categories.remove(existing_category)
                else:
                    print(f"Warning: Category '{category_name}' already exists.")
            category_list.append(self.get_or_create_category(category_name))                

        return category_list

    # ------------------------------------------------
    def create_categories_from_dict(self, category_dict: dict[str, list[type[Node]]], force_overwrite: bool = False):
        """
        Creates a list of categories for the "Add" menu and adds the desired nodes to each
        
        Parameters:
        - category_dict: A dictionary containing the category labels as keys and lists of node classes as values.
        - force_overwrite: specifiy if existing categories should be unregistered first.
        """
        # create category list from the dictionary        
        category_list = self.add_categories(list(category_dict.keys()), force_overwrite=force_overwrite)
        
        # add nodes to the categories
        for category in category_list:
            node_classes = category_dict.get(category.label, [])
            if node_classes:
                category.add_nodes(*node_classes)
    
    
    # ------------------------------------------------
    def register(self):
        try:
            if self.force_overwrite:
                unregister_class(self.editor_class)  # Remove previously registered class
        except:
            pass
        
        try:
            register_class(self.editor_class)
            print(f"Editor '{self.name}' successfully registered.")
        except Exception as e:
            print(f"Error registering editor '{self.name}': {e}")

    # ------------------------------------------------
    def unregister(self):
        try:
            unregister_class(self.editor_class)
            self.editor_class = None
            print(f"Editor '{self.name}' successfully unregistered.")
        except:
            pass   
        
    # ------------------------------------------------
    def unregister_all(self):
        """
        Unregister all categories in reverse order.
        """
        for category in reversed(self.categories):
            category.unregister()

        self.categories.clear()

# ----------------------------------------------------------------------------------
class CCNNodeEditorManager:
    # ------------------------------------------------
    def __init__(self):
        self.editors = []       # List to track all registered editor classes

    # ------------------------------------------------
    def is_idname_unique(self, idname: str) -> bool:
        """
        Checks if the bl_idname is unique among already registered editors.
        """
        for editor in self.editors:
            if editor.bl_idname == idname:
                return False
        return True

    # ------------------------------------------------
    def is_label_unique(self, label: str) -> bool:
        """
        Checks if the bl_label is unique among already registered editors.
        """
        for editor in self.editors:
            if editor.bl_label == label:
                return False
        return True

    # ------------------------------------------------
    def add_editor(self, name: str, icon: str = 'NODETREE', force_overwrite:bool = False):
        
        test_flag: bool
        if force_overwrite:
            test_flag = True
        else:
            test_flag = self.is_idname_unique(CCNNodeEditor.get_idname_from_label(name)) and \
                        self.is_label_unique(name)
    
        if test_flag:
            new_editor = CCNNodeEditor(name, icon, force_overwrite)
            new_editor.register()
            self.editors.append(new_editor)
            return new_editor
        else:
            print(f"Error: Could not add editor '{name}'. Name or ID is not unique.")
            return None

    # ------------------------------------------------
    def get_editor(self, name: str) -> CCNNodeEditor:
        """
        Retrieves an editor by its name.
        """
        for editor in self.editors:
            if editor.name == name:
                return editor
        return None
    
    # ------------------------------------------------
    def get_or_create_editor(self, name):
        editor = self.get_editor(name)
        if not editor:
            editor = self.add_editor(name)
        return editor

    # ------------------------------------------------
    def unregister_editor(self, name: str):
        """
        Unregisters a specific editor by its name.
        """
        editor = self.get_editor(name)
        if editor:
            editor.unregister()
            self.editors.remove(editor)
            print(f"Editor '{name}' successfully unregistered.")
        else:
            print(f"No editor with name '{name}' found.")

    # ------------------------------------------------
    def unregister_all(self):
        """
        Unregister all categories and editors in reverse order.
        """
        for editor in reversed(self.editors):
            editor.unregister_all()

        self.editors.clear()
        print("All nodes, categories, and editors successfully unregistered.")
