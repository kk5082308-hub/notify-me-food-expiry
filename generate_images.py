import os
from PIL import Image, ImageDraw

def generate_placeholder_images():
    img_dir = os.path.join('static', 'img')
    os.makedirs(img_dir, exist_ok=True)
    
    # 1. Generate 192x192 Icon
    icon_192 = Image.new('RGB', (192, 192), color='#2ecc71')
    draw = ImageDraw.Draw(icon_192)
    # Draw simple visual representative of a food bag or bell
    draw.rectangle([40, 50, 152, 160], fill='#27ae60', outline='#ffffff', width=4)
    draw.ellipse([70, 75, 122, 127], fill='#ffffff')
    draw.arc([75, 45, 115, 85], start=180, end=360, fill='#ffffff', width=4)
    icon_192.save(os.path.join(img_dir, 'icon-192.png'))
    
    # 2. Generate 512x512 Icon
    icon_512 = Image.new('RGB', (512, 512), color='#2ecc71')
    draw = ImageDraw.Draw(icon_512)
    draw.rectangle([100, 130, 412, 430], fill='#27ae60', outline='#ffffff', width=8)
    draw.ellipse([180, 190, 332, 342], fill='#ffffff')
    draw.arc([190, 110, 320, 240], start=180, end=360, fill='#ffffff', width=8)
    icon_512.save(os.path.join(img_dir, 'icon-512.png'))
    
    # 3. Generate default profile image
    default_profile = Image.new('RGB', (300, 300), color='#7f8c8d')
    draw = ImageDraw.Draw(default_profile)
    # Draw a simple avatar silhouette
    draw.ellipse([100, 50, 200, 150], fill='#ffffff')
    draw.chord([50, 180, 250, 350], start=180, end=360, fill='#ffffff')
    default_profile.save(os.path.join(img_dir, 'default.jpg'))
    
    # 4. Generate default food icon placeholder
    default_food = Image.new('RGB', (400, 300), color='#bdc3c7')
    draw = ImageDraw.Draw(default_food)
    # Draw food-like outline
    draw.ellipse([120, 100, 280, 220], fill='#95a5a6')
    draw.rectangle([180, 80, 220, 120], fill='#7f8c8d')
    default_food.save(os.path.join(img_dir, 'default_food.png'))

    print("Successfully generated all placeholder and PWA images.")

if __name__ == '__main__':
    generate_placeholder_images()
