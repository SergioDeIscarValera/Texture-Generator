bl_info = {
    "name": "Texture Generator",
    "author": "Sergio de Iscar Valera",
    "version": (1, 6, 10),
    "blender": (4, 2, 0),
    "location": "UV Editor > Sidebar > Tools",
    "description": "A Blender add-on integrated with the UV Editor to generate textures using remote AI APIs. Supports groups of faces with custom descriptions and colors.",
    "category": "UV",
}

import bpy
import os
import tempfile
import urllib.request
import json
import time
import base64
import random
import string
import bmesh
from bpy.types import PropertyGroup
from bpy.props import StringProperty, CollectionProperty, IntProperty

class TextureGeneratorGroup(PropertyGroup):
    """Property group to store face group data"""
    name: StringProperty(
        name="Group Description",
        description="Description for the group of faces (e.g., 'Cara del personaje')",
        default="Group"
    )
    face_indices: StringProperty(
        name="Face Indices",
        description="JSON-encoded list of face indices in this group",
        default="[]"
    )
    face_count: IntProperty(
        name="Face Count",
        description="Number of faces in this group",
        default=0
    )

class TextureGeneratorAddGroupOperator(bpy.types.Operator):
    """Operator to add a new face group from selected faces"""
    bl_idname = "uv.texture_generator_add_group"
    bl_label = "Add Face Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or context.mode != 'EDIT_MESH':
            self.report({'ERROR'}, "Select a mesh in Edit Mode!")
            return {'CANCELLED'}
        
        # Verificar límite de 4 grupos
        if len(context.scene.texture_generator_groups) >= 4:
            self.report({'ERROR'}, "Maximum of 4 groups reached!")
            return {'CANCELLED'}
        
        # Obtener caras seleccionadas
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)
        selected_faces = [f.index for f in bm.faces if f.select]
        if not selected_faces:
            self.report({'ERROR'}, "No faces selected! Please select at least one face to create a group.")
            return {'CANCELLED'}
        
        # Añadir grupo
        group = context.scene.texture_generator_groups.add()
        group.name = f"Group {len(context.scene.texture_generator_groups)}"
        group.face_count = len(selected_faces)
        group.face_indices = json.dumps(selected_faces)
        print(f"DEBUG: Added group '{group.name}' with indices: {group.face_indices}")
        
        self.report({'INFO'}, f"Added group '{group.name}' with {group.face_count} faces")
        return {'FINISHED'}

class TextureGeneratorRemoveGroupOperator(bpy.types.Operator):
    """Operator to remove a face group"""
    bl_idname = "uv.texture_generator_remove_group"
    bl_label = "Remove Face Group"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, context):
        context.scene.texture_generator_groups.remove(self.index)
        self.report({'INFO'}, f"Removed group at index {self.index}")
        return {'FINISHED'}

class TextureGeneratorSelectGroupFacesOperator(bpy.types.Operator):
    """Operator to select faces of a group"""
    bl_idname = "uv.texture_generator_select_group_faces"
    bl_label = "Select Group Faces"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object!")
            return {'CANCELLED'}
        
        # Cambiar a modo Edit
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        
        # Desseleccionar todas las caras
        for face in bm.faces:
            face.select = False
        
        # Seleccionar caras del grupo
        group = context.scene.texture_generator_groups[self.index]
        face_indices = json.loads(group.face_indices)
        print(f"DEBUG: Selecting faces for group '{group.name}': {face_indices}")
        for face_idx in face_indices:
            if face_idx < len(bm.faces):
                bm.faces[face_idx].select = True
        
        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"Selected {len(face_indices)} faces for group '{group.name}'")
        return {'FINISHED'}

