import streamlit as st
import json
import random

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="G Remote Universal", page_icon="📺", layout="wide")

# ---------- DEFAULT CHANNEL DATA ----------
# This is a simplified channel list per country.
# In production, you would fetch this from an external API or a larger database.
CHANNELS = {
    "US": [
        {"number": 2, "name": "CBS"},
        {"number": 4, "name": "NBC"},
        {"number": 5, "name": "FOX"},
        {"number": 7, "name": "ABC"},
        {"number": 9, "name": "PBS"},
        {"number": 11, "name": "CW"},
        {"number": 13, "name": "MyNetworkTV"},
        {"number": 25, "name": "CNN"},
        {"number": 30, "name": "ESPN"},
        {"number": 35, "name": "MTV"},
        {"number": 42, "name": "Discovery"},
        {"number": 50, "name": "History"},
        {"number": 60, "name": "TLC"},
        {"number": 70, "name": "AMC"},
        {"number": 80, "name": "HBO"},
        {"number": 90, "name": "Showtime"},
    ],
    "UK": [
        {"number": 1, "name": "BBC One"},
        {"number": 2, "name": "BBC Two"},
        {"number": 3, "name": "ITV"},
        {"number": 4, "name": "Channel 4"},
        {"number": 5, "name": "Channel 5"},
        {"number": 6, "name": "Sky News"},
        {"number": 7, "name": "Sky Sports"},
        {"number": 8, "name": "E4"},
        {"number": 9, "name": "More4"},
        {"number": 10, "name": "Dave"},
        {"number": 20, "name": "BBC News"},
        {"number": 30, "name": "CBBC"},
        {"number": 40, "name": "CBeebies"},
    ],
    "FR": [
        {"number": 1, "name": "TF1"},
        {"number": 2, "name": "France 2"},
        {"number": 3, "name": "France 3"},
        {"number": 4, "name": "Canal+"},
        {"number": 5, "name": "France 5"},
        {"number": 6, "name": "M6"},
        {"number": 7, "name": "Arte"},
        {"number": 8, "name": "C8"},
        {"number": 9, "name": "W9"},
        {"number": 10, "name": "TMC"},
        {"number": 20, "name": "BFM TV"},
        {"number": 30, "name": "LCI"},
        {"number": 40, "name": "France Info"},
    ],
    "HT": [  # Haiti
        {"number": 1, "name": "TNH"},
        {"number": 2, "name": "Métropole"},
        {"number": 3, "name": "Canal 11"},
        {"number": 4, "name": "Télé Haïti"},
        {"number": 5, "name": "Radio Télévision Caraïbes"},
        {"number": 6, "name": "Scoop FM"},
        {"number": 7, "name": "Magik 9"},
        {"number": 8, "name": "Haiti TV"},
    ],
}

# ---------- SESSION STATE ----------
if "tv_connected" not in st.session_state:
    st.session_state.tv_connected = False
if "current_channel" not in st.session_state:
    st.session_state.current_channel = 1
if "custom_channels" not in st.session_state:
    st.session_state.custom_channels = {}  # key: number, value: channel name
if "selected_country" not in st.session_state:
    st.session_state.selected_country = "US"
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = "Samsung"
if "volume" not in st.session_state:
    st.session_state.volume = 50
if "muted" not in st.session_state:
    st.session_state.muted = False

# ---------- HELPER FUNCTIONS ----------
def get_channel_name(number, country):
    """Return the channel name for a given number, checking custom mappings first."""
    if number in st.session_state.custom_channels:
        return st.session_state.custom_channels[number]
    channels = CHANNELS.get(country, [])
    for ch in channels:
        if ch["number"] == number:
            return ch["name"]
    return "Unknown"

def get_channel_list(country):
    """Return the full list of channels for the country, with custom overrides."""
    base = CHANNELS.get(country, [])
    # Add custom channels if they are not already in base
    existing_numbers = {ch["number"] for ch in base}
    for num, name in st.session_state.custom_channels.items():
        if num not in existing_numbers:
            base.append({"number": num, "name": name})
    return sorted(base, key=lambda x: x["number"])

def set_channel(number):
    if 0 <= number <= 999:  # Allow up to 999
        st.session_state.current_channel = number
        st.success(f"Tuned to channel {number}: {get_channel_name(number, st.session_state.selected_country)}")
    else:
        st.warning("Channel number out of range (0-999)")

def change_channel(delta):
    new_num = st.session_state.current_channel + delta
    if new_num < 0:
        new_num = 0
    if new_num > 999:
        new_num = 999
    set_channel(new_num)

# ---------- MAIN UI ----------
st.title("📺 G Remote Universal")
st.markdown("Control any flatscreen TV via Bluetooth – program channels for your country.")

