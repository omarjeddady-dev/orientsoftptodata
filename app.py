import streamlit as st
import pandas as pd
import json
import io
import base64
import os
import re
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import plotly.express as px

# --- 1. CONFIGURATION & BRANDING ---
COMPANY_NAME = "Orient Scale Solutions"
WEBSITE_URL = "https://www.orientscale.ma"
PHONE_NUMBER = "0661572700"
LOGO_PATH = "logo.png"

# --- 🛠️ JSON KEY MAPPING 🛠️ ---
JSON_KEY_PLATE = "plate"
JSON_KEY_PRODUCT = "product"
JSON_KEY_CLIENT = "client"
JSON_KEY_DRIVER = "driver"
JSON_KEY_WEIGHT = "net"
JSON_KEY_PRICE = "price"
JSON_KEY_DATE = "date_out"

# --- 🛠️ CUSTOM FIELDS CONFIGURATION 🛠️ ---
UI_NAME_1 = "Destination"
JSON_KEY_1 = "ex1"

UI_NAME_2 = "Source"
JSON_KEY_2 = "ex2"

UI_NAME_3 = "Remorque"
JSON_KEY_3 = "ex3"

# Drive Config
FOLDER_ID = "115OinwLcQMYZ2l50qMEACnCt-9pXiy1o"
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# --- PAGE CONFIG ---
st.set_page_config(page_title=COMPANY_NAME, layout="wide", page_icon="⚖️")

# --- 2. TRANSLATION DICTIONARY ---
TRANSLATIONS = {
    "FR": {
        "title": "Tableau de Bord des Opérations",
        "last_update": "Dernière mise à jour :",
        "refresh_btn": "🔄 ACTUALISER LES DONNÉES",
        "contact": "Contact :",
        "filter_title": "🔍 Filtres & Recherche Avancée",
        "date_range": "📅 Période",
        "clients": "👤 Clients",
        "vehicles": "🚛 Véhicules",
        "products": "📦 Produits",
        "drivers": "👮 Chauffeurs",
        "global_search": "🔎 Recherche Globale (Note, ID...)",
        "tab_ops": "📝 Opérations",
        "tab_ana": "📊 Statistiques & Totaux",
        "tab_exp": "📤 Exporter Sélection",
        "tickets_found": "Tickets Trouvés",
        "doc_preview": "📄 Aperçu du Document",
        "download_pdf": "⬇️ Télécharger PDF",
        "pdf_missing": "⚠️ PDF Introuvable",
        "loading": "Chargement...",
        "total_rev": "Total Prix",
        "total_weight": "Poids Total",
        "count": "Nbr Opérations",
        "curr": "DH",
        "weight_unit": "kg"
    },
    "EN": {
        "title": "Operations Dashboard",
        "last_update": "Last update:",
        "refresh_btn": "🔄 REFRESH DATA",
        "contact": "Contact:",
        "filter_title": "🔍 Advanced Filters & Search",
        "date_range": "📅 Date Range",
        "clients": "👤 Clients",
        "vehicles": "🚛 Vehicles",
        "products": "📦 Products",
        "drivers": "👮 Drivers",
        "global_search": "🔎 Global Search (Note, ID...)",
        "tab_ops": "📝 Operations",
        "tab_ana": "📊 Statistics & Totals",
        "tab_exp": "📤 Export Selection",
        "tickets_found": "Tickets Found",
        "doc_preview": "📄 Document Preview",
        "download_pdf": "⬇️ Download PDF",
        "pdf_missing": "⚠️ PDF Not Found",
        "loading": "Loading...",
        "total_rev": "Total Price",
        "total_weight": "Total Weight",
        "count": "Total Ops",
        "curr": "MAD",
        "weight_unit": "kg"
    },
    "AR": {
        "title": "لوحة قيادة العمليات",
        "last_update": "آخر تحديث:",
        "refresh_btn": "🔄 تحديث البيانات",
        "contact": "للتواصل:",
        "filter_title": "🔍 بحث وتصفية متقدمة",
        "date_range": "📅 الفترة الزمنية",
        "clients": "👤 العملاء",
        "vehicles": "🚛 المركبات",
        "products": "📦 المنتجات",
        "drivers": "👮 السائقين",
        "global_search": "🔎 بحث شامل (ملاحظات، رقم...)",
        "tab_ops": "📝 العمليات",
        "tab_ana": "📊 الإحصائيات والمجاميع",
        "tab_exp": "📤 تصدير البيانات المختارة",
        "tickets_found": "التذاكر الموجودة",
        "doc_preview": "📄 معاينة الوثيقة",
        "download_pdf": "⬇️ تحميل PDF",
        "pdf_missing": "⚠️ الملف غير موجود",
        "loading": "جار التحميل...",
        "total_rev": "إجمالي السعر",
        "total_weight": "إجمالي الوزن",
        "count": "عدد العمليات",
        "curr": "درهم",
        "weight_unit": "كغ"
    }
}

