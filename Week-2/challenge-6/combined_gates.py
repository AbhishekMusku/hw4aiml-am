import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

print("🔄 Loading GIFs...")

and_frames = imageio.mimread("and_training.gif")
or_frames = imageio.mimread("or_training.gif")
nand_frames = imageio.mimread("nand_training.gif")
xor_frames = imageio.mimread("xor_training.gif")

print("✅ All GIFs loaded!")
print(f"Frames per GIF: AND={len(and_frames)}, OR={len(or_frames)}, NAND={len(nand_frames)}, XOR={len(xor_frames)}")

frame_count = min(len(and_frames), len(or_frames), len(nand_frames), len(xor_frames))
combined_frames = []

print("🛠️  Stitching frames together with quadrant labels...")

# Load Windows font explicitly
try:
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
except:
    font = ImageFont.load_default()
    print("⚠️ Warning: Arial not found, using default font.")

# Function to add label with background
def label_gate(img, text):
    labeled = img.convert("RGB")
    draw = ImageDraw.Draw(labeled)
    x, y = 10, 10
    draw.rectangle([x - 5, y - 5, x + 120, y + 35], fill=(0, 0, 0))  # black background
    draw.text((x, y), text, font=font, fill=(255, 255, 255))        # white text
    return labeled

for i in range(frame_count):
    and_img = Image.fromarray(and_frames[i])
    or_img = Image.fromarray(or_frames[i])
    nand_img = Image.fromarray(nand_frames[i])
    xor_img = Image.fromarray(xor_frames[i])

    size = and_img.size  # assume all are same size
    or_img = or_img.resize(size)
    nand_img = nand_img.resize(size)
    xor_img = xor_img.resize(size)

    # Label each quadrant
    and_labeled = label_gate(and_img, "AND")
    or_labeled = label_gate(or_img, "OR")
    nand_labeled = label_gate(nand_img, "NAND")
    xor_labeled = label_gate(xor_img, "XOR")

    # Build top and bottom rows
    top_row = Image.new('RGB', (size[0]*2, size[1]))
    top_row.paste(and_labeled, (0, 0))
    top_row.paste(or_labeled, (size[0], 0))

    bottom_row = Image.new('RGB', (size[0]*2, size[1]))
    bottom_row.paste(nand_labeled, (0, 0))
    bottom_row.paste(xor_labeled, (size[0], 0))

    # Build full 2x2 grid frame
    full_frame = Image.new('RGB', (size[0]*2, size[1]*2))
    full_frame.paste(top_row, (0, 0))
    full_frame.paste(bottom_row, (0, size[1]))

    combined_frames.append(np.array(full_frame))

print("💾 Saving combined GIF as combined_gates.gif...")
imageio.mimsave("combined_gates.gif", combined_frames, duration=0.05)
print("✅ Done! Combined GIF saved as combined_gates.gif 🎉")