# ---- Sidebar ----
with st.sidebar:
    st.header("🔧 Settings")
    brand = st.selectbox("TV Brand", ["Samsung", "LG", "Sony", "Panasonic", "TCL", "Hisense", "Other"],
                         index=0, key="brand_select")
    if brand != st.session_state.selected_brand:
        st.session_state.selected_brand = brand

    country = st.selectbox("Country", list(CHANNELS.keys()), index=list(CHANNELS.keys()).index(st.session_state.selected_country),
                           key="country_select")
    if country != st.session_state.selected_country:
        st.session_state.selected_country = country
        # Reset current channel to first available
        channels = get_channel_list(country)
        if channels:
            st.session_state.current_channel = channels[0]["number"]
        else:
            st.session_state.current_channel = 1

    st.divider()
    st.header("📡 Connection")
    if st.button("🔗 Connect Bluetooth"):
        # Simulate connection
        st.session_state.tv_connected = True
        st.success("Bluetooth connected to TV!")
    if st.button("🔌 Disconnect"):
        st.session_state.tv_connected = False
        st.warning("Disconnected")
    st.write(f"Status: {'✅ Connected' if st.session_state.tv_connected else '❌ Disconnected'}")

# ---- Main area ----
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📟 Remote Control")
    # Display current channel info
    if st.session_state.tv_connected:
        ch_name = get_channel_name(st.session_state.current_channel, st.session_state.selected_country)
        st.markdown(f"### 📺 Now Playing: **{ch_name}** (Channel {st.session_state.current_channel})")
        # Volume bar
        vol_col1, vol_col2 = st.columns([3, 1])
        with vol_col1:
            new_vol = st.slider("Volume", 0, 100, st.session_state.volume, key="vol_slider")
            if new_vol != st.session_state.volume:
                st.session_state.volume = new_vol
        with vol_col2:
            if st.button("🔇 Mute"):
                st.session_state.muted = not st.session_state.muted
                st.rerun()
            st.write("Muted" if st.session_state.muted else "Unmuted")
    else:
        st.info("Connect to TV to control it.")

    # Remote buttons
    if st.session_state.tv_connected:
        st.markdown("#### Buttons")
        col_pwr, col_input, col_menu = st.columns(3)
        with col_pwr:
            if st.button("⏻ Power"):
                st.info("Power toggled (simulated)")
        with col_input:
            if st.button("Source"):
                st.info("Input source menu (simulated)")
        with col_menu:
            if st.button("☰ Menu"):
                st.info("Menu opened (simulated)")

        # Number pad
        st.markdown("#### Number Pad")
        num_cols = st.columns(5)
        numbers = ["1","2","3","4","5","6","7","8","9","0"]
        for i, num in enumerate(numbers):
            with num_cols[i % 5]:
                if st.button(num, key=f"num_{num}"):
                    # For simplicity, just set channel to the number (single digit)
                    # In real remotes, you'd accumulate digits; we'll just set direct.
                    try:
                        set_channel(int(num))
                    except:
                        pass
        # Channel up/down
        ch_col1, ch_col2 = st.columns(2)
        with ch_col1:
            if st.button("CH ▲"):
                change_channel(1)
        with ch_col2:
            if st.button("CH ▼"):
                change_channel(-1)

        # Additional buttons
        st.markdown("#### Other")
        extra_cols = st.columns(4)
        with extra_cols[0]:
            if st.button("⬆ Up"):
                st.info("Up")
        with extra_cols[1]:
            if st.button("⬇ Down"):
                st.info("Down")
        with extra_cols[2]:
            if st.button("⬅ Left"):
                st.info("Left")
        with extra_cols[3]:
            if st.button("➡ Right"):
                st.info("Right")
        if st.button("OK/Select"):
            st.info("OK pressed")
    else:
        st.warning("Please connect to the TV first.")

with col2:
    st.subheader("📋 Channel Programming")
    st.markdown(f"**Country:** {st.session_state.selected_country}")
    st.markdown("#### Available Channels")
    channels = get_channel_list(st.session_state.selected_country)
    if not channels:
        st.info("No channels for this country.")
    else:
        # Show channel list with ability to assign custom names
        for ch in channels:
            col_a, col_b, col_c = st.columns([1, 3, 2])
            with col_a:
                st.write(f"**{ch['number']}**")
            with col_b:
                st.write(ch['name'])
            with col_c:
                if st.button("✏️", key=f"edit_{ch['number']}"):
                    # Open a popover for editing
                    with st.popover(f"Edit channel {ch['number']}"):
                        new_name = st.text_input("Channel name", value=ch['name'])
                        if st.button("Save"):
                            st.session_state.custom_channels[ch['number']] = new_name
                            st.rerun()
        # Add custom channel
        st.markdown("#### Add Custom Channel")
        with st.form("add_channel"):
            new_num = st.number_input("Channel number", min_value=0, max_value=999, step=1, value=100)
            new_name = st.text_input("Channel name")
            if st.form_submit_button("Add"):
                if new_name.strip():
                    st.session_state.custom_channels[new_num] = new_name.strip()
                    st.rerun()
                else:
                    st.warning("Please enter a name.")

    # Reset custom channels
    if st.button("Reset All Custom Channels"):
        st.session_state.custom_channels = {}
        st.rerun()

# Footer
st.divider()
st.caption("G Remote Universal v1.0 – Simulated Bluetooth remote control. For demonstration only.")
