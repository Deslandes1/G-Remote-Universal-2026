"""
G Remote Universal – Bluetooth TV Remote Control
- Uses 'bleak' for real Bluetooth communication (local machine only)
- Falls back to simulation if bleak is not available
- Scan, connect, explore services, and send commands
"""

import streamlit as st
import asyncio
import json
import random
import threading
import time
from datetime import datetime
import os

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
if "custom_command" not in st.session_state:
    st.session_state.custom_command = ""
if "command_history" not in st.session_state:
    st.session_state.command_history = []
if "bleak_available" not in st.session_state:
    st.session_state.bleak_available = False

# ---------- ENVIRONMENT CHECK ----------
def is_running_on_streamlit_cloud():
    """Detect if running on Streamlit Cloud (or similar remote)."""
    return 'STREAMLIT_SERVER' in os.environ or 'STREAMLIT_CLOUD' in os.environ

if is_running_on_streamlit_cloud():
    st.warning("🌐 You are running on Streamlit Cloud. Bluetooth is not available. This app will work in simulation mode only.")
    st.info("To control a real TV, clone the repository and run the app locally on your computer.")
    st.session_state.bleak_available = False
else:
    try:
        import bleak
        from bleak import BleakScanner, BleakClient
        st.session_state.bleak_available = True
    except ImportError:
        st.warning("⚠️ 'bleak' is not installed. Install it with: pip install bleak")
        st.info("If you are running locally, install it and restart the app to enable real Bluetooth.")
        st.session_state.bleak_available = False

# ---------- HELPER FUNCTIONS ----------
def run_async(coro):
    """Run an async coroutine in a new event loop."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except Exception as e:
        st.error(f"Async error: {e}")
        return None

def scan_devices_sync():
    """Scan for BLE devices (synchronous wrapper). Returns a list of dicts."""
    if not st.session_state.bleak_available:
        return simulate_scan()
    try:
        devices = run_async(BleakScanner.discover())
        if not devices:
            return []
        # Convert to list of dicts, handling possible missing attributes
        device_list = []
        for d in devices:
            # Use getattr to safely access attributes
            name = getattr(d, 'name', None) or "Unknown"
            address = getattr(d, 'address', None)
            if not address:
                # Some versions may use 'address' or 'device.address'
                address = getattr(d, 'address', str(d))
            device_list.append({"name": name, "address": address})
        return device_list
    except Exception as e:
        st.error(f"Scan failed: {e}")
        return []

def simulate_scan():
    """Return fake devices for simulation."""
    return [
        {"name": "Samsung TV (Mock)", "address": "00:11:22:33:44:55"},
        {"name": "LG TV (Mock)", "address": "66:77:88:99:AA:BB"},
        {"name": "Sony TV (Mock)", "address": "CC:DD:EE:FF:00:11"},
        {"name": "Hisense (Mock)", "address": "22:33:44:55:66:77"},
    ]

def connect_device_sync(address):
    """Connect to a device and return client."""
    if not st.session_state.bleak_available:
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
            # Discover services
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
    if st.session_state.client and st.session_state.bleak_available:
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
    """Send data to a characteristic."""
    if not st.session_state.bleak_available or not st.session_state.is_connected:
        # Simulate
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
        # Convert data to bytes if string
        if isinstance(data, str):
            if data.startswith("0x") or data.startswith("0X"):
                # Hex string
                data = bytes.fromhex(data[2:])
            else:
                data = data.encode('utf-8')
        # Write
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
st.markdown("Control any Bluetooth‑enabled TV (or any BLE device) right from your computer.")

# Sidebar – Connection
with st.sidebar:
    st.header("🔗 Bluetooth Connection")
    if st.session_state.bleak_available:
        st.caption("Using real Bluetooth (bleak)")
    else:
        st.caption("⚠️ Simulation mode")

    # Scan
    if st.button("🔄 Scan for Devices"):
        with st.spinner("Scanning..."):
            devices = scan_devices_sync()  # now returns a list of dicts
            st.session_state.device_list = devices
            if not devices:
                st.warning("No devices found. Try again.")
            else:
                st.success(f"Found {len(devices)} devices")

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

# Main area
col1, col2 = st.columns([2, 1])

with col1:
    if st.session_state.is_connected:
        st.subheader("📟 Remote Control")
        # Display current status
        st.markdown(f"**TV:** {st.session_state.selected_device}")

        # Services & Characteristics
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

        # Command sending
        st.markdown("#### Send Command")
        if st.session_state.selected_char:
            # Preset commands
            st.markdown("**Presets** (common media keys)")
            preset_cols = st.columns(4)
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
            # Show preset buttons in groups
            keys = list(presets.keys())
            for i in range(0, len(keys), 4):
                cols = st.columns(4)
                for j, key in enumerate(keys[i:i+4]):
                    with cols[j]:
                        if st.button(key, key=f"preset_{key}"):
                            send_command_sync(st.session_state.selected_char, presets[key])
            st.divider()
            # Custom command
            st.markdown("**Custom Command**")
            custom_input = st.text_input("Data (text or hex with 0x prefix)", key="custom_data")
            if st.button("Send Custom"):
                if custom_input:
                    send_command_sync(st.session_state.selected_char, custom_input)
                else:
                    st.warning("Enter data.")
        else:
            st.info("Select a characteristic first.")

        # Command history
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
        st.write("**Bluetooth:**", "Real" if st.session_state.bleak_available else "Simulated")
    else:
        st.warning("Not connected.")

    st.divider()
    st.subheader("📋 Programming Tips")
    st.markdown("""
    - To control a TV, you need to know the correct **Service UUID** and **Characteristic UUID**.
    - Many TVs use **HID over GATT** (Human Interface Device) for remote control.  
      The service UUID is often `00001812-0000-1000-8000-00805f9b34fb`.
    - The characteristic for **Report** is usually `00002a4d-0000-1000-8000-00805f9b34fb`.
    - You may need to send **Report IDs** (first byte) to specify which key.
    - Experiment with the presets above – they send simple byte codes that many devices understand.
    - Check your TV's manual or look for online documentation for the correct UUIDs and command formats.
    """)

# Footer
st.divider()
st.caption("G Remote Universal v2.0 – Real Bluetooth via bleak. Connect locally to control your TV.")
