bl_info = {
    "name": "Texture Generator",
    "author": "Sergio de Iscar Valera",
    "version": (1, 5, 0),
    "blender": (4, 2, 0),
    "location": "UV Editor > Sidebar > Tools",
    "description": "A Blender add-on integrated with the UV Editor to generate textures using remote AI APIs. Extracts UV map data, sends it to an AI service with a user-defined prompt, style, and model, and applies the resulting texture to the active mesh.",
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

class TextureGeneratorPreferences(bpy.types.AddonPreferences):
    """Preferences for the Texture Generator add-on"""
    bl_idname = __name__

    api_key: bpy.props.StringProperty(
        name="Replicate API Key",
        default="",
        subtype='PASSWORD',
        description="Enter your Replicate API key here. It will be stored in Blender's preferences file."
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
        
        # Verificar si la API key está configurada
        if not api_key:
            self.report({'ERROR'}, "Replicate API key not set. Configure it in Add-on Preferences.")
            return {'CANCELLED'}
        
        # Obtener el prompt, estilo y modelo
        prompt = context.scene.texture_generator_prompt
        style = context.scene.texture_generator_style
        model = context.scene.texture_generator_model
        use_custom_colors = context.scene.texture_generator_use_custom_colors
        
        # Obtener colores si se usan custom
        if use_custom_colors:
            color1 = context.scene.texture_generator_color1
            color2 = context.scene.texture_generator_color2
            color3 = context.scene.texture_generator_color3
            color4 = context.scene.texture_generator_color4
            colors_info = f"Colors: {color1[:]}, {color2[:]}, {color3[:]}, {color4[:]}"
        else:
            colors_info = "Colors: Random"
        
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
        
        # Indicar que la operación está en curso (bloquea el botón)
        context.scene.texture_generator_is_running = True
        context.window_manager.progress_begin(0, 100)
        context.window_manager.progress_update(10)
        self.report({'INFO'}, "Generating texture, please wait...")
        
        # Exportar el layout UV como imagen PNG
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            uv_filepath = tmp_file.name
        
        try:
            bpy.ops.uv.export_layout(
                filepath=uv_filepath,
                export_all=True,
                mode='PNG',
                size=(1024, 1024),
                opacity=1.0
            )
            print(f"DEBUG: UV layout exported to {uv_filepath}")
            # Verificar que el archivo existe y tiene tamaño
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
            try:
                os.remove(uv_filepath)
            except:
                pass
            return {'CANCELLED'}
        
        # Borrar el archivo UV temporal
        try:
            os.remove(uv_filepath)
            print(f"DEBUG: Deleted UV temp file: {uv_filepath}")
        except Exception as e:
            print(f"DEBUG: Failed to delete UV temp file: {str(e)}")
        
        context.window_manager.progress_update(30)
        
        # Crear predicción en Replicate usando base64 directamente
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
            "prompt": f"{prompt}, style: {style.lower()}" + (f", colors: {colors_info}" if use_custom_colors else "")
        }
        
        if model == 'NANO_BANANA':
            input_payload["image_input"] = [data_url]  # Array de URLs/imágenes para Nano Banana
            input_payload["output_format"] = "png"
        elif model == 'FLUX_KONTEXT_DEV':
            input_payload["input_image"] = data_url  # input_image para Flux
            input_payload["output_format"] = "png"
            input_payload["aspect_ratio"] = "match_input_image"
            input_payload["num_inference_steps"] = 30
            input_payload["guidance"] = 2.5
        elif model == 'QWEN_IMAGE_EDIT':
            input_payload["image"] = data_url  # Asumiendo "image" para Qwen
            input_payload["output_format"] = "png"
        elif model == 'SEEDEDIT_3_0':
            input_payload["image"] = data_url  # Asumiendo "image" para Seededit
            input_payload["output_format"] = "png"
        
        payload = {
            "input": input_payload
        }
        print(f"DEBUG: Payload: {json.dumps(payload, indent=2)}")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "wait"  # Esperar hasta que termine (hasta 30s)
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
                
                # Si usamos Prefer: wait, el resultado puede estar ya disponible
                if prediction.get("status") == "succeeded":
                    output_url = prediction["output"]
                    print(f"DEBUG: Prediction completed immediately! Output URL: {output_url}")
                else:
                    # Polling normal
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
        
        context.window_manager.progress_update(100)
        context.window_manager.progress_end()
        context.scene.texture_generator_is_running = False
        
        # Reportar éxito
        self.report({'INFO'}, f"Texture generated and saved to {output_filepath}. Prompt: {prompt}, Style: {style}, Model: {model}, {colors_info}")
        print(f"SUCCESS: Texture saved at: {output_filepath}")
        print(f"Prompt: {prompt}, Style: {style}, Model: {model}, {colors_info}")
        
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
        layout.enabled = not context.scene.texture_generator_is_running  # Deshabilitar durante operación
        # Campo de texto para el prompt
        layout.prop(context.scene, "texture_generator_prompt", text="Prompt")
        # Selector de estilos
        layout.prop(context.scene, "texture_generator_style", text="Style")
        # Selector de modelo
        layout.prop(context.scene, "texture_generator_model", text="Model")
        # Checkbox para usar colores custom
        layout.prop(context.scene, "texture_generator_use_custom_colors", text="Use Custom Colors")
        # Si checked, mostrar los selectores de color
        if context.scene.texture_generator_use_custom_colors:
            layout.prop(context.scene, "texture_generator_color1", text="Color 1")
            layout.prop(context.scene, "texture_generator_color2", text="Color 2")
            layout.prop(context.scene, "texture_generator_color3", text="Color 3")
            layout.prop(context.scene, "texture_generator_color4", text="Color 4")
        # Botón para generar la textura
        layout.operator(TextureGeneratorOperator.bl_idname, text="Generate")

def register():
    bpy.utils.register_class(TextureGeneratorPreferences)
    # Propiedad para el prompt
    bpy.types.Scene.texture_generator_prompt = bpy.props.StringProperty(
        name="Texture Prompt",
        default="",
        description="Enter a texture description (e.g., 'wooden surface')"
    )
    # Propiedad para el selector de estilos
    bpy.types.Scene.texture_generator_style = bpy.props.EnumProperty(
        name="Texture Style",
        description="Select the style for the generated texture",
        items=[
            ('REALISTIC', "Realistic", "Photorealistic texture style"),
            ('CARTOON', "Cartoon", "Cartoon or stylized texture style"),
            ('ANIME', "Anime", "Anime-inspired texture style"),
            ('PIXEL_ART', "Pixel Art", "Pixel art texture style"),
        ],
        default='REALISTIC'
    )
    # Propiedad para el selector de modelo
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
    # Propiedad para el checkbox de colores custom
    bpy.types.Scene.texture_generator_use_custom_colors = bpy.props.BoolProperty(
        name="Use Custom Colors",
        default=False,
        description="Enable to specify a custom color palette; otherwise, random colors will be used"
    )
    # Propiedades para los 4 colores
    bpy.types.Scene.texture_generator_color1 = bpy.props.FloatVectorProperty(
        name="Color 1",
        subtype='COLOR',
        default=(1.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
        description="First color in the palette"
    )
    bpy.types.Scene.texture_generator_color2 = bpy.props.FloatVectorProperty(
        name="Color 2",
        subtype='COLOR',
        default=(0.0, 1.0, 0.0),
        min=0.0,
        max=1.0,
        description="Second color in the palette"
    )
    bpy.types.Scene.texture_generator_color3 = bpy.props.FloatVectorProperty(
        name="Color 3",
        subtype='COLOR',
        default=(0.0, 0.0, 1.0),
        min=0.0,
        max=1.0,
        description="Third color in the palette"
    )
    bpy.types.Scene.texture_generator_color4 = bpy.props.FloatVectorProperty(
        name="Color 4",
        subtype='COLOR',
        default=(1.0, 1.0, 0.0),
        min=0.0,
        max=1.0,
        description="Fourth color in the palette"
    )
    # Propiedad para bloquear el botón durante la operación
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
    # Eliminar propiedades personalizadas
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