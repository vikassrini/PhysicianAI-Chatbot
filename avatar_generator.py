from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import io
import os
import random

def create_avatar_app():
    avatar_app = FastAPI()

    def generate_stylized_avatar(image):
        # Resize the image to a larger size while maintaining aspect ratio
        base_size = 500
        aspect_ratio = image.width / image.height
        if aspect_ratio > 1:
            new_width = base_size
            new_height = int(base_size / aspect_ratio)
        else:
            new_height = base_size
            new_width = int(base_size * aspect_ratio)
        
        image = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Create a square canvas
        size = max(new_width, new_height)
        square_img = Image.new('RGB', (size, size), (255, 255, 255))
        
        # Paste the resized image onto the square canvas
        offset = ((size - new_width) // 2, (size - new_height) // 2)
        square_img.paste(image, offset)
        
        # Apply pixelation effect
        pixel_size = 8  # Adjust this value to control pixelation level
        small_size = (size // pixel_size, size // pixel_size)
        square_img = square_img.resize(small_size, Image.NEAREST).resize((size, size), Image.NEAREST)
        
        # Enhance color and contrast
        enhancer = ImageEnhance.Color(square_img)
        square_img = enhancer.enhance(1.2)
        enhancer = ImageEnhance.Contrast(square_img)
        square_img = enhancer.enhance(1.1)
        
        # Create a circular mask
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        
        # Apply the mask
        output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        output.paste(square_img, (0, 0), mask)
        
        # Resize to final size (300x300)
        output = output.resize((300, 300), Image.LANCZOS)
        
        return output

    @avatar_app.post("/upload-image/")
    async def upload_image(file: UploadFile = File(...)):
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # Generate stylized avatar
        avatar = generate_stylized_avatar(image)
        
        # Save avatar
        os.makedirs("avatars", exist_ok=True)
        avatar_filename = f"{file.filename.split('.')[0]}_avatar_{random.randint(1000, 9999)}.png"
        avatar_path = os.path.join("avatars", avatar_filename)
        avatar.save(avatar_path)
        
        return JSONResponse(content={"avatar_path": f"/avatars/{avatar_filename}"})

    return avatar_app
