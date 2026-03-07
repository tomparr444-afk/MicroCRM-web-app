import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from math import radians, cos, sin, asin, sqrt
import pandas as pd
from supabase import create_client, Client
import time
from datetime import datetime, date, timedelta
import requests
import json

# --- CONFIGURATION ---
APP_NAME = "KartaFlow"
LOGO_FILENAME = "KartaFlow Logo.png"
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

# ⚠️ YOUR LIVE KEYS
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GOOGLE_MAPS_API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]
# Note: Add GEMINI_API_KEY to your secrets to use the AI Auto-Find!
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# --- PAGE SETUP ---
st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📍", initial_sidebar_state="expanded")

# --- DB CONNECTION ---
@st.cache_resource
def init_connection():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except: return None
supabase = init_connection()

# --- STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'company_id' not in st.session_state: st.session_state.company_id = None
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
if 'search_result' not in st.session_state: st.session_state.search_result = None
if 'search_active' not in st.session_state: st.session_state.search_active = False
if 'route_stops' not in st.session_state: st.session_state.route_stops = []
if 'cached_routes' not in st.session_state: st.session_state.cached_routes = []
if 'theme_toggle' not in st.session_state: st.session_state.theme_toggle = False
if 'cust_draft' not in st.session_state: 
    st.session_state.cust_draft = {"name": "", "pc": "", "email": "", "phone": "", "directors": "", "reg_no": "", "offices": "", "notes": ""}

# --- AUTH ---
def check_login(username, password):
    if not supabase: return False
    if username.lower() == "admin" and password == ADMIN_PASSWORD: return "ADMIN"
    try:
        res = supabase.table("clients").select("*").eq("company_id", username).eq("password", password).execute()
        return username if res.data else None
    except: return None

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    # Inject basic dark theme for login
    st.markdown("<style>.stApp { background-color: #050505; color: #ffffff; }</style>", unsafe_allow_html=True)
    login_holder = st.empty() 
    with login_holder.container():
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown(f"<h1 style='text-align: center; color: white;'>🔐 {APP_NAME} Login</h1>", unsafe_allow_html=True)
            with st.form("login"):
                user = st.text_input("Username", key="login_username_input")
                pw = st.text_input("Password", type="password", key="login_password_input")
                
                if st.form_submit_button("Connect"): 
                    res = check_login(user, pw)
                    if res:
                        st.session_state.logged_in = True
                        st.session_state.is_admin = (res == "ADMIN")
                        st.session_state.company_id = "demo" if res == "ADMIN" else res
                        login_holder.empty() 
                        st.rerun()
                    else: st.error("Access Denied")
    st.stop()

# --- TOP BAR / THEME TOGGLE ---
c1, c2 = st.columns([9, 1])
with c2:
    is_light = st.toggle("☀️ Light Mode", key="theme_toggle")

# --- 🎨 DYNAMIC CSS ---
if is_light:
    bg_color, text_color, sidebar_bg, card_bg, border_color = "#f4f6f9", "#111111", "#ffffff", "#ffffff", "#dddddd"
    button_bg, button_text = "#e0e4e8", "#111111"
    tiles_style = "CartoDB positron"
else:
    bg_color, text_color, sidebar_bg, card_bg, border_color = "#050505", "#ffffff", "#0b0c0e", "#1e1e1e", "#333333"
    button_bg, button_text = "#2a2d33", "#ffffff"
    tiles_style = "CartoDB dark_matter"

