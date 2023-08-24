# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from .blender_handler_base import BlenderHandlerBase

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")


class CyclesHandler(BlenderHandlerBase):
    """
    Render handler for Cycles
    """

    def __init__(self):
        """
        Initializes the Cycles renderer handler
        """
        super().__init__()
        self.action_dict["scene"] = self.set_scene
        self.action_dict["layer"] = self.set_layer

    def set_scene(self, data: dict) -> None:
        """
        Sets the active scene.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['scene']
        """
        scene_name = data.get("scene", None)
        if scene_name:
            scene = bpy.data.scenes.get(scene_name)
            bpy.context.window.scene = scene

            # Make sure we're using the Cycles render engine in the cycles handler
            bpy.context.window.scene.render.engine = "CYCLES"

            # The Cycles render engine always renders all layers marked for rendering from a
            # scene. We need to adjust the number of expected outputs for progress reporting.
            num_outputs = 0
            for layer in scene.view_layers:
                if layer.use:
                    num_outputs += 1

            # It is possible to produce a render without any renderable views.
            # To prevent divide-by-zero errors in the progress reporting, if num_outputs
            # is less than one, don't overwrite the default num_outputs in the adaptor.
            if num_outputs > 1:
                num_outputs = len(scene.view_layers)
                print(f"BlenderAdaptor Configuration: Performing {num_outputs} renders.")

    def set_layer(self, data: dict) -> None:
        """
        Sets the active layer.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['layer']
        """
        print("Active scene is set to use Cycles, rendering all renderable layers.")
