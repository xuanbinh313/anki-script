# ------------------------
# Tải audio từ URL vào thư mục audios
# ------------------------
def download_audio_file(audio_url, file_name):
    headers = {"User-Agent": "Mozilla/5.0"}
    audios_folder = "audios"
    if not os.path.exists(audios_folder):
        os.makedirs(audios_folder)
    file_path = os.path.join(audios_folder, file_name)
    try:
        resp = requests.get(audio_url, headers=headers, timeout=10)
        resp.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(resp.content)
        print(f"✅ Downloaded: {file_path}")
        return file_path
    except Exception as e:
        print(f"❌ Error downloading audio: {e}")
        return ""

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

        # Find all audio sources for US English
        audio_url = None
        audio_sources = soup.find_all("source", attrs={"type": "audio/mpeg"})
        if audio_sources:
            # Try to find the source whose src contains the phrase (no spaces, lowercase)
            word_key = word.replace(" ", "").lower()
            for src_tag in audio_sources:
                src_val = src_tag.get("src", "")
                if word_key in src_val.replace("/us/media/english/us_pron/", "").replace(".mp3", "").replace("/", "").lower():
                    audio_url = src_val
                    break
            # If not found, just use the first
            if not audio_url:
                audio_url = audio_sources[0].get("src", "")
        # Fallback: Try to find <audio> tag with <source type="audio/mpeg">
        if not audio_url:
            audio_section = soup.find("audio", class_="hdn")
            if audio_section:
                source_tag = audio_section.find("source", attrs={"type": "audio/mpeg"})
                if source_tag and source_tag.has_attr("src"):
                    audio_url = source_tag["src"]
        # Fallback: Try to find <span class="audio_play_button">
        if not audio_url:
            audio_tag = soup.find("span", class_="audio_play_button")
            if audio_tag and audio_tag.has_attr("data-src-mp3"):
                audio_url = audio_tag["data-src-mp3"]

        # Fix relative audio URLs
        if audio_url and audio_url.startswith("/"):
            audio_url = "https://dictionary.cambridge.org" + audio_url

        audio_file = ""
        if audio_url:
            audio_file = download_audio_file(audio_url, f"{word.replace(' ', '_')}.mp3")

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
                audio_list = []
                for w in words:
                    ipa, pos, audio = get_ipa_and_pos_cambridge(w)
                    ipa_list.append(ipa)
                    pos_list.append(pos)
                    audio_list.append(audio)
                merged_ipa = " ".join(ipa_list)
                merged_pos = ", ".join(sorted(set(pos_list)))
                merged_audio = ";".join([a for a in audio_list if a])
                return merged_ipa, merged_pos, merged_audio
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
    all_terms = sorted(set(words + phrases))  # gộp & loại trùng
    return all_terms

# ------------------------
# Xử lý toàn bộ từ và xuất Excel
# ------------------------
def option1_generate_excel(input_txt, output_excel):
    words = read_unique_words_from_text(input_txt)
    data = []
    for word in words:
        ipa, pos, audio = get_ipa_and_pos_cambridge(word)
        vi = translate_to_vietnamese(word)
        print(f"{word:<15} | {ipa:<18} | {pos:<10} | {vi} | {audio}")
        data.append({
            'word': word,
            'pos': pos,
            'ipa': ipa,
            'tiếng Việt': vi,
            'audio': audio
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
    audio_files = [f for f in os.listdir('.') if f.endswith('.mp3')]
    if audio_files:
        for audio_file in audio_files:
            src = os.path.join('.', audio_file)
            dst = os.path.join(media_path, audio_file)
            shutil.copy2(src, dst)
            print(f"🔊 Copy {audio_file} -> {media_path}")
        print("✅ Đã copy toàn bộ audio vào collection.media.")
    else:
        print("⚠️ Không tìm thấy file audio (.mp3) trong thư mục hiện tại.")

# ------------------------
if __name__ == "__main__":
    while True:
        mode = input("Chọn chế độ (1: Tạo Excel, 2: Tải ảnh & CSV Anki, 3: Copy ảnh/audio vào Anki").strip()
        if mode == "1":
            option1_generate_excel("input.txt", "output.xlsx")
        elif mode == "2":
            option2_add_images("output.xlsx", "output_with_images.csv")
        elif mode == "3":
            option3_copy_images_to_anki()
        else:
            print("❌ Lựa chọn không hợp lệ!")
