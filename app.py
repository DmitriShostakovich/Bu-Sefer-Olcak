import streamlit as st
import pandas as pd
import yfinance as yf
from tefas import Crawler
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

# --- 1. AYARLAR VE DOSYA HAZIRLIĞI ---
st.set_page_config(page_title="Akıllı Portföyüm", layout="wide")

if "para_birimi" not in st.session_state:
    st.session_state["para_birimi"] = "TL"

PORTFOY_DOSYASI = "portfoy_verileri.csv"
GECMIS_DOSYASI = "gelisim_gecmisi.csv"

if not os.path.exists(PORTFOY_DOSYASI):
    pd.DataFrame(columns=['hisse_kodu', 'adet', 'tur', 'birim_fiyat']).to_csv(PORTFOY_DOSYASI, sep=';', index=False)

if not os.path.exists(GECMIS_DOSYASI):
    pd.DataFrame(columns=['tarih', 'toplam_tl', 'toplam_usd']).to_csv(GECMIS_DOSYASI, sep=';', index=False)

st.markdown("""<style>.stApp { background-color: #0e1117; color: white; } .ai-card { background-color: #1e2130; padding: 15px; border-radius: 10px; border-left: 5px solid #00ffcc; margin-bottom: 10px; }</style>""", unsafe_allow_html=True)

# --- 2. ÇEKİRDEK FONKSİYONLAR ---
def verileri_getir():
    df = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna(subset=['hisse_kodu'])
    if df.empty: return df, 1.0
    
    df.columns = df.columns.str.strip().str.lower()
    tefas = Crawler()
    bas_tar = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    bit_tar = datetime.now().strftime('%Y-%m-%d')
    
    try: usd_kur = yf.Ticker("USDTRY=X").history(period="1d")['Close'].iloc[-1]
    except: usd_kur = 1.0
    
    fiyatlar, isimler = [], []
    for _, row in df.iterrows():
        kod, tur = str(row['hisse_kodu']).upper(), str(row['tur']).lower()
        try:
            if tur == 'diger': 
                f, n = float(row['birim_fiyat']), kod
            elif tur == 'fon':
                fv = tefas.fetch(start=bas_tar, end=bit_tar, name=kod)
                if not fv.empty: f, n = fv['price'].iloc[-1], fv['title'].iloc[-1]
                else: f, n = 0, kod
            else:
                ykod = kod
                if kod in ["BTC", "ETH", "SOL"]: ykod, n = f"{kod}-USD", kod
                elif kod == "ALTIN": ykod, n = "GC=F", "Gram Altın"
                elif kod == "GUMUS": ykod, n = "SI=F", "Gram Gümüş"
                elif kod == "PLATIN": ykod, n = "PL=F", "Gram Platin"
                elif kod == "PALADYUM": ykod, n = "PA=F", "Gram Paladyum"
                else:
                    if tur == 'bist' and not kod.endswith(".IS"): ykod = f"{kod}.IS"
                    elif tur == 'doviz': ykod = f"{kod}TRY=X"
                    tick = yf.Ticker(ykod)
                    n = tick.info.get('shortName', kod)
                
                hist = yf.Ticker(ykod).history(period="5d")
                f = hist['Close'].iloc[-1] if not hist.empty else 0
                
                if (tur in ['abd', 'kripto'] or (tur == 'doviz' and kod != 'USD')) and kod not in ["ALTIN", "GUMUS", "PLATIN", "PALADYUM"]: 
                    if tur != 'doviz': f *= usd_kur
                if kod in ["ALTIN", "GUMUS", "PLATIN", "PALADYUM"]: f = (f / 31.1035) * usd_kur
            
            fiyatlar.append(f); isimler.append(n)
        except: fiyatlar.append(0); isimler.append(kod)
        
    df['Varlık İsmi'], df['birim_fiyat'] = isimler, fiyatlar
    df['Toplam Değer'] = df.apply(lambda r: r['birim_fiyat'] if r['tur'] == 'diger' else r['adet'] * r['birim_fiyat'], axis=1)
    
    toplam_tl = round(df['Toplam Değer'].sum(), 2)
    bugun = datetime.now().strftime("%Y-%m-%d")
    if toplam_tl > 0:
        gecmis_df = pd.read_csv(GECMIS_DOSYASI, sep=';').dropna()
        if bugun not in gecmis_df['tarih'].values:
            yeni = pd.DataFrame([[bugun, toplam_tl, round(toplam_tl/usd_kur, 2)]], columns=['tarih','toplam_tl','toplam_usd'])
            pd.concat([gecmis_df, yeni], ignore_index=True).to_csv(GECMIS_DOSYASI, sep=';', index=False)
        else:
            idx = gecmis_df[gecmis_df['tarih'] == bugun].index[0]
            gecmis_df.at[idx, 'toplam_tl'] = toplam_tl
            gecmis_df.to_csv(GECMIS_DOSYASI, sep=';', index=False)

    if st.session_state["para_birimi"] == "USD":
        df['Toplam Değer'] /= usd_kur
        df['birim_fiyat'] /= usd_kur
    return df.rename(columns={'hisse_kodu': 'Kod', 'adet': 'Adet'}), usd_kur

