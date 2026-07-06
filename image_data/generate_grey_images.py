import os
from pathlib import Path
from PIL import Image

def main():
    root_dir = Path(__file__).resolve().parent
    src_dir = root_dir / "images" / "pokemon"
    dst_dir = root_dir / "grey_images"
    dst_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading sprites from: {src_dir}")
    print(f"Saving grey images to: {dst_dir}")

    # Use a clean mid-grey (120, 120, 120)
    grey_color = (120, 120, 120)

    count = 0
    for file_path in src_dir.glob("*.png"):
        try:
            with Image.open(file_path) as img:
                img_rgba = img.convert("RGBA")
                r, g, b, a = img_rgba.split()
                
                # Create a solid grey image of the same size
                grey_img = Image.new("RGBA", img_rgba.size, (*grey_color, 255))
                # Apply the original alpha mask
                grey_img.putalpha(a)
                
                # Save the new silhouette image
                dst_path = dst_dir / file_path.name
                grey_img.save(dst_path, "PNG")
                count += 1
        except Exception as e:
            print(f"Failed to process {file_path.name}: {e}")

    print(f"Successfully generated {count} grey silhouette images.")

if __name__ == "__main__":
    main()
