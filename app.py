import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="G Remote Universal", page_icon="📺", layout="wide")

# ---------- PARENT MESSAGE LISTENER ----------
st.markdown("""
<script>
window.addEventListener('message', function(event) {
    const data = event.data;
    if (data && data.type === 'bt_update') {
        const url = new URL(window.location.href);
        const params = data.data;
        for (let key in params) {
            if (params[key] !== null && params[key] !== undefined) {
                url.searchParams.set(key, params[key]);
            } else {
                url.searchParams.delete(key);
            }
        }
        window.history.replaceState({}, '', url);
        window.dispatchEvent(new Event('popstate'));
    }
});
</script>
""", unsafe_allow_html=True)

# ---------- SESSION STATE ----------
if "device_name" not in st.session_state:
    st.session_state.device_name = None
if "is_connected" not in st.session_state:
    st.session_state.is_connected = False
if "services" not in st.session_state:
    st.session_state.services = {}
if "selected_char" not in st.session_state:
    st.session_state.selected_char = None
if "command_history" not in st.session_state:
    st.session_state.command_history = []

# ---------- FULL UUID CONSTANTS ----------
GENERIC_ACCESS = "00001800-0000-1000-8000-00805f9b34fb"
GENERIC_ATTRIBUTE = "00001801-0000-1000-8000-00805f9b34fb"
DEVICE_INFO = "0000180a-0000-1000-8000-00805f9b34fb"
HID_SERVICE = "00001812-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"

