import streamlit as st
import json
import os
import base64
from datetime import datetime

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="G Remote Universal", page_icon="📺", layout="wide")

# ---------- SESSION STATE ----------
if "device_name" not in st.session_state:
    st.session_state.device_name = None
if "device_id" not in st.session_state:
    st.session_state.device_id = None
if "is_connected" not in st.session_state:
    st.session_state.is_connected = False
if "services" not in st.session_state:
    st.session_state.services = {}
if "selected_service" not in st.session_state:
    st.session_state.selected_service = None
if "selected_char" not in st.session_state:
    st.session_state.selected_char = None
if "command_history" not in st.session_state:
    st.session_state.command_history = []
if "web_bt_supported" not in st.session_state:
    st.session_state.web_bt_supported = False
if "force_simulation" not in st.session_state:
    st.session_state.force_simulation = False

# ---------- HELPERS ----------
def get_web_bt_html():
    """Return HTML/JS component that uses Web Bluetooth."""
    return """
    <div id="bt-status" style="margin-bottom: 10px;">🔍 Ready to scan</div>
    <button id="scan-btn" onclick="scan()">🔍 Scan for Devices</button>
    <button id="disconnect-btn" onclick="disconnect()" style="display:none;">🔌 Disconnect</button>
    <div id="device-list" style="margin-top:10px;"></div>
    <div id="services-list" style="margin-top:10px;"></div>
    <div id="cmd-output" style="margin-top:10px; background:#f0f0f0; padding:5px; border-radius:5px;"></div>

    <script>
        let device = null;
        let server = null;
        let serviceMap = {};
        let charMap = {};
        let selectedCharUUID = null;

        function log(msg) {
            document.getElementById('cmd-output').innerHTML += msg + '<br>';
        }

        function updateStatus(msg) {
            document.getElementById('bt-status').innerText = msg;
            // Update URL query param for Streamlit to read
            const url = new URL(window.location);
            url.searchParams.set('bt_status', msg);
            window.history.replaceState({}, '', url);
        }

        async function scan() {
            if (!navigator.bluetooth) {
                alert('Web Bluetooth not supported in this browser. Use Chrome/Edge.');
                return;
            }
            try {
                document.getElementById('scan-btn').disabled = true;
                updateStatus('Scanning...');

                device = await navigator.bluetooth.requestDevice({
                    filters: [{ services: ['00001800-0000-1000-8000-00805f9b34fb'] }],
                    optionalServices: ['00001800-0000-1000-8000-00805f9b34fb',
                                       '00001801-0000-1000-8000-00805f9b34fb',
                                       '0000180a-0000-1000-8000-00805f9b34fb',
                                       '00001812-0000-1000-8000-00805f9b34fb']
                });

                if (device) {
                    // Connect
                    server = await device.gatt.connect();
                    updateStatus('Connected to ' + device.name);
                    // Store in URL params for Python
                    const url = new URL(window.location);
                    url.searchParams.set('device_name', device.name);
                    url.searchParams.set('device_id', device.id);
                    url.searchParams.set('connected', 'true');
                    window.history.replaceState({}, '', url);

                    // Discover services
                    const services = await server.getPrimaryServices();
                    let svcHtml = '<h4>Services</h4><ul>';
                    for (let svc of services) {
                        const uuid = svc.uuid;
                        serviceMap[uuid] = svc;
                        svcHtml += `<li><strong>${uuid}</strong>`;
                        // Get characteristics
                        const chars = await svc.getCharacteristics();
                        svcHtml += `<ul>`;
                        for (let ch of chars) {
                            const chUuid = ch.uuid;
                            charMap[chUuid] = ch;
                            svcHtml += `<li>${chUuid} (${ch.properties.join(', ')})</li>`;
                        }
                        svcHtml += `</ul></li>`;
                    }
                    svcHtml += '</ul>';
                    document.getElementById('services-list').innerHTML = svcHtml;

                    // Store services JSON in URL for Python
                    const servicesJson = {};
                    for (let svc of services) {
                        const uuid = svc.uuid;
                        const chars = await svc.getCharacteristics();
                        servicesJson[uuid] = {
                            characteristics: chars.map(c => ({ uuid: c.uuid, properties: c.properties }))
                        };
                    }
                    const url2 = new URL(window.location);
                    url2.searchParams.set('services', JSON.stringify(servicesJson));
                    window.history.replaceState({}, '', url2);

                    document.getElementById('scan-btn').style.display = 'none';
                    document.getElementById('disconnect-btn').style.display = 'inline';
                    document.getElementById('device-list').innerHTML = `<p>✅ Connected to: ${device.name}</p>`;
                }
            } catch (error) {
                alert('Error: ' + error.message);
                updateStatus('Error: ' + error.message);
            } finally {
                document.getElementById('scan-btn').disabled = false;
            }
        }

        async function disconnect() {
            if (server) {
                try { await server.disconnect(); } catch(e) {}
            }
            device = null;
            server = null;
            serviceMap = {};
            charMap = {};
            document.getElementById('disconnect-btn').style.display = 'none';
            document.getElementById('scan-btn').style.display = 'inline';
            document.getElementById('device-list').innerHTML = '';
            document.getElementById('services-list').innerHTML = '';
            updateStatus('Disconnected');
            const url = new URL(window.location);
            url.searchParams.delete('device_name');
            url.searchParams.delete('device_id');
            url.searchParams.delete('connected');
            url.searchParams.delete('services');
            window.history.replaceState({}, '', url);
        }

        // Called when user selects a characteristic from Python (via dropdown)
        window.selectCharacteristic = function(uuid) {
            selectedCharUUID = uuid;
        };

        // Send command
        window.sendCommand = async function(data) {
            if (!selectedCharUUID) {
                alert('Select a characteristic first.');
                return;
            }
            if (!server || !device) {
                alert('Not connected.');
                return;
            }
            try {
                const char = charMap[selectedCharUUID];
                if (!char) {
                    alert('Characteristic not found.');
                    return;
                }
                // Convert data to ArrayBuffer
                let bytes;
                if (typeof data === 'string') {
                    if (data.startsWith('0x') || data.startsWith('0X')) {
                        const hex = data.slice(2);
                        bytes = new Uint8Array(hex.match(/.{1,2}/g).map(b => parseInt(b, 16))).buffer;
                    } else {
                        const encoder = new TextEncoder();
                        bytes = encoder.encode(data);
                    }
                } else {
                    bytes = data;
                }
                await char.writeValue(bytes);
                log(`✅ Sent: ${data}`);
                // Update history in URL
                const url = new URL(window.location);
                const history = JSON.parse(url.searchParams.get('history') || '[]');
                history.push({ time: new Date().toLocaleTimeString(), data: data });
                url.searchParams.set('history', JSON.stringify(history));
                window.history.replaceState({}, '', url);
            } catch (e) {
                alert('Send error: ' + e.message);
            }
        };

        // Auto-run on load: read query params to restore state
        (function() {
            const params = new URLSearchParams(window.location.search);
            const connected = params.get('connected') === 'true';
            const deviceName = params.get('device_name');
            if (connected && deviceName) {
                document.getElementById('device-list').innerHTML = `<p>✅ Connected to: ${deviceName}</p>`;
                document.getElementById('scan-btn').style.display = 'none';
                document.getElementById('disconnect-btn').style.display = 'inline';
                updateStatus('Connected to ' + deviceName);
            }
            const servicesJson = params.get('services');
            if (servicesJson) {
                try {
                    const svc = JSON.parse(servicesJson);
                    let html = '<h4>Services</h4><ul>';
                    for (let [uuid, data] of Object.entries(svc)) {
                        html += `<li><strong>${uuid}</strong><ul>`;
                        for (let ch of data.characteristics) {
                            html += `<li>${ch.uuid} (${ch.properties.join(', ')})</li>`;
                        }
                        html += `</ul></li>`;
                    }
                    html += '</ul>';
                    document.getElementById('services-list').innerHTML = html;
                } catch(e) {}
            }
        })();
    </script>
    """