st.markdown(f"""
<style>
    /* Main Backgrounds */
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    [data-testid="stSidebar"] {{ background-color: {sidebar_bg}; border-right: 1px solid {border_color}; }}
    
    /* Make Sidebar Text Bigger */
    [data-testid="stSidebar"] .stRadio label p {{ font-size: 1.15rem !important; font-weight: 500; padding: 5px 0px; }}
    
    /* Text Inputs */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {{
        background-color: {card_bg}; color: {text_color}; border: 1px solid {border_color}; border-radius: 4px;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{ border-color: #00ADB5; }}
    
    /* Standard Buttons (Fixed for Light/Dark) */
    .stButton button {{ 
        background-color: {button_bg} !important; 
        border: 1px solid {border_color} !important; 
        border-radius: 4px; 
        transition: all 0.2s; 
    }}
    .stButton button p {{ color: {button_text} !important; font-weight: bold; }}
    
    /* Hover state for buttons */
    .stButton button:hover {{ border-color: #00ADB5 !important; transform: scale(1.02); }}
    .stButton button:hover p {{ color: #00ADB5 !important; }}

    /* Primary Form Submit Buttons */
    .stButton button[kind="primary"] {{ background-color: #00ADB5 !important; border-color: #00ADB5 !important; }}
    .stButton button[kind="primary"] p {{ color: #ffffff !important; }}
    .stButton button[kind="primary"]:hover {{ opacity: 0.9; }}

    /* Expander Cards */
    .streamlit-expanderHeader {{ background-color: {card_bg}; border-radius: 4px; color: {text_color}; }}
    
    /* Calendar Card Style */
    .schedule-card {{ background-color: {card_bg}; border-radius: 5px; padding: 10px; margin-bottom: 10px; border-left: 4px solid #00ADB5; box-shadow: 0 2px 4px rgba(0,0,0,0.1); color: {text_color}; }}
    .schedule-card.install {{ border-left: 4px solid #9b59b6; }}
    .schedule-card.note {{ border-left: 4px solid #f1c40f; }}
    
    /* Fonts overrides */
    h1, h2, h3, h4, h5, h6, label {{ color: {text_color} !important; }}
    .stMarkdown p {{ color: {text_color}; }}
    
    /* Hide Default Branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    return c * 3956

def decode_polyline(polyline_str):
    index, lat, lng, coordinates, length = 0, 0, 0, [], len(polyline_str)
    while index < length:
        b, shift, result = 0, 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20: break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        shift, result = 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20: break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        coordinates.append((lat / 100000.0, lng / 100000.0))
    return coordinates

def get_google_route(start_lat, start_lon, end_lat, end_lon):
    if not GOOGLE_MAPS_API_KEY: return None
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={start_lat},{start_lon}&destination={end_lat},{end_lon}&mode=driving&units=imperial&key={GOOGLE_MAPS_API_KEY}"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            pts = res['routes'][0]['overview_polyline']['points']
            leg = res['routes'][0]['legs'][0]
            return decode_polyline(pts), leg['distance']['text'], leg['duration']['text']
    except: pass
    return None

def fetch_company_info_ai(company_name, postcode):
    """Uses Gemini API to extract public details about a business based on name/postcode"""
    if not GEMINI_API_KEY:
        st.error("GEMINI_API_KEY missing from secrets. Auto-find disabled.")
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""
    Find public business information for a UK company named '{company_name}' near postcode '{postcode}'. 
    Return ONLY a JSON object with these exact keys:
    "directors" (string, comma separated names),
    "email" (string, best guess generic contact email),
    "phone" (string, best guess contact number),
    "registration_number" (string, UK Companies House number),
    "offices" (string, list of addresses or locations).
    If you don't know a field, leave it as an empty string. DO NOT include markdown backticks around the JSON.
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    try:
        res = requests.post(url, json=payload).json()
        text = res['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text)
    except Exception as e:
        print(f"AI Fetch Error: {e}")
        return None

def optimize_route(start_coords, stops):
    route, current_loc, unvisited = [], start_coords, stops.copy()
    while unvisited:
        nearest, min_dist = None, float('inf')
        for stop in unvisited:
            dist = haversine(current_loc[1], current_loc[0], stop['lon'], stop['lat'])
            if dist < min_dist: min_dist, nearest = dist, stop
        if nearest:
            route.append(nearest)
            current_loc = (nearest['lat'], nearest['lon'])
            unvisited.remove(nearest)
    return route

def get_engineer_color(name, status, custom_color=None):
    if status in ["Sick", "Holiday"]: return "gray"
    valid_colors = {'red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray'}
    clean_color = custom_color.split()[0].lower() if custom_color else None
    if clean_color and clean_color in valid_colors: return clean_color
    return "blue"

def get_job_color(severity):
    severity = str(severity).lower() if severity else 'low'
    if "critical" in severity or "high" in severity: return "red"
    if "medium" in severity: return "orange" 
    return "green"

def find_nearest_engineer_text(lat, lon, engineers_list):
    working_statuses = ["Active", "Driving", "On Site", "In Office", "Home"]
    active_engs = [e for e in engineers_list if e['status'] in working_statuses]
    if not active_engs: return "No active engineers found."
    for e in active_engs: e['temp_dist'] = haversine(lon, lat, e['lon'], e['lat'])
    active_engs.sort(key=lambda x: x['temp_dist'])
    nearest = active_engs[0]
    return f"Nearest Engineer: {nearest['name']} ({nearest['temp_dist']:.1f} miles away)"

# --- DATABASE FETCHERS ---
def get_engineers(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Engineers").select("*").eq("Company_ID", company_id).order('id').execute()
        return [{
            'id': r['id'], 
            'name': r.get('Name') or r.get('name'), 
            'lat': r['Latitude'], 
            'lon': r['Longitude'], 
            'status': r.get('status', 'Active'), 
            'pin_color': r.get('pin_color') or 'blue',
            'email': r.get('email', ''),     # Added
            'mobile': r.get('mobile', '')    # Added
        } for r in res.data]
    except: return []

def get_jobs(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Jobs").select("*").eq("Company_ID", company_id).execute()
        return [{'id': r['id'], 'ref': r.get('Job_Ref'), 'lat': r['Latitude'], 'lon': r['Longitude'], 'desc': r.get('Description', ''), 'director': r.get('Director_Name', ''), 'severity': r.get('severity') or 'Low'} for r in res.data if r.get('Latitude') and r.get('Longitude')]
    except: return []

def get_installs(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Installs").select("*").eq("Company_ID", company_id).execute()
        return [{'id': r['id'], 'ref': r.get('Install_Ref') or r.get('Job_Ref'), 'status': r.get('status') or 'Not passed Finance', 'postcode': r.get('Postcode'), 'lat': r['Latitude'], 'lon': r['Longitude'], 'desc': r.get('Description', ''), 'director': r.get('Director_Name', '')} for r in res.data if r.get('Latitude') and r.get('Longitude')]
    except: return []

def get_customers(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Customers").select("*").eq("Company_ID", company_id).execute()
        return res.data
    except: return []

def get_schedule(company_id, start_date=None, end_date=None):
    if not supabase: return []
    try:
        query = supabase.table("job_schedule").select("*").eq("company_id", company_id)
        if start_date: query = query.gte("scheduled_date", str(start_date))
        if end_date: query = query.lte("scheduled_date", str(end_date))
        res = query.order("scheduled_date", desc=False).execute()
        return res.data
    except: return []

def add_schedule_item(company_id, engineer, job, date_obj, notes, job_type="Maintenance"):
    if not supabase: return False
    try:
        payload = {
            "company_id": company_id,
            "engineer_name": engineer,
            "job_ref": job,
            "scheduled_date": str(date_obj),
            "notes": notes,
        }
        if job_type == "Install": payload["notes"] = f"[INSTALL] {notes}"
        elif job_type == "Note": payload["notes"] = f"[NOTE] {notes}"
        
        supabase.table("job_schedule").insert(payload).execute()
        return True
    except Exception as e:
        print(f"Schedule Error: {e}")
        return False

# --- DATABASE WRITERS ---
def update_engineer_status_color(engineer_id, new_status, new_color):
    try:
        payload = {"status": new_status}
        if new_color: payload["pin_color"] = new_color
        supabase.table("Engineers").update(payload).eq("id", engineer_id).execute()
        return True
    except: return False

def update_install_status(install_id, new_status):
    try:
        supabase.table("Installs").update({"status": new_status}).eq("id", install_id).execute()
        return True
    except: return False

def delete_record(table, record_id, record_ref=None, ref_col=None):
    try:
        if record_ref and ref_col:
            supabase.table("job_schedule").delete().eq("job_ref", record_ref).execute()
        supabase.table(table).delete().eq("id", record_id).execute()
        return True
    except Exception as e:
        return False

def add_entry(table, name_col, name_val, postcode, company_id, desc=None, director=None, severity=None, pin_color=None, install_status=None):
    geolocator = Nominatim(user_agent="kartaflow_adder_v18")
    try:
        loc = geolocator.geocode(postcode)
        if loc:
            payload = {
                name_col: name_val,
                "Company_ID": company_id,
                "Latitude": loc.latitude,
                "Longitude": loc.longitude
            }
            if table == "Engineers": 
                payload["status"] = "Active"
                if pin_color: payload["pin_color"] = pin_color
            elif table == "Jobs":
                if desc: payload["Description"] = desc 
                if director: payload["Director_Name"] = director
                if severity: payload["severity"] = severity
            elif table == "Installs":
                payload["Postcode"] = postcode 
                if install_status: payload["status"] = install_status
                if desc: payload["Description"] = desc
                if director: payload["Director_Name"] = director

            supabase.table(table).insert(payload).execute()
            return True, f"Added {name_val}", (loc.latitude, loc.longitude)
        return False, "Postcode not found", None
    except Exception as e: 
        return False, "Error", None

def process_bulk_upload(df, type_flag, company_id):
    geolocator = Nominatim(user_agent=f"kartaflow_bulk_v18")
    progress_bar = st.progress(0)
    success_count = 0
    total = len(df)
    df.columns = [c.lower() for c in df.columns]
    for index, row in df.iterrows():
        try:
            if type_flag == "user":
                name_val = row['name']
                table_target = "Engineers"
                col_target = "Name"
            else:
                name_val = row['ref']
                table_target = "Jobs"
                col_target = "Job_Ref"
            pcode = row['postcode']
            location = geolocator.geocode(pcode)
            if location:
                payload = {
                    col_target: name_val,
                    "Company_ID": company_id,
                    "Latitude": location.latitude,
                    "Longitude": location.longitude
                }
                if type_flag == "user": payload["status"] = "Active"
                supabase.table(table_target).insert(payload).execute()
                success_count += 1
                time.sleep(1)
        except: pass
        progress_bar.progress((index + 1) / total)
    return success_count

def get_all_companies():
    if not supabase: return []
    try:
        res = supabase.table("Engineers").select("Company_ID").execute()
        return sorted(list(set([r['Company_ID'] for r in res.data if r['Company_ID']])))
    except: return []

# --- LOAD DATA ---
engineers = get_engineers(st.session_state.company_id)
jobs = get_jobs(st.session_state.company_id)
installs = get_installs(st.session_state.company_id)
customers = get_customers(st.session_state.company_id)

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    try: st.image(LOGO_FILENAME, width=200)
    except: st.header(APP_NAME)
    st.caption(f"CONNECTED: {st.session_state.company_id.upper()}")
    if st.button("LOGOUT", use_container_width=True): 
        st.session_state.logged_in = False
        st.rerun()
    st.markdown("---")
    
    page = st.radio("MAIN MENU", [
        "🏠 Dashboard", 
        "📋 Fleet List", 
        "🔧 Maintenance", 
        "🛠️ Installations", 
        "👥 Customers",
        "📅 Schedule Work",
        "⬆️ Data Upload"
    ], label_visibility="collapsed")
    
    st.markdown("---")
    if st.session_state.is_admin:
        try:
            res = supabase.table("Engineers").select("Company_ID").execute()
            comps = sorted(list(set([r['Company_ID'] for r in res.data if r['Company_ID']])))
            if comps: st.session_state.company_id = st.selectbox("TARGET ADMIN:", comps)
        except: pass

# --- PAGE: DASHBOARD ---
if page == "🏠 Dashboard":
    st.title("Operations Dashboard")
    
    # Top Metrics
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Active Engineers", len([e for e in engineers if e['status'] in ["Active", "Driving", "On Site"]]))
    mc2.metric("Open Maintenance", len(jobs))
    mc3.metric("Pending Installations", len(installs))
    
    today_str = str(date.today())
    todays_jobs = get_schedule(st.session_state.company_id, today_str, today_str)
    mc4.metric("Jobs Today", len(todays_jobs))
    
    st.divider()
    
    col_map, col_sched = st.columns([5, 3])
    
    with col_map:
        st.subheader("🌍 Dispatch Map")
        
        # 1. Search Single
        with st.expander("🔍 Single Visit", expanded=False):
            with st.form("search"):
                c1, c2 = st.columns([3,1], vertical_alignment="bottom")
                with c1: p_code = st.text_input("Postcode")
                with c2: search = st.form_submit_button("Scan", type="primary")
            
            if search and p_code:
                geo = Nominatim(user_agent="kartaflow_search_v18", timeout=10)
                try:
                    l = geo.geocode(p_code)
                    if l:
                        st.session_state.search_result = {'lat': l.latitude, 'lon': l.longitude, 'addr': l.address}
                        st.session_state.search_active = True
                        
                        st.session_state.cached_routes = [] 
                        working_statuses = ["Active", "Driving", "On Site", "In Office", "Home"]
                        active_engineers = [e for e in engineers if e['status'] in working_statuses]
                        
                        for e in active_engineers:
                            e['temp_dist'] = haversine(l.longitude, l.latitude, e['lon'], e['lat'])
                        active_engineers.sort(key=lambda x: x['temp_dist'])
                        top3 = active_engineers[:3]
                        
                        for eng in top3:
                            route_data = get_google_route(eng['lat'], eng['lon'], l.latitude, l.longitude)
                            if route_data:
                                pts, d_text, dur_text = route_data
                                st.session_state.cached_routes.append({'name': eng['name'], 'points': pts, 'dist_text': d_text, 'dur_text': dur_text, 'color': "blue"})
                            else:
                                st.session_state.cached_routes.append({'name': eng['name'], 'points': None, 'dist_text': f"{eng['temp_dist']:.1f} miles (Direct)", 'dur_text': "N/A", 'color': "orange"})
                    else: st.error("Not Found")
                except: st.error("Search Failed")

        # 2. Route Planner
        with st.expander("🚚 Multiple Visits", expanded=False):
            c1, c2 = st.columns([3, 1])
            new_stop = c1.text_input("Add Stop (Postcode)", key="route_input")
            if c2.button("Add Stop") and new_stop:
                geo_r = Nominatim(user_agent="kartaflow_route_v1")
                l_r = geo_r.geocode(new_stop)
                if l_r:
                    st.session_state.route_stops.append({'addr': new_stop, 'lat': l_r.latitude, 'lon': l_r.longitude})
                    st.rerun()
                else: st.error("Invalid Postcode")
            
            if st.session_state.route_stops:
                st.write(f"Stops added: {len(st.session_state.route_stops)}")
                st.dataframe(pd.DataFrame(st.session_state.route_stops)[['addr']], hide_index=True, use_container_width=True)
                start_opts = ["Custom..."] + [e['name'] for e in engineers]
                start_sel = st.selectbox("Start From:", start_opts)
                
                start_coords = None
                if start_sel == "Custom...":
                    start_txt = st.text_input("Custom Start Postcode")
                    if start_txt:
                        geo_s = Nominatim(user_agent="kartaflow_start")
                        ls = geo_s.geocode(start_txt)
                        if ls: start_coords = (ls.latitude, ls.longitude)
                else:
                    eng = next((e for e in engineers if e['name'] == start_sel), None)
                    if eng: start_coords = (eng['lat'], eng['lon'])

                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("Optimize Route", use_container_width=True) and start_coords:
                    optimized = optimize_route(start_coords, st.session_state.route_stops)
                    st.session_state.optimized_route = {'start': start_coords, 'path': optimized}
                
                if col_btn2.button("Clear Route", use_container_width=True):
                    st.session_state.route_stops = []
                    if 'optimized_route' in st.session_state: del st.session_state.optimized_route
                    st.rerun()

        # Render Map
        m = folium.Map(location=[54.5, -4.0], zoom_start=6, tiles=tiles_style)

        for eng in engineers:
            folium.Marker(
                [eng['lat'], eng['lon']],
                tooltip=f"{eng['name']} ({eng['status']})", 
                popup=f"USER: {eng['name']}\nSTATUS: {eng['status']}",
                icon=folium.Icon(color=get_engineer_color(eng['name'], eng['status'], eng.get('pin_color')), icon="user")
            ).add_to(m)

        for job in jobs:
            popup_content = f"JOB: {job.get('ref')}\nDESC: {job.get('desc', '')}\nSEVERITY: {job.get('severity')}"
            folium.Marker(
                [job['lat'], job['lon']],
                tooltip=f"JOB: {job.get('ref')}", popup=popup_content,
                icon=folium.Icon(color=get_job_color(job.get('severity', 'Low')), icon="briefcase", prefix='fa')
            ).add_to(m)

        for inst in installs:
            folium.Marker(
                [inst['lat'], inst['lon']],
                tooltip=f"INSTALL: {inst.get('ref')}", popup=f"INSTALL: {inst.get('ref')}\nSTATUS: {inst.get('status')}",
                icon=folium.Icon(color='purple', icon="wrench", prefix='fa') 
            ).add_to(m)

        if 'optimized_route' in st.session_state:
            rt = st.session_state.optimized_route
            current_pos = rt['start']
            folium.Marker(rt['start'], popup="Start", icon=folium.Icon(color="green", icon="play", prefix='fa')).add_to(m)
            
            for idx, stop in enumerate(rt['path']):
                stop_pos = (stop['lat'], stop['lon'])
                path_points = get_google_route(current_pos[0], current_pos[1], stop_pos[0], stop_pos[1])
                
                if path_points and path_points[0]:
                    folium.PolyLine(path_points[0], color="#4dabf7", weight=5, opacity=0.8, tooltip=f"Leg {idx+1}: {path_points[1]} ({path_points[2]})").add_to(m)
                else:
                    folium.PolyLine([current_pos, stop_pos], color="cyan", weight=3, opacity=0.6, dash_array='5, 10', tooltip=f"Leg {idx+1} (Direct)").add_to(m)
                
                folium.Marker(stop_pos, icon=folium.DivIcon(html=f"<div style='font-size: 16pt; color: #4dabf7; font-weight: 900; text-shadow: 2px 2px #000;'>{str(idx + 1)}</div>")).add_to(m)
                current_pos = stop_pos

        if st.session_state.search_active and st.session_state.search_result:
            t = st.session_state.search_result
            folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="red", icon="crosshairs", prefix='fa')).add_to(m)
            
            if st.session_state.cached_routes:
                with st.container():
                    st.markdown("##### 👷 Nearest Active Engineers")
                    cc1, cc2, cc3 = st.columns(3)
                    for i, r_data in enumerate(st.session_state.cached_routes):
                        col = [cc1, cc2, cc3][i] if i < 3 else None
                        if col:
                            col.info(f"**{r_data['name']}**\n\n🛣️ {r_data['dist_text']} \n\n⏱️ {r_data['dur_text']}")
                        if r_data['points']:
                            folium.PolyLine(r_data['points'], color=r_data['color'], weight=4, opacity=0.7, tooltip=f"To {r_data['name']}: {r_data['dist_text']} ({r_data['dur_text']})").add_to(m)
            m.fit_bounds([[t['lat'], t['lon']]])

        st_folium(m, width=None, height=600, key="map_dashboard", returned_objects=[])

    with col_sched:
        c_head, c_filt = st.columns([3, 2])
        c_head.subheader("📆 Week Schedule")
        focus_date = c_filt.date_input("Week of:", value=datetime.today(), label_visibility="collapsed")
        
        start_of_week = focus_date - timedelta(days=focus_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        schedule_items = get_schedule(st.session_state.company_id, start_of_week, end_of_week)
        
        days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        # Display as a vertical list of days for the dashboard right panel
        for i in range(7):
            current_day = start_of_week + timedelta(days=i)
            day_str = current_day.strftime('%Y-%m-%d')
            day_items = [item for item in schedule_items if item['scheduled_date'] == day_str]
            
            with st.expander(f"{days_names[i]} - {current_day.strftime('%d/%m')}", expanded=(current_day == date.today() or bool(day_items))):
                if not day_items:
                    st.caption("No jobs scheduled.")
                for item in day_items:
                    note_text = str(item.get('notes', ''))
                    if "[INSTALL]" in note_text: css_class = "install"
                    elif "[NOTE]" in note_text: css_class = "note"
                    else: css_class = "job"
                    
                    content = item['job_ref']
                    if css_class == "note": content = note_text.replace("[NOTE]", "").strip()
                    
                    st.markdown(f"""
                    <div class="schedule-card {css_class}" style="padding: 5px 10px; margin-bottom: 5px;">
                        <small style="color: gray;"><b>{item['engineer_name']}</b></small><br>
                        <span style="font-size: 0.95em;">{content}</span>
                    </div>
                    """, unsafe_allow_html=True)

# --- PAGE: FLEET LIST ---
elif page == "📋 Fleet List":
    st.title("📋 Fleet Management")
    if engineers:
        today_str = str(date.today())
        todays_jobs = get_schedule(st.session_state.company_id, today_str, today_str)
        job_map = {}
        for j in todays_jobs:
            eng = j['engineer_name']
            if eng in job_map: job_map[eng].append(j['job_ref'])
            else: job_map[eng] = [j['job_ref']]
        
        df_data = []
        for e in engineers:
            df_data.append({
                'id': str(e['id']), # Ensure string to prevent UUID errors
                'name': e['name'],
                'status': e['status'],
                'email': e.get('email', ''),
                'mobile': e.get('mobile', ''),
                'current_job': ", ".join(job_map.get(e['name'], ["Available"]))
            })
        
        df = pd.DataFrame(df_data)
        status_options = ["Active", "Home", "Driving", "On Site", "In Office", "Sick", "Holiday"]
        
        edited_df = st.data_editor(
            df,
            column_config={
                "id": None,
                "name": st.column_config.TextColumn("Name", required=True),
                "status": st.column_config.SelectboxColumn("Status", options=status_options, required=True),
                "email": st.column_config.TextColumn("Email Address"),
                "mobile": st.column_config.TextColumn("Mobile Number"),
                "current_job": st.column_config.TextColumn("Current Job (Today)", disabled=True)
            },
            use_container_width=True, num_rows="fixed", key="fleet_editor"
        )
        
        if st.button("Save Fleet Changes", type="primary"):
            try:
                for index, row in edited_df.iterrows():
                    # Handle updating extra columns (Ensure they exist in your Supabase 'Engineers' table)
                    payload = {"Name": row['name'], "status": row['status']}
                    if 'email' in row: payload['email'] = row['email']
                    if 'mobile' in row: payload['mobile'] = row['mobile']
                    
                    supabase.table("Engineers").update(payload).eq("id", str(row['id'])).execute()
                st.success(f"Updated engineers successfully!")
                time.sleep(1)
                st.rerun()
            except Exception as e: 
                st.error(f"Update failed. (Did you add 'email' and 'mobile' columns to the Engineers table?) Details: {e}")
    else: st.info("No engineers found.")

# --- PAGE: MAINTENANCE ---
elif page == "🔧 Maintenance":
    st.title("🔧 Maintenance Jobs")
    if jobs:
        h1, h2, h3, h4, h5 = st.columns([2, 3, 2, 2, 1])
        h1.markdown("**Ref**")
        h2.markdown("**Description**")
        h3.markdown("**Director**")
        h4.markdown("**Severity**")
        h5.markdown("**Action**")
        st.divider()
        for j in jobs:
            c1, c2, c3, c4, c5 = st.columns([2, 3, 2, 2, 1])
            c1.write(j['ref'])
            c2.write(j.get('desc', '-'))
            c3.write(j.get('director', '-'))
            sev = j.get('severity') or 'Low'
            color = "green" if "low" in sev.lower() else "orange" if "medium" in sev.lower() else "red"
            c4.markdown(f":{color}[{sev}]")
            if c5.button("Delete", key=f"del_{j['id']}", type="primary", help="Cancels job and removes from diary"):
                if delete_record("Jobs", j['id'], j['ref'], "job_ref"):
                    st.success("Deleted & Cancelled!")
                    time.sleep(0.5); st.rerun()
    else: st.info("No active jobs found.")

# --- PAGE: INSTALLATIONS ---
elif page == "🛠️ Installations":
    st.title("🛠️ Installation Tracker")
    if installs:
        ih1, ih2, ih3, ih4 = st.columns([2, 2, 4, 1])
        ih1.markdown("**Reference**")
        ih2.markdown("**Details**") 
        ih3.markdown("**Status**")
        ih4.markdown("**Action**")
        st.divider()
        for inst in installs:
            ic1, ic2, ic3, ic4 = st.columns([2, 2, 4, 1])
            ic1.write(inst['ref'])
            details = f"📍 {inst['postcode']}"
            if inst.get('desc'): details += f"\n📝 {inst['desc']}"
            if inst.get('director'): details += f"\n👤 {inst['director']}"
            ic2.text(details)
            current_status = inst.get('status', 'Not passed Finance')
            options = ["Not passed Finance", "Passed Finance", "Kit Ordered", "Kit Arrived"]
            if current_status not in options: options.insert(0, current_status)
            new_status = ic3.select_slider("Status", options=options, value=current_status, key=f"sl_inst_{inst['id']}", label_visibility="collapsed")
            if new_status != current_status:
                update_install_status(inst['id'], new_status)
                st.toast(f"Updated {inst['ref']}")
                time.sleep(0.5); st.rerun()
            if ic4.button("Delete", key=f"del_inst_{inst['id']}", type="primary"):
                if delete_record("Installs", inst['id'], inst['ref'], "job_ref"):
                    st.success("Deleted & Cancelled!")
                    time.sleep(0.5); st.rerun()
    else: st.info("No installs active.")

# --- PAGE: CUSTOMERS ---
elif page == "👥 Customers":
    st.title("👥 Customer Directory")
    
    st.subheader("🤖 Auto-Find Company Info (AI)")
    st.caption("Enter the business name and postcode, and AI will search public records for contact info and directors.")
    with st.form("ai_find_form"):
        c1, c2 = st.columns([3, 1])
        search_name = c1.text_input("Registered Business Name")
        search_pc = c2.text_input("Postcode")
        
        if st.form_submit_button("Search AI", type="primary"):
            if not search_name:
                st.warning("Please enter a business name to search.")
            else:
                with st.spinner("Searching public records..."):
                    ai_data = fetch_company_info_ai(search_name, search_pc)
                    if ai_data:
                        st.session_state.cust_draft['name'] = search_name
                        st.session_state.cust_draft['pc'] = search_pc
                        st.session_state.cust_draft['email'] = ai_data.get('email', '')
                        st.session_state.cust_draft['phone'] = ai_data.get('phone', '')
                        st.session_state.cust_draft['directors'] = ai_data.get('directors', '')
                        st.session_state.cust_draft['reg_no'] = ai_data.get('registration_number', '')
                        st.session_state.cust_draft['offices'] = ai_data.get('offices', '')
                        st.success("Information found! Review and save below.")
                    else:
                        st.warning("Could not automatically retrieve data. Please fill manually below.")

    st.subheader("📝 Manual Entry & Save")
    with st.form("new_customer_form"):
        c1, c2 = st.columns(2)
        c_name = c1.text_input("Customer / Company Name", value=st.session_state.cust_draft.get('name', ''))
        c_pc = c2.text_input("Main Postcode", value=st.session_state.cust_draft.get('pc', ''))
        
        c3, c4 = st.columns(2)
        c_email = c3.text_input("Email Address", value=st.session_state.cust_draft.get('email', ''))
        c_phone = c4.text_input("Phone Number", value=st.session_state.cust_draft.get('phone', ''))
        
        c5, c6 = st.columns(2)
        c_directors = c5.text_input("Main Directors", value=st.session_state.cust_draft.get('directors', ''))
        c_reg = c6.text_input("Business Registration Number", value=st.session_state.cust_draft.get('reg_no', ''))
        
        c_offices = st.text_area("Multiple Offices / Addresses", value=st.session_state.cust_draft.get('offices', ''))
        c_notes = st.text_area("Customer Notes", value=st.session_state.cust_draft.get('notes', ''))
        
        if st.form_submit_button("Save Customer", type="primary"):
            if not c_name or not c_pc:
                st.error("Error: Customer Name and Postcode are required.")
            else:
                try:
                    supabase.table("Customers").insert({
                        "Company_ID": st.session_state.company_id,
                        "Name": c_name, "Postcode": c_pc, "Email": c_email, "Phone": c_phone,
                        "Directors": c_directors, "Registration_Number": c_reg, "Offices": c_offices, "Notes": c_notes
                    }).execute()
                    st.success("Customer saved successfully!")
                    # Clear draft after save
                    st.session_state.cust_draft = {"name": "", "pc": "", "email": "", "phone": "", "directors": "", "reg_no": "", "offices": "", "notes": ""}
                    time.sleep(1); st.rerun()
                except Exception as e:
                    st.error(f"Error saving customer. Make sure all columns exist in your Supabase 'Customers' table. Error: {e}")
    
    st.divider()
    st.subheader("Saved Customers")
    if customers:
        df_cust = pd.DataFrame(customers)
        # Reorder columns to show important ones first if they exist
        cols_to_show = [c for c in ['Name', 'Postcode', 'Email', 'Phone', 'Directors', 'Registration_Number', 'Offices', 'Notes'] if c in df_cust.columns]
        st.dataframe(df_cust[cols_to_show], hide_index=True, use_container_width=True)
    else:
        st.info("No customers found. Add your first customer above.")

# --- PAGE: SCHEDULE WORK ---
elif page == "📅 Schedule Work":
    st.title("📅 Schedule Management")
    eng_names = [e['name'] for e in engineers] if engineers else []
    sel_date = st.date_input("Date to Schedule", min_value=datetime.today())
    
    col_forms, col_sched = st.columns([1, 1])
    
    with col_forms:
        st.subheader("Assign Tasks")
        
        with st.expander("🔧 Maintenance", expanded=True):
            with st.form("schedule_maint_form"):
                m_eng = st.selectbox("Engineer", eng_names, key="m_eng")
                maint_options = [j['ref'] for j in jobs] if jobs else []
                m_ref = st.selectbox("Maintenance Ref", maint_options, index=None, placeholder="Select Job...", key="m_ref")
                m_notes = st.text_area("Notes", key="m_notes")
                if st.form_submit_button("Assign Maintenance", type="primary"):
                    if m_eng and m_ref:
                        if add_schedule_item(st.session_state.company_id, m_eng, m_ref, sel_date, m_notes, "Maintenance"):
                            st.success(f"Assigned {m_eng} to {m_ref}"); time.sleep(1); st.rerun()
                    else: st.warning("Select Engineer and Job")
                    
        with st.expander("🛠️ Installation", expanded=False):
            with st.form("schedule_install_form"):
                i_eng = st.selectbox("Engineer", eng_names, key="i_eng")
                inst_options = [i['ref'] for i in installs] if installs else []
                i_ref = st.selectbox("Install Ref", inst_options, index=None, placeholder="Select Install...", key="i_ref")
                i_notes = st.text_area("Notes", key="i_notes")
                if st.form_submit_button("Assign Installation", type="primary"):
                    if i_eng and i_ref:
                        if add_schedule_item(st.session_state.company_id, i_eng, i_ref, sel_date, i_notes, "Install"):
                            st.success(f"Assigned {i_eng} to {i_ref}"); time.sleep(1); st.rerun()
                    else: st.warning("Select Engineer and Install")
                    
        with st.expander("📝 Note / Message", expanded=False):
            with st.form("diary_note_form"):
                n_eng = st.selectbox("For Engineer (Optional)", ["All"] + eng_names, key="n_eng")
                n_msg = st.text_area("Message / Special Request")
                if st.form_submit_button("Add Note", type="primary"):
                    if n_msg:
                        target = "ALL STAFF" if n_eng == "All" else n_eng
                        add_schedule_item(st.session_state.company_id, target, "NOTE", sel_date, n_msg, "Note")
                        st.success("Note Added"); time.sleep(1); st.rerun()

    with col_sched:
        c_head, c_filt = st.columns([3, 2])
        c_head.subheader("📆 Week Schedule")
        focus_date = c_filt.date_input("Week of:", value=datetime.today(), label_visibility="collapsed")
        
        start_of_week = focus_date - timedelta(days=focus_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        schedule_items = get_schedule(st.session_state.company_id, start_of_week, end_of_week)
        
        days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        for i in range(7):
            current_day = start_of_week + timedelta(days=i)
            day_str = current_day.strftime('%Y-%m-%d')
            day_items = [item for item in schedule_items if item['scheduled_date'] == day_str]
            
            with st.expander(f"{days_names[i]} - {current_day.strftime('%d/%m')}", expanded=(current_day == date.today() or bool(day_items))):
                if not day_items:
                    st.caption("No jobs scheduled.")
                for item in day_items:
                    note_text = str(item.get('notes', ''))
                    if "[INSTALL]" in note_text: css_class = "install"
                    elif "[NOTE]" in note_text: css_class = "note"
                    else: css_class = "job"
                    
                    content = item['job_ref']
                    if css_class == "note": content = note_text.replace("[NOTE]", "").strip()
                    
                    st.markdown(f"""
                    <div class="schedule-card {css_class}" style="padding: 5px 10px; margin-bottom: 5px;">
                        <small style="color: gray;"><b>{item['engineer_name']}</b></small><br>
                        <span style="font-size: 0.95em;">{content}</span>
                    </div>
                    """, unsafe_allow_html=True)

# --- PAGE: DATA UPLOAD ---
elif page == "⬆️ Data Upload":
    st.title("⬆️ Data Upload & Entry")
    
    with st.expander("🚦 Single Eng. Manager", expanded=False):
        st.caption("Quickly update a single engineer's status or color from here.")
        if engineers:
            eng_map = {e['name']: e['id'] for e in engineers}
            s_name = st.selectbox("Select Engineer", list(eng_map.keys()), key="se_upload")
            curr = next((e for e in engineers if e['name'] == s_name), None)
            
            stat = curr['status'] if curr else "Active"
            status_options = ["Active", "Home", "Driving", "On Site", "In Office", "Sick", "Holiday"]
            try: stat_index = status_options.index(stat)
            except: stat_index = 0 
            new_stat = st.radio("Status:", status_options, index=stat_index, key="se_stat")
            
            color_opts = ["blue", "green", "red", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen", "cadetblue", "darkpurple", "white", "pink", "lightblue", "lightgreen", "gray", "black", "lightgray"]
            curr_color = curr.get('pin_color')
            if curr_color: curr_color = curr_color.split()[0].lower()
            if not curr_color or curr_color not in color_opts: curr_color = "blue"
            new_color = st.selectbox("Pin Color:", color_opts, index=color_opts.index(curr_color), key="se_col")
            
            if st.button("Update Engineer Status", type="primary"):
                try:
                    payload = {"status": new_stat, "pin_color": new_color}
                    supabase.table("Engineers").update(payload).eq("id", eng_map[s_name]).execute()
                    st.success("Engineer Updated")
                    time.sleep(1)
                    st.rerun()
                except: pass
    
    st.divider()

    tab_single, tab_bulk = st.tabs(["Add Single Record", "Bulk Excel Upload"])
    
    with tab_single:
        col_u, col_j = st.columns(2)
        with col_u:
            st.subheader("New Engineer")
            with st.form("add_user_form"):
                u_n = st.text_input("Name")
                u_p = st.text_input("Postcode")
                u_color = st.selectbox("Pin Color", ["blue", "green", "red", "purple", "orange", "darkred", "cadetblue"])
                if st.form_submit_button("Add User", type="primary"):
                    if not u_n or not u_p:
                        st.error("Name and Postcode are required.")
                    else:
                        ok, m, coords = add_entry("Engineers", "Name", u_n, u_p, st.session_state.company_id, pin_color=u_color)
                        if ok: st.success(m); time.sleep(1); st.rerun()
                        else: st.error(m)
        with col_j:
            st.subheader("New Job")
            with st.form("add_job_form"):
                j_r = st.text_input("Ref")
                j_p = st.text_input("Postcode")
                j_desc = st.text_input("Description (Optional)")
                j_dir = st.text_input("Director Name (Optional)")
                j_sev = st.select_slider("Severity", options=["Low", "Medium", "Critical"], value="Low")
                if st.form_submit_button("Add Job", type="primary"):
                    if not j_r or not j_p:
                        st.error("Ref and Postcode are required.")
                    else:
                        ok, m, coords = add_entry("Jobs", "Job_Ref", j_r, j_p, st.session_state.company_id, desc=j_desc, director=j_dir, severity=j_sev)
                        if ok: 
                            st.success(m)
                            if coords: st.info(find_nearest_engineer_text(coords[0], coords[1], engineers))
                            time.sleep(3); st.rerun()
                        else: st.error(m)

    with tab_bulk:
        st.subheader("Upload .xlsx File")
        u_file = st.file_uploader("Choose Excel File", type=['xlsx'])
        u_type = st.radio("Content Contains:", ["Users", "Jobs"])
        if u_file and st.button("Start Upload", type="primary"):
            try:
                df = pd.read_excel(u_file)
                cols = [c.lower() for c in df.columns]
                has_name = 'name' in cols if u_type == "Users" else 'ref' in cols
                if has_name and 'postcode' in cols:
                    t_flag = "user" if u_type == "Users" else "job"
                    with st.spinner('Uploading data to cloud...'):
                        cnt = process_bulk_upload(df, t_flag, st.session_state.company_id)
                    st.success(f"Successfully Uploaded {cnt} records.")
                    time.sleep(1); st.rerun()
                else: st.error("Error: File must contain 'Name' (or 'Ref' for Jobs) and 'Postcode' columns.")
            except Exception as e: st.error(f"File processing error: {e}")