class TextureGeneratorOverwriteGroupFacesOperator(bpy.types.Operator):
    """Operator to overwrite faces of a group with currently selected faces"""
    bl_idname = "uv.texture_generator_overwrite_group_faces"
    bl_label = "Overwrite Group Faces"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or context.mode != 'EDIT_MESH':
            self.report({'ERROR'}, "Select a mesh in Edit Mode!")
            return {'CANCELLED'}
        
        # Obtener caras seleccionadas
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)
        selected_faces = [f.index for f in bm.faces if f.select]
        if not selected_faces:
            self.report({'ERROR'}, "No faces selected! Please select at least one face to overwrite the group.")
            return {'CANCELLED'}
        
        # Sobreescribir grupo
        group = context.scene.texture_generator_groups[self.index]
        group.face_count = len(selected_faces)
        group.face_indices = json.dumps(selected_faces)
        print(f"DEBUG: Overwrote group '{group.name}' with indices: {group.face_indices}")
        
        self.report({'INFO'}, f"Overwrote group '{group.name}' with {group.face_count} faces")
        return {'FINISHED'}

class TextureGeneratorPreferences(bpy.types.AddonPreferences):
    """Preferences for the Texture Generator add-on"""
    bl_idname = __name__

    api_key: StringProperty(
        name="Replicate API Key",
        default="",
        subtype='PASSWORD',
        description="Enter your Replicate API key here."
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_key")

class TextureGeneratorOperator(bpy.types.Operator):
    """Operator to generate a texture using an AI prompt, style, and model"""
    bl_idname = "uv.texture_generator"
    bl_label = "Generate Texture"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Obtener preferencias del add-on
        prefs = context.preferences.addons[__name__].preferences
        api_key = prefs.api_key
        
        if not api_key:
            self.report({'ERROR'}, "Replicate API key not set. Configure it in Add-on Preferences.")
            return {'CANCELLED'}
        
        # Obtener el prompt, estilo y modelo
        sub_prompt = context.scene.texture_generator_prompt
        style = context.scene.texture_generator_style
        model = context.scene.texture_generator_model
        use_custom_colors = context.scene.texture_generator_use_custom_colors
        
        # Obtener colores si se usan custom
        if use_custom_colors:
            color1 = context.scene.texture_generator_color1
            color2 = context.scene.texture_generator_color2
            color3 = context.scene.texture_generator_color3
            color4 = context.scene.texture_generator_color4
            colors_info = f"{color1[:]}, {color2[:]}, {color3[:]}, {color4[:]}"
        else:
            colors_info = "Random"
        
        # Mapa de estilos con descripciones detalladas
        style_descriptions = {
            'REALISTIC': "Photorealistic, ultra-detailed, 8K resolution, realistic lighting, DSLR quality, sharp textures, natural materials",
            'CARTOON': "Cartoonish, bold outlines, vibrant colors, flat shading, stylized design, clean and exaggerated features",
            'ANIME': "Anime-inspired, smooth gradients, vibrant and expressive colors, soft shading, clean lines, stylized proportions",
            'PIXEL_ART': "Pixel art style, retro 16-bit aesthetic, distinct pixelated edges, limited color palette, blocky textures"
        }
        style_description = style_descriptions.get(style, "Photorealistic, ultra-detailed, 8K resolution, realistic lighting, DSLR quality, sharp textures, natural materials")
        
        # Construir el prompt base actualizado para Nano Banana
        prompt_base = (
            "This is a flat 2D UV layout map for 3D model texturing. It represents unwrapped surfaces of a 3D object, "
            "with islands and shapes that must be filled exactly as they are – do not alter the layout, proportions, or boundaries. "
            "Ignore any natural scale or perspective; adapt all content perfectly to fit the UV islands without distortions or stretching. "
            "The colors in this reference image are only markers to identify different UV regions (like labels); do not use, replicate, or incorporate these colors in the output – they are guides only for area identification. "
            "Fill the empty shapes and contours of the UV layout exactly with the following content: {sub_prompt}. "
            "Ensure the fill perfectly matches the UV islands without distortions, maintaining sharp edges and precise boundaries. "
            "Apply the visual style: {style_description}, with the color palette: {colors}. "
            "Fill every part of the UV layout completely, with no empty or unedited areas; ensure 100% coverage of all islands and shapes. "
        )
        # Añadir descripciones de grupos con colores
        group_colors = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 1.0, 0.0)]  # Rojo, Verde, Azul, Amarillo
        color_names = ["red", "green", "blue", "yellow"]
        groups = context.scene.texture_generator_groups
        if groups:
            group_prompt = "Use the following color mappings for specific areas: "
            for i, group in enumerate(groups[:4]):
                group_prompt += f"The {color_names[i]} areas correspond to '{group.name}', fill with {group.name.lower()} texture; "
            prompt_base += group_prompt
        prompt = prompt_base + "Generate a clean, high-resolution 2D image with seamless textures and no overlaps, ready for 3D texturing, without adding elements outside the original layout."
        
        # Sustituir valores en el prompt
        prompt = prompt.format(
            sub_prompt=sub_prompt,
            style_description=style_description,
            colors=colors_info
        )
        print(f"DEBUG: Generated prompt: {prompt}")
        
        # Verificar que hay un objeto mesh seleccionado
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object!")
            return {'CANCELLED'}
        
        # Asegurar modo de edición para UVs
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Obtener el mesh y verificar capa UV activa
        me = obj.data
        if not me.uv_layers.active:
            self.report({'ERROR'}, "No active UV layer! Please unwrap the mesh first.")
            return {'CANCELLED'}
        
        # Indicar que la operación está en curso
        context.scene.texture_generator_is_running = True
        context.window_manager.progress_begin(0, 100)
        context.window_manager.progress_update(10)
        self.report({'INFO'}, "Generating texture, please wait...")
        
        # Crear archivo temporal para el UV map
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            uv_filepath = tmp_file.name
        
        try:
            # Guardar materiales originales
            bpy.ops.object.mode_set(mode='OBJECT')
            original_materials = [slot.material for slot in obj.material_slots]
            
            # Crear material blanco por defecto
            default_mat = bpy.data.materials.new(name="Temp_Default_White")
            default_mat.use_nodes = True
            nodes = default_mat.node_tree.nodes
            nodes.clear()
            emission = nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)  # Blanco
            output = nodes.new("ShaderNodeOutputMaterial")
            default_mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
            
            # Crear materiales temporales para cada grupo
            temp_materials = [default_mat]
            for i, color in enumerate(group_colors):
                mat = bpy.data.materials.new(name=f"Temp_Color_{i}")
                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                nodes.clear()
                emission = nodes.new("ShaderNodeEmission")
                emission.inputs["Color"].default_value = color + (1.0,)
                output = nodes.new("ShaderNodeOutputMaterial")
                mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
                temp_materials.append(mat)
            
            # Asignar materiales a las ranuras
            obj.data.materials.clear()
            for mat in temp_materials:
                obj.data.materials.append(mat)
            
            # Asignar material blanco a todas las caras
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()
            for face in bm.faces:
                face.material_index = 0  # Material blanco por defecto
            print(f"DEBUG: Assigned default white material to {len(bm.faces)} faces")
            
            # Asignar materiales a caras de grupos
            if groups:
                for i, group in enumerate(groups[:4]):
                    face_indices = json.loads(group.face_indices)
                    print(f"DEBUG: Assigning color {group_colors[i]} to group '{group.name}', indices: {face_indices}")
                    for face_idx in face_indices:
                        if face_idx < len(bm.faces):
                            bm.faces[face_idx].material_index = i + 1  # Material del grupo (1, 2, 3, 4)
                bmesh.update_edit_mesh(me)
            
            # Configurar Cycles para hornear
            bpy.context.scene.render.engine = 'CYCLES'
            bpy.context.scene.cycles.bake_type = 'EMIT'
            bpy.context.scene.render.bake.use_pass_direct = False
            bpy.context.scene.render.bake.use_pass_indirect = False
            bpy.context.scene.render.bake.margin = 2  # Margen pequeño para evitar sangrado
            
            # Crear imagen para hornear
            image_name = f"Temp_UV_{random.randint(0, 10000)}"
            image = bpy.data.images.new(name=image_name, width=2048, height=2048, alpha=True)
            image.filepath_raw = uv_filepath
            image.file_format = 'PNG'
            
            # Asignar imagen al nodo de imagen en cada material
            for slot in obj.material_slots:
                if slot.material:
                    nodes = slot.material.node_tree.nodes
                    image_node = nodes.new("ShaderNodeTexImage")
                    image_node.image = image
                    image_node.select = True
                    nodes.active = image_node
            
            # Seleccionar objeto para hornear
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            
            # Hornear la imagen
            print(f"DEBUG: Baking UV map with colors to {uv_filepath}")
            bpy.ops.object.bake(type='EMIT')
            
            # Guardar la imagen
            image.save()
            print(f"DEBUG: UV map with group colors saved at: {uv_filepath}")
            
            # Exportar mapa UV con contornos para combinar
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_contour:
                contour_filepath = tmp_contour.name
            bpy.ops.uv.export_layout(
                filepath=contour_filepath,
                export_all=True,
                mode='PNG',
                size=(2048, 2048),
                opacity=0.5
            )
            print(f"DEBUG: UV contour map saved at: {contour_filepath}")
            
            # Restaurar materiales originales
            obj.data.materials.clear()
            for mat in original_materials:
                obj.data.materials.append(mat)
            for mat in temp_materials:
                bpy.data.materials.remove(mat)
            bpy.data.images.remove(image)
            
            file_size = os.path.getsize(uv_filepath)
            print(f"DEBUG: UV layout file size: {file_size} bytes")
            if file_size == 0:
                raise Exception("Exported UV layout file is empty")
        except Exception as e:
            context.scene.texture_generator_is_running = False
            context.window_manager.progress_end()
            self.report({'ERROR'}, f"Failed to export UV layout: {str(e)}")
            return {'CANCELLED'}
        
        # Codificar la imagen en base64
        print(f"DEBUG: Starting base64 encoding...")
        try:
            with open(uv_filepath, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            data_url = f"data:image/png;base64,{base64_image}"
            print(f"DEBUG: Base64 data URL created, length: {len(data_url)} characters")
        except Exception as e:
            context.scene.texture_generator_is_running = False
            context.window_manager.progress_end()
            self.report({'ERROR'}, f"Failed to encode UV layout to base64: {str(e)}")
            return {'CANCELLED'}
        
        context.window_manager.progress_update(30)
        
        # Crear predicción en Replicate usando base64
        print(f"DEBUG: Creating prediction with base64 image...")
        model_map = {
            'NANO_BANANA': 'google/nano-banana',
            'QWEN_IMAGE_EDIT': 'qwen/qwen-image-edit',
            'FLUX_KONTEXT_DEV': 'black-forest-labs/flux-kontext-dev',
            'SEEDEDIT_3_0': 'bytedance/seededit-3.0'
        }
        model_id = model_map[model]
        print(f"DEBUG: Using model: {model_id}")
        
        # Configurar payload según el modelo
        input_payload = {
            "prompt": prompt
        }
        
        if model == 'NANO_BANANA':
            input_payload["image_input"] = [data_url]
            input_payload["output_format"] = "png"
        elif model == 'FLUX_KONTEXT_DEV':
            input_payload["input_image"] = data_url
            input_payload["output_format"] = "png"
            input_payload["aspect_ratio"] = "match_input_image"
            input_payload["num_inference_steps"] = 30
            input_payload["guidance"] = 2.5
        elif model == 'QWEN_IMAGE_EDIT':
            input_payload["image"] = data_url
            input_payload["output_format"] = "png"
        elif model == 'SEEDEDIT_3_0':
            input_payload["image"] = data_url
            input_payload["output_format"] = "png"
        
        payload = {
            "input": input_payload
        }
        print(f"DEBUG: Payload: {json.dumps(payload, indent=2)}")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "wait"
        }
        try:
            req = urllib.request.Request(
                f"https://api.replicate.com/v1/models/{model_id}/predictions",
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urllib.request.urlopen(req) as response:
                prediction = json.loads(response.read().decode('utf-8'))
                print(f"DEBUG: Prediction response: {json.dumps(prediction, indent=2)}")
                
                if prediction.get("status") == "succeeded":
                    output_url = prediction["output"]
                    print(f"DEBUG: Prediction completed immediately! Output URL: {output_url}")
                else:
                    prediction_id = prediction["id"]
                    prediction_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
                    print(f"DEBUG: Prediction created: ID={prediction_id}, starting polling...")
                    
                    while True:
                        poll_req = urllib.request.Request(prediction_url, headers={"Authorization": f"Bearer {api_key}"})
                        with urllib.request.urlopen(poll_req) as poll_response:
                            status_data = json.loads(poll_response.read().decode('utf-8'))
                            status = status_data["status"]
                            print(f"DEBUG: Prediction status: {status}")
                            if status == "succeeded":
                                output_url = status_data["output"]
                                print(f"DEBUG: Prediction succeeded! Output URL: {output_url}")
                                break
                            elif status in ["failed", "canceled"]:
                                error_msg = status_data.get('error', 'Unknown error')
                                print(f"DEBUG: Prediction {status}: {error_msg}")
                                context.scene.texture_generator_is_running = False
                                context.window_manager.progress_end()
                                self.report({'ERROR'}, f"Prediction {status}: {error_msg}")
                                return {'CANCELLED'}
                            time.sleep(5)
                        context.window_manager.progress_update(50 + (status_data.get("progress", 0) * 40))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') and callable(e.read) else "No response body"
            print(f"DEBUG: HTTP Error {e.code}: {e.reason}")
            print(f"DEBUG: Response body: {error_body}")
            context.scene.texture_generator_is_running = False
            context.window_manager.progress_end()
            self.report({'ERROR'}, f"Failed to create prediction (HTTP {e.code}): {error_body}")
            return {'CANCELLED'}
        except Exception as e:
            print(f"DEBUG: Prediction creation exception: {str(e)}")
            context.scene.texture_generator_is_running = False
            context.window_manager.progress_end()
            self.report({'ERROR'}, f"Failed to create prediction: {str(e)}")
            return {'CANCELLED'}
        
        context.window_manager.progress_update(70)
        
        # Descargar la imagen generada
        print(f"DEBUG: Downloading generated texture...")
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_output:
            output_filepath = tmp_output.name
        
        try:
            req = urllib.request.Request(output_url, headers={"Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(req) as response:
                with open(output_filepath, 'wb') as f:
                    f.write(response.read())
                print(f"DEBUG: Texture downloaded to {output_filepath}, size: {os.path.getsize(output_filepath)} bytes")
        except Exception as e:
            print(f"DEBUG: Download exception: {str(e)}")
            context.scene.texture_generator_is_running = False
            context.window_manager.progress_end()
            self.report({'ERROR'}, f"Failed to download generated texture: {str(e)}")
            return {'CANCELLED'}
        
        # Aplicar la textura al mesh seleccionado
        print(f"DEBUG: Applying texture to mesh...")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            mat_name = f"Generated_Texture_{obj.name}"
            if mat_name in bpy.data.materials:
                mat = bpy.data.materials[mat_name]
            else:
                mat = bpy.data.materials.new(name=mat_name)
                mat.use_nodes = True
            
            if not obj.data.materials:
                obj.data.materials.append(mat)
            else:
                obj.data.materials[0] = mat
            
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            principled = nodes.get("Principled BSDF")
            if not principled:
                self.report({'ERROR'}, "Principled BSDF node not found in material!")
                return {'CANCELLED'}
            
            tex_image = nodes.new("ShaderNodeTexImage")
            tex_image.image = bpy.data.images.load(output_filepath)
            tex_image.label = "Generated Texture"
            links.new(tex_image.outputs["Color"], principled.inputs["Base Color"])
            
            print(f"DEBUG: Texture applied to material {mat_name} on object {obj.name}")
        except Exception as e:
            print(f"DEBUG: Apply texture exception: {str(e)}")
            context.scene.texture_generator_is_running = False
            context.window_manager.progress_end()
            self.report({'ERROR'}, f"Failed to apply texture to mesh: {str(e)}")
            return {'CANCELLED'}
        
        context.window_manager.progress_update(100)
        context.window_manager.progress_end()
        context.scene.texture_generator_is_running = False
        
        self.report({'INFO'}, f"Texture generated and applied to {obj.name}. UV map saved at: {uv_filepath}. Contour map saved at: {contour_filepath}. Texture saved at: {output_filepath}. Prompt: {sub_prompt}, Style: {style_description}, Model: {model}, {colors_info}")
        print(f"SUCCESS: Texture saved at: {output_filepath} and applied to {obj.name}")
        print(f"SUCCESS: UV map saved at: {uv_filepath}")
        print(f"SUCCESS: Contour map saved at: {contour_filepath}")
        print(f"Prompt: {sub_prompt}, Style: {style_description}, Model: {model}, {colors_info}")
        
        return {'FINISHED'}

class TextureGeneratorPanel(bpy.types.Panel):
    """Panel for the Texture Generator add-on in the UV Editor"""
    bl_label = "Texture Generator"
    bl_idname = "PT_TextureGenerator"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout
        layout.enabled = not context.scene.texture_generator_is_running
        
        # Subpanel para grupos de caras
        box = layout.box()
        box.label(text="Face Groups")
        for i, group in enumerate(context.scene.texture_generator_groups):
            row = box.row()
            row.prop(group, "name", text="")
            row.operator("uv.texture_generator_select_group_faces", text="", icon="RESTRICT_SELECT_OFF").index = i
            row.operator("uv.texture_generator_overwrite_group_faces", text="", icon="FILE_REFRESH").index = i
            row.operator("uv.texture_generator_remove_group", text="", icon="REMOVE").index = i
        row = box.row()
        row.enabled = len(context.scene.texture_generator_groups) < 4
        row.operator("uv.texture_generator_add_group", text="Add Group")
        
        # Configuración principal
        layout.prop(context.scene, "texture_generator_prompt", text="Prompt")
        layout.prop(context.scene, "texture_generator_style", text="Style")
        layout.prop(context.scene, "texture_generator_model", text="Model")
        layout.prop(context.scene, "texture_generator_use_custom_colors", text="Use Custom Colors")
        if context.scene.texture_generator_use_custom_colors:
            layout.prop(context.scene, "texture_generator_color1", text="Color 1")
            layout.prop(context.scene, "texture_generator_color2", text="Color 2")
            layout.prop(context.scene, "texture_generator_color3", text="Color 3")
            layout.prop(context.scene, "texture_generator_color4", text="Color 4")
        layout.operator(TextureGeneratorOperator.bl_idname, text="Generate")

def register():
    bpy.utils.register_class(TextureGeneratorGroup)
    bpy.utils.register_class(TextureGeneratorAddGroupOperator)
    bpy.utils.register_class(TextureGeneratorRemoveGroupOperator)
    bpy.utils.register_class(TextureGeneratorSelectGroupFacesOperator)
    bpy.utils.register_class(TextureGeneratorOverwriteGroupFacesOperator)
    bpy.utils.register_class(TextureGeneratorPreferences)
    bpy.types.Scene.texture_generator_groups = CollectionProperty(
        type=TextureGeneratorGroup,
        name="Face Groups",
        description="Groups of faces with custom descriptions"
    )
    bpy.types.Scene.texture_generator_prompt = StringProperty(
        name="Texture Prompt",
        default="",
        description="Enter a texture description (e.g., 'wooden surface')"
    )
    bpy.types.Scene.texture_generator_style = bpy.props.EnumProperty(
        name="Texture Style",
        description="Select the style for the generated texture",
        items=[
            ('REALISTIC', "Realistic", "Photorealistic, ultra-detailed, 8K resolution, realistic lighting, DSLR quality, sharp textures, natural materials"),
            ('CARTOON', "Cartoon", "Cartoonish, bold outlines, vibrant colors, flat shading, stylized design, clean and exaggerated features"),
            ('ANIME', "Anime", "Anime-inspired, smooth gradients, vibrant and expressive colors, soft shading, clean lines, stylized proportions"),
            ('PIXEL_ART', "Pixel Art", "Pixel art style, retro 16-bit aesthetic, distinct pixelated edges, limited color palette, blocky textures"),
        ],
        default='REALISTIC'
    )
    bpy.types.Scene.texture_generator_model = bpy.props.EnumProperty(
        name="AI Model",
        description="Select the AI model for texture generation",
        items=[
            ('NANO_BANANA', "Nano Banana ($0.039)", "Google Nano Banana model (google/nano-banana)"),
            ('QWEN_IMAGE_EDIT', "Qwen Image Edit ($0.03)", "Qwen Image Edit model (qwen/qwen-image-edit)"),
            ('FLUX_KONTEXT_DEV', "Flux Kontext Dev ($0.025)", "Black Forest Labs Flux Kontext Dev model (black-forest-labs/flux-kontext-dev)"),
            ('SEEDEDIT_3_0', "Seededit 3.0 ($0.03)", "ByteDance Seededit 3.0 model (bytedance/seededit-3.0)"),
        ],
        default='NANO_BANANA'
    )
    bpy.types.Scene.texture_generator_use_custom_colors = bpy.props.BoolProperty(
        name="Use Custom Colors",
        default=False,
        description="Enable to specify a custom color palette"
    )
    bpy.types.Scene.texture_generator_color1 = bpy.props.FloatVectorProperty(
        name="Color 1",
        subtype='COLOR',
        default=(1.0, 0.0, 0.0),
        min=0.0,
        max=1.0
    )
    bpy.types.Scene.texture_generator_color2 = bpy.props.FloatVectorProperty(
        name="Color 2",
        subtype='COLOR',
        default=(0.0, 1.0, 0.0),
        min=0.0,
        max=1.0
    )
    bpy.types.Scene.texture_generator_color3 = bpy.props.FloatVectorProperty(
        name="Color 3",
        subtype='COLOR',
        default=(0.0, 0.0, 1.0),
        min=0.0,
        max=1.0
    )
    bpy.types.Scene.texture_generator_color4 = bpy.props.FloatVectorProperty(
        name="Color 4",
        subtype='COLOR',
        default=(1.0, 1.0, 0.0),
        min=0.0,
        max=1.0
    )
    bpy.types.Scene.texture_generator_is_running = bpy.props.BoolProperty(
        name="Operation Running",
        default=False,
        description="Indicates if a texture generation is in progress"
    )
    bpy.utils.register_class(TextureGeneratorOperator)
    bpy.utils.register_class(TextureGeneratorPanel)

def unregister():
    bpy.utils.unregister_class(TextureGeneratorPanel)
    bpy.utils.unregister_class(TextureGeneratorOperator)
    bpy.utils.unregister_class(TextureGeneratorPreferences)
    bpy.utils.unregister_class(TextureGeneratorOverwriteGroupFacesOperator)
    bpy.utils.unregister_class(TextureGeneratorSelectGroupFacesOperator)
    bpy.utils.unregister_class(TextureGeneratorRemoveGroupOperator)
    bpy.utils.unregister_class(TextureGeneratorAddGroupOperator)
    bpy.utils.unregister_class(TextureGeneratorGroup)
    del bpy.types.Scene.texture_generator_groups
    del bpy.types.Scene.texture_generator_prompt
    del bpy.types.Scene.texture_generator_style
    del bpy.types.Scene.texture_generator_model
    del bpy.types.Scene.texture_generator_use_custom_colors
    del bpy.types.Scene.texture_generator_color1
    del bpy.types.Scene.texture_generator_color2
    del bpy.types.Scene.texture_generator_color3
    del bpy.types.Scene.texture_generator_color4
    del bpy.types.Scene.texture_generator_is_running

if __name__ == "__main__":
    register()