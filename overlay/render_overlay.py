import os
import sys
import json
import math
import random
import pymupdf
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OVERLAYS_DIR = PROJECT_ROOT / "reports" / "overlays"
OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)

# Helper to draw wobbly sketch lines (Excalidraw style)
def draw_sketch_line(draw, p1, p2, color, width=2):
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    
    if dist < 15:
        draw.line([p1, p2], fill=color, width=width)
        return
        
    # Divide the line into segments and apply slight random offsets
    num_segments = max(2, int(dist / 25))
    points = [p1]
    
    for i in range(1, num_segments):
        t = i / num_segments
        x = x1 + dx * t
        y = y1 + dy * t
        
        # Jitter perpendicular to the line direction
        jitter = random.uniform(-1.2, 1.2)
        if abs(dx) > abs(dy):
            y += jitter
        else:
            x += jitter
        points.append((x, y))
        
    points.append(p2)
    
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=color, width=width)

def draw_wobbly_rect(draw, rect, color, label=""):
    x0, y0, x1, y1 = rect
    
    # Draw sketchy rectangle with double strokes for hand-drawn feel
    for offset in [0, 0.6]:
        draw_sketch_line(draw, (x0 + offset, y0), (x1 - offset, y0), color, width=2)
        draw_sketch_line(draw, (x1, y0 + offset), (x1, y1 - offset), color, width=2)
        draw_sketch_line(draw, (x1 - offset, y1), (x0 + offset, y1), color, width=2)
        draw_sketch_line(draw, (x0, y1 - offset), (x0, y0 + offset), color, width=2)
        
    # Draw field label if provided
    if label:
        try:
            # Comic Sans MS provides the best default "hand-drawn/marker" font on Windows
            font = ImageFont.truetype("comic.ttf", 9)
        except IOError:
            try:
                font = ImageFont.truetype("arial.ttf", 9)
            except IOError:
                font = ImageFont.load_default()
                
        # Safe text bounding box
        if hasattr(draw, "textbbox"):
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        else:
            tw, th = len(label) * 5, 10
            
        draw.rectangle([x0, y0 - th - 3, x0 + tw + 4, y0], fill=(255, 255, 255, 220))
        draw.text((x0 + 2, y0 - th - 2), label, fill=color, font=font)

def search_text_coords(doc, text_val) -> list:
    """Finds coordinates of a text value in the PDF."""
    if not text_val:
        return []
    
    text_str = str(text_val).strip()
    if len(text_str) < 2 or text_str.lower() in ["present", "true", "false", "yes", "no"]:
        return []
        
    # Standardize whitespace for searching
    text_str_norm = " ".join(text_str.split())
    
    matches = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        rects = page.search_for(text_str_norm)
        if not rects:
            # Try a partial/first line search if the string is multi-line
            lines = text_str_norm.split("\n")
            if lines and len(lines[0]) > 3:
                rects = page.search_for(lines[0])
        for r in rects:
            matches.append((page_num, r))
    return matches

