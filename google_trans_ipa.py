import re
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import pandas as pd
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ====== Config from .env ======
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
ANKI_BASE_FOLDER = os.getenv("ANKI_BASE_FOLDER")
IMAGES_FOLDER = os.getenv("IMAGES_FOLDER", "images")
AUDIOS_FOLDER = os.getenv("AUDIOS_FOLDER", "audios")

# ------------------------
def get_ipa_and_pos_cambridge(word):
    try:
        url = f"https://dictionary.cambridge.org/us/dictionary/english/{word}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        ipa_span = soup.find("span", class_="ipa")
        ipa_text = f"/{ipa_span.text.strip()}/" if ipa_span else None

        pos_span = soup.find("span", class_="pos dpos")
        pos_text = pos_span.text.strip().lower() if pos_span else None

        # Generate audio using gtts
        audio_file = ""
        try:
            audios_folder = AUDIOS_FOLDER
            if not os.path.exists(audios_folder):
                os.makedirs(audios_folder)
            audio_file = os.path.join(audios_folder, f"{word.replace(' ', '_')}.mp3")
            from gtts import gTTS
            tts = gTTS(text=word, lang='en')
            tts.save(audio_file)
        except Exception as e:
            print(f"❌ Error generating audio with gtts: {e}")
            audio_file = ""

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

        # For phrases: if IPA is missing or looks like only one word, use IPA from each word instead
        if " " in word:
            phrase_word_count = len(word.split())
            ipa_word_count = len(re.findall(r"/[^/]+/", ipa_text)) if ipa_text else 0
            if not ipa_text or ipa_word_count < phrase_word_count:
                words = word.split()
                ipa_list = []
                pos_list = []
                for w in words:
                    ipa, pos, _ = get_ipa_and_pos_cambridge(w)
                    ipa_list.append(ipa)
                    pos_list.append(pos)
                merged_ipa = " ".join(ipa_list)
                merged_pos = ", ".join(set(pos_list))
                # Always use phrase audio (gtts) for phrases
                return merged_ipa, merged_pos, audio_file
        vi_pos = pos_map.get(pos_text, "(khác)") if pos_text else "(khác)"
        return ipa_text if ipa_text else "(không tìm thấy IPA)", vi_pos, audio_file
    except Exception as e:
        print(f"[❌ IPA/POS] {word}: {e}")
        return "(lỗi IPA)", "khác", ""

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
    all_terms = set(words + phrases)  # gộp & loại trùng
    return all_terms

# ------------------------
# Xử lý toàn bộ từ và xuất Excel
# ------------------------
def option1_generate_words_per_space(input_txt, output_excel):
    words = read_unique_words_from_text(input_txt)
    data = []
    for word in words:
        ipa, pos, _ = get_ipa_and_pos_cambridge(word)  # Do not generate audio here
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
# Xử lý từng dòng và xuất Excel (mỗi dòng là 1 từ/cụm từ)
# ------------------------
def option2_generate_words_per_line(input_txt, output_excel):
    with open(input_txt, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    data = []
    for word in lines:
        ipa, pos, _ = get_ipa_and_pos_cambridge(word)
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
# Option 3: Đọc Excel, tải ảnh, xuất CSV cho Anki
# ------------------------
def option3_add_images(input_excel, output_csv):
    df = pd.read_excel(input_excel, engine='openpyxl')
    img_tags = []
    audio_tags = []

    for idx, row in df.iterrows():
        word = row['word']
        img_file = download_unsplash_image(word)
        if img_file:
            img_tags.append(f'<img src="{img_file}">')
        else:
            img_tags.append("")
        # Generate audio here using gtts
        try:
            audios_folder = AUDIOS_FOLDER
            if not os.path.exists(audios_folder):
                os.makedirs(audios_folder)
            audio_file = os.path.join(audios_folder, f"{word.replace(' ', '_')}.mp3")
            from gtts import gTTS
            tts = gTTS(text=word, lang='en')
            tts.save(audio_file)
            audio_tags.append(f'[sound:{os.path.basename(audio_file)}]')
        except Exception as e:
            print(f"❌ Error generating audio with gtts: {e}")
            audio_tags.append("")

    df['image_html'] = img_tags
    df['audio'] = audio_tags

    # Ensure 'audio' is the last column
    cols = list(df.columns)
    if 'audio' in cols:
        cols = [c for c in cols if c != 'audio'] + ['audio']
        df = df[cols]

    import csv
    df.to_csv(output_csv, index=False, encoding='utf-8-sig', header=False, sep='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
    print(f"✅ CSV cho Anki: {output_csv}")
    print(f"📂 Ảnh đã lưu trong thư mục: {IMAGES_FOLDER}")

# ------------------------
def option4_copy_images_to_anki():
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

    # Copy images
    if not os.path.exists(IMAGES_FOLDER):
        print("⚠️ Thư mục ảnh chưa tồn tại. Hãy chạy Option 2 trước.")
    else:
        for img_file in os.listdir(IMAGES_FOLDER):
            src = os.path.join(IMAGES_FOLDER, img_file)
            dst = os.path.join(media_path, img_file)
            shutil.copy2(src, dst)
            print(f"📂 Copy {img_file} -> {media_path}")
        print("✅ Đã copy toàn bộ ảnh vào collection.media.")

    # Copy audio files
    
    # Copy images
    if not os.path.exists(AUDIOS_FOLDER):
        print("⚠️ Thư mục audio chưa tồn tại. Hãy chạy Option 2 trước.")
    else:
        for audio_file in os.listdir(AUDIOS_FOLDER):
            src = os.path.join(AUDIOS_FOLDER, audio_file)
            dst = os.path.join(media_path, audio_file)
            shutil.copy2(src, dst)
            print(f"📂 Copy {audio_file} -> {media_path}")
        print("✅ Đã copy toàn bộ audio vào collection.media.")

# ------------------------
if __name__ == "__main__":
    while True:
        print("\nChọn chế độ:")
        print("1: Lấy từ vựng từ đoạn văn")
        print("2: Lấy từ vựng theo từng dòng")
        print("3: Tải ảnh & CSV Anki")
        print("4: Copy ảnh/audio vào Anki")
        print("5: Thoát ứng dụng")
        mode = input("Nhập số chế độ (1-5): ").strip()
        if mode == "1":
            option1_generate_words_per_space("input.txt", "output.xlsx")
        elif mode == "2":
            option2_generate_words_per_line("input.txt", "output.xlsx")
        elif mode == "3":
            option3_add_images("output.xlsx", "output_with_images.csv")
        elif mode == "4":
            option4_copy_images_to_anki()
        elif mode == "5":
            print("👋 Đã thoát ứng dụng.")
            break
        else:
            print("❌ Lựa chọn không hợp lệ!")