# ---------- UI ----------
st.title("📺 G Remote Universal")
st.markdown("Control any Bluetooth‑enabled TV using **Web Bluetooth** (works in Chrome/Edge).")

# Sidebar
with st.sidebar:
    st.header("🔗 Connection")

    # Detect Web Bluetooth support
    if 'web_bt_supported' not in st.session_state:
        # Check via query param from component
        st.session_state.web_bt_supported = True  # assume for now, will be set by JS

    # Use st.html to embed the Web Bluetooth component
    st.components.v1.html(get_web_bt_html(), height=400, scrolling=True)

    st.divider()
    st.caption("If scanning fails, try refreshing the page and allow Bluetooth permissions.")

    # Force simulation toggle
    force = st.checkbox("Force Simulation Mode", value=st.session_state.force_simulation)
    if force != st.session_state.force_simulation:
        st.session_state.force_simulation = force
        st.rerun()

# Main columns
col1, col2 = st.columns([2, 1])

with col1:
    # Read connection status from query params
    params = st.query_params
    device_name = params.get("device_name", None)
    connected = params.get("connected", "false") == "true"
    services_json = params.get("services", None)

    if connected and device_name:
        st.session_state.is_connected = True
        st.session_state.device_name = device_name
        if services_json:
            try:
                st.session_state.services = json.loads(services_json)
            except:
                pass
    else:
        if st.session_state.is_connected and not connected:
            st.session_state.is_connected = False
            st.session_state.device_name = None
            st.session_state.services = {}

    if st.session_state.is_connected:
        st.subheader("📟 Remote Control")
        st.markdown(f"**TV:** {st.session_state.device_name}")

        # Display services/characteristics
        if st.session_state.services:
            st.markdown("#### Services & Characteristics")
            service_uuids = list(st.session_state.services.keys())
            if service_uuids:
                sel_svc = st.selectbox("Service", service_uuids,
                                       format_func=lambda u: u[:8])
                if sel_svc:
                    chars = st.session_state.services[sel_svc]["characteristics"]
                    if chars:
                        char_options = [f"{c['uuid'][:8]}" for c in chars]
                        sel_char_idx = st.selectbox("Characteristic", range(len(chars)), format_func=lambda i: char_options[i])
                        selected_char = chars[sel_char_idx]["uuid"]
                        # Store selected char in session for JS to use
                        st.session_state.selected_char = selected_char
                        # Write to query param so JS can read it
                        st.query_params["selected_char"] = selected_char
                        st.write(f"Selected: {selected_char}")
                    else:
                        st.info("No characteristics in this service.")

        # Command sending
        st.markdown("#### Send Command")
        if st.session_state.selected_char:
            # Preset commands
            st.markdown("**Presets** (common media keys)")
            presets = {
                "▶ Play": "0x01",
                "⏸ Pause": "0x02",
                "⏹ Stop": "0x03",
                "⏭ Next": "0x04",
                "⏮ Prev": "0x05",
                "🔊 Vol Up": "0x06",
                "🔉 Vol Down": "0x07",
                "🔇 Mute": "0x08",
                "CH+": "0x09",
                "CH-": "0x0a",
                "0": "0x30",
                "1": "0x31",
                "2": "0x32",
                "3": "0x33",
                "4": "0x34",
                "5": "0x35",
                "6": "0x36",
                "7": "0x37",
                "8": "0x38",
                "9": "0x39",
            }
            keys = list(presets.keys())
            for i in range(0, len(keys), 4):
                cols = st.columns(4)
                for j, key in enumerate(keys[i:i+4]):
                    with cols[j]:
                        if st.button(key, key=f"preset_{key}"):
                            # Call JavaScript function via st.components.v1.html with a script
                            js = f"""
                            <script>
                            if (window.sendCommand) {{
                                window.sendCommand("{presets[key]}");
                            }} else {{
                                alert("Not connected or component not loaded.");
                            }}
                            </script>
                            """
                            st.components.v1.html(js, height=0)
                            st.rerun()

            st.divider()
            st.markdown("**Custom Command**")
            custom_input = st.text_input("Data (text or hex with 0x prefix)", key="custom_data")
            if st.button("Send Custom"):
                if custom_input:
                    js = f"""
                    <script>
                    if (window.sendCommand) {{
                        window.sendCommand("{custom_input}");
                    }} else {{
                        alert("Not connected or component not loaded.");
                    }}
                    </script>
                    """
                    st.components.v1.html(js, height=0)
                    st.rerun()
                else:
                    st.warning("Enter data.")
        else:
            st.info("Select a characteristic first.")

        # Command history from URL
        history_json = params.get("history", "[]")
        try:
            history = json.loads(history_json)
        except:
            history = []
        if history:
            st.markdown("#### Command History")
            for entry in history[-10:]:
                st.text(f"[{entry['time']}] {entry['data']}")
    else:
        st.info("Use the 'Scan for Devices' button above to connect to a TV.")

with col2:
    st.subheader("⚙️ Info")
    if st.session_state.is_connected:
        st.write("**Connected:**", st.session_state.device_name)
        st.write("**Mode:** Web Bluetooth (client-side)")
    else:
        st.warning("Not connected.")

    st.divider()
    st.subheader("📋 Tips")
    st.markdown("""
    - **Web Bluetooth** works in Chrome, Edge, and other Chromium browsers.
    - Your browser will ask for permission to access Bluetooth.
    - After scanning, select your TV from the list.
    - Once connected, you'll see services/characteristics – pick one and send commands.
    - If you don't see your TV, ensure it's in pairing/discoverable mode.
    """)

st.divider()
st.caption("G Remote Universal – Web Bluetooth Edition. Works on Streamlit Cloud!")