def ai_analiz(kod, tur):
    ykod = kod
    if kod in ["BTC", "ETH", "SOL"]: ykod = f"{kod}-USD"
    elif kod in ["ALTIN", "GUMUS", "PLATIN", "PALADYUM"]: ykod = {"ALTIN":"GC=F","GUMUS":"SI=F","PLATIN":"PL=F","PALADYUM":"PA=F"}[kod]
    elif tur == 'bist': ykod = f"{kod}.IS"
    elif tur == 'doviz': ykod = f"{kod}TRY=X"
    
    hist = yf.Ticker(ykod).history(period="3mo")
    if len(hist) < 20: return "Yetersiz veri"
    rsi = 100 - (100 / (1 + (hist['Close'].diff().where(hist['Close'].diff() > 0, 0).rolling(14).mean() / -hist['Close'].diff().where(hist['Close'].diff() < 0, 0).rolling(14).mean()))).iloc[-1]
    if rsi < 35: return "🟢 ALIM FIRSATI"
    elif rsi > 65: return "🔴 SATIM ZAMANI"
    else: return "🟡 TUT"

# --- 3. ARAYÜZ ---
with st.sidebar:
    st.title("💰 Akıllı Portföy")
    sayfa = st.radio("Menü", ["Portföyü İzle", "Pasta Grafik (Dağılım)", "YZ Danışmanı", "Varlık Grafikleri", "Gelişim Grafiği", "Varlık Yönetimi"])
    st.divider()
    if st.button("🔄 Piyasayı Güncelle"): st.rerun()

data, usd_kur = verileri_getir()

if sayfa == "Portföyü İzle":
    st.header("Anlık Portföy Durumu")
    if not data.empty:
        birim = "$" if st.session_state["para_birimi"] == "USD" else "TL"
        st.metric("Toplam Değer", f"{data['Toplam Değer'].sum():,.2f} {birim}")
        for t in ["maden", "bist", "abd", "fon", "kripto", "doviz", "diger"]:
            subset = data[data['tur'] == t]
            if not subset.empty:
                st.subheader(t.upper())
                st.dataframe(subset[['Varlık İsmi', 'Kod', 'Adet', 'Toplam Değer']], use_container_width=True, hide_index=True)

