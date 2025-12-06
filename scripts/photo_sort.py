
import os
import cv2
import hashlib
import re
import shutil
from PIL import Image, ExifTags
import pandas as pd
from datetime import datetime
from collections import defaultdict

TOP_PHOTOS_PER_EVENT = 5       # Max per day
GLOBAL_LIMIT = 150             # Max overall

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def score_image_quality(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = gray.mean()
    contrast = gray.std()
    height, width = img.shape[:2]
    resolution = width * height
    return (sharpness * 0.4) + (brightness * 0.2) + (contrast * 0.2) + ((resolution / 1e6) * 0.2)

def get_image_date(image_path):
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if exif_data:
            for tag, value in exif_data.items():
                decoded = ExifTags.TAGS.get(tag)
                if decoded in ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]:
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").date()
    except Exception:
        pass

    filename = os.path.basename(image_path)

    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass

    match = re.search(r'(\d{8})', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            pass

    match = re.search(r'(\d{14})', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d%H%M%S").date()
        except ValueError:
            pass

    return datetime.fromtimestamp(os.path.getmtime(image_path)).date()

def get_image_location(image_path):
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if not exif_data:
            return None
        gps_info = {}
        for tag, value in exif_data.items():
            decoded = ExifTags.TAGS.get(tag)
            if decoded == "GPSInfo":
                gps_info = value
        if gps_info:
            def convert_to_degrees(value):
                d, m, s = value
                return d[0]/d[1] + (m[0]/m[1])/60 + (s[0]/s[1])/3600
            lat = convert_to_degrees(gps_info[2]) if 2 in gps_info else None
            lon = convert_to_degrees(gps_info[4]) if 4 in gps_info else None
            if lat and lon:
                return f"{round(lat, 5)}_{round(lon, 5)}"
    except Exception:
        pass
    return None

def get_image_hash(image_path):
    try:
        with open(image_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return None

def group_photos_by_event(photo_info):
    events = defaultdict(list)
    for info in photo_info:
        events[info['date']].append(info)
    return events

def select_top_photos(events, top_n, global_limit):
    selected_photos = []
    for date, photos in events.items():
        sorted_photos = sorted(photos, key=lambda x: x['score'], reverse=True)
        selected_photos.extend(sorted_photos[:top_n])
    return sorted(selected_photos, key=lambda x: x['score'], reverse=True)[:global_limit]

def copy_selected_photos(selected_photos, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    for idx, info in enumerate(selected_photos, start=1):
        src = info['path']
        date_str = info['date'].strftime("%Y-%m-%d")
        location_str = info.get('location') or "NoLocation"
        folder_name = os.path.basename(os.path.dirname(src))  # Add original folder name
        base, ext = os.path.splitext(os.path.basename(src))
        new_name = f"{date_str}_{location_str}_{folder_name}_{idx}{ext}"
        dst = os.path.join(output_folder, new_name)
        try:
            shutil.copy2(src, dst)
            print(f"[{idx}/{len(selected_photos)}] Copied: {src} -> {dst}")
        except Exception as e:
            print(f"Error copying {src}: {e}")

# -----------------------------
# VERSION 1: FILTERED SELECTION
# -----------------------------
def main(input_folder, output_folder):
    photo_info = []
    seen_hashes = set()

    print("Scanning photos recursively...")
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                path = os.path.join(root, file)
                img_hash = get_image_hash(path)
                if img_hash in seen_hashes:
                    print(f"Skipping duplicate content: {file}")
                    continue
                seen_hashes.add(img_hash)

                quality_score = score_image_quality(path)
                date = get_image_date(path)
                location = get_image_location(path)
                photo_info.append({'path': path, 'score': quality_score, 'date': date, 'location': location})

    print(f"Found {len(photo_info)} unique photos. Grouping by date...")
    events = group_photos_by_event(photo_info)
    selected_photos = select_top_photos(events, TOP_PHOTOS_PER_EVENT, GLOBAL_LIMIT)
    print(f"Selected {len(selected_photos)} photos to copy.")

    copy_selected_photos(selected_photos, output_folder)

    df = pd.DataFrame(selected_photos)
    csv_path = os.path.join(output_folder, "curated_photos_report.csv")
    df.to_csv(csv_path, index=False)
    print(f"Report saved to {csv_path}")

# -----------------------------
# VERSION 2: COPY ALL IMAGES
# -----------------------------
def copy_all_images(input_folder, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    idx = 1
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                src = os.path.join(root, file)
                date = get_image_date(src)
                location = get_image_location(src)
                date_str = date.strftime("%Y-%m-%d") if date else "UnknownDate"
                location_str = location or "NoLocation"
                folder_name = os.path.basename(root)
                base, ext = os.path.splitext(file)
                new_name = f"{date_str}_{location_str}_{folder_name}_{idx}{ext}"
                dst = os.path.join(output_folder, new_name)
                try:
                    shutil.copy2(src, dst)
                    print(f"[{idx}] Copied: {src} -> {dst}")
                    idx += 1
                except Exception as e:
                    print(f"Error copying {src}: {e}")

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    input_folder = "D:/new"
    output_folder = "D:/curated_photos"

    # Version 1: Filtered selection
    # main(input_folder, output_folder)

    # Version 2: Copy ALL images
    copy_all_images(input_folder, output_folder)
