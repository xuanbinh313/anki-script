import re
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import pandas as pd
import os
import shutil
from pathlib import Path

# ====== Config ======
UNSPLASH_ACCESS_KEY = "DzW_NqMUMjX98oo3Ua1lq6AhPaR7G9GF2yyBgAD-XxM"  # <-- API key Unsplash
ANKI_BASE_FOLDER = r"C:\Users\THU PHAN\AppData\Roaming\Anki2"  # <-- Thay đúng đường dẫn gốc Anki
# ANKI_BASE_FOLDER = os.path.expanduser("~/Library/Application Support/Anki2")
IMAGES_FOLDER = "images"  # Thư mục lưu ảnh trước khi copy

# ------------------------
def get_ipa_and_pos_cambridge(word):
    try:
        url = f"https://dictionary.cambridge.org/us/dictionary/english/{word}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        ipa_span = soup.find("span", class_="ipa")
        ipa_text = f"/{ipa_span.text.strip()}/" if ipa_span else "(không tìm thấy IPA)"

        pos_span = soup.find("span", class_="pos dpos")
        pos_text = pos_span.text.strip().lower() if pos_span else "khác"

        # Dịch loại từ sang tiếng Việt
        pos_map = {
            "noun": "(n)",
            "verb": "(v)",
            "adjective": "(adj)",
            "adverb": "(adv)",
            "pronoun": "(pron)",
            "preposition": "(prep)",
            "conjunction": "(conj)",
            "determiner": "(det)",
            "exclamation": "(excl)"
        }
        vi_pos = pos_map.get(pos_text, "(khác)")

        return ipa_text, vi_pos
    except Exception as e:
        print(f"[❌ IPA/POS] {word}: {e}")
        return "(lỗi IPA)", "khác"

# ------------------------
# Dịch nghĩa tiếng Việt
# ------------------------
def translate_to_vietnamese(text):
    try:
        return GoogleTranslator(source='en', target='vi').translate(text)
    except Exception as e:
        print(f"[❌ Dịch] {text}: {e}")
        return "(lỗi dịch)"

# ------------------------
# Tải ảnh từ Unsplash
# ------------------------
def download_unsplash_image(query):
    try:
        if not os.path.exists(IMAGES_FOLDER):
            os.makedirs(IMAGES_FOLDER)

        url = f"https://api.unsplash.com/search/photos?query={query}&client_id={UNSPLASH_ACCESS_KEY}&per_page=1"
        resp = requests.get(url, timeout=10)
        data = resp.json()

        if data.get("results"):
            image_url = data["results"][0]["urls"]["regular"]
            image_data = requests.get(image_url).content

            file_name = f"{query}.jpg"
            file_path = os.path.join(IMAGES_FOLDER, file_name)
            with open(file_path, "wb") as f:
                f.write(image_data)
            return file_name
        else:
            return ""
    except:
        return ""

# ------------------------
def read_unique_words_from_text(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read().lower()

    phrases = re.findall(r"'([^']+)'", text)  # lấy cụm từ trong dấu '
    for p in phrases:
        text = text.replace(f"'{p}'", "")  # xoá khỏi text gốc để không split tiếp

    words = re.findall(r'\b[a-zA-Z]+\b', text)  # các từ lẻ
    all_terms = sorted(set(words + phrases))  # gộp & loại trùng
    return all_terms

# ------------------------
# Xử lý toàn bộ từ và xuất Excel
# ------------------------
def option1_generate_excel(input_txt, output_excel):
    words = read_unique_words_from_text(input_txt)
    data = []
    for word in words:
        ipa, pos = get_ipa_and_pos_cambridge(word)
        vi = translate_to_vietnamese(word)
        print(f"{word:<15} | {ipa:<18} | {pos:<10} | {vi}")
        data.append({
            'word': word,
            'pos': pos,
            'ipa': ipa,
            'tiếng Việt': vi
        })
    pd.DataFrame(data).to_excel(output_excel, index=False, engine='openpyxl')
    print(f"✅ Đã tạo file Excel: {output_excel}")

# ------------------------
# Option 2: Đọc Excel, tải ảnh, xuất CSV cho Anki
# ------------------------
def option2_add_images(input_excel, output_csv):
    df = pd.read_excel(input_excel, engine='openpyxl')
    # img_files = []
    img_tags = []

    for word in df['word']:
        img_file = download_unsplash_image(word)
        # img_files.append(img_file)
        if img_file:
            img_tags.append(f'<img src="{img_file}">')
        else:
            img_tags.append("")

    # df['image_file'] = img_files
    df['image_html'] = img_tags

    df.to_csv(output_csv, index=False, encoding='utf-8-sig', header=False)
    print(f"✅ CSV cho Anki: {output_csv}")
    print(f"📂 Ảnh đã lưu trong thư mục: {IMAGES_FOLDER}")

# ------------------------
def option3_copy_images_to_anki():
    anki_path = Path(os.path.expandvars(ANKI_BASE_FOLDER))
    if not anki_path.exists():
        print("⚠️ Đường dẫn Anki không tồn tại.")
        return

    profiles = [p.name for p in anki_path.iterdir() if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("addon")]
    if not profiles:
        print("⚠️ Không tìm thấy profile nào.")
        return

    print("\nDanh sách profile:")
    for i, p in enumerate(profiles, 1):
        print(f"{i}. {p}")

    try:
        choice = int(input("Chọn số profile: "))
        profile_name = profiles[choice - 1]
    except:
        print("❌ Lựa chọn không hợp lệ.")
        return

    media_path = anki_path / profile_name / "collection.media"
    if not media_path.exists():
        print("⚠️ Không tìm thấy thư mục collection.media.")
        return

    if not os.path.exists(IMAGES_FOLDER):
        print("⚠️ Thư mục ảnh chưa tồn tại. Hãy chạy Option 2 trước.")
        return

    for img_file in os.listdir(IMAGES_FOLDER):
        src = os.path.join(IMAGES_FOLDER, img_file)
        dst = os.path.join(media_path, img_file)
        shutil.copy2(src, dst)
        print(f"📂 Copy {img_file} -> {media_path}")

    print("✅ Đã copy toàn bộ ảnh vào collection.media.")

# ------------------------
if __name__ == "__main__":
    while True:
        mode = input("Chọn chế độ (1: Tạo Excel, 2: Tải ảnh & CSV Anki, 3: Copy ảnh vào Anki, 4: Thoát): ").strip()
        if mode == "1":
            option1_generate_excel("input.txt", "output.xlsx")
        elif mode == "2":
            option2_add_images("output.xlsx", "output_with_images.csv")
        elif mode == "3":
            option3_copy_images_to_anki()
        elif mode == "4":
            print("👋 Đã thoát chương trình.")
            break
        else:
            print("❌ Lựa chọn không hợp lệ!")
