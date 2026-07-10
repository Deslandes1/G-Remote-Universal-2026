"""
G Remote Universal – Bluetooth TV Remote Control
- Uses 'bleak' for real Bluetooth (local only)
- Falls back to simulation if bleak is not available or scanning fails
- Works on Streamlit Cloud (simulation) and locally (real or simulated)
"""

import streamlit as st
import asyncio
import os
from datetime import datetime

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="G Remote Universal", page_icon="📺", layout="wide")

# ---------- SESSION STATE ----------
if "device_list" not in st.session_state:
    st.session_state.device_list = []
if "selected_device" not in st.session_state:
    st.session_state.selected_device = None
if "is_connected" not in st.session_state:
    st.session_state.is_connected = False
if "client" not in st.session_state:
    st.session_state.client = None
if "services" not in st.session_state:
    st.session_state.services = {}
if "selected_service" not in st.session_state:
    st.session_state.selected_service = None
if "selected_char" not in st.session_state:
    st.session_state.selected_char = None
if "command_history" not in st.session_state:
    st.session_state.command_history = []
if "bleak_available" not in st.session_state:
    st.session_state.bleak_available = False
if "force_simulation" not in st.session_state:
    st.session_state.force_simulation = False
if "scan_attempted" not in st.session_state:
    st.session_state.scan_attempted = False

# ---------- ENVIRONMENT CHECK ----------
def is_running_on_streamlit_cloud():
    return 'STREAMLIT_SERVER' in os.environ or 'STREAMLIT_CLOUD' in os.environ

if is_running_on_streamlit_cloud():
    st.session_state.bleak_available = False
    st.session_state.force_simulation = True
else:
    try:
        import bleak
        from bleak import BleakScanner, BleakClient
        st.session_state.bleak_available = True
    except ImportError:
        st.session_state.bleak_available = False
        st.session_state.force_simulation = True

# ---------- HELPER FUNCTIONS ----------
def run_async(coro):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except Exception as e:
        st.error(f"Async error: {e}")
        return None

def simulate_scan():
    return [
        {"name": "Samsung TV (Mock)", "address": "00:11:22:33:44:55"},
        {"name": "LG TV (Mock)", "address": "66:77:88:99:AA:BB"},
        {"name": "Sony TV (Mock)", "address": "CC:DD:EE:FF:00:11"},
        {"name": "Hisense (Mock)", "address": "22:33:44:55:66:77"},
    ]

def scan_devices_sync(force_sim=False):
    """Scan for BLE devices. Returns list of dicts with name/address."""
    if force_sim or not st.session_state.bleak_available:
        return simulate_scan()
    try:
        devices = run_async(BleakScanner.discover())
        if not devices:
            return []
        device_list = []
        for d in devices:
            name = getattr(d, 'name', None) or "Unknown"
            address = getattr(d, 'address', None)
            if not address:
                address = str(d)
            device_list.append({"name": name, "address": address})
        return device_list
    except Exception as e:
        st.error(f"⚠️ Bluetooth scan failed: {e}")
        st.warning("Switching to simulation mode. You can still test the interface.")
        st.session_state.force_simulation = True
        return simulate_scan()

