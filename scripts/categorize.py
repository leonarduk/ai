
import os
import shutil
import re
import pandas as pd
from datetime import datetime

def extract_date_parts(filename):
    # Extract YYYY-MM-DD from filename
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        try:
            date_obj = datetime.strptime(match.group(1), "%Y-%m-%d")
            month_str = date_obj.strftime("%Y-%m")
            day_str = date_obj.strftime("%Y-%m-%d")
            return month_str, day_str
        except ValueError:
            pass
    return "UnknownMonth", "UnknownDate"

def categorize_photos_nested(input_folder, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    photo_data = []
    for file in os.listdir(input_folder):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            src = os.path.join(input_folder, file)
            month_str, day_str = extract_date_parts(file)

            # Create month folder
            month_folder = os.path.join(output_folder, month_str)
            if not os.path.exists(month_folder):
                os.makedirs(month_folder)

            # Create day folder inside month
            day_folder = os.path.join(month_folder, day_str)
            if not os.path.exists(day_folder):
                os.makedirs(day_folder)

            dst = os.path.join(day_folder, file)
            try:
                shutil.copy2(src, dst)
                photo_data.append({"filename": file, "month": month_str, "day": day_str, "path": dst})
            except Exception as e:
                print(f"Error copying {file}: {e}")

    # Save CSV report
    df = pd.DataFrame(photo_data)
    csv_path = os.path.join(output_folder, "photo_categorization_nested.csv")
    df.to_csv(csv_path, index=False)
    print(f"Categorization complete. Nested structure created. Report saved to {csv_path}")

if __name__ == "__main__":
    input_folder = "D:/curated_photos"
    output_folder = "D:/categorized_photos"
    categorize_photos_nested(input_folder, output_folder)
