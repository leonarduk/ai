
import os
import cv2
import face_recognition
from PIL import Image, ExifTags
import pandas as pd
from datetime import datetime
from collections import defaultdict

# -----------------------------
# CONFIGURATION
# -----------------------------
INPUT_FOLDER = "path/to/your/photos"  # Replace with actual path
REFERENCE_FOLDER = "path/to/reference/images"  # Replace with actual path
OUTPUT_FOLDER = "path/to/output/folder"  # Replace with actual path
TOP_PHOTOS_PER_EVENT = 5  # Number of top photos per event

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def load_reference_faces(reference_folder):
    """Load reference images and compute face encodings."""
    reference_encodings = []
    for file in os.listdir(reference_folder):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            img_path = os.path.join(reference_folder, file)
            image = face_recognition.load_image_file(img_path)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                reference_encodings.append(encodings[0])
    return reference_encodings

def detect_faces_and_match(image_path, reference_encodings):
    """Detect faces and check if any match reference faces."""
    image = face_recognition.load_image_file(image_path)
    face_encodings = face_recognition.face_encodings(image)
    for encoding in face_encodings:
        matches = face_recognition.compare_faces(reference_encodings, encoding, tolerance=0.6)
        if any(matches):
            return True
    return False

def score_image_quality(image_path):
    """Score image quality based on sharpness, brightness, contrast, and resolution."""
    img = cv2.imread(image_path)
    if img is None:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = gray.mean()
    contrast = gray.std()
    height, width = img.shape[:2]
    resolution = width * height

    score = (sharpness * 0.4) + (brightness * 0.2) + (contrast * 0.2) + ((resolution / 1e6) * 0.2)
    return score

def get_image_date(image_path):
    """Extract date from EXIF or fallback to file modified time."""
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if exif_data:
            for tag, value in exif_data.items():
                decoded = ExifTags.TAGS.get(tag)
                if decoded == "DateTimeOriginal":
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").date()
    except Exception:
        pass
    return datetime.fromtimestamp(os.path.getmtime(image_path)).date()

def group_photos_by_event(photo_info):
    events = defaultdict(list)
    for info in photo_info:
        events[info['date']].append(info)
    return events

def select_top_photos(events, top_n):
    selected_photos = []
    for date, photos in events.items():
        sorted_photos = sorted(photos, key=lambda x: x['score'], reverse=True)
        selected_photos.extend(sorted_photos[:top_n])
    return selected_photos

def copy_selected_photos(selected_photos, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    for info in selected_photos:
        src = info['path']
        dst = os.path.join(output_folder, os.path.basename(src))
        try:
            Image.open(src).save(dst)
        except Exception as e:
            print(f"Error copying {src}: {e}")

# -----------------------------
# MAIN WORKFLOW
# -----------------------------
def main():
    reference_encodings = load_reference_faces(REFERENCE_FOLDER)
    photo_info = []

    for file in os.listdir(INPUT_FOLDER):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            path = os.path.join(INPUT_FOLDER, file)
            has_face_match = detect_faces_and_match(path, reference_encodings)
            quality_score = score_image_quality(path)
            date = get_image_date(path)
            combined_score = quality_score + (1000 if has_face_match else 0)
            photo_info.append({'path': path, 'score': combined_score, 'date': date})

    events = group_photos_by_event(photo_info)
    selected_photos = select_top_photos(events, TOP_PHOTOS_PER_EVENT)
    copy_selected_photos(selected_photos, OUTPUT_FOLDER)

    df = pd.DataFrame(selected_photos)
    csv_path = os.path.join(OUTPUT_FOLDER, "curated_photos_report.csv")
    df.to_csv(csv_path, index=False)
    print(f"Curated photos and report saved to {OUTPUT_FOLDER}")

if __name__ == "__main__":
    main()