elif sayfa == "Pasta Grafik (Dağılım)":
    st.header("📊 Varlık Dağılım Analizi")
    if not data.empty:
        st.subheader("Bireysel Varlık Dağılımı")
        fig1, ax1 = plt.subplots()
        ax1.pie(data['Toplam Değer'], labels=data['Kod'], autopct='%1.1f%%', startangle=90, textprops={'color':"white"})
        fig1.patch.set_alpha(0)
        st.pyplot(fig1)

        st.subheader("Varlık Sınıfı Dağılımı")
        tur_ozet = data.groupby('tur')['Toplam Değer'].sum()
        fig2, ax2 = plt.subplots()
        ax2.pie(tur_ozet, labels=tur_ozet.index.str.upper(), autopct='%1.1f%%', startangle=90, textprops={'color':"white"})
        fig2.patch.set_alpha(0)
        st.pyplot(fig2)
    else:
        st.warning("Gösterilecek veri bulunamadı.")

elif sayfa == "YZ Danışmanı":
    st.header("🤖 YZ Yatırım Asistanı")
    if not data.empty:
        for _, row in data[~data['tur'].isin(['diger', 'fon'])].iterrows():
            st.markdown(f'<div class="ai-card"><b>{row["Varlık İsmi"]}</b>: {ai_analiz(row["Kod"], row["tur"])}</div>', unsafe_allow_html=True)

elif sayfa == "Varlık Grafikleri":
    st.header("📈 Canlı Grafikler")
    if not data.empty:
        grafik_listesi = data[~data['tur'].isin(['diger', 'fon'])]['Kod'].unique()
        secim = st.selectbox("Varlık Seçin", grafik_listesi)
        if secim:
            row = data[data['Kod'] == secim].iloc[0]
            ykod = secim
            if secim in ["BTC", "ETH", "SOL"]: ykod = f"{secim}-USD"
            elif secim == "ALTIN": ykod = "GC=F"
            elif secim == "GUMUS": ykod = "SI=F"
            elif secim == "PLATIN": ykod = "PL=F"
            elif secim == "PALADYUM": ykod = "PA=F"
            elif row['tur'] == 'bist': ykod = f"{secim}.IS"
            elif row['tur'] == 'doviz': ykod = f"{secim}TRY=X"
            
            hist = yf.Ticker(ykod).history(period="1mo")
            if not hist.empty: st.line_chart(hist['Close'])

elif sayfa == "Gelişim Grafiği":
    st.header("📉 Toplam Gelişim")
    gecmis = pd.read_csv(GECMIS_DOSYASI, sep=';')
    if not gecmis.empty: st.line_chart(gecmis.set_index('tarih')['toplam_tl' if st.session_state["para_birimi"] == "TL" else 'toplam_usd'])

elif sayfa == "Varlık Yönetimi":
    st.header("Varlık Yönetimi")
    with st.form("ekle", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        y_k = c1.text_input("Kod (Örn: THYAO, AUD, PLATIN)").upper().strip()
        y_t = c2.selectbox("Tür", ["maden", "bist", "abd", "fon", "kripto", "doviz", "diger"])
        y_v = c3.number_input("Miktar", format="%.4f")
        if st.form_submit_button("Ekle / Üzerine Ekle"):
            df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';')
            if y_k in df_m['hisse_kodu'].values:
                df_m.loc[df_m['hisse_kodu'] == y_k, 'adet' if y_t != 'diger' else 'birim_fiyat'] += y_v
            else:
                yeni = pd.DataFrame([[y_k, y_v if y_t != 'diger' else 1.0, y_t, y_v if y_t == 'diger' else 0.0]], columns=df_m.columns)
                df_m = pd.concat([df_m, yeni])
            df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False); st.rerun()

    df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna()
    for i, r in df_m.iterrows():
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        c1.write(f"**{r['hisse_kodu']}**")
        nv = c2.number_input(f"Miktar", value=float(r['adet'] if r['tur'] != 'diger' else r['birim_fiyat']), key=f"v_{i}")
        if c3.button("🔄", key=f"u_{i}"):
            df_m.at[i, 'adet' if r['tur'] != 'diger' else 'birim_fiyat'] = nv
            df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False); st.rerun()
        if c4.button("🗑️", key=f"d_{i}"):
            df_m.drop(i).to_csv(PORTFOY_DOSYASI, sep=';', index=False); st.rerun()