def render_overlay_for_run(result_row: dict):
    resume = result_row["resume"]
    extractor = result_row["extractor"]
    field_diffs = result_row.get("field_diffs") or []
    completed = result_row["completed"]
    
    pdf_path = PROJECT_ROOT / "corpus" / "raw" / resume
    if not pdf_path.exists():
        return
        
    # Render PDF pages to images
    doc = pymupdf.open(str(pdf_path))
    pages_imgs = []
    dpi = 150
    scale = dpi / 72.0  # scale points to pixels
    
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        pages_imgs.append(img.convert("RGBA"))
        
    # Color mapping for Excalidraw aesthetic
    colors_map = {
        "correct": (46, 204, 113, 255),       # Green
        "incorrect": (231, 76, 60, 255),      # Red
        "hallucinated": (243, 156, 18, 255),   # Amber
        "missed": (127, 140, 141, 255)         # Grey
    }
    
    unlocated_diffs = []
    
    # Process diffs and draw located bounding boxes
    for diff in field_diffs:
        status = diff["status"]
        path = diff["path"]
        
        # Decide which value to search for
        val_to_search = diff["ground_truth"] if status in ["correct", "incorrect", "missed"] else diff["predicted"]
        if not val_to_search:
            val_to_search = diff["predicted"]
            
        coords = search_text_coords(doc, val_to_search)
        
        if coords:
            # Draw on the first match page
            page_num, rect = coords[0]
            if page_num < len(pages_imgs):
                img = pages_imgs[page_num]
                draw = ImageDraw.Draw(img)
                # Scale rect to match DPI
                pixel_rect = (rect.x0 * scale, rect.y0 * scale, rect.x1 * scale, rect.y1 * scale)
                draw_wobbly_rect(draw, pixel_rect, colors_map[status], label=path)
        else:
            unlocated_diffs.append(diff)
            
    # Combine pages vertically and append a sidebar audit panel
    total_w = max(img.width for img in pages_imgs)
    total_h = sum(img.height for img in pages_imgs)
    
    # Sidebar width
    sidebar_w = 260
    final_w = total_w + sidebar_w
    
    combined_img = Image.new("RGBA", (final_w, total_h), (255, 255, 255, 255))
    
    # Paste pages
    current_y = 0
    for img in pages_imgs:
        combined_img.paste(img, (0, current_y), img)
        current_y += img.height
        
    # Draw Sidebar Panel
    draw_side = ImageDraw.Draw(combined_img)
    # Draw vertical divider line
    draw_sketch_line(draw_side, (total_w, 0), (total_w, total_h), (189, 195, 199, 255), width=2)
    
    # Sidebar Header
    try:
        font_header = ImageFont.truetype("comic.ttf", 14)
        font_sub = ImageFont.truetype("comic.ttf", 10)
    except IOError:
        try:
            font_header = ImageFont.truetype("arial.ttf", 14)
            font_sub = ImageFont.truetype("arial.ttf", 10)
        except IOError:
            font_header = font_sub = ImageFont.load_default()
            
    draw_side.text((total_w + 15, 15), "EXTRACTOR AUDIT", fill=(44, 62, 80, 255), font=font_header)
    draw_side.text((total_w + 15, 35), f"Pipeline: {extractor}", fill=(127, 140, 141, 255), font=font_sub)
    draw_sketch_line(draw_side, (total_w + 15, 50), (total_w + 245, 50), (189, 195, 199, 255), width=1)
    
    # List of unlocated or non-visual issues
    y_pos = 65
    draw_side.text((total_w + 15, y_pos), "Non-Visual Audit Log:", fill=(52, 73, 94, 255), font=font_sub)
    y_pos += 20
    
    if not completed:
        draw_side.text((total_w + 15, y_pos), "CRITICAL: Extraction Failed", fill=(231, 76, 60, 255), font=font_sub)
        y_pos += 15
        reason = result_row.get("failure_reason") or "Unknown"
        # Wrap reason text
        for line in [reason[i:i+30] for i in range(0, len(reason), 30)]:
            draw_side.text((total_w + 15, y_pos), line, fill=(127, 140, 141, 255), font=font_sub)
            y_pos += 15
    else:
        # Show stats
        stats = result_row["scores"]
        draw_side.text((total_w + 15, y_pos), f"Leaf Accuracy: {stats['leaf_accuracy']}%", fill=(44, 62, 80, 255), font=font_sub)
        y_pos += 15
        draw_side.text((total_w + 15, y_pos), f"Precision: {stats['precision']}", fill=(44, 62, 80, 255), font=font_sub)
        y_pos += 15
        draw_side.text((total_w + 15, y_pos), f"Recall: {stats['recall']}", fill=(44, 62, 80, 255), font=font_sub)
        y_pos += 25
        
        draw_sketch_line(draw_side, (total_w + 15, y_pos), (total_w + 245, y_pos), (189, 195, 199, 255), width=1)
        y_pos += 15
        
        draw_side.text((total_w + 15, y_pos), "Issues & Unlocated Diffs:", fill=(52, 73, 94, 255), font=font_sub)
        y_pos += 20
        
        if not unlocated_diffs:
            draw_side.text((total_w + 15, y_pos), "None (Perfect layout match!)", fill=(46, 204, 113, 255), font=font_sub)
        else:
            for diff in unlocated_diffs[:15]: # Show top 15 issues to fit page
                status = diff["status"]
                path = diff["path"]
                if status == "correct":
                    continue # only show errors/misses in sidebar log
                    
                label_text = f"[{status[0].upper()}] {path}"
                # Truncate label if too long
                if len(label_text) > 32:
                    label_text = label_text[:29] + "..."
                    
                draw_side.text((total_w + 15, y_pos), label_text, fill=colors_map[status], font=font_sub)
                y_pos += 16
                
            if len(unlocated_diffs) > 15:
                draw_side.text((total_w + 15, y_pos), f"... and {len(unlocated_diffs)-15} more", fill=(127, 140, 141, 255), font=font_sub)
                
    # Save combined image
    out_filename = OVERLAYS_DIR / f"{Path(resume).stem}_{extractor}.png"
    combined_img.convert("RGB").save(str(out_filename), "PNG")

def main():
    results_path = PROJECT_ROOT / "reports" / "results.jsonl"
    if not results_path.exists():
        print(f"Error: results.jsonl not found at {results_path}")
        sys.exit(1)
        
    print("--- Starting Excalidraw-Style Visual Overlay Generation ---")
    count = 0
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            render_overlay_for_run(row)
            count += 1
            print(f"Generated overlay for {row['resume']} ({row['extractor']})")
            
    print(f"Finished. Generated {count} overlay images in reports/overlays/")

if __name__ == "__main__":
    main()
