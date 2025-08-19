import streamlit as st
import requests
import re
import statistics

# --- FUNGSI-FUNGSI UTAMA (Termasuk yang baru) ---

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

# --- TAMBAHAN: FUNGSI UNTUK FILTER LEBIH KETAT ---

def generate_negative_keywords(product_name):
    """Membuat kata kunci negatif untuk model lama secara dinamis."""
    match = re.search(r'\b(\d+)\b', product_name)
    if not match: return ""

    current_model_num = int(match.group(1))
    # Ambil basis nama produk sebelum angka. Cth: "Samsung Z Flip 5" -> "Samsung Z Flip"
    product_base_name = product_name[:match.start()].strip() 
    
    negative_keywords = []
    # Buat keyword negatif untuk 3 model sebelumnya agar lebih presisi
    for i in range(1, 4):
        if current_model_num - i > 0:
            negative_keywords.append(f'-"{product_base_name} {current_model_num - i}"')
            
    return " ".join(negative_keywords)

def is_title_relevant(title, product_name):
    """Memvalidasi apakah judul listing relevan dengan nama produk yang dicari."""
    title_lower = title.lower()
    # Pecah nama produk menjadi kata kunci esensial dan abaikan kata pendek
    required_keywords = [word for word in product_name.lower().split() if len(word) > 1]
    
    # Judul harus mengandung SEMUA kata kunci esensial
    return all(keyword in title_lower for keyword in required_keywords)

# --- FUNGSI API & PROSES DATA (Dengan Modifikasi) ---

def search_price_on_google(api_key, search_engine_id, query, pages=3):
    """Mencari di beberapa halaman Google untuk mendapatkan lebih banyak data."""
    all_items = []
    st.info(f"⚙️ Query yang dikirim ke Google: `{query}`") # Tampilkan query final
    
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

def process_search_results(items, product_name): # --- MODIFIKASI: Tambahkan product_name ---
    """Memproses hasil pencarian mentah menjadi data harga yang bersih."""
    data_final = []
    processed_links = set()

    for item in items:
        link = item.get("link", "")
        title = item.get("title", "")

        # --- MODIFIKASI: Terapkan filter relevansi judul di sini ---
        if not is_title_relevant(title, product_name):
            continue # Lewati item ini jika judulnya tidak relevan
        
        if link in processed_links or "youtube.com" in link or "/berita/" in link:
            continue
            
        snippet = item.get("snippet", "")
        combined_text = f"{title} {snippet}"
        price = extract_price(combined_text)
        
        if price:
            data_final.append({"judul": title, "harga": price, "link": link})
            processed_links.add(link)
            
    return data_final

# --- UI STREAMLIT ---

st.set_page_config(page_title="Cek Harga Bekas", layout="wide")
st.title("📊 Aplikasi Pengecek Rata-Rata Harga Barang Bekas")
st.write("Masukkan nama barang yang spesifik (termasuk model dan varian) untuk hasil terbaik.")

with st.form("search_form"):
    API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    SEARCH_ENGINE_ID = st.secrets.get("GOOGLE_CX", "")

    product_name = st.text_input("Nama Barang", "Samsung Z Flip 5 256GB")
    submitted = st.form_submit_button("Cari Harga Rata-rata!")

if submitted:
    if not API_KEY or not SEARCH_ENGINE_ID:
        st.error("Harap konfigurasikan `GOOGLE_API_KEY` dan `GOOGLE_CX` di Streamlit Secrets!")
    elif not product_name:
        st.warning("Nama barang tidak boleh kosong.")
    else:
        # --- MODIFIKASI: Buat query yang lebih presisi ---
        negative_keywords = generate_negative_keywords(product_name)
        base_query = f'harga "{product_name}" (bekas|second|seken) (site:tokopedia.com OR site:shopee.co.id) -baru -kredit'
        query = f"{base_query} {negative_keywords}"
        
        with st.spinner(f"Mencari harga untuk '{product_name}'..."):
            raw_items = search_price_on_google(API_KEY, SEARCH_ENGINE_ID, query, pages=3)
            
            if not raw_items:
                st.warning("Tidak ada hasil yang ditemukan dari Google. Coba kata kunci yang lebih umum.")
            else:
                st.write(f"Ditemukan {len(raw_items)} total hasil mentah. Memfilter dan memproses...")
                
                final_data = process_search_results(raw_items, product_name) # Kirim product_name ke fungsi proses
                
                if not final_data:
                    st.error("Tidak ada data harga yang valid ditemukan setelah difilter. Pastikan nama produk spesifik dan coba lagi.")
                else:
                    st.success(f"Berhasil mengekstrak harga dari **{len(final_data)}** listing yang sangat relevan!")
                    
                    all_prices = [item['harga'] for item in final_data]
                    
                    st.subheader("📊 Hasil Analisis Harga")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Harga Rata-rata", f"Rp {int(statistics.mean(all_prices)):,}")
                    col2.metric("Harga Tengah (Median)", f"Rp {int(statistics.median(all_prices)):,}")
                    col3.metric("Harga Terendah", f"Rp {min(all_prices):,}")
                    col4.metric("Harga Tertinggi", f"Rp {max(all_prices):,}")

                    st.write("---")
                    st.subheader("📋 Detail Listing yang Ditemukan")
                    
                    display_data = [{"Harga": f"Rp {item['harga']:,}", "Judul Listing": item['judul'], "Link": item['link']} for item in sorted(final_data, key=lambda x: x['harga'])]
                    st.dataframe(display_data, use_container_width=True)
