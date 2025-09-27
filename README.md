# Texture Generator Blender Add-on

A Blender add-on for generating textures from UV maps using Replicate AI models, primarily Nano Banana, allowing users to define face groups and customize prompts for seamless 3D texturing.

## Overview

The **Texture Generator** is a Blender add-on integrated into the UV Editor that enables users to generate high-quality textures for 3D models using AI-powered image generation via the Replicate API. It allows artists to define groups of faces on a mesh, assign descriptive prompts, and generate textures that precisely fit the UV layout. The add-on bakes a temporary UV map with colored regions to guide the AI, ensuring accurate texture placement for specific model parts (e.g., "Eyes" or "Top head"). The primary model used is Google's Nano Banana, with support for other Replicate models.

## Features

- **Face Group Management**: Create up to 4 groups of faces with custom descriptions (e.g., "Eyes", "Top head") to guide texture generation.
- **AI Texture Generation**: Uses Replicate API to generate textures based on user-defined prompts and styles (Realistic, Cartoon, Anime, Pixel Art).
- **UV Map Precision**: Bakes a high-resolution (2048x2048) UV map with sharp edges, using colors to mark regions (white for ungrouped faces, red/green/blue/yellow for groups).
- **Customizable Styles**: Supports detailed style descriptions (e.g., "Photorealistic, ultra-detailed, 8K resolution") for precise control over texture output.
- **Seamless Integration**: Operates within Blender's UV Editor, automatically applying generated textures to the selected mesh.

## Installation

1. Download the `texture_generator.py` file from this repository.
2. In Blender, go to **Edit > Preferences > Add-ons > Install** and select the `texture_generator.py` file.
3. Enable the add-on by checking the box next to "Texture Generator".
4. Configure your Replicate API key in **Edit > Preferences > Add-ons > Texture Generator > Replicate API Key**. Obtain your key from [Replicate](https://replicate.com/account/api-tokens).

## Usage

1. **Prepare Your Mesh**:

   - Select a mesh object in Blender and enter **Edit Mode** (`Tab`).
   - Ensure the mesh has a UV map (unwrap with `U > Smart UV Project`, recommended settings: Angle Limit 66, Island Margin 0.02).

2. **Define Face Groups**:

   - In the **UV Editor** sidebar (`N` key), find the **Texture Generator** panel.
   - Select faces in Edit Mode, then click **Add Group** to create a group (up to 4 groups).
   - Name each group (e.g., "Eyes", "Top head") to describe the region for texture generation.

3. **Configure Texture Settings**:

   - Enter a **Prompt** (e.g., "metallic armor") to describe the desired texture.
   - Choose a **Style** (Realistic, Cartoon, Anime, Pixel Art).
   - Select a **Model** (default: Nano Banana).
   - Optionally, enable **Use Custom Colors** to specify a color palette.

4. **Generate Texture**:

   - Click **Generate** to bake a temporary UV map, send it to Replicate, and apply the generated texture to the mesh.
   - Check the Blender console (`Window > Toggle System Console`) for debug logs, including paths to the UV map, contour map, and final texture.

5. **Inspect Output**:
   - The add-on saves:
     - A UV map with colored regions (`/tmp/tmpXXXX.png`).
     - A contour map for UV island boundaries (`/tmp/tmpZZZZ.png`).
     - The generated texture (`/tmp/tmpYYYY.png`), applied to the mesh.
   - Verify that group regions (e.g., red for "Eyes", green for "Top head") are correctly textured, with ungrouped faces in a default texture.

## Supported Models

The add-on supports the following Replicate AI models for texture generation:

- **Nano Banana ($0.039)**: Google Nano Banana (`google/nano-banana`), the primary model, optimized for high-quality UV map texturing.
- **Qwen Image Edit ($0.03)**: Qwen Image Edit (`qwen/qwen-image-edit`), for precise image editing tasks.
- **Flux Kontext Dev ($0.025)**: Black Forest Labs Flux Kontext Dev (`black-forest-labs/flux-kontext-dev`), for advanced texture generation.
- **Seededit 3.0 ($0.03)**: ByteDance Seededit 3.0 (`bytedance/seededit-3.0`), for stylized texture outputs.

## License

This add-on is open-source and free to use, modify, and distribute without any restrictions. You are welcome to copy, adapt, or build upon it for any purpose. A mention or credit to the original author, **Sergio de Iscar Valera**, is greatly appreciated but not required.

## Acknowledgments

- **Author**: [Sergio de Iscar Valera](https://www.linkedin.com/in/sergio-de-iscar-valera/)
- **Replicate**: For providing the AI models used in texture generation.
- **Blender Community**: For inspiration and support in developing this add-on.

Feel free to contribute, report issues, or suggest improvements via GitHub!
