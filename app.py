import streamlit as st
import requests
import re
import statistics
import numpy as np

# --- FUNGSI-FUNGSI UTAMA ---

def extract_price(text):
    """Mengekstrak harga dari teks dengan regex yang lebih fleksibel."""
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

# --- PERUBAHAN: Fungsi filter dan analisis yang disempurnakan ---

def build_smartphone_query(product_name):
    """Membangun query yang fleksibel dan kuat khusus untuk smartphone."""
    # Definisikan kata kunci wajib untuk kondisi bekas
    used_keywords = "(bekas|second|seken|2nd|preloved)"
    # Definisikan kata kunci negatif yang kuat
    negative_keywords = "-BNIB -segel -resmi -baru -official"
    
    # Logika sederhana untuk memecah nama produk
    parts = product_name.split()
    brand = parts[0]
    model_keywords = " ".join(parts[1:])
    
    # Gabungkan menjadi model inti dalam tanda kutip jika lebih dari satu kata
    if len(parts) > 2:
        # Cth: "iPhone 14 Pro", "Galaxy S23 Ultra"
        model_part = f'"{model_keywords}"'
    else:
        # Cth: "13T" (jika brand sudah dipisah)
        model_part = model_keywords
        
    # Template query final
    query = f'harga {brand} {model_part} {used_keywords} (site:tokopedia.com OR site:shopee.co.id) {negative_keywords}'
    return query

def is_definitely_used(title, snippet):
    """Fungsi validasi ketat untuk memastikan listing adalah barang bekas."""
    text = f"{title} {snippet}".lower()
    positive_signals = ['bekas', 'second', 'seken', '2nd', 'preloved']
    if not any(word in text for word in positive_signals):
        return False
    strong_negative_signals = ['bnib', 'segel', 'brand new', 'garansi resmi', 'official store', 'baru']
    if any(word in text for word in strong_negative_signals):
        return False
    return True

def remove_price_outliers(prices):
    """Membersihkan daftar harga dari nilai ekstrem (outlier) menggunakan IQR."""
    if len(prices) < 4:
        return prices
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    return [price for price in prices if lower_bound <= price <= upper_bound]

# --- FUNGSI API & PROSES DATA ---

def search_price_on_google(api_key, search_engine_id, query, pages=2): # Mengurangi halaman untuk pencarian lebih terfokus
    """Mencari di beberapa halaman Google."""
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
    """Memproses hasil pencarian mentah menjadi data harga yang bersih."""
    data_final = []
    processed_links = set()
    for item in items:
        link = item.get("link", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        
        # --- PERUBAHAN: Gunakan filter is_definitely_used yang lebih ketat ---
        if not is_definitely_used(title, snippet):
            continue
            
        if link in processed_links:
            continue
            
        price = extract_price(f"{title} {snippet}")
        if price:
            data_final.append({"judul": title, "harga": price, "link": link})
            processed_links.add(link)
    return data_final

# --- UI STREAMLIT ---

st.set_page_config(page_title="Cek Harga Smartphone Bekas", layout="wide")
st.title("📱 Aplikasi Pengecek Harga Smartphone Bekas")
st.write("Fokus pada Smartphone. Masukkan Merek, Model, dan Varian untuk hasil terbaik.")

with st.form("search_form"):
    API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    SEARCH_ENGINE_ID = st.secrets.get("GOOGLE_CX", "")

    product_name = st.text_input("Nama Smartphone", "Apple iPhone 14 Pro 256GB")
    submitted = st.form_submit_button("Cek Harga Pasaran!")

if submitted:
    if not API_KEY or not SEARCH_ENGINE_ID:
        st.error("Harap konfigurasikan `GOOGLE_API_KEY` dan `GOOGLE_CX` di Streamlit Secrets!")
    elif not product_name:
        st.warning("Nama smartphone tidak boleh kosong.")
    else:
        # --- PERUBAHAN: Gunakan fungsi baru untuk membangun query ---
        query = build_smartphone_query(product_name)
        
        with st.spinner(f"Mencari harga untuk '{product_name}'..."):
            raw_items = search_price_on_google(API_KEY, SEARCH_ENGINE_ID, query, pages=3)
            
            if not raw_items:
                st.warning("Tidak ada hasil yang ditemukan dari Google. Coba kata kunci yang lebih spesifik.")
            else:
                st.write(f"Ditemukan {len(raw_items)} total hasil mentah. Menerapkan filter ketat...")
                
                final_data = process_search_results(raw_items)
                
                if not final_data:
                    st.error("Tidak ada data harga yang valid ditemukan setelah difilter. Coba lagi dengan nama produk lain.")
                else:
                    all_prices = [item['harga'] for item in final_data]
                    
                    # --- PERUBAHAN: Bersihkan harga dari outlier sebelum dianalisis ---
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