# ---------- WEB BLUETOOTH COMPONENT ----------
def web_bt_component():
    return f"""
    <div id="bt-status" style="margin-bottom:10px;">🔍 Click 'Scan' to connect</div>
    <button id="scan-btn" onclick="scan()">🔍 Scan for Devices</button>
    <button id="disconnect-btn" onclick="disconnect()" style="display:none;">🔌 Disconnect</button>
    <div id="device-info" style="margin-top:10px;"></div>
    <div id="services-info" style="margin-top:10px;"></div>
    <div id="cmd-log" style="margin-top:10px; background:#f4f4f4; padding:5px; border-radius:5px; max-height:200px; overflow-y:auto;"></div>

    <script>
        const GENERIC_ACCESS = "{GENERIC_ACCESS}";
        const GENERIC_ATTRIBUTE = "{GENERIC_ATTRIBUTE}";
        const DEVICE_INFO = "{DEVICE_INFO}";
        const HID_SERVICE = "{HID_SERVICE}";
        const BATTERY_SERVICE = "{BATTERY_SERVICE}";

        let device = null, server = null, charMap = {{}}, selectedCharUUID = null;

        function updateParent(data) {{
            window.parent.postMessage({{ type: 'bt_update', data }}, '*');
        }}

        function log(msg) {{
            const el = document.getElementById('cmd-log');
            el.innerHTML += msg + '<br>';
            el.scrollTop = el.scrollHeight;
        }}

        function updateStatus(msg) {{
            document.getElementById('bt-status').innerText = msg;
            updateParent({{ bt_status: msg }});
        }}

        async function scan() {{
            if (!navigator.bluetooth) {{
                alert('❌ Web Bluetooth not supported. Please use Chrome or Edge.');
                return;
            }}
            try {{
                document.getElementById('scan-btn').disabled = true;
                updateStatus('🔍 Scanning...');
                
                device = await navigator.bluetooth.requestDevice({{
                    filters: [{{ services: [GENERIC_ACCESS] }}],
                    optionalServices: [GENERIC_ACCESS, GENERIC_ATTRIBUTE, DEVICE_INFO, HID_SERVICE, BATTERY_SERVICE]
                }});
                
                if (device) {{
                    server = await device.gatt.connect();
                    updateStatus('✅ Connected to ' + device.name);
                    updateParent({{ device_name: device.name, connected: 'true' }});

                    const services = await server.getPrimaryServices();
                    let svcHtml = '<h4>📋 Services</h4><ul>';
                    let svcJson = {{}};
                    for (let svc of services) {{
                        const uuid = svc.uuid;
                        svcHtml += `<li><strong>${{uuid}}</strong><ul>`;
                        svcJson[uuid] = {{ characteristics: [] }};
                        const chars = await svc.getCharacteristics();
                        for (let ch of chars) {{
                            charMap[ch.uuid] = ch;
                            svcHtml += `<li>${{ch.uuid}} (${{ch.properties.join(', ')}})</li>`;
                            svcJson[uuid].characteristics.push({{ uuid: ch.uuid, properties: ch.properties }});
                        }}
                        svcHtml += `</ul></li>`;
                    }}
                    svcHtml += '</ul>';
                    document.getElementById('services-info').innerHTML = svcHtml;
                    updateParent({{ services: JSON.stringify(svcJson) }});

                    document.getElementById('scan-btn').style.display = 'none';
                    document.getElementById('disconnect-btn').style.display = 'inline';
                    document.getElementById('device-info').innerHTML = `✅ Connected to: ${{device.name}}`;
                }}
            }} catch (err) {{
                if (err.message && err.message.includes('cancelled')) {{
                    alert('⚠️ You cancelled the device selection. Click "Scan" again to try.');
                    updateStatus('⚠️ Selection cancelled – try again');
                }} else {{
                    alert('❌ Error: ' + err.message);
                    updateStatus('❌ Error: ' + err.message);
                }}
            }} finally {{
                document.getElementById('scan-btn').disabled = false;
            }}
        }}

        async function disconnect() {{
            if (server) {{
                try {{ await server.disconnect(); }} catch(e) {{}}
            }}
            device = null; server = null; charMap = {{}};
            document.getElementById('disconnect-btn').style.display = 'none';
            document.getElementById('scan-btn').style.display = 'inline';
            document.getElementById('device-info').innerHTML = '';
            document.getElementById('services-info').innerHTML = '';
            updateStatus('🔌 Disconnected');
            updateParent({{ device_name: null, connected: 'false', services: null }});
        }}

        // This function is called from Python
        window.sendCommand = async function(data) {{
            if (!selectedCharUUID) {{ alert('⚠️ Select a characteristic first.'); return; }}
            if (!server) {{ alert('⚠️ Not connected.'); return; }}
            try {{
                const char = charMap[selectedCharUUID];
                if (!char) {{ alert('⚠️ Characteristic not found.'); return; }}
                let bytes;
                if (typeof data === 'string') {{
                    if (data.startsWith('0x')) {{
                        const hex = data.slice(2);
                        if (hex.length % 2 !== 0) {{ alert('⚠️ Hex string must have even length'); return; }}
                        bytes = new Uint8Array(hex.match(/.{{1,2}}/g).map(b => parseInt(b, 16))).buffer;
                    }} else {{
                        bytes = new TextEncoder().encode(data);
                    }}
                }}
                await char.writeValue(bytes);
                log(`✅ Sent: ${{data}}`);
                let hist = [];
                try {{ hist = JSON.parse(new URL(window.parent.location.href).searchParams.get('history') || '[]'); }} catch(e) {{}}
                hist.push({{ time: new Date().toLocaleTimeString(), data }});
                updateParent({{ history: JSON.stringify(hist) }});
            }} catch (e) {{
                alert('❌ Send error: ' + e.message);
            }}
        }};

        // Restore state on load
        (function() {{
            const parentUrl = new URL(window.parent.location.href);
            const connected = parentUrl.searchParams.get('connected') === 'true';
            const name = parentUrl.searchParams.get('device_name');
            if (connected && name) {{
                document.getElementById('device-info').innerHTML = `✅ Connected to: ${{name}}`;
                document.getElementById('scan-btn').style.display = 'none';
                document.getElementById('disconnect-btn').style.display = 'inline';
                updateStatus('✅ Connected to ' + name);
            }}
            const svc = parentUrl.searchParams.get('services');
            if (svc) {{
                try {{
                    const data = JSON.parse(svc);
                    let html = '<h4>📋 Services</h4><ul>';
                    for (let [uuid, info] of Object.entries(data)) {{
                        html += `<li><strong>${{uuid}}</strong><ul>`;
                        for (let ch of info.characteristics) {{
                            html += `<li>${{ch.uuid}} (${{ch.properties.join(', ')}})</li>`;
                        }}
                        html += `</ul></li>`;
                    }}
                    html += '</ul>';
                    document.getElementById('services-info').innerHTML = html;
                }} catch(e) {{}}
            }}
            const sel = parentUrl.searchParams.get('selected_char');
            if (sel) selectedCharUUID = sel;
        }})();
    </script>
    """

# ---------- MAIN UI ----------
st.title("📺 G Remote Universal")
st.markdown("Control any Bluetooth TV using Web Bluetooth (Chrome/Edge).")

with st.sidebar:
    st.header("🔗 Connection")
    st.components.v1.html(web_bt_component(), height=450, scrolling=True)
    st.divider()
    st.info("💡 **Correct procedure:**\n\n"
            "1. **On your TV:** go to **Settings → Bluetooth** and make sure it is **discoverable** (do NOT start a scan from the TV).\n"
            "2. **In the app:** click **Scan** – your computer will search for devices.\n"
            "3. **Select your TV** from the list (look for its model name).\n"
            "4. The TV will ask to confirm pairing – accept it.\n\n"
            "**The list you see on the TV screen (like 'ios') is the TV scanning for other devices – ignore it.**")
    st.warning("📌 **Already paired with another remote?**\n\n"
               "You can still connect this app as a second remote. Most TVs support multiple Bluetooth connections simultaneously.")

col1, col2 = st.columns([2,1])

