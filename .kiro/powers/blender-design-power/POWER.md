---
name: "blender-design-power"
displayName: "Blender Design Power"
description: "Structured design assistant for Blender features in Deadline Cloud. Creates comprehensive design documents covering data structures, UX changes, job templates, and adapter modifications."
keywords: ["blender", "design", "python", "bpy", "cycles", "eevee"]
author: "AWS Deadline Cloud Team"
---

# Blender Design Power

## Overview

A structured design assistant for creating comprehensive feature designs for Blender integration with AWS Deadline Cloud. This power helps create well-structured design documents following a consistent four-section format that covers all aspects of implementation.

## Code Snippet Style Guide

When including code in design documents, use **concise inline snippets** in the main sections and put **full implementations in an appendix**.

### Inline Code Format

Show only the relevant changes with context:

```python
def existing_function():
    ...existing logic...
    
    # NEW: Add feature X support
    if feature_x_enabled:
        self._configure_feature_x(data)
    
    ...rest of function...
```

### Appendix Format

Put complete implementations in a clearly marked appendix section:

```markdown
---

## Appendix: Full Code Implementations

<!-- REVIEW: New render handler implementation -->

### A.1 CyclesHandler.configure_render (Full Implementation)

\`\`\`python
def configure_render(self, data: dict) -> None:
    """Full implementation here..."""
    # Complete code
\`\`\`
```

### Guidelines

1. **Data structures are the exception**: Always show full definitions - they anchor the design
2. **Other sections**: Show what changes and where, not full implementations
3. **Use `...` or comments** to indicate existing/unchanged code
4. **Flag new sections** with `<!-- REVIEW: description -->` comments in the appendix
5. **Don't include review tags** in final generated code

## Research Requirements

Before finalizing any design, research Blender Python API (bpy), Cycles/Eevee renderer APIs, and internet sources. Refer to **research-guide.md** for details.

## Key Technical Patterns

Refer to **research-guide.md** for bpy patterns, renderer detection, scene manipulation, and render settings access.

## External References

Refer to **external-references.md** for GitHub discussions and documentation links.

## Blender-Specific Considerations

### Blender Python API (bpy)
- Scene access: `bpy.context.scene`, `bpy.data.scenes`
- Render settings: `scene.render`, `scene.cycles`, `scene.eevee`
- File paths: `bpy.path.abspath()` for resolving relative paths
- Operators: `bpy.ops.*` for UI operations

### Render Engines
- **Cycles**: Path tracing renderer (`scene.cycles`)
- **Eevee**: Real-time renderer (`scene.eevee`)
- **Workbench**: Viewport renderer
- Detection: `scene.render.engine` returns 'CYCLES', 'BLENDER_EEVEE', etc.

### Add-on Structure
- Manifest: `blender_manifest.toml` (Blender 4.2+) or `bl_info` dict
- Registration: `register()` and `unregister()` functions
- Operators: Classes inheriting from `bpy.types.Operator`
- Panels: Classes inheriting from `bpy.types.Panel`

### Job Submission Patterns
- Scene file handling: `.blend` files
- Asset references: Textures, caches, libraries
- Output paths: Frame sequences, render layers
- Frame ranges: `scene.frame_start`, `scene.frame_end`, `scene.frame_step`
