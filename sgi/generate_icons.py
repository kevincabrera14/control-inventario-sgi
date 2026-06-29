from PIL import Image
import os

SOURCE = r"C:\Users\ka584\OneDrive\Desktop\logo.png"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "static", "icons")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sizes = [72, 96, 128, 144, 152, 192, 384, 512]

img = Image.open(SOURCE).convert("RGBA")

for size in sizes:
    resized = img.resize((size, size), Image.LANCZOS)
    # Fondo morado para versión maskable
    bg = Image.new("RGBA", (size, size), (123, 31, 162, 255))
    bg.paste(resized, (0, 0), resized)
    bg.convert("RGB").save(
        os.path.join(OUTPUT_DIR, f"icon-{size}x{size}.png"), "PNG"
    )
    print(f"Generado: icon-{size}x{size}.png")

# Copia también el logo original para usarlo en el splash
img.save(os.path.join(OUTPUT_DIR, "logo-original.png"), "PNG")
print("Todos los íconos generados correctamente.")