def connect_device_sync(address):
    if st.session_state.force_simulation or not st.session_state.bleak_available:
        # Simulate connection
        st.session_state.is_connected = True
        st.session_state.services = {
            "00001800-0000-1000-8000-00805f9b34fb": {
                "name": "Generic Access",
                "characteristics": [
                    {"uuid": "00002a00-0000-1000-8000-00805f9b34fb", "name": "Device Name"},
                ]
            },
            "00001801-0000-1000-8000-00805f9b34fb": {
                "name": "Generic Attribute",
                "characteristics": []
            },
            "0000180a-0000-1000-8000-00805f9b34fb": {
                "name": "Device Information",
                "characteristics": [
                    {"uuid": "00002a29-0000-1000-8000-00805f9b34fb", "name": "Manufacturer Name"},
                ]
            }
        }
        return "simulated_client"

    try:
        client = run_async(BleakClient(address))
        if client and client.is_connected:
            st.session_state.is_connected = True
            services = run_async(client.get_services())
            service_dict = {}
            for svc in services:
                chars = []
                for char in svc.characteristics:
                    chars.append({
                        "uuid": char.uuid,
                        "name": char.description or char.uuid,
                        "properties": char.properties
                    })
                service_dict[svc.uuid] = {
                    "name": svc.description or svc.uuid,
                    "characteristics": chars
                }
            st.session_state.services = service_dict
            return client
        else:
            st.error("Connection failed")
            return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def disconnect_device():
    if st.session_state.client and st.session_state.bleak_available and not st.session_state.force_simulation:
        try:
            run_async(st.session_state.client.disconnect())
        except:
            pass
    st.session_state.is_connected = False
    st.session_state.client = None
    st.session_state.services = {}
    st.session_state.selected_service = None
    st.session_state.selected_char = None

def send_command_sync(char_uuid, data):
    if st.session_state.force_simulation or not st.session_state.bleak_available or not st.session_state.is_connected:
        st.session_state.command_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "char": char_uuid,
            "data": data
        })
        st.success(f"📤 Sent (simulated): {data}")
        return True

    if not st.session_state.client:
        st.error("Not connected")
        return False

    try:
        if isinstance(data, str):
            if data.startswith("0x") or data.startswith("0X"):
                data = bytes.fromhex(data[2:])
            else:
                data = data.encode('utf-8')
        run_async(st.session_state.client.write_gatt_char(char_uuid, data))
        st.session_state.command_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "char": char_uuid,
            "data": data.hex() if isinstance(data, bytes) else str(data)
        })
        st.success("✅ Command sent!")
        return True
    except Exception as e:
        st.error(f"Send error: {e}")
        return False

# ---------- UI ----------
st.title("📺 G Remote Universal")
st.markdown("Control any Bluetooth‑enabled TV (or any BLE device).")

# Sidebar
with st.sidebar:
    st.header("🔗 Connection")
    if st.session_state.bleak_available and not st.session_state.force_simulation:
        st.caption("🟢 Real Bluetooth mode")
    else:
        st.caption("🟡 Simulation mode")

    force_sim = st.checkbox("Force Simulation Mode", value=st.session_state.force_simulation)
    if force_sim != st.session_state.force_simulation:
        st.session_state.force_simulation = force_sim
        if st.session_state.is_connected:
            disconnect_device()
        st.rerun()

    if st.button("🔄 Scan for Devices"):
        with st.spinner("Scanning..."):
            devices = scan_devices_sync(force_sim)
            st.session_state.device_list = devices
            if not devices:
                st.warning("No devices found. Try again.")
            else:
                st.success(f"Found {len(devices)} devices")
            st.session_state.scan_attempted = True

    if st.session_state.device_list:
        device_names = [f"{d['name']} ({d['address']})" for d in st.session_state.device_list]
        selected = st.selectbox("Select a device", device_names)
        if selected:
            idx = device_names.index(selected)
            addr = st.session_state.device_list[idx]["address"]
            if st.button("🔗 Connect"):
                with st.spinner(f"Connecting to {selected}..."):
                    client = connect_device_sync(addr)
                    if client:
                        st.session_state.client = client
                        st.session_state.selected_device = selected
                        st.success("Connected!")
                        st.rerun()

    if st.session_state.is_connected:
        st.info(f"Connected to: {st.session_state.selected_device}")
        if st.button("🔌 Disconnect"):
            disconnect_device()
            st.rerun()

# Main columns
col1, col2 = st.columns([2, 1])

