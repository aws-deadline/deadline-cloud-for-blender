# Research Guide

## Blender Python API (bpy) Resources

### Official Documentation
- [Blender Python API Documentation](https://docs.blender.org/api/current/) - Complete API reference
- [Blender Python API Quick Start](https://docs.blender.org/api/current/info_quickstart.html) - Getting started guide
- [Blender Python API Best Practices](https://docs.blender.org/api/current/info_best_practice.html) - Recommended patterns

### Render Engine APIs
- [Cycles API Reference](https://docs.blender.org/api/current/bpy.types.CyclesRenderSettings.html) - Cycles render settings
- [Eevee API Reference](https://docs.blender.org/api/current/bpy.types.SceneEEVEE.html) - Eevee render settings
- [Render Settings](https://docs.blender.org/api/current/bpy.types.RenderSettings.html) - General render configuration

### Scene and Data Access
- [Scene API](https://docs.blender.org/api/current/bpy.types.Scene.html) - Scene properties and methods
- [Context API](https://docs.blender.org/api/current/bpy.context.html) - Accessing current context
- [Data API](https://docs.blender.org/api/current/bpy.data.html) - Accessing Blender data blocks

### File and Path Handling
- [Path Module](https://docs.blender.org/api/current/bpy.path.html) - Path utilities including `abspath()`
- [File I/O](https://docs.blender.org/api/current/bpy.ops.wm.html#module-bpy.ops.wm) - File operations

## Key Patterns

### Renderer Detection
```python
# Get current render engine
engine = bpy.context.scene.render.engine
# Returns: 'CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'BLENDER_WORKBENCH'
```

### Scene Manipulation
```python
# Access current scene
scene = bpy.context.scene

# Access all scenes
for scene in bpy.data.scenes:
    print(scene.name)

# Switch active scene
bpy.context.window.scene = bpy.data.scenes['SceneName']
```

### Render Settings Access
```python
# General render settings
scene.render.resolution_x
scene.render.resolution_y
scene.render.fps

# Cycles-specific settings
scene.cycles.samples
scene.cycles.device

# Eevee-specific settings
scene.eevee.taa_render_samples
scene.eevee.use_gtao
```

### Frame Range
```python
# Get frame range
start = scene.frame_start
end = scene.frame_end
step = scene.frame_step
```

## Research Workflow

1. **Check Official Docs First** - Always start with the official Blender Python API documentation
2. **Test in Blender Console** - Use Blender's Python console to experiment with API calls
3. **Check Version Compatibility** - Note which Blender versions support specific features
4. **Review Existing Code** - Look at similar implementations in the codebase
5. **Search Community Resources** - Blender Stack Exchange and forums for real-world examples
