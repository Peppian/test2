import streamlit as st
import requests
import re
import statistics
import numpy as np

# --- (Fungsi extract_price, is_valid_product_listing, dll TIDAK BERUBAH) ---
# ... (Salin fungsi-fungsi dari respons sebelumnya di sini) ...
def extract_price(text):
    pattern = r"(?:Rp\s?\.?)?(\d{1,3}(?:\.\d{3})+(?!\d)|\d{6,})"
    matches = re.findall(pattern, text)
    if not matches: return None
    for match in matches:
        cleaned_price = re.sub(r"[^\d]", "", match)
        if cleaned_price.isdigit():
            price = int(cleaned_price)
            if price > 100000:
                return price
    return None

def is_valid_product_listing(title, snippet):
    text = f"{title} {snippet}".lower()
    accessory_blacklist = [
        'case', 'casing', 'cover', 'tempered glass', 'hydrogel', 'spy', 'privacy',
        'kaca', 'baterai', 'batre', 'charger', 'kabel', 'part', 'sparepart',
        'backdoor', 'lcd', 'layar', 'gamepad', 'controller', 'holder', 'strap',
        'earphone', 'headset', 'antigores'
    ]
    if any(word in text for word in accessory_blacklist):
        return False
    shop_page_blacklist = ['toko', 'online', 'produk lengkap', 'harga terbaik']
    if any(phrase in text for phrase in shop_page_blacklist) and "jual" not in text:
        return False
    positive_signals = ['bekas', 'second', 'seken', '2nd', 'preloved']
    if not any(word in text for word in positive_signals):
        return False
    strong_negative_signals = ['bnib', 'segel', 'brand new', 'garansi resmi', 'official store', 'baru']
    if any(word in text for word in strong_negative_signals):
        return False
    return True

def remove_price_outliers(prices):
    if len(prices) < 4:
        return prices
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    return [price for price in prices if lower_bound <= price <= upper_bound]

def search_price_on_google(api_key, search_engine_id, query, pages=2):
    all_items = []
    st.info(f"⚙️ Query yang dikirim ke Google: `{query}`")
    for page in range(pages):
        start_index = page * 10 + 1
        params = {'key': api_key, 'cx': search_engine_id, 'q': query, 'num': 10, 'start': start_index}
        try:
            response = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
            response.raise_for_status()
            items = response.json().get("items", [])
            if not items: break
            all_items.extend(items)
        except requests.exceptions.RequestException as e:
            st.error(f"Gagal menghubungi Google API: {e}")
            return []
    return all_items

def process_search_results(items):
    data_final = []
    processed_links = set()
    for item in items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        if not is_valid_product_listing(title, snippet):
            continue
        link = item.get("link", "")
        if link in processed_links:
            continue
        price = extract_price(f"{title} {snippet}")
        if price:
            data_final.append({"judul": title, "harga": price, "link": link})
            processed_links.add(link)
    return data_final

# --- PERUBAHAN UTAMA ADA DI SINI ---

def create_slug(text):
    """Mengubah teks menjadi format slug URL (lowercase, hyphenated)."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text) # Hapus karakter non-alfanumerik
    text = re.sub(r'[\s-]+', '-', text).strip('-') # Ganti spasi dengan hyphen
    return text

def build_smartphone_query(brand, model, spec):
    """Membangun query dengan filter inurl:[model-slug] untuk presisi tinggi."""
    used_keywords = "(bekas|second|seken|2nd|preloved)"
    negative_keywords = "-BNIB -segel -resmi -baru -official"
    negative_url_patterns = "-inurl:search" # Cukup search saja sekarang

    # Buat slug dari gabungan merek dan model untuk target URL
    model_slug = create_slug(f"{brand} {model}")
    
    # Kata kunci pencarian utama tetap fleksibel
    search_keywords = f'{brand} "{model}" {spec}'
    
    # Gabungkan semua bagian
    query = f'{search_keywords} inurl:{model_slug} {used_keywords} (site:tokopedia.com OR site:shopee.co.id) {negative_keywords} {negative_url_patterns}'
    return query.strip()

# --- UI STREAMLIT (Tidak ada perubahan) ---
st.set_page_config(page_title="Cek Harga Smartphone Bekas", layout="wide")
st.title("📱 Aplikasi Pengecek Harga Smartphone Bekas")
st.write("Masukkan detail smartphone untuk mendapatkan estimasi harga pasaran bekas.")

with st.form("search_form"):
    API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    SEARCH_ENGINE_ID = st.secrets.get("GOOGLE_CX", "")
    col1, col2, col3 = st.columns(3)
    with col1:
        brand = st.text_input("Merek Smartphone", "Apple")
    with col2:
        model = st.text_input("Model Inti", "iPhone 14 Pro")
    with col3:
        spec = st.text_input("Spesifikasi (Opsional)", "256GB")
    submitted = st.form_submit_button("Cek Harga Pasaran!")

# ... (Sisa kode setelah `if submitted` sama persis, karena perubahan hanya di build_smartphone_query) ...
if submitted:
    if not API_KEY or not SEARCH_ENGINE_ID:
        st.error("Harap konfigurasikan `GOOGLE_API_KEY` dan `GOOGLE_CX` di Streamlit Secrets!")
    elif not brand or not model:
        st.warning("Merek dan Model wajib diisi.")
    else:
        query = build_smartphone_query(brand, model, spec)
        product_name_display = f"{brand} {model} {spec}".strip()
        with st.spinner(f"Mencari harga untuk '{product_name_display}'..."):
            raw_items = search_price_on_google(API_KEY, SEARCH_ENGINE_ID, query, pages=3)
            if not raw_items:
                st.warning("Tidak ada hasil yang ditemukan. Coba periksa kembali input atau coba tanpa spesifikasi.")
            else:
                st.write(f"Ditemukan {len(raw_items)} total hasil mentah. Menerapkan filter super ketat...")
                final_data = process_search_results(raw_items)
                if not final_data:
                    st.error("Tidak ada data harga yang valid ditemukan setelah difilter. Coba lagi dengan kata kunci lain.")
                else:
                    all_prices = [item['harga'] for item in final_data]
                    cleaned_prices = remove_price_outliers(all_prices)
                    if not cleaned_prices:
                         st.error("Data harga yang ditemukan terlalu bervariasi untuk dianalisis. Coba kata kunci yang lebih spesifik.")
                    else:
                        st.success(f"Berhasil menganalisis **{len(cleaned_prices)}** dari **{len(all_prices)}** listing yang relevan (setelah membersihkan outlier).")
                        st.subheader("📊 Hasil Analisis Harga")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Harga Rata-rata", f"Rp {int(statistics.mean(cleaned_prices)):,}")
                        col2.metric("Harga Tengah (Median)", f"Rp {int(statistics.median(cleaned_prices)):,}")
                        col3.metric("Harga Terendah", f"Rp {min(cleaned_prices):,}")
                        col4.metric("Harga Tertinggi", f"Rp {max(cleaned_prices):,}")
                        st.write("---")
                        st.subheader("📋 Detail Listing yang Dianalisis")
                        display_data = [{"Harga": f"Rp {item['harga']:,}", "Judul Listing": item['judul'], "Link": item['link']} 
                                        for item in sorted(final_data, key=lambda x: x['harga']) 
                                        if item['harga'] in cleaned_prices]
                        st.dataframe(display_data, use_container_width=True)