# --- 3. AUTHENTICATION (FIXED FOR SECRETS) ---
@st.cache_resource
def get_drive_service():
    """
    Connect to Google Drive using either a local 'credentials.json' file
    OR Streamlit Secrets (for Cloud).
    This version sanitizes and normalizes the private_key in case it contains
    literal "\\n" sequences or accidental surrounding quotes.
    """
    creds = None

    # 1. Try Local File (Dev mode)
    if os.path.exists('credentials.json'):
        try:
            creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            st.error(f"Failed to load local credentials.json: {e}")
            st.stop()

    # 2. Try Streamlit Secrets (Cloud mode)
    elif 'gcp_service_account' in st.secrets:
        try:
            # Load the dictionary from secrets.toml
            creds_dict = dict(st.secrets["gcp_service_account"])

            # --- SANITIZE private_key ---
            # If private_key contains literal "\n" (two chars backslash + n), convert them to real newlines.
            if "private_key" in creds_dict and isinstance(creds_dict["private_key"], str):
                pk = creds_dict["private_key"]

                # Remove accidental surrounding triple quotes or single/double quotes the user might
                # have included when pasting (e.g. '"-----BEGIN PRIVATE KEY-----\n..."')
                if pk.startswith('"') and pk.endswith('"'):
                    pk = pk[1:-1]
                if pk.startswith("'''") and pk.endswith("'''"):
                    pk = pk[3:-3]
                if pk.startswith('"""') and pk.endswith('"""'):
                    pk = pk[3:-3]

                # Replace literal backslash-n with actual newlines
                if "\\n" in pk and "\n" not in pk:
                    pk = pk.replace("\\n", "\n")

                # Ensure it has BEGIN/END markers on separate lines
                if "-----BEGIN PRIVATE KEY-----" in pk and "-----END PRIVATE KEY-----" in pk:
                    # normalize spacing (strip trailing/leading spaces)
                    pk = "\n".join([line.strip() for line in pk.splitlines() if line.strip() != ""])
                creds_dict["private_key"] = pk

            # Now create credentials
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

        except Exception as e:
            # Provide helpful debug info (non-secret)
            st.error("❌ Error while loading service account from Streamlit Secrets.")
            st.info("Common causes: private_key contains literal '\\n' sequences or was double-quoted when pasted.")
            st.exception(e)
            st.stop()

    # 3. If neither works, stop app
    if not creds:
        st.error("❌ Critical Error: No Google Credentials found.")
        st.info("If you are running online, please ensure you pasted the keys into Streamlit Secrets.")
        st.stop()

    return build('drive', 'v3', credentials=creds)

# --- 4. DATA LOADER ---
def normalize_filename(name):
    name_no_ext = os.path.splitext(name)[0]
    return re.sub(r'[^a-zA-Z0-9]', '', name_no_ext).lower()

