
import face_recognition

# Path to a test image
image_path = "D:/2025 Photos/202412/54175676812_ab507092db_o.jpg"

# Load image and find faces
image = face_recognition.load_image_file(image_path)
face_locations = face_recognition.face_locations(image)

print(f"Found {len(face_locations)} face(s) in the image.")