with col1:
    if st.session_state.is_connected:
        st.subheader("📟 Remote Control")
        st.markdown(f"**TV:** {st.session_state.selected_device}")

        st.markdown("#### Services & Characteristics")
        if st.session_state.services:
            service_uuids = list(st.session_state.services.keys())
            if service_uuids:
                sel_svc = st.selectbox("Service", service_uuids, 
                                       format_func=lambda u: f"{st.session_state.services[u]['name']} ({u[:8]})")
                if sel_svc:
                    st.session_state.selected_service = sel_svc
                    chars = st.session_state.services[sel_svc]["characteristics"]
                    if chars:
                        char_options = [f"{c['name']} ({c['uuid'][:8]})" for c in chars]
                        sel_char_idx = st.selectbox("Characteristic", range(len(chars)), format_func=lambda i: char_options[i])
                        st.session_state.selected_char = chars[sel_char_idx]["uuid"]
                        st.write(f"Selected: {chars[sel_char_idx]['name']} ({chars[sel_char_idx]['uuid']})")
                    else:
                        st.info("No characteristics in this service.")
            else:
                st.info("No services found.")
        else:
            st.info("No services discovered (connect to a device to see them).")

        st.markdown("#### Send Command")
        if st.session_state.selected_char:
            st.markdown("**Presets** (common media keys)")
            presets = {
                "▶ Play": b"\x01",
                "⏸ Pause": b"\x02",
                "⏹ Stop": b"\x03",
                "⏭ Next": b"\x04",
                "⏮ Prev": b"\x05",
                "🔊 Vol Up": b"\x06",
                "🔉 Vol Down": b"\x07",
                "🔇 Mute": b"\x08",
                "CH+": b"\x09",
                "CH-": b"\x0a",
                "0": b"\x30",
                "1": b"\x31",
                "2": b"\x32",
                "3": b"\x33",
                "4": b"\x34",
                "5": b"\x35",
                "6": b"\x36",
                "7": b"\x37",
                "8": b"\x38",
                "9": b"\x39",
            }
            keys = list(presets.keys())
            for i in range(0, len(keys), 4):
                cols = st.columns(4)
                for j, key in enumerate(keys[i:i+4]):
                    with cols[j]:
                        if st.button(key, key=f"preset_{key}"):
                            send_command_sync(st.session_state.selected_char, presets[key])
            st.divider()
            st.markdown("**Custom Command**")
            custom_input = st.text_input("Data (text or hex with 0x prefix)", key="custom_data")
            if st.button("Send Custom"):
                if custom_input:
                    send_command_sync(st.session_state.selected_char, custom_input)
                else:
                    st.warning("Enter data.")
        else:
            st.info("Select a characteristic first.")

        st.markdown("#### Command History")
        if st.session_state.command_history:
            for entry in st.session_state.command_history[-10:]:
                st.text(f"[{entry['time']}] {entry['char'][:8]} -> {entry['data']}")
        else:
            st.caption("No commands sent yet.")
    else:
        st.info("Connect to a TV using the sidebar to start controlling it.")

with col2:
    st.subheader("⚙️ Device Info")
    if st.session_state.is_connected:
        st.write("**Connected Device:**", st.session_state.selected_device)
        st.write("**Services:**", len(st.session_state.services))
        st.write("**Mode:**", "Real Bluetooth" if (st.session_state.bleak_available and not st.session_state.force_simulation) else "Simulation")
    else:
        st.warning("Not connected.")

    st.divider()
    st.subheader("📋 Programming Tips")
    st.markdown("""
    - **Real Bluetooth** works only when you run this app **locally**.
    - On **Streamlit Cloud** or when scanning fails, the app uses **simulation** – you can still test the UI.
    - To control a real TV, find the correct **Service** and **Characteristic** UUIDs.
    - Common HID service: `00001812-0000-1000-8000-00805f9b34fb`  
      Report characteristic: `00002a4d-0000-1000-8000-00805f9b34fb`.
    - Preset buttons send simple byte codes that many devices understand.
    """)

st.divider()
st.caption("G Remote Universal v2.1 – Real Bluetooth via bleak, with automatic fallback to simulation.")