@st.cache_data(ttl=600)
def load_data_and_map_files(_service, folder_id):
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        results = _service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
    except Exception as e:
        st.error(f"Error connecting to Google Drive: {e}")
        return pd.DataFrame()

    json_files = [f for f in files if 'json' in f['name'].lower()]
    pdf_map = {normalize_filename(f['name']): f['id'] for f in files if 'pdf' in f['name'].lower()}

    all_records = []

    for file in json_files:
        try:
            request = _service.files().get_media(fileId=file['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)

            content = fh.read().decode('utf-8')
            if not content: continue

            data = json.loads(content)
            items = data if isinstance(data, list) else [data]

            for item in items:
                # Add Metadata
                item['_json_filename'] = file['name']
                norm_name = normalize_filename(file['name'])
                item['_pdf_file_id'] = pdf_map.get(norm_name)

                # Fill missing keys
                keys_to_check = [
                    JSON_KEY_PLATE, JSON_KEY_PRODUCT, JSON_KEY_CLIENT,
                    JSON_KEY_DRIVER, JSON_KEY_WEIGHT, JSON_KEY_PRICE,
                    JSON_KEY_DATE, JSON_KEY_1, JSON_KEY_2, JSON_KEY_3
                ]
                for k in keys_to_check:
                    if k not in item:
                        item[k] = ""

                all_records.append(item)
        except:
            pass

    df = pd.DataFrame(all_records)

    if not df.empty:
        # Clean Date
        df['clean_date'] = pd.to_datetime(df[JSON_KEY_DATE], errors='coerce')
        if 'date_in' in df.columns:
            df['clean_date'] = df['clean_date'].fillna(pd.to_datetime(df['date_in'], errors='coerce'))
        df['clean_date'] = df['clean_date'].fillna(pd.to_datetime(datetime.datetime.now()))

        df['Hour'] = df['clean_date'].dt.hour

        # Clean Price
        df['clean_price'] = pd.to_numeric(
            df[JSON_KEY_PRICE].astype(str).str.replace(r'[^\d.]', '', regex=True),
            errors='coerce'
        ).fillna(0)

        # Clean Weight
        df['clean_weight'] = pd.to_numeric(
            df[JSON_KEY_WEIGHT].astype(str).str.replace(r'[^\d.]', '', regex=True),
            errors='coerce'
        ).fillna(0)

        # Standardize Strings
        df['Main_Product'] = df[JSON_KEY_PRODUCT].astype(str)
        df['Vehicle_Ref'] = df[JSON_KEY_PLATE].astype(str)
        df['Client_Ref'] = df[JSON_KEY_CLIENT].astype(str)
        df['Driver_Ref'] = df[JSON_KEY_DRIVER].astype(str)

    return df

def fetch_pdf_bytes(service, file_id):
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        fh.seek(0)
        return fh
    except:
        return None

# --- MAIN APP ---
def main():
    # --- SIDEBAR ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=160)
        st.markdown(f"## {COMPANY_NAME}")
        st.markdown(f"🌐 [{WEBSITE_URL}]({WEBSITE_URL})")

        lang_code = st.radio("🌍 Language / اللغة", ["Français", "العربية", "English"])
        if lang_code == "Français": L = TRANSLATIONS["FR"]; is_rtl = False
        elif lang_code == "العربية": L = TRANSLATIONS["AR"]; is_rtl = True
        else: L = TRANSLATIONS["EN"]; is_rtl = False

        st.markdown(f"📞 **{L['contact']}** {PHONE_NUMBER}")
        st.divider()

    # --- STYLING ---
    if is_rtl:
        st.markdown("""<style>.stApp { direction: rtl; text-align: right; } .stMarkdown, .stMetric, .stDataFrame, .stExpander, .stTextInput, .stButton {text-align: right !important;}</style>""", unsafe_allow_html=True)
    st.markdown("""<style>div[data-testid="stMetricValue"] {font-size: 24px; color: #0068c9;}</style>""", unsafe_allow_html=True)

    # --- HEADER & REFRESH ---
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.title(L["title"])
    with col_t2:
        st.write("")
        if st.button(L["refresh_btn"], type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    now_str = datetime.datetime.now().strftime("%H:%M")
    st.caption(f"{L['last_update']} {now_str}")

    # --- LOAD DATA ---
    service = get_drive_service()
    raw_df = load_data_and_map_files(service, FOLDER_ID)

    if raw_df.empty:
        st.info("Waiting for data / En attente de données...")
        st.stop()

    # Sort Newest First
    raw_df = raw_df.sort_values(by='clean_date', ascending=False)

    # --- 🔍 FILTERS ---
    with st.expander(L["filter_title"], expanded=True):
        c1, c2 = st.columns([1, 2])
        min_d = raw_df['clean_date'].min().date() if not raw_df.empty else datetime.date.today()
        max_d = raw_df['clean_date'].max().date() if not raw_df.empty else datetime.date.today()

        date_range = c1.date_input(L["date_range"], value=(min_d, max_d))
        search_term = c2.text_input(L["global_search"], placeholder="...")

        c3, c4, c5, c6 = st.columns(4)
        sel_clients = c3.multiselect(L["clients"], raw_df['Client_Ref'].unique())
        sel_vehs = c4.multiselect(L["vehicles"], raw_df['Vehicle_Ref'].unique())
        sel_prods = c5.multiselect(L["products"], raw_df['Main_Product'].unique())
        sel_drivers = c6.multiselect(L["drivers"], raw_df['Driver_Ref'].unique())

        custom_filters = {}
        if UI_NAME_1 or UI_NAME_2 or UI_NAME_3:
            st.markdown("---")
            cc1, cc2, cc3 = st.columns(3)
            if UI_NAME_1 and JSON_KEY_1 in raw_df.columns:
                vals = [x for x in raw_df[JSON_KEY_1].astype(str).unique() if x and x != "nan"]
                custom_filters[JSON_KEY_1] = cc1.multiselect(f"{UI_NAME_1}", vals)

            if UI_NAME_2 and JSON_KEY_2 in raw_df.columns:
                vals = [x for x in raw_df[JSON_KEY_2].astype(str).unique() if x and x != "nan"]
                custom_filters[JSON_KEY_2] = cc2.multiselect(f"{UI_NAME_2}", vals)

            if UI_NAME_3 and JSON_KEY_3 in raw_df.columns:
                vals = [x for x in raw_df[JSON_KEY_3].astype(str).unique() if x and x != "nan"]
                custom_filters[JSON_KEY_3] = cc3.multiselect(f"{UI_NAME_3}", vals)

    # --- APPLY FILTERS ---
    filtered_df = raw_df.copy()

    if isinstance(date_range, tuple) and len(date_range) == 2:
        filtered_df = filtered_df[(filtered_df['clean_date'].dt.date >= date_range[0]) & (filtered_df['clean_date'].dt.date <= date_range[1])]

    if sel_clients: filtered_df = filtered_df[filtered_df['Client_Ref'].isin(sel_clients)]
    if sel_vehs: filtered_df = filtered_df[filtered_df['Vehicle_Ref'].isin(sel_vehs)]
    if sel_prods: filtered_df = filtered_df[filtered_df['Main_Product'].isin(sel_prods)]
    if sel_drivers: filtered_df = filtered_df[filtered_df['Driver_Ref'].isin(sel_drivers)]

    for key, val in custom_filters.items():
        if val: filtered_df = filtered_df[filtered_df[key].astype(str).isin(val)]

    if search_term:
        mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
        filtered_df = filtered_df[mask]

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs([L["tab_ops"], L["tab_ana"], L["tab_exp"]])

    # === TAB 1: LIST & PDF ===
    with tab1:
        col_list, col_view = st.columns([1.6, 1])
        with