with col1:
    params = st.query_params
    connected = params.get("connected", "false") == "true"
    device_name = params.get("device_name")
    services_json = params.get("services")
    selected_char = params.get("selected_char")
    history_json = params.get("history", "[]")

    if connected and device_name:
        st.session_state.is_connected = True
        st.session_state.device_name = device_name
        if services_json:
            try: st.session_state.services = json.loads(services_json)
            except: pass
        if selected_char:
            st.session_state.selected_char = selected_char
    else:
        st.session_state.is_connected = False
        st.session_state.device_name = None

    if st.session_state.is_connected:
        st.subheader(f"📟 Remote – {st.session_state.device_name}")
        if st.session_state.services:
            services = list(st.session_state.services.keys())
            if services:
                sel_svc = st.selectbox("Service", services, format_func=lambda u: u[:8])
                if sel_svc:
                    chars = st.session_state.services[sel_svc]["characteristics"]
                    if chars:
                        char_opts = [c["uuid"] for c in chars]
                        sel_char_idx = st.selectbox("Characteristic", range(len(chars)), format_func=lambda i: char_opts[i][:8])
                        st.session_state.selected_char = chars[sel_char_idx]["uuid"]
                        st.query_params["selected_char"] = st.session_state.selected_char
                        st.success(f"Selected: {st.session_state.selected_char}")

        if st.session_state.selected_char:
            st.markdown("#### 🎮 Presets")
            presets = {
                "▶ Play": "0x01", "⏸ Pause": "0x02", "⏹ Stop": "0x03",
                "⏭ Next": "0x04", "⏮ Prev": "0x05",
                "🔊 Vol+": "0x06", "🔉 Vol-": "0x07", "🔇 Mute": "0x08",
                "CH+": "0x09", "CH-": "0x0a",
                "0":"0x30","1":"0x31","2":"0x32","3":"0x33","4":"0x34",
                "5":"0x35","6":"0x36","7":"0x37","8":"0x38","9":"0x39"
            }
            keys = list(presets.keys())
            for i in range(0, len(keys), 4):
                cols = st.columns(4)
                for j, k in enumerate(keys[i:i+4]):
                    with cols[j]:
                        if st.button(k, key=f"preset_{k}"):
                            st.components.v1.html(f"""
                            <script>
                            var iframe = window.parent.document.querySelector('iframe');
                            if (iframe && iframe.contentWindow) {{
                                iframe.contentWindow.sendCommand("{presets[k]}");
                            }}
                            </script>
                            """, height=0)
                            st.rerun()

            st.markdown("#### ✏️ Custom Command")
            custom = st.text_input("Data (text or hex like 0x0102)")
            if st.button("Send Custom") and custom:
                st.components.v1.html(f"""
                <script>
                var iframe = window.parent.document.querySelector('iframe');
                if (iframe && iframe.contentWindow) {{
                    iframe.contentWindow.sendCommand("{custom}");
                }}
                </script>
                """, height=0)
                st.rerun()

        try:
            history = json.loads(history_json)
            if history:
                st.markdown("#### 📜 Command History")
                for entry in history[-10:]:
                    st.text(f"[{entry['time']}] {entry['data']}")
        except: pass
    else:
        st.info("🔌 Click **'Scan for Devices'** in the sidebar to connect to your TV.")
        st.markdown("""
        ### ℹ️ How to pair (correct way)
        1. **On the TV:** go to **Settings → Bluetooth** and **make it discoverable** (usually it's already visible; if not, select "Add device" or "Pair new device").
        2. **Do NOT start a scan from the TV** – that only shows nearby phones, not the TV itself.
        3. **On your computer:** click the **Scan** button in the app.
        4. A browser picker appears showing all nearby Bluetooth devices.
        5. **Select your TV** from that list (it will show its model name).
        6. The TV will ask to confirm pairing – accept it.
        7. You are now connected and can send commands.

        ### 🔄 Already paired with another remote?
        - You can connect this app **without disconnecting** the original remote.
        - Most modern TVs support multiple simultaneous Bluetooth connections.
        - Just follow the steps above – the TV will allow a new pairing.
        """)

with col2:
    st.subheader("📋 Quick Guide")
    st.markdown("""
    - **Browser:** Chrome 56+, Edge 79+
    - **TV must support Bluetooth LE (BLE)**
    - **Common HID service:**  
      `00001812-0000-1000-8000-00805f9b34fb`  
      **Report characteristic:**  
      `00002a4d-0000-1000-8000-00805f9b34fb`
    - The preset commands send standard HID key codes (0x01 = Play, 0x02 = Pause, etc.)
    - If the TV doesn't respond, try the **HID service** and the **Report** characteristic.
    - **Troubleshooting:**  
      - Refresh the page if the picker doesn't appear.  
      - Ensure no other Bluetooth app is using the device.
    """)

st.divider()
st.caption("G Remote Universal – Web Bluetooth Edition. Works on Streamlit Cloud!")
