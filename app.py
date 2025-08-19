import streamlit as st
import requests
import re
import statistics
from collections import Counter

# --- FUNGSI-FUNGSI UTAMA ---

def extract_price(text):
    """Mengekstrak harga dari teks dengan regex yang lebih fleksibel."""
    # Pola ini mencari angka (dengan/tanpa titik) yang memiliki minimal 5-6 digit.
    # Ini membantu membedakan harga dari angka lain (stok, terjual, model).
    # Bisa didahului "Rp" (opsional).
    # Contoh: Rp15.000.000, 15.000.000, Rp 1.500.000, 500000
    pattern = r"(?:Rp\s?\.?)?(\d{1,3}(?:\.\d{3})+(?!\d)|\d{6,})"
    matches = re.findall(pattern, text)
    
    if not matches:
        return None
    
    # Ambil angka valid pertama, bersihkan dari titik, dan konversi
    for match in matches:
        cleaned_price = re.sub(r"[^\d]", "", match)
        if cleaned_price.isdigit():
            price = int(cleaned_price)
            # Filter sederhana untuk harga yang tidak masuk akal (di bawah 100rb)
            if price > 100000:
                return price
    return None

def search_price_on_google(api_key, search_engine_id, query, pages=3):
    """Mencari di beberapa halaman Google untuk mendapatkan lebih banyak data."""
    all_items = []
    st.write(f"🔍 Mencari dengan query: `{query}`")
    
    for page in range(pages):
        start_index = page * 10 + 1
        params = {
            'key': api_key,
            'cx': search_engine_id,
            'q': query,
            'num': 10,
            'start': start_index,
        }
        
        try:
            response = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
            response.raise_for_status() # Lontarkan error jika status code bukan 2xx
            search_results = response.json()
            items = search_results.get("items", [])
            if not items:
                break # Berhenti jika tidak ada hasil lagi
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
        
        # Filter 1: Hindari duplikat & URL yang tidak relevan
        if link in processed_links or "youtube.com" in link or "/berita/" in link:
            continue
            
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        combined_text = f"{title} {snippet}"
        
        price = extract_price(combined_text)
        
        if price:
            data_final.append({
                "judul": title,
                "harga": price,
                "link": link
            })
            processed_links.add(link)
            
    return data_final

# --- UI STREAMLIT ---

st.set_page_config(page_title="Cek Harga Bekas", layout="wide")
st.title("📊 Aplikasi Pengecek Rata-Rata Harga Barang Bekas")
st.write("Masukkan nama barang untuk mencari estimasi harga bekasnya di Tokopedia & Shopee.")

# --- FORM INPUT ---
with st.form("search_form"):
    # Gunakan st.secrets untuk menyimpan API Key & CX
    API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    SEARCH_ENGINE_ID = st.secrets.get("GOOGLE_CX", "")

    product_name = st.text_input("Nama Barang (contoh: Samsung Z Flip 5 256GB)", "iPhone 14 Pro 128GB")
    
    submitted = st.form_submit_button("Cari Harga Rata-rata!")

if submitted:
    if not API_KEY or not SEARCH_ENGINE_ID:
        st.error("Harap konfigurasikan `GOOGLE_API_KEY` dan `GOOGLE_CX` di Streamlit Secrets!")
    elif not product_name:
        st.warning("Nama barang tidak boleh kosong.")
    else:
        # Buat query yang lebih optimal
        query = f'harga "{product_name}" (bekas|second|seken) (site:tokopedia.com OR site:shopee.co.id) -baru -kredit'
        
        with st.spinner(f"Mencari harga untuk '{product_name}'... Ini mungkin butuh beberapa detik."):
            raw_items = search_price_on_google(API_KEY, SEARCH_ENGINE_ID, query, pages=3)
            
            if not raw_items:
                st.warning("Tidak ada hasil yang ditemukan dari Google. Coba kata kunci yang lebih umum.")
            else:
                st.info(f"Ditemukan {len(raw_items)} total hasil pencarian mentah. Memproses...")
                
                final_data = process_search_results(raw_items)
                
                if not final_data:
                    st.error("Tidak ada data harga yang valid ditemukan setelah diproses. Coba ubah kata kunci Anda.")
                else:
                    st.success(f"Berhasil mengekstrak harga dari **{len(final_data)}** listing yang relevan!")
                    
                    all_prices = [item['harga'] for item in final_data]
                    
                    # --- TAMPILKAN HASIL ANALISIS ---
                    st.subheader("📊 Hasil Analisis Harga")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Harga Rata-rata", f"Rp {int(statistics.mean(all_prices)):,}")
                    col2.metric("Harga Tengah (Median)", f"Rp {int(statistics.median(all_prices)):,}")
                    col3.metric("Harga Terendah", f"Rp {min(all_prices):,}")
                    col4.metric("Harga Tertinggi", f"Rp {max(all_prices):,}")

                    st.write("---")
                    st.subheader("📋 Detail Listing yang Ditemukan")
                    
                    # Tampilkan dalam bentuk tabel yang rapi
                    display_data = []
                    for item in sorted(final_data, key=lambda x: x['harga']):
                        display_data.append({
                            "Harga": f"Rp {item['harga']:,}",
                            "Judul Listing": item['judul'],
                            "Link": item['link']
                        })
                    
                    st.dataframe(display_data, use_container_width=True)
