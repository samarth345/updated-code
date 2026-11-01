import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import os
import time
from google import genai
import json
import threading
import uuid
import paho.mqtt.client as mqtt
import io
import html
import math
import re
import copy
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ------------------------------------------------------------------------------
# MATH UTILITY FIX
# ------------------------------------------------------------------------------
def fact(n):
    result = 1
    for i in range(1, n + 1):
        result *= i
        print(result)
    return result

# ------------------------------------------------------------------------------
# 1. CONFIGURATION & CIRCUIT DATABASE (RECTIFIERS & DIGITAL CIRCUITS)
# ------------------------------------------------------------------------------
APP_NAME = "AI-Based Electronic Circuit Tester"
APP_VERSION = "2.4.0"
AUTHOR = "Final Year B.Tech Project"

CIRCUIT_DATABASE = {
    "Rectifiers": {
        "Half Wave Rectifier": {
            "description": "Converts AC to DC by passing only one half-cycle of the AC supply.",
            "components": "12V AC Transformer, 1N4007 Diode (D1), 1kΩ Load Resistor (RL), 100µF Filter Capacitor (C1)",
            "exp_input_v": 12.0, "exp_output_v": 5.4, "exp_input_i": 0.5, "exp_output_i": 0.45,
            "exp_eff": 40.6, "exp_ripple": 121.0, "formula_eff": "Eff = (P_dc / P_ac) * 100",
            "diagram": "AC Source -> Diode (D1) -> Load Resistor (RL) -> Ground",
            "probes": [
                {"step": 1, "name": "Input Probe", "loc": "Across AC Secondary Transformer Winding"},
                {"step": 2, "name": "Output Probe", "loc": "Across Load Resistor (RL)"},
                {"step": 3, "name": "Current Probe", "loc": "In Series with Diode D1 Anode"}
            ]
        },
        "Full Wave Rectifier (Center Tap)": {
            "description": "Converts both AC half-cycles using a center-tapped transformer and 2 diodes.",
            "components": "12-0-12V Center-Tap Transformer, 2x 1N4007 Diodes (D1, D2), 1kΩ Load Resistor (RL), 470µF Filter Capacitor (C1)",
            "exp_input_v": 12.0, "exp_output_v": 10.8, "exp_input_i": 0.8, "exp_output_i": 0.75,
            "exp_eff": 81.2, "exp_ripple": 48.0, "formula_eff": "Eff = (P_dc / P_ac) * 100",
            "diagram": "Center Tap Transformer -> Diodes (D1, D2) -> Load (RL) -> Center Tap Return",
            "probes": [
                {"step": 1, "name": "Input Probe", "loc": "Across Upper Secondary Winding to Ground"},
                {"step": 2, "name": "Output Probe", "loc": "Across Load Resistor (RL)"},
                {"step": 3, "name": "Current Probe", "loc": "In Series with Center Tap Ground Line"}
            ]
        },
        "Bridge Rectifier": {
            "description": "Uses four diodes in a bridge arrangement to achieve full-wave rectification without center-tap.",
            "components": "12V AC Transformer, Bridge Rectifier IC (1B4B42 / 4x 1N4007), 1kΩ Load Resistor (RL), 1000µF Filter Capacitor (C1)",
            "exp_input_v": 12.0, "exp_output_v": 10.1, "exp_input_i": 1.0, "exp_output_i": 0.95,
            "exp_eff": 81.2, "exp_ripple": 48.0, "formula_eff": "V_dc = (2 * V_peak) / pi",
            "diagram": "AC Terminals -> Bridge Diodes (D1-D4) -> Filter Cap -> Load Resistor",
            "probes": [
                {"step": 1, "name": "Input Probe", "loc": "Across Bridge AC Input Terminals"},
                {"step": 2, "name": "Output Probe", "loc": "Across DC Positive and Ground Output Rails"},
                {"step": 3, "name": "Current Probe", "loc": "In Series with Positive Output Terminal"}
            ]
        }
    },
    "Digital Circuits": {
        "AND Gate": {
            "type": "logic_gate", "sub_type": "AND", "inputs": ["A", "B"], "outputs": ["Y"],
            "description": "Basic 2-input AND gate. Output is HIGH only if both inputs are HIGH.",
            "diagram": "Inputs A, B -> [ AND Gate ] -> Output Y = A & B",
            "probes": [{"step": 1, "name": "Input A", "loc": "Pin 1"}, {"step": 2, "name": "Input B", "loc": "Pin 2"}, {"step": 3, "name": "Output Y", "loc": "Pin 3"}]
        },
        "NAND Gate": {
            "type": "logic_gate", "sub_type": "NAND", "inputs": ["A", "B"], "outputs": ["Y"],
            "description": "Universal 2-input NAND gate. Output is LOW only if both inputs are HIGH.",
            "diagram": "Inputs A, B -> [ NAND Gate ] -> Output Y = ~(A & B)",
            "probes": [{"step": 1, "name": "Input A", "loc": "Pin 1"}, {"step": 2, "name": "Input B", "loc": "Pin 2"}, {"step": 3, "name": "Output Y", "loc": "Pin 3"}]
        },
        "OR Gate": {
            "type": "logic_gate", "sub_type": "OR", "inputs": ["A", "B"], "outputs": ["Y"],
            "description": "Basic 2-input OR gate. Output is HIGH if at least one input is HIGH.",
            "diagram": "Inputs A, B -> [ OR Gate ] -> Output Y = A | B",
            "probes": [{"step": 1, "name": "Input A", "loc": "Pin 1"}, {"step": 2, "name": "Input B", "loc": "Pin 2"}, {"step": 3, "name": "Output Y", "loc": "Pin 3"}]
        },
        "NOR Gate": {
            "type": "logic_gate", "sub_type": "NOR", "inputs": ["A", "B"], "outputs": ["Y"],
            "description": "Universal 2-input NOR gate. Output is HIGH only if both inputs are LOW.",
            "diagram": "Inputs A, B -> [ NOR Gate ] -> Output Y = ~(A | B)",
            "probes": [{"step": 1, "name": "Input A", "loc": "Pin 1"}, {"step": 2, "name": "Input B", "loc": "Pin 2"}, {"step": 3, "name": "Output Y", "loc": "Pin 3"}]
        },
        "XOR Gate": {
            "type": "logic_gate", "sub_type": "XOR", "inputs": ["A", "B"], "outputs": ["Y"],
            "description": "Exclusive-OR gate. Output is HIGH if inputs are different.",
            "diagram": "Inputs A, B -> [ XOR Gate ] -> Output Y = A ^ B",
            "probes": [{"step": 1, "name": "Input A", "loc": "Pin 1"}, {"step": 2, "name": "Input B", "loc": "Pin 2"}, {"step": 3, "name": "Output Y", "loc": "Pin 3"}]
        },
        "XNOR Gate": {
            "type": "logic_gate", "sub_type": "XNOR", "inputs": ["A", "B"], "outputs": ["Y"],
            "description": "Exclusive-NOR gate. Output is HIGH if inputs are identical.",
            "diagram": "Inputs A, B -> [ XNOR Gate ] -> Output Y = ~(A ^ B)",
            "probes": [{"step": 1, "name": "Input A", "loc": "Pin 1"}, {"step": 2, "name": "Input B", "loc": "Pin 2"}, {"step": 3, "name": "Output Y", "loc": "Pin 3"}]
        },
        "NOT Gate": {
            "type": "logic_gate", "sub_type": "NOT", "inputs": ["A"], "outputs": ["Y"],
            "description": "Inverter gate. Output is the logical negation of the input.",
            "diagram": "Input A -> [ NOT Gate ] -> Output Y = ~A",
            "probes": [{"step": 1, "name": "Input A", "loc": "Pin 1"}, {"step": 2, "name": "Output Y", "loc": "Pin 2"}]
        },
        "Binary-to-Gray Converter": {
            "type": "code_converter", "sub_type": "bin_to_gray", "inputs": ["configurable"], "outputs": ["configurable"],
            "description": "Converts binary code to Gray code (minimizing single-bit transition errors). Supports 2-bit, 3-bit, and 4-bit configurations.",
            "diagram": "Binary Bits (Bn...B0) -> [ XOR Network ] -> Gray Bits (Gn...G0)",
            "probes": [{"step": 1, "name": "Binary Inputs", "loc": "Bus A"}, {"step": 2, "name": "Gray Outputs", "loc": "Bus B"}]
        },
        "Gray-to-Binary Converter": {
            "type": "code_converter", "sub_type": "gray_to_bin", "inputs": ["configurable"], "outputs": ["configurable"],
            "description": "Converts Gray code back to standard binary code. Supports 2-bit, 3-bit, and 4-bit configurations.",
            "diagram": "Gray Bits (Gn...G0) -> [ Cumulative XOR ] -> Binary Bits (Bn...B0)",
            "probes": [{"step": 1, "name": "Gray Inputs", "loc": "Bus A"}, {"step": 2, "name": "Binary Outputs", "loc": "Bus B"}]
        },
        "Half Adder": {
            "type": "arithmetic", "sub_type": "half_adder", "inputs": ["A", "B"], "outputs": ["Sum", "Carry"],
            "description": "Adds two 1-bit binary numbers producing Sum and Carry outputs.",
            "diagram": "Inputs A, B -> [ Half Adder ] -> Sum (A^B), Carry (A & B)",
            "probes": [{"step": 1, "name": "Input A", "loc": "Pin A"}, {"step": 2, "name": "Input B", "loc": "Pin B"}, {"step": 3, "name": "Sum/Carry Outputs", "loc": "Pins S, C"}]
        },
        "Full Adder": {
            "type": "arithmetic", "sub_type": "full_adder", "inputs": ["A", "B", "Cin"], "outputs": ["Sum", "Carry-out"],
            "description": "Adds three 1-bit binary numbers including carry-in.",
            "diagram": "Inputs A, B, Cin -> [ Full Adder ] -> Sum, Carry-out",
            "probes": [{"step": 1, "name": "Inputs A, B, Cin", "loc": "Pins A, B, Cin"}, {"step": 2, "name": "Outputs", "loc": "Pins Sum, Cout"}]
        },
        "Half Subtractor": {
            "type": "arithmetic", "sub_type": "half_subtractor", "inputs": ["A", "B"], "outputs": ["Difference", "Borrow"],
            "description": "Subtracts one bit from another producing Difference and Borrow.",
            "diagram": "Inputs A, B -> [ Half Subtractor ] -> Difference (A^B), Borrow (~A & B)",
            "probes": [{"step": 1, "name": "Inputs A, B", "loc": "Pins A, B"}, {"step": 2, "name": "Outputs", "loc": "Pins Diff, Borrow"}]
        },
        "Full Subtractor": {
            "type": "arithmetic", "sub_type": "full_subtractor", "inputs": ["A", "B", "Bin"], "outputs": ["Difference", "Borrow-out"],
            "description": "Subtracts two bits and borrow-in producing Difference and Borrow-out.",
            "diagram": "Inputs A, B, Bin -> [ Full Subtractor ] -> Difference, Borrow-out",
            "probes": [{"step": 1, "name": "Inputs A, B, Bin", "loc": "Pins A, B, Bin"}, {"step": 2, "name": "Outputs", "loc": "Pins Diff, Bout"}]
        },
        "2:1 Multiplexer": {
            "type": "multiplexer", "sub_type": "mux_2_1", "inputs": ["S", "I0", "I1"], "outputs": ["Y"],
            "description": "Mandatory 2:1 MUX routing data input I0 or I1 to output Y based on select S. Boolean equation: Y = (~S & I0) | (S & I1).",
            "diagram": "Select S, Data I0, I1 -> [ 2:1 MUX ] -> Output Y = (~S & I0) | (S & I1)",
            "probes": [{"step": 1, "name": "Select S & Data I0, I1", "loc": "Pins S, I0, I1"}, {"step": 2, "name": "Output Y", "loc": "Pin Y"}]
        }
    }
}

# ==============================================================================
# MQTT COMMUNICATION MODULE (st.cache_resource-BACKED SINGLETON MANAGER)
# ==============================================================================
#
# ROOT CAUSE OF THE ORIGINAL BUG:
# Streamlit does not "import" this script once like a normal Python module --
# it re-executes the ENTIRE file, top to bottom, on every single rerun
# (every button click, every widget interaction, every st.rerun()). That
# means plain module-level globals such as the old
#     _mqtt_client = None
#     _mqtt_started = False
#     _latest_mqtt_packet = None
#     _mqtt_status = "Disconnected"
#     _mqtt_packet_count = 0
# were being RESET TO THEIR DEFAULTS on every rerun. Because _mqtt_started
# flipped back to False each time, initialize_mqtt() kept thinking no client
# existed yet and spun up a BRAND NEW mqtt.Client + a brand new loop_start()
# background thread on every rerun -- while the client(s) from earlier
# reruns kept running in the background too (never stopped), silently
# continuing to receive packets into globals that the current script
# execution can no longer see. The UI, reading the freshly-reset
# "_latest_mqtt_packet = None" of *this* rerun, showed "WAITING FOR DATA"
# even though a packet had already arrived (into an orphaned older
# instance's state).
#
# THE FIX: move all MQTT state (client, lock, latest packet, counters,
# connection status) into a single object that is created ONCE per Python
# process -- not once per script run -- using st.cache_resource. Every
# read and write goes through that one persistent object, so reruns can
# no longer wipe out or duplicate MQTT state.
# ==============================================================================
MQTT_BROKER_HOST = "broker.hivemq.com"
MQTT_BROKER_PORT = 1883
MQTT_TOPIC = "circuit/tester"
MQTT_KEEPALIVE = 60

# ESP32 is considered ONLINE only while valid telemetry keeps arriving. If no
# valid packet has arrived for this many seconds, the ESP32 is shown OFFLINE.
# (Independent of the MQTT broker connection state.) Easy to change.
ESP32_OFFLINE_TIMEOUT = 10

# Fallback transport: MQTT-over-WebSockets. Used automatically if plain
# TCP on MQTT_BROKER_PORT doesn't connect within a few seconds -- see
# _mqtt_fallback_watchdog(). Port 8000 is HiveMQ's public unencrypted
# WebSocket listener.
MQTT_WS_PORT = 8000
MQTT_WS_PATH = "/mqtt"

# Mandatory fields (after alias normalization) required for a packet to be
# considered valid for diagnosis.
MQTT_REQUIRED_FIELDS = ["input_voltage", "output_voltage", "input_current", "output_current"]

# Canonical field name -> accepted raw JSON key aliases.
MQTT_FIELD_ALIASES = {
    "input_voltage":  ["input_voltage", "input_v"],
    "output_voltage": ["output_voltage", "output_v"],
    "input_current":  ["input_current", "input_i"],
    "output_current": ["output_current", "output_i"],
    "frequency":      ["frequency", "freq"],
    "temperature":    ["temperature", "temp"],
}


class MQTTManager:
    """Thread-safe, process-persistent MQTT state container. Exactly one
    instance of this class exists for the life of the Streamlit process
    (see get_mqtt_manager() below)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.client = None
        self.client_id = f"nexus_streamlit_{uuid.uuid4().hex[:12]}"
        self.started = False

        # Pure MQTT broker CONNECTION state -- set only by on_connect/on_disconnect.
        self.connection_status = "Disconnected"   # "Connected" | "Disconnected"

        # Pure DATA state -- set only by on_message. This is a DIFFERENT
        # concept from connection_status: you can be connected with no
        # data yet, or (briefly) still holding good data while reconnecting.
        self.latest_packet = None        # normalized dict, or None
        self.latest_raw_packet = None    # raw payload dict, for debugging
        self.packet_count = 0
        self.last_packet_time = None
        self.last_packet_topic = None

        # Diagnostics: WHY it's disconnected, if it is. This is what was
        # previously invisible -- print(...) only reaches server-side
        # logs, never the Streamlit UI itself, so a genuine connection
        # failure (e.g. an outbound port being blocked by the hosting
        # platform) looked identical to "no data yet" with no way to
        # tell them apart from inside the app.
        self.last_error = None
        self.transport = "tcp"          # "tcp" | "websockets"
        self.connect_attempt_time = None
        self.fallback_attempted = False


@st.cache_resource
def get_mqtt_manager():
    """Returns the single MQTTManager instance for this process. Because
    it's wrapped in st.cache_resource, Streamlit hands back the SAME
    object on every rerun instead of constructing a fresh one."""
    return MQTTManager()


def normalize_mqtt_packet(raw):
    """
    Normalize a raw MQTT JSON payload into the canonical field set
    (input_voltage, output_voltage, input_current, output_current,
    frequency, temperature), accepting both the full field names and the
    short aliases (input_v/output_v/input_i/output_i) already used
    elsewhere in this app.

    Returns None if `raw` isn't a dict or is missing any mandatory
    diagnostic field. Optional fields (frequency/temperature) default to
    0.0 rather than causing rejection.
    """
    if not isinstance(raw, dict):
        return None

    normalized = {}
    for canonical, aliases in MQTT_FIELD_ALIASES.items():
        for key in aliases:
            if key in raw and raw[key] is not None:
                try:
                    normalized[canonical] = float(raw[key])
                except (TypeError, ValueError):
                    continue
                break

    if not all(field in normalized for field in MQTT_REQUIRED_FIELDS):
        return None

    normalized.setdefault("frequency", 0.0)
    normalized.setdefault("temperature", 0.0)
    return normalized


# ------------------------------------------------------------------------
# CONNACK reason lookup for readable error messages (v3.1.1 codes; Paho
# also accepts these for v5 ints in VERSION1 compatibility mode).
# ------------------------------------------------------------------------
MQTT_CONNACK_REASONS = {
    1: "Connection refused - incorrect protocol version",
    2: "Connection refused - invalid client identifier",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad username or password",
    5: "Connection refused - not authorised",
}

def _is_int_like(value):
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


# ------------------------------------------------------------------------
# Paho callbacks. These run on the MQTT network thread -- they must ONLY
# touch the thread-safe manager, never Streamlit UI calls.
# ------------------------------------------------------------------------
def on_connect(client, userdata, flags, rc, properties=None):
    manager = userdata
    # rc may be an int (VERSION1 API) or a ReasonCode-like object; both
    # compare equal to 0 on success, and str()/int() give a readable value
    # for the "connection refused" reasons either way.
    if rc == 0:
        print("MQTT CONNECTED", flush=True)
        with manager.lock:
            manager.connection_status = "Connected"
            manager.last_error = None
        client.subscribe(MQTT_TOPIC)
        print(f"MQTT SUBSCRIBED [{MQTT_TOPIC}]", flush=True)
    else:
        reason = MQTT_CONNACK_REASONS.get(int(rc), f"Unknown reason code {rc}") if _is_int_like(rc) else str(rc)
        print(f"MQTT CONNECTION ERROR: {rc} ({reason})", flush=True)
        with manager.lock:
            manager.connection_status = "Disconnected"
            manager.last_error = f"Broker refused connection: {reason}"

def on_disconnect(client, userdata, rc, properties=None):
    manager = userdata
    print(f"MQTT DISCONNECTED: {rc}", flush=True)
    with manager.lock:
        manager.connection_status = "Disconnected"
        if rc != 0:
            manager.last_error = f"Disconnected unexpectedly (rc={rc}). Broker/network dropped the connection."

def on_message(client, userdata, msg):
    manager = userdata
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        normalized = normalize_mqtt_packet(data)

        if normalized is not None:
            with manager.lock:
                manager.latest_packet = normalized
                manager.latest_raw_packet = data if isinstance(data, dict) else None
                manager.packet_count += 1
                manager.last_packet_time = datetime.datetime.now()
                manager.last_packet_topic = msg.topic
            print(f"MQTT MESSAGE [{msg.topic}]: {payload_str}", flush=True)
        else:
            # Malformed/incomplete payload: log it, but deliberately do
            # NOT touch manager.latest_packet -- a previously received
            # valid packet must never be wiped out by a bad payload.
            print(f"MQTT MESSAGE IGNORED (missing required fields) [{msg.topic}]: {payload_str}", flush=True)
    except json.JSONDecodeError as e:
        print(f"MQTT JSON ERROR: {e}", flush=True)
    except Exception as e:
        print(f"MQTT MESSAGE ERROR: {e}", flush=True)


def initialize_mqtt():
    """
    Singleton initializer for the MQTT client, backed by the persistent
    MQTTManager. Guarantees only one client and one loop_start() thread
    ever exist for the life of the process, no matter how many times
    Streamlit reruns this script. Non-blocking: reconnection is handled
    natively by Paho's loop_start() thread + reconnect_delay_set().

    Also starts a background watchdog that automatically retries over
    MQTT-over-WebSockets if plain TCP hasn't connected within a few
    seconds -- see _mqtt_fallback_watchdog() for why this matters.
    """
    manager = get_mqtt_manager()

    with manager.lock:
        if manager.started and manager.client is not None:
            return
        manager.started = True

    print("MQTT CONNECTING (tcp)", flush=True)
    try:
        client = _create_mqtt_client(manager, transport="tcp")
        _connect_client(client, "tcp")

        with manager.lock:
            manager.client = client
            manager.transport = "tcp"
            manager.connect_attempt_time = datetime.datetime.now()

        watchdog = threading.Thread(target=_mqtt_fallback_watchdog, args=(manager,), daemon=True)
        watchdog.start()
    except Exception as e:
        print(f"MQTT CONNECTION ERROR: {e}", flush=True)
        with manager.lock:
            manager.connection_status = "Disconnected"
            manager.last_error = f"Failed to start MQTT client: {e}"
            manager.started = False


def _create_mqtt_client(manager, transport="tcp"):
    try:
        # Compatible with Paho MQTT v2.x
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=manager.client_id, transport=transport)
    except AttributeError:
        # Fallback for Paho MQTT v1.x
        client = mqtt.Client(client_id=manager.client_id, transport=transport)

    if transport == "websockets":
        client.ws_set_options(path=MQTT_WS_PATH)

    # Bind our persistent manager as the callback userdata so on_connect/
    # on_disconnect/on_message can update it without touching globals.
    client.user_data_set(manager)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    if hasattr(client, "reconnect_delay_set"):
        client.reconnect_delay_set(min_delay=1, max_delay=10)

    return client


def _connect_client(client, transport):
    port = MQTT_BROKER_PORT if transport == "tcp" else MQTT_WS_PORT
    client.connect_async(MQTT_BROKER_HOST, port, MQTT_KEEPALIVE)
    client.loop_start()


def _mqtt_fallback_watchdog(manager, timeout_seconds=8):
    """
    Runs once per process on a background thread. If the initial plain-TCP
    MQTT connection (port 1883) hasn't succeeded within `timeout_seconds`,
    automatically retries over MQTT-over-WebSockets (port 8000).

    WHY THIS MATTERS: raw TCP on a non-standard port like 1883 is exactly
    the kind of outbound connection many hosting platforms (Streamlit
    Community Cloud, various container/PaaS platforms, restrictive
    corporate networks) silently block or drop -- Paho just keeps retrying
    forever with no error raised, which from inside the app looks
    identical to "the code never connects". If you deployed this app to a
    platform like that, this is almost certainly why MQTT STATUS shows
    DISCONNECTED even though your ESP32 is publishing fine. WebSockets on
    port 8000 rides over a normal HTTP-style connection and is far less
    likely to be blocked.
    """
    time.sleep(timeout_seconds)
    with manager.lock:
        already_connected = manager.connection_status == "Connected"
        already_tried = manager.fallback_attempted
        old_client = manager.client

    if already_connected or already_tried:
        return

    print(f"MQTT TCP CONNECT TIMED OUT after {timeout_seconds}s -- retrying over WebSockets (port {MQTT_WS_PORT})", flush=True)
    try:
        if old_client is not None:
            try:
                old_client.loop_stop()
                old_client.disconnect()
            except Exception:
                pass

        ws_client = _create_mqtt_client(manager, transport="websockets")
        _connect_client(ws_client, "websockets")

        with manager.lock:
            manager.client = ws_client
            manager.transport = "websockets"
            manager.fallback_attempted = True
            manager.connect_attempt_time = datetime.datetime.now()
            if manager.connection_status != "Connected":
                manager.last_error = (
                    f"Plain TCP MQTT (port {MQTT_BROKER_PORT}) did not connect within "
                    f"{timeout_seconds}s -- likely blocked by the hosting network/firewall. "
                    f"Retrying now over MQTT-over-WebSockets (port {MQTT_WS_PORT})."
                )
    except Exception as e:
        print(f"MQTT WEBSOCKET FALLBACK ERROR: {e}", flush=True)
        with manager.lock:
            manager.fallback_attempted = True
            manager.last_error = f"TCP connect timed out, and WebSocket fallback also failed: {e}"


def get_mqtt_connection_status():
    """Pure broker connection truth: 'Connected' or 'Disconnected'.
    Never conflated with whether a data packet has arrived."""
    manager = get_mqtt_manager()
    with manager.lock:
        return manager.connection_status


def get_mqtt_last_error():
    """Human-readable reason for the current disconnected state, or None
    if connected / not yet known. Surfaced in the UI debug panel since
    print() output alone is invisible once the app is deployed."""
    manager = get_mqtt_manager()
    with manager.lock:
        return manager.last_error


def get_mqtt_transport():
    manager = get_mqtt_manager()
    with manager.lock:
        return manager.transport


def get_mqtt_data_status():
    """Pure data truth: 'Packet Received' or 'Waiting for Data'."""
    manager = get_mqtt_manager()
    with manager.lock:
        return "Packet Received" if manager.latest_packet is not None else "Waiting for Data"


def get_mqtt_status():
    """
    Backward-compatible combined status consumed by the existing UI code:
      'Connected'         -> broker connected AND a valid packet received
      'Waiting for Data'   -> broker connected, no valid packet yet
      'Disconnected'       -> broker not connected
    Connection state and data state are tracked separately internally
    (see get_mqtt_connection_status / get_mqtt_data_status) and only
    combined here for display purposes.
    """
    manager = get_mqtt_manager()
    with manager.lock:
        if manager.connection_status != "Connected":
            return "Disconnected"
        if manager.latest_packet is None:
            return "Waiting for Data"
        return "Connected"


def get_mqtt_packet_count():
    manager = get_mqtt_manager()
    with manager.lock:
        return manager.packet_count


def get_mqtt_last_packet_time():
    manager = get_mqtt_manager()
    with manager.lock:
        return manager.last_packet_time


def get_mqtt_last_topic():
    manager = get_mqtt_manager()
    with manager.lock:
        return manager.last_packet_topic


def get_latest_sensor_packet():
    """Returns a COPY of the latest normalized, validated sensor packet, or
    None if no valid packet has been received yet. Backed by the
    cache_resource-persisted MQTTManager, so a valid packet survives
    Streamlit reruns instead of being reset to None."""
    manager = get_mqtt_manager()
    with manager.lock:
        if manager.latest_packet is None:
            return None
        return dict(manager.latest_packet)


def get_latest_raw_packet():
    """Returns a COPY of the last raw (pre-normalization) packet payload,
    for the debug panel."""
    manager = get_mqtt_manager()
    with manager.lock:
        if manager.latest_raw_packet is None:
            return None
        return dict(manager.latest_raw_packet)

def get_latest_packet_and_time():
    """Atomically returns (copy of latest valid packet or None, its arrival
    datetime or None) so the pair can never be mismatched."""
    manager = get_mqtt_manager()
    with manager.lock:
        if manager.latest_packet is None:
            return None, None
        return dict(manager.latest_packet), manager.last_packet_time


def get_esp32_status():
    """
    ESP32 online state, derived ONLY from the age of the last valid telemetry
    packet (never from the MQTT broker connection state):
      ("ONLINE",  age_seconds)  valid packet within ESP32_OFFLINE_TIMEOUT
      ("OFFLINE", age_seconds)  last valid packet is older than the timeout
      ("WAITING", None)         broker connected, no valid packet received yet
      ("OFFLINE", None)         no valid packet ever and broker not connected
    """
    manager = get_mqtt_manager()
    with manager.lock:
        last_time = manager.last_packet_time
        broker_connected = manager.connection_status == "Connected"
    if last_time is None:
        return ("WAITING", None) if broker_connected else ("OFFLINE", None)
    age = (datetime.datetime.now() - last_time).total_seconds()
    if age <= ESP32_OFFLINE_TIMEOUT:
        return "ONLINE", age
    return "OFFLINE", age


def validate_sensor_packet(raw):
    """Returns the list of required electrical fields that are missing or
    non-finite in `raw`. Empty list == all four measurements present."""
    missing = []
    for field in MQTT_REQUIRED_FIELDS:
        try:
            ok = raw is not None and raw.get(field) is not None and math.isfinite(float(raw[field]))
        except (TypeError, ValueError):
            ok = False
        if not ok:
            missing.append(field)
    return missing

# ------------------------------------------------------------------------------
# DIGITAL CIRCUIT TRUTH TABLE GENERATORS & LOGIC THRESHOLDS
# ------------------------------------------------------------------------------
def classify_digital_voltage(voltage, v_il=0.8, v_ih=2.0):
    """Classifies measured voltage into logic 0, logic 1, or INVALID based on thresholds."""
    try:
        v = float(voltage)
        if not math.isfinite(v):
            return "INVALID"
        if v <= v_il:
            return "0"
        elif v >= v_ih:
            return "1"
        else:
            return "INVALID"
    except (TypeError, ValueError):
        return "INVALID"

def generate_expected_truth_table(circuit_name, width=4):
    """Programmatically generates expected truth tables for all supported digital circuits."""
    ckt = CIRCUIT_DATABASE.get("Digital Circuits", {}).get(circuit_name, {})
    stype = ckt.get("sub_type")
    
    rows = []
    if stype == "AND":
        for a in [0, 1]:
            for b in [0, 1]:
                rows.append({"Inputs": f"A={a}, B={b}", "A": a, "B": b, "Expected Y": a & b})
    elif stype == "NAND":
        for a in [0, 1]:
            for b in [0, 1]:
                rows.append({"Inputs": f"A={a}, B={b}", "A": a, "B": b, "Expected Y": 1 if not (a & b) else 0})
    elif stype == "OR":
        for a in [0, 1]:
            for b in [0, 1]:
                rows.append({"Inputs": f"A={a}, B={b}", "A": a, "B": b, "Expected Y": a | b})
    elif stype == "NOR":
        for a in [0, 1]:
            for b in [0, 1]:
                rows.append({"Inputs": f"A={a}, B={b}", "A": a, "B": b, "Expected Y": 1 if not (a | b) else 0})
    elif stype == "XOR":
        for a in [0, 1]:
            for b in [0, 1]:
                rows.append({"Inputs": f"A={a}, B={b}", "A": a, "B": b, "Expected Y": a ^ b})
    elif stype == "XNOR":
        for a in [0, 1]:
            for b in [0, 1]:
                rows.append({"Inputs": f"A={a}, B={b}", "A": a, "B": b, "Expected Y": 0 if (a ^ b) else 1})
    elif stype == "NOT":
        for a in [0, 1]:
            rows.append({"Inputs": f"A={a}", "A": a, "Expected Y": 0 if a else 1})
    elif stype == "bin_to_gray":
        n = width
        for i in range(2**n):
            b_bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
            g_val = i ^ (i >> 1)
            g_bits = [(g_val >> (n - 1 - k)) & 1 for k in range(n)]
            input_label = "".join(str(b) for b in b_bits)
            row = {"Input": input_label}
            for k in range(n):
                row[f"B{n-1-k}"] = b_bits[k]
            for k in range(n):
                row[f"Expected G{n-1-k}"] = g_bits[k]
            rows.append(row)
    elif stype == "gray_to_bin":
        n = width
        for i in range(2**n):
            g_bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
            b_val = 0
            for k in range(n):
                b_val ^= (i >> k)
            b_bits = [(b_val >> (n - 1 - k)) & 1 for k in range(n)]
            input_label = "".join(str(g) for g in g_bits)
            row = {"Input": input_label}
            for k in range(n):
                row[f"G{n-1-k}"] = g_bits[k]
            for k in range(n):
                row[f"Expected B{n-1-k}"] = b_bits[k]
            rows.append(row)
    elif stype == "half_adder":
        for a in [0, 1]:
            for b in [0, 1]:
                s = a ^ b
                c = a & b
                rows.append({"A": a, "B": b, "Expected Sum": s, "Expected Carry": c})
    elif stype == "full_adder":
        for a in [0, 1]:
            for b in [0, 1]:
                for cin in [0, 1]:
                    s = a ^ b ^ cin
                    cout = (a & b) | (cin & (a ^ b))
                    rows.append({"A": a, "B": b, "Cin": cin, "Expected Sum": s, "Expected Carry-out": cout})
    elif stype == "half_subtractor":
        for a in [0, 1]:
            for b in [0, 1]:
                diff = a ^ b
                borrow = (not a) & b
                rows.append({"A": a, "B": b, "Expected Difference": diff, "Expected Borrow": 1 if borrow else 0})
    elif stype == "full_subtractor":
        for a in [0, 1]:
            for b in [0, 1]:
                for bin_val in [0, 1]:
                    diff = a ^ b ^ bin_val
                    borrow = ((not a) & b) | ((not (a ^ b)) & bin_val)
                    rows.append({"A": a, "B": b, "Bin": bin_val, "Expected Difference": diff, "Expected Borrow-out": 1 if borrow else 0})
    elif stype == "mux_2_1":
        for s in [0, 1]:
            for i0 in [0, 1]:
                for i1 in [0, 1]:
                    y = ((not s) & i0) | (s & i1)
                    rows.append({"S": s, "I0": i0, "I1": i1, "Expected Y": 1 if y else 0})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------
# DIGITAL TESTER HELPERS (cell selection, fresh-measurement capture, analysis)
# ------------------------------------------------------------------------------
def get_digital_table_layout(expected_df):
    """Splits the expected truth table into input columns, output columns and
    output labels using the same rule the digital tester has always used."""
    output_cols = [c for c in expected_df.columns if c.startswith("Expected ") or c in ["Y", "Sum", "Carry", "Carry-out", "Difference", "Borrow", "Borrow-out"]]
    input_cols = [c for c in expected_df.columns if c not in output_cols]
    possible_outputs = [c.replace("Expected ", "") for c in output_cols]
    return input_cols, output_cols, possible_outputs


def get_fresh_output_measurement():
    """Returns (voltage, packet_time, error_message). Only a genuine, recent,
    fully valid telemetry packet yields a voltage; otherwise voltage is None
    and an error message explains why. Never fabricates a zero."""
    packet, packet_time = get_latest_packet_and_time()
    if packet is None or packet_time is None:
        return None, None, "No valid sensor telemetry packet has been received yet."
    age = (datetime.datetime.now() - packet_time).total_seconds()
    if age > ESP32_OFFLINE_TIMEOUT:
        return None, packet_time, f"Latest sensor packet is stale ({age:.1f} s old, limit {ESP32_OFFLINE_TIMEOUT} s). ESP32 appears offline."
    missing = validate_sensor_packet(packet)
    if missing:
        return None, packet_time, "Latest sensor packet is incomplete (missing/invalid: " + ", ".join(missing) + ")."
    try:
        voltage = float(packet.get("output_voltage", packet.get("output_v")))
    except (TypeError, ValueError):
        return None, packet_time, "Latest sensor packet has no usable output voltage."
    if not math.isfinite(voltage):
        return None, packet_time, "Latest sensor packet has a non-finite output voltage."
    return voltage, packet_time, None


def digital_table_signature(expected_df):
    return (len(expected_df), tuple(str(c) for c in expected_df.columns))


def digital_invalidate_analysis(circuit_name):
    """Drops the stored analysis (deterministic result + Gemini report) of one circuit only."""
    st.session_state.digital_analysis.pop(circuit_name, None)


def digital_select_cell(circuit_name, row_idx, out_label):
    """on_click callback for a truth-table cell button: changes only the active destination."""
    st.session_state.digital_selected_cells[circuit_name] = (row_idx, out_label)
    st.session_state.digital_save_notice.pop(circuit_name, None)


def compute_digital_analysis(circuit_name, expected_df, measurements):
    """Deterministic comparison of saved measurements with the expected truth table."""
    input_cols, output_cols, possible_outputs = get_digital_table_layout(expected_df)
    total = len(expected_df) * len(possible_outputs)
    valid = invalid = mismatches = 0
    details = []
    cells = []
    for i in range(len(expected_df)):
        inputs_txt = ", ".join(f"{c}={expected_df.iloc[i][c]}" for c in input_cols)
        for out_l in possible_outputs:
            exp_col = f"Expected {out_l}" if f"Expected {out_l}" in expected_df.columns else out_l
            exp_val = int(expected_df.iloc[i][exp_col])
            m = measurements.get((i, out_l))
            if m is None:
                status_c, v_txt, state_c = "MISSING", "\u2014", "MISSING"
            else:
                try:
                    v_txt = f"{float(m['voltage']):.3f} V"
                except (TypeError, ValueError):
                    v_txt = "N/A"
                if m.get("logic_state") in ("0", "1"):
                    valid += 1
                    state_c = m["logic_state"]
                    if int(state_c) == exp_val:
                        status_c = "MATCH"
                    else:
                        status_c = "MISMATCH"
                        mismatches += 1
                else:
                    invalid += 1
                    state_c, status_c = "INVALID", "INVALID"
            cells.append({"row": i, "inputs": inputs_txt, "output": out_l, "expected": exp_val,
                          "voltage": v_txt, "state": state_c, "status": status_c})
            if status_c != "MATCH":
                details.append({"Row": i, "Inputs": inputs_txt, "Output": out_l, "Expected": exp_val,
                                "Measured V": v_txt, "Measured State": state_c, "Status": status_c})
    missing = total - valid - invalid
    coverage = (valid / total * 100.0) if total > 0 else 0.0
    if total == 0 or missing > 0 or invalid > 0:
        status = "INCOMPLETE"
    elif mismatches > 0:
        status = "FAIL"
    else:
        status = "PASS"
    return {
        "circuit": circuit_name,
        "signature": digital_table_signature(expected_df),
        "det_status": status,
        "coverage_pct": coverage,
        "total_cells": total,
        "valid_cells": valid,
        "correct_matches": valid - mismatches,
        "mismatches": mismatches,
        "missing_cells": missing,
        "invalid_cells": invalid,
        "details": details,
        "cells": cells,
        "thresholds": dict(st.session_state.digital_thresholds),
        "analysed_at": datetime.datetime.now(),
        "gemini_report": None,
        "gemini_status": "NOT_RUN",
        "gemini_error": None,
    }


# ------------------------------------------------------------------------------
# HELPER FUNCTIONS, STATE MANAGEMENT & TEXT-TO-SPEECH (TTS)
# ------------------------------------------------------------------------------
def init_session_state():
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = "Rectifiers"
    if "selected_circuit" not in st.session_state:
        st.session_state.selected_circuit = "Bridge Rectifier"
    if "page" not in st.session_state:
        st.session_state.page = "Home"
    if "last_digital_circuit" not in st.session_state:
        st.session_state.last_digital_circuit = None
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "historical_tests" not in st.session_state:
        st.session_state.historical_tests = []
    if "loaded_once" not in st.session_state:
        st.session_state.loaded_once = False
    if "is_muted" not in st.session_state:
        st.session_state.is_muted = False

    # HOLD / RELEASE snapshot state (UI-only; never touches MQTTManager)
    if "data_hold" not in st.session_state:
        st.session_state.data_hold = False
    # INPUT-ONLY hold: {"input_v", "input_i", "captured_at", "circuit"}.
    # Never contains output voltage/current, frequency or temperature.
    if "held_input_data" not in st.session_state:
        st.session_state.held_input_data = None
    if "hold_timestamp" not in st.session_state:
        st.session_state.hold_timestamp = None
    if "hold_error" not in st.session_state:
        st.session_state.hold_error = None
    # Last successful Gemini analysis (+ the exact snapshot it analysed)
    if "last_gemini_result" not in st.session_state:
        st.session_state.last_gemini_result = None
        
    # Target value session state definitions
    if "target_input_voltage" not in st.session_state:
        st.session_state.target_input_voltage = None
    if "target_output_voltage" not in st.session_state:
        st.session_state.target_output_voltage = None
    if "target_input_current" not in st.session_state:
        st.session_state.target_input_current = None
    if "target_output_current" not in st.session_state:
        st.session_state.target_output_current = None

    # Digital testing state variables
    if "digital_measurements" not in st.session_state:
        st.session_state.digital_measurements = {}
    if "digital_selected_cell" not in st.session_state:
        st.session_state.digital_selected_cell = (0, 0)
    if "digital_bit_width" not in st.session_state:
        st.session_state.digital_bit_width = 4
    if "digital_thresholds" not in st.session_state:
        st.session_state.digital_thresholds = {"v_il": 0.8, "v_ih": 2.0}
    if "digital_selected_cells" not in st.session_state:
        st.session_state.digital_selected_cells = {}
    if "digital_analysis" not in st.session_state:
        st.session_state.digital_analysis = {}
    if "digital_save_notice" not in st.session_state:
        st.session_state.digital_save_notice = {}
    if "digital_table_sigs" not in st.session_state:
        st.session_state.digital_table_sigs = {}
    if "analysis_records" not in st.session_state:
        st.session_state.analysis_records = []
    if "student_details" not in st.session_state:
        st.session_state.student_details = {}
    if "report_state" not in st.session_state:
        st.session_state.report_state = None
    if "report_selected_test" not in st.session_state:
        st.session_state.report_selected_test = None
    if "report_validate_attempted" not in st.session_state:
        st.session_state.report_validate_attempted = False
    # Lab-assistant additions (new keys only - nothing existing is renamed or removed)
    if "gemini_pending" not in st.session_state:
        st.session_state.gemini_pending = None
    if "gemini_notice" not in st.session_state:
        st.session_state.gemini_notice = None
    if "digital_pending" not in st.session_state:
        st.session_state.digital_pending = None
    if "digital_ic_context" not in st.session_state:
        st.session_state.digital_ic_context = {}
    if "pending_speech" not in st.session_state:
        st.session_state.pending_speech = None

    initialize_mqtt()

def get_active_targets(circuit_info):
    target_in_v = st.session_state.target_input_voltage if st.session_state.target_input_voltage is not None else circuit_info.get("exp_input_v", 12.0)
    target_out_v = st.session_state.target_output_voltage if st.session_state.target_output_voltage is not None else circuit_info.get("exp_output_v", 10.0)
    target_in_i = st.session_state.target_input_current if st.session_state.target_input_current is not None else circuit_info.get("exp_input_i", 1.0)
    target_out_i = st.session_state.target_output_current if st.session_state.target_output_current is not None else circuit_info.get("exp_output_i", 0.9)

    return {
        "target_input_voltage": float(target_in_v),
        "target_output_voltage": float(target_out_v),
        "target_input_current": float(target_in_i),
        "target_output_current": float(target_out_i)
    }

def speak_text(text_to_speak):
    if st.session_state.get("is_muted", False):
        st.components.v1.html("""
        <script>
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        </script>
        """, height=0, width=0)
        return

    clean_text = text_to_speak.replace('"', '\\"').replace("'", "\\'").replace('\n', ' ')
    tts_html = f"""
    <script>
    if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
        
        function speakFemale() {{
            var msg = new SpeechSynthesisUtterance("{clean_text}");
            msg.rate = 1.0;
            msg.pitch = 1.1;
            
            var voices = window.speechSynthesis.getVoices();
            var femaleVoice = voices.find(function(voice) {{
                var name = voice.name.toLowerCase();
                return voice.lang.includes('en') && (
                    name.includes('female') || 
                    name.includes('zira') || 
                    name.includes('victoria') || 
                    name.includes('google uk english female') ||
                    name.includes('samantha') ||
                    name.includes('karen')
                );
            }});

            if (femaleVoice) {{
                msg.voice = femaleVoice;
            }}
            
            window.speechSynthesis.speak(msg);
        }}

        if (window.speechSynthesis.getVoices().length === 0) {{
            window.speechSynthesis.onvoiceschanged = speakFemale;
        }} else {{
            speakFemale();
        }}
    }}
    </script>
    """
    st.components.v1.html(tts_html, height=0, width=0)

def is_valid_selection(category, circuit):
    return category in CIRCUIT_DATABASE and circuit in CIRCUIT_DATABASE[category]


def set_active_circuit(category, circuit):
    """Single authoritative writer of the selected category/circuit.
    Returns False (and changes nothing) if the pair is not in CIRCUIT_DATABASE."""
    if not is_valid_selection(category, circuit):
        return False
    changed = (st.session_state.get("selected_category") != category
               or st.session_state.get("selected_circuit") != circuit)
    st.session_state.selected_category = category
    st.session_state.selected_circuit = circuit
    if changed:
        # Rectifier targets belong to one circuit; never carry them over to another.
        st.session_state.target_input_voltage = None
        st.session_state.target_output_voltage = None
        st.session_state.target_input_current = None
        st.session_state.target_output_current = None
    return True


def get_current_circuit_data():
    """Returns the selected circuit's dict, or None if the stored selection is invalid.
    It never silently substitutes another circuit."""
    cat = st.session_state.get("selected_category")
    ckt = st.session_state.get("selected_circuit")
    if is_valid_selection(cat, ckt):
        return CIRCUIT_DATABASE[cat][ckt]
    return None


def ensure_valid_selection():
    """Only called on pages where the user is *choosing* a circuit (Home / Circuit Type).
    Repairs a genuinely invalid stored pair; a valid pair is never touched."""
    cat = st.session_state.get("selected_category")
    ckt = st.session_state.get("selected_circuit")
    if cat not in CIRCUIT_DATABASE:
        cat = "Rectifiers" if "Rectifiers" in CIRCUIT_DATABASE else list(CIRCUIT_DATABASE.keys())[0]
        ckt = None
    if ckt not in CIRCUIT_DATABASE[cat]:
        ckt = "Bridge Rectifier" if (cat == "Rectifiers" and "Bridge Rectifier" in CIRCUIT_DATABASE[cat]) \
            else list(CIRCUIT_DATABASE[cat].keys())[0]
    set_active_circuit(cat, ckt)


def route_for(category, circuit=None):
    """Which testing interface a circuit belongs to (driven by CIRCUIT_DATABASE data, not by name)."""
    info = CIRCUIT_DATABASE.get(category, {}).get(circuit) if circuit else None
    if category == "Digital Circuits" or (info and info.get("type") in
            ("logic_gate", "code_converter", "arithmetic", "multiplexer")):
        return "Digital Circuit Tester"
    return "Configuration"


# ---- navigation callbacks (run BEFORE the next script run, so state is correct when pages render) ----
def cb_home_category_changed():
    cat = st.session_state.get("home_cat_select")
    if cat in CIRCUIT_DATABASE:
        cur = st.session_state.get("selected_circuit")
        # keep the current circuit if it belongs to the new category, else first circuit of that category
        target = cur if cur in CIRCUIT_DATABASE[cat] else list(CIRCUIT_DATABASE[cat].keys())[0]
        set_active_circuit(cat, target)


def cb_home_circuit_changed():
    ckt = st.session_state.get("home_ckt_select")
    cat = st.session_state.get("selected_category")
    if ckt is not None:
        set_active_circuit(cat, ckt)


def cb_digital_circuit_changed():
    ckt = st.session_state.get("dig_ckt_select")
    if ckt is not None:
        set_active_circuit("Digital Circuits", ckt)


def cb_launch_selected():
    """Home -> 'Launch': open the right interface for exactly the selected circuit."""
    cat = st.session_state.get("selected_category")
    ckt = st.session_state.get("selected_circuit")
    if is_valid_selection(cat, ckt):
        st.session_state.page = route_for(cat, ckt)


def cb_launch_digital_module():
    """Home -> 'Open digital tester': keep a valid digital selection; otherwise open the digital
    module with the last digital circuit used (or the first one) - and say so on the page."""
    cat = st.session_state.get("selected_category")
    ckt = st.session_state.get("selected_circuit")
    if not (cat == "Digital Circuits" and is_valid_selection(cat, ckt)):
        digital = list(CIRCUIT_DATABASE["Digital Circuits"].keys())
        last = st.session_state.get("last_digital_circuit")
        set_active_circuit("Digital Circuits", last if last in digital else digital[0])
    st.session_state.page = "Digital Circuit Tester"


def cb_load_circuit(category, circuit):
    if set_active_circuit(category, circuit):
        st.session_state.page = route_for(category, circuit)


def cb_go_home():
    st.session_state.page = "Home"


def render_selection_banner(category, circuit, info, interface):
    """Prominent confirmation of what the dashboard is actually showing."""
    sub = info.get("sub_type")
    kind = f" · TYPE: {html.escape(str(info.get('type')))}" + (f" / {html.escape(str(sub))}" if sub else "") if info.get("type") else ""
    st.markdown(f"""
    <div class="os-card" style="border-left: 6px solid #00ff87 !important;">
        <div style="font-family:Orbitron; font-size:0.72rem; color:#8fa3b8; letter-spacing:2px;">ACTIVE SELECTION · {html.escape(interface)}</div>
        <div style="font-family:Orbitron; font-size:1.5rem; color:#00ff87; font-weight:700; margin:4px 0;">{html.escape(circuit)}</div>
        <div style="color:#00f2fe;"><b>CATEGORY:</b> {html.escape(category)}{kind}</div>
        <div style="margin-top:6px;">{html.escape(str(info.get('description', '')))}</div>
    </div>
    """, unsafe_allow_html=True)


def render_no_selection_message(page_name):
    st.header(f"⚠️ {page_name.upper()} - NO CIRCUIT SELECTED")
    st.warning("No valid circuit is currently selected, so nothing is shown here. "
               "Pick a category and circuit on the Home page first.")
    st.button("← RETURN TO HOME", key=f"no_sel_home_{page_name}", on_click=cb_go_home, use_container_width=True)


def get_live_sensor_data(circuit_info):
    packet, packet_time = get_latest_packet_and_time()
    data = build_sensor_data(packet, circuit_info)
    data["packet_time"] = packet_time
    return data

def build_sensor_data(packet, circuit_info):
    active_targets = get_active_targets(circuit_info)
    if packet is not None:
        meas_in = float(packet.get("input_voltage", packet.get("input_v", 0)))
        meas_out = float(packet.get("output_voltage", packet.get("output_v", 0)))
        meas_in_i = float(packet.get("input_current", packet.get("input_i", 0)))
        meas_out_i = float(packet.get("output_current", packet.get("output_i", 0)))
        temp = float(packet.get("temperature", 0))
        freq = float(packet.get("frequency", 0))
    else:
        meas_in = 0.0
        meas_out = 0.0
        meas_in_i = 0.0
        meas_out_i = 0.0
        temp = 0.0
        freq = 0.0

    p_in = meas_in * meas_in_i
    p_out = meas_out * meas_out_i
    eff = (p_out / p_in * 100.0) if p_in > 0 else 0.0
    v_drop = max(0.0, meas_in - meas_out)

    v_dev = abs(meas_out - active_targets["target_output_voltage"]) / active_targets["target_output_voltage"] if active_targets["target_output_voltage"] > 0 else 0
    health = max(0, min(100, int((1.0 - v_dev) * 100)))

    return {
        "input_v": meas_in, "output_v": meas_out,
        "input_i": meas_in_i, "output_i": meas_out_i,
        "power_in": round(p_in, 2), "power_out": round(p_out, 2),
        "efficiency": round(eff, 2), "v_drop": round(v_drop, 2),
        "temperature": temp, "frequency": freq, "health": health
    }

# ------------------------------------------------------------------------------
# HOLD / RELEASE (UI snapshot only -- MQTT keeps receiving in the background)
# ------------------------------------------------------------------------------
def hold_testing_data():
    packet, _packet_time = get_latest_packet_and_time()
    if packet is None:
        st.session_state.hold_error = "No valid sensor data available to hold."
        return
    try:
        measured_input_voltage = float(packet.get("input_voltage", packet.get("input_v")))
        measured_input_current = float(packet.get("input_current", packet.get("input_i")))
        if not (math.isfinite(measured_input_voltage) and math.isfinite(measured_input_current)):
            raise ValueError("non-finite input measurement")
    except (TypeError, ValueError):
        st.session_state.hold_error = "Input voltage/current missing from the latest packet - nothing held."
        return
    captured_at = datetime.datetime.now()
    st.session_state.held_input_data = {
        "input_v": measured_input_voltage,
        "input_i": measured_input_current,
        "captured_at": captured_at,
        "circuit": st.session_state.selected_circuit,
    }
    st.session_state.hold_timestamp = captured_at
    st.session_state.data_hold = True
    st.session_state.hold_error = None

def release_testing_data():
    st.session_state.data_hold = False
    st.session_state.held_input_data = None
    st.session_state.hold_timestamp = None
    st.session_state.hold_error = None

def is_data_held():
    return bool(st.session_state.get("data_hold")) and st.session_state.get("held_input_data") is not None

def merge_held_input(packet):
    merged = dict(packet) if packet is not None else {}
    if is_data_held():
        held = st.session_state.held_input_data
        merged["input_voltage"] = held["input_v"]
        merged["input_current"] = held["input_i"]
        merged["input_v"] = held["input_v"]
        merged["input_i"] = held["input_i"]
    return merged

def get_testing_sensor_data(circuit_info):
    if is_data_held():
        packet, packet_time = get_latest_packet_and_time()
        data = build_sensor_data(merge_held_input(packet), circuit_info)
        data["packet_time"] = packet_time
        data["captured_at"] = st.session_state.held_input_data["captured_at"]
        data["source"] = "HELD"
        return data
    data = get_live_sensor_data(circuit_info)
    data["source"] = "LIVE"
    return data

# ------------------------------------------------------------------------------
# NEXUS TELEMETRY: HELD INPUT (V, I)  vs  LIVE OUTPUT (V, I)
# ------------------------------------------------------------------------------
def compute_power_efficiency(v_in, i_in, v_out, i_out):
    p_in = float(v_in) * float(i_in)
    p_out = float(v_out) * float(i_out)
    eff = (p_out / p_in * 100.0) if p_in > 1e-9 else None
    return p_in, p_out, eff


def generate_waveform_chart(freq_val, v_in, v_out, i_in=0.0, i_out=0.0, input_held=False):
    f_draw = freq_val if (freq_val is not None and freq_val > 0) else 50.0
    t = np.linspace(0, 0.04, 500)
    s = np.sin(2 * np.pi * f_draw * t)

    in_tag = "HELD" if input_held else "LIVE"
    in_col = "#ffb703" if input_held else "#00f2fe"
    out_v_col, out_i_col = "#00ff87", "#9d4edd"

    fig = make_subplots(
        rows=2, cols=2, shared_xaxes=True, vertical_spacing=0.20, horizontal_spacing=0.07,
        subplot_titles=(
            f"{in_tag} INPUT VOLTAGE  ({v_in:.2f} V)",
            f"LIVE OUTPUT VOLTAGE  ({v_out:.2f} V)",
            f"{in_tag} INPUT CURRENT  ({i_in:.3f} A)",
            f"LIVE OUTPUT CURRENT  ({i_out:.3f} A)",
        ))
    fig.update_annotations(font=dict(size=11, color="#c8d6e5"))

    fig.add_trace(go.Scatter(x=t, y=v_in * s, mode="lines", name=f"{in_tag} Input V(t)",
                             line=dict(color=in_col, width=3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=np.abs(v_out * s), mode="lines", name="LIVE Output V(t)",
                             line=dict(color=out_v_col, width=3)), row=1, col=2)
    fig.add_trace(go.Scatter(x=t, y=i_in * s, mode="lines", name=f"{in_tag} Input I(t)",
                             line=dict(color=in_col, width=3, dash="dot")), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=np.abs(i_out * s), mode="lines", name="LIVE Output I(t)",
                             line=dict(color=out_i_col, width=3, dash="dot")), row=2, col=2)

    grid = dict(gridcolor="rgba(0, 242, 254, 0.15)", zerolinecolor="rgba(0, 242, 254, 0.3)")
    fig.update_xaxes(**grid, title_text="time (s)", row=2)
    fig.update_xaxes(**grid)
    fig.update_yaxes(**grid)
    fig.update_yaxes(title_text="V", row=1, col=1)
    fig.update_yaxes(title_text="V", row=1, col=2)
    fig.update_yaxes(title_text="A", row=2, col=1)
    fig.update_yaxes(title_text="A", row=2, col=2)
    fig.add_annotation(
        xref="paper", yref="paper", x=0.5, y=-0.20, showarrow=False,
        text=f"Telemetry representation: sine model from measured amplitude and frequency "
             f"({f_draw:.1f} Hz{'' if freq_val and freq_val > 0 else ' assumed - no frequency reported'}). "
             f"Not raw ESP32 samples.",
        font=dict(size=10, color="#8fa3b8"))
    fig.update_layout(
        height=520, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(3, 7, 18, 0.65)",
        font=dict(color="#00f2fe", family="Orbitron", size=11),
        margin=dict(l=20, r=20, t=45, b=70), hovermode="x unified", showlegend=False)
    return fig


def _tele_card(title, value_txt, source, color):
    dot = "● HELD" if source == "HELD" else "● LIVE"
    return (
        f'<div class="os-card" style="border-left:5px solid {color} !important; text-align:center; padding:14px !important; margin-bottom:10px !important;">'
        f'<div style="font-family:Orbitron,sans-serif; font-size:0.72rem; letter-spacing:1px; color:{color};">{title}</div>'
        f'<div style="color:#c8d6e5; font-size:0.8rem; margin-top:4px;">{source} VALUE:</div>'
        f'<div style="font-family:Orbitron,sans-serif; font-size:1.55rem; color:#ffffff;">{value_txt}</div>'
        f'<div style="color:{color}; font-weight:700; font-size:0.8rem;">{dot}</div></div>')


def render_nexus_telemetry(sensor_data):
    held = sensor_data.get("source") == "HELD"
    in_src = "HELD" if held else "LIVE"
    in_col = "#ffb703" if held else "#00f2fe"
    out_col = "#00ff87"

    in_v, in_i = sensor_data["input_v"], sensor_data["input_i"]
    out_v, out_i = sensor_data["output_v"], sensor_data["output_i"]
    freq = sensor_data["frequency"]

    p_in, p_out, _ = compute_power_efficiency(in_v, in_i, out_v, out_i)

    st.markdown("### 📈 NEXUS TELEMETRY")
    st.markdown(
        f'<div style="text-align:center; font-family:Orbitron,sans-serif; letter-spacing:1px; color:#c8d6e5; margin-bottom:8px;">'
        f'<span style="color:{in_col};">{in_src} INPUT</span> &nbsp;VS&nbsp; <span style="color:{out_col};">LIVE OUTPUT</span></div>',
        unsafe_allow_html=True)

    c_in, c_out = st.columns(2)
    with c_in:
        st.markdown(f'<div style="font-family:Orbitron,sans-serif; color:{in_col}; font-weight:700; text-align:center;">INPUT TELEMETRY</div>', unsafe_allow_html=True)
        st.markdown(_tele_card(f"{in_src} INPUT VOLTAGE", f"{in_v:.2f} V", in_src, in_col), unsafe_allow_html=True)
        st.markdown(_tele_card(f"{in_src} INPUT CURRENT", f"{in_i:.3f} A", in_src, in_col), unsafe_allow_html=True)
    with c_out:
        st.markdown(f'<div style="font-family:Orbitron,sans-serif; color:{out_col}; font-weight:700; text-align:center;">OUTPUT TELEMETRY</div>', unsafe_allow_html=True)
        st.markdown(_tele_card("LIVE OUTPUT VOLTAGE", f"{out_v:.2f} V", "LIVE", out_col), unsafe_allow_html=True)
        st.markdown(_tele_card("LIVE OUTPUT CURRENT", f"{out_i:.3f} A", "LIVE", out_col), unsafe_allow_html=True)

    row = lambda k, v, c="#c8d6e5": (f'<div style="display:flex; justify-content:space-between;"><span style="color:{c};">{k}</span>'
                                     f'<span style="color:#ffffff; font-family:Orbitron,sans-serif;">{v}</span></div>')
    st.markdown(
        '<div class="os-card" style="padding:16px !important;">'
        f'<div style="font-family:Orbitron,sans-serif; color:#9d4edd; letter-spacing:1px; margin-bottom:6px;">POWER - {in_src} INPUT P vs LIVE OUTPUT P</div>'
        + row(f"{in_src} INPUT VOLTAGE", f"{in_v:.2f} V", in_col)
        + row(f"{in_src} INPUT CURRENT", f"{in_i:.3f} A", in_col)
        + row("LIVE OUTPUT VOLTAGE", f"{out_v:.2f} V", out_col)
        + row("LIVE OUTPUT CURRENT", f"{out_i:.3f} A", out_col)
        + '<hr style="border-color:rgba(0,242,254,0.2); margin:6px 0;">'
        + row("INPUT POWER (V x I)", f"{p_in:.2f} W", in_col)
        + row("OUTPUT POWER (V x I)", f"{p_out:.2f} W", out_col)
        + '</div>', unsafe_allow_html=True)

    st.plotly_chart(generate_waveform_chart(freq, in_v, out_v, in_i, out_i, input_held=held),
                    use_container_width=True)

def create_circular_gauge(title, value, max_val, unit, color="#00f2fe"):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        number = {'suffix': f" {unit}", 'font': {'color': "#ffffff", 'size': 20, 'family': "Orbitron"}},
        title = {'text': title.upper(), 'font': {'color': color, 'size': 11, 'family': "Orbitron"}},
        gauge = {
            'axis': {'range': [0, max_val], 'tickwidth': 1, 'tickcolor': "rgba(0, 242, 254, 0.4)"},
            'bar': {'color': color, 'thickness': 0.35},
            'bgcolor': "rgba(3, 7, 18, 0.8)",
            'borderwidth': 1,
            'bordercolor': "rgba(0, 242, 254, 0.25)",
            'steps': [
                {'range': [0, max_val], 'color': 'rgba(0, 242, 254, 0.03)'}
            ]
        }
    ))
    fig.update_layout(
        height=170, margin=dict(l=15, r=15, t=35, b=15),
        paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#ffffff')
    )
    return fig

# ------------------------------------------------------------------------------
# 3. GEMINI AI INTEGRATION & DIAGNOSIS LOGIC
# ------------------------------------------------------------------------------
def evaluate_pass_fail_status(active_targets, meas_data):
    def calc_dev(meas, target):
        return (abs(meas - target) / target * 100.0) if target > 0 else 0.0

    dev_in_v = calc_dev(meas_data.get('input_v', 0), active_targets['target_input_voltage'])
    dev_out_v = calc_dev(meas_data.get('output_v', 0), active_targets['target_output_voltage'])
    dev_in_i = calc_dev(meas_data.get('input_i', 0), active_targets['target_input_current'])
    dev_out_i = calc_dev(meas_data.get('output_i', 0), active_targets['target_output_current'])

    deviations = {
        "Input Voltage": dev_in_v,
        "Output Voltage": dev_out_v,
        "Input Current": dev_in_i,
        "Output Current": dev_out_i
    }

    max_dev = max(deviations.values())

    if max_dev <= 5.0:
        status = "PASS"
    elif max_dev <= 10.0:
        status = "WARNING"
    else:
        status = "FAIL"

    return status, deviations

@st.cache_resource
def get_cached_gemini_client(api_key):
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Gemini Client Init Error: {e}", flush=True)
        return None

def get_gemini_client():
    api_key = st.session_state.get("api_key") or os.environ.get("GEMINI_API_KEY")
    return get_cached_gemini_client(api_key)

def get_mqtt_status_display_text():
    status = get_mqtt_status()
    if status == "Connected":
        return "Connected"
    elif status == "Waiting for Data":
        return "Connected — Waiting for Data"
    return "Disconnected"

GEMINI_MODEL_NAME = 'gemini-3.6-flash'

def _fmt(value, nd=2):
    try:
        return f"{float(value):.{nd}f}"
    except (TypeError, ValueError):
        return "N/A"

def _build_measured_block(circuit_name, source, status, targets, snap, deviations):
    in_tag = "HELD" if str(source).upper() == "HELD" else "LIVE"
    return f"""NEXUS AI DIAGNOSTIC REPORT

CIRCUIT:
{circuit_name}

ANALYSIS SOURCE:
{source}

OVERALL RESULT:
{status}

MEASURED PARAMETERS:

Input Voltage ({in_tag}):
Measured: {_fmt(snap.get('input_v'))} V
Target: {_fmt(targets['target_input_voltage'])} V
Deviation: {_fmt(deviations['Input Voltage'])} %

Output Voltage (LIVE):
Measured: {_fmt(snap.get('output_v'))} V
Target: {_fmt(targets['target_output_voltage'])} V
Deviation: {_fmt(deviations['Output Voltage'])} %

Input Current ({in_tag}):
Measured: {_fmt(snap.get('input_i'), 3)} A
Target: {_fmt(targets['target_input_current'], 3)} A
Deviation: {_fmt(deviations['Input Current'])} %

Output Current (LIVE):
Measured: {_fmt(snap.get('output_i'), 3)} A
Target: {_fmt(targets['target_output_current'], 3)} A
Deviation: {_fmt(deviations['Output Current'])} %

Input Power:
{_fmt(snap.get('power_in'))} W

Output Power:
{_fmt(snap.get('power_out'))} W

Efficiency:
{_fmt(snap.get('efficiency'))} %
"""

def _extract_percent(text, label):
    m = re.search(rf"{label}\s*:?\s*\**\s*\n?\s*\**\s*(\d{{1,3}}(?:\.\d+)?)\s*%", text or "", re.IGNORECASE)
    if not m:
        return None
    try:
        return max(0, min(100, int(round(float(m.group(1))))))
    except ValueError:
        return None

_VALID_CONDITIONS = ("NORMAL", "WARNING", "FAULT", "CRITICAL")

def build_diagnostic_payload(snap, source, frequency, temperature):
    in_src = "HELD" if str(source).upper() == "HELD" else "LIVE"
    k = in_src.lower()
    return {
        "data_sources": {
            "input_voltage": in_src, "input_current": in_src,
            "output_voltage": "LIVE", "output_current": "LIVE",
            "frequency": "LIVE", "temperature": "LIVE",
        },
        "values": {
            f"{k}_input_voltage": round(float(snap.get("input_v", 0)), 3),
            f"{k}_input_current": round(float(snap.get("input_i", 0)), 4),
            "live_output_voltage": round(float(snap.get("output_v", 0)), 3),
            "live_output_current": round(float(snap.get("output_i", 0)), 4),
            "live_frequency": round(float(frequency or 0), 2),
            "live_temperature": round(float(temperature or 0), 2),
            "input_power_w": snap.get("power_in"),
            "output_power_w": snap.get("power_out"),
            "efficiency_percent": snap.get("efficiency"),
            "voltage_drop_v": snap.get("v_drop"),
        },
    }

def _normalize_condition(cond, status):
    c = str(cond or "").strip().upper()
    if c not in _VALID_CONDITIONS:
        c = {"PASS": "NORMAL", "WARNING": "WARNING"}.get(status, "FAULT")
    if status == "PASS" and c in ("FAULT", "CRITICAL"):
        c = "WARNING"
    if status == "FAIL" and c == "NORMAL":
        c = "FAULT"
    return c

# ==============================================================================
# GEMINI LAB-ASSISTANT LAYER
#   * shared helpers: sanitising, friendly errors, retry-on-invalid-JSON, background job runner
#   * analogue prompt/schema/validator/offline fields  (parse_gemini_json, build_offline_structured ...)
#   * digital prompt/schema/validator                  (parse_digital_json ...)
# Gemini only EXPLAINS the evidence computed by Python; deterministic PASS/FAIL/INCOMPLETE and the
# evidence-based IC verdicts are never overridden by AI output.
# ==============================================================================
LAB_ASSISTANT_PERSONA = """You are the NEXUS Lab Assistant: an experienced electronics laboratory instructor, embedded-systems engineer and diagnostic engineer who guides engineering students through circuit testing. Use correct technical language but explain it in a clear, student-friendly way. Be practical and safety-conscious."""

AI_PROBABILITY_RULES = """PROBABILITY AND EVIDENCE RULES (mandatory):
- Percentages are YOUR ESTIMATES from the supplied data. They are not statistically validated probabilities; the system has not been calibrated against a labelled fault dataset. Never present them as measured facts.
- Keep three things separate: (1) fault_probability = chance that a real fault exists; (2) overall_circuit_diagnosis_probability = your confidence that the diagnosis/detected_problem is correct; (3) overall_circuit_guide_probability = your confidence that the recommended procedure is the right guidance.
- Do not invent numbers to look intelligent. If the evidence is insufficient for a quantity, use null for that percentage and say why. If the whole diagnosis cannot be supported, set data_sufficiency to "INSUFFICIENT DATA" and use null probabilities.
- Component and wiring probabilities must be null unless the supplied measurements actually give evidence about them.
- Use only the supplied data. Do not invent measurements, components, ripple values, diode readings or pin voltages. Never claim that something that was not measured has passed.
- Never claim a component or IC is definitely defective unless the numbers prove it; prefer 'suspected', 'possible', 'cannot be excluded'.
- Plain text inside JSON strings (no markdown, no asterisks)."""

TEACHING_SCHEMA = """  "teaching": {
    "purpose": "purpose of this experiment",
    "why_components": ["why each key component/IC is used"],
    "how_it_works": "how the circuit works, in student-friendly language",
    "what_to_observe": ["what the student should observe when the circuit is healthy"],
    "abnormal_readings": ["what specific abnormal readings indicate"],
    "troubleshooting_tips": ["how the student can troubleshoot"],
    "precautions": ["safety and handling precautions"],
    "learning_outcomes": ["what the student should learn"]
  },
  "lab_assistant_next_steps": ["the next PRACTICAL actions for the student, in order (not theory)"],"""


# ---- sanitising helpers -------------------------------------------------------------------
_CTRL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _as_str(v, n=1800):
    if v is None:
        return ""
    s = v if isinstance(v, str) else (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
    s = _CTRL_CHARS.sub(" ", s).replace("**", "").strip()
    return s[:n]


def _as_list(v, items=14, n=700):
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, (list, tuple)):
        return []
    out = []
    for x in v:
        s = _as_str(x, n)
        s = re.sub(r"^\s*(step\s*)?\d+\s*[.):\-]\s*", "", s, flags=re.IGNORECASE).strip()
        if s:
            out.append(s)
    return out[:items]


def _as_pct(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(str(v).replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return max(0, min(100, int(round(f))))


def _as_enum(v, allowed, default):
    s = _as_str(v, 40).upper().replace("_", " ")
    for a in allowed:
        if s == a.upper().replace("_", " "):
            return a
    return default


def _clean_teaching(t):
    t = t if isinstance(t, dict) else {}
    return {"purpose": _as_str(t.get("purpose")), "why_components": _as_list(t.get("why_components")),
            "how_it_works": _as_str(t.get("how_it_works")), "what_to_observe": _as_list(t.get("what_to_observe")),
            "abnormal_readings": _as_list(t.get("abnormal_readings")), "troubleshooting_tips": _as_list(t.get("troubleshooting_tips")),
            "precautions": _as_list(t.get("precautions")), "learning_outcomes": _as_list(t.get("learning_outcomes"))}


def _teaching_from_knowledge(k):
    t = (k or {}).get("teaching", {})
    return {"purpose": t.get("purpose", ""), "why_components": list(t.get("why_components", [])),
            "how_it_works": (k or {}).get("working_principle", ""), "what_to_observe": list(t.get("observe", [])),
            "abnormal_readings": list(t.get("abnormal", [])), "troubleshooting_tips": list(t.get("troubleshooting", [])),
            "precautions": list(t.get("precautions", [])), "learning_outcomes": list(t.get("learning", []))}


def _clean_components(v, max_items=10):
    out = []
    for x in (v if isinstance(v, list) else []):
        if not isinstance(x, dict):
            continue
        comp = _as_str(x.get("component"), 80)
        if not comp:
            continue
        out.append({"component": comp, "probability_percent": _as_pct(x.get("probability_percent")),
                    "evidence": _as_str(x.get("evidence"), 500), "verify": _as_str(x.get("verify"), 500)})
    return out[:max_items]


def _clean_wiring(v):
    v = v if isinstance(v, dict) else {}
    return {"probability_percent": _as_pct(v.get("probability_percent")), "evidence": _as_str(v.get("evidence"), 600),
            "checks": _as_list(v.get("checks"), 8, 400)}


def _clean_sensor(v):
    v = v if isinstance(v, dict) else {}
    return {"rating": _as_enum(v.get("rating"), ("GOOD", "QUESTIONABLE", "UNKNOWN"), "UNKNOWN"), "evidence": _as_str(v.get("evidence"), 600)}


def _json_from_text(text):
    if not text:
        return None
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", str(text).strip())
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        d = json.loads(t[a:b + 1])
    except (ValueError, TypeError):
        return None
    return d if isinstance(d, dict) else None


_SECRET_RE = re.compile(r"(key=|api[_-]?key[\"':= ]+)[A-Za-z0-9_\-]{8,}", re.IGNORECASE)


def friendly_gemini_error(exc):
    """Turns an SDK/network exception into a student-readable message (never leaks keys)."""
    raw = _SECRET_RE.sub(r"\1***", f"{type(exc).__name__}: {exc}")
    low = raw.lower()
    code = None
    for attr in ("code", "status_code", "status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            code = val
            break
    if code == 429 or "429" in low or "resource_exhausted" in low or "quota" in low or "rate limit" in low:
        msg = "Gemini quota or rate limit reached. Wait a minute and press ANALYZE again, or check the API plan/quota."
    elif code in (401, 403) or "api key" in low or "api_key" in low or "permission_denied" in low or "unauthenticated" in low:
        msg = "Gemini rejected the API key (invalid, expired or not permitted). Check the key in Settings."
    elif code == 404 or "not found" in low and "model" in low:
        msg = f"The Gemini model '{GEMINI_MODEL_NAME}' was not found or is not available for this key."
    elif code in (500, 502, 503, 504) or "unavailable" in low or "overloaded" in low or "deadline" in low:
        msg = "The Gemini service is busy or temporarily unavailable. Try again shortly."
    elif "timeout" in low or "timed out" in low or "connection" in low or "name or service" in low or "network" in low:
        msg = "Could not reach Gemini (network problem or timeout). Check the internet connection and retry."
    else:
        msg = "Gemini request failed."
    return f"{msg} [{raw[:160]}]"


def call_gemini_json(client, prompt, validator=None):
    """One call, plus ONE retry if the reply is empty/invalid JSON. Returns (text, attempts).
    API exceptions propagate (quota etc.) except on the retry, where the first reply is kept."""
    from google.genai import types
    cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
    resp = client.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt, config=cfg)
    text = (getattr(resp, "text", None) or "").strip()
    if text and (validator is None or validator(text)):
        return text, 1
    try:
        retry = prompt + ("\n\nYour previous reply was not valid JSON for the required schema. Reply again with ONLY the single "
                          "JSON object described above - no code fences and no commentary.")
        resp2 = client.models.generate_content(model=GEMINI_MODEL_NAME, contents=retry, config=cfg)
        text2 = (getattr(resp2, "text", None) or "").strip()
        if text2:
            return text2, 2
    except Exception:
        pass
    return text, 2


# ---- background job runner (keeps the Streamlit UI and MQTT telemetry live while Gemini works) ----
@st.cache_resource
def get_gemini_job_store():
    return {"lock": threading.Lock(), "jobs": {}}


def _gemini_worker(store, job_id, client, prompt, validator):
    try:
        text, attempts = call_gemini_json(client, prompt, validator)
        out = {"state": "done", "text": text, "error": None, "attempts": attempts}
    except Exception as exc:  # noqa: BLE001 - every failure is reported to the UI
        out = {"state": "done", "text": "", "error": friendly_gemini_error(exc), "attempts": 1}
    out["finished_at"] = time.time()
    with store["lock"]:
        store["jobs"][job_id] = {**store["jobs"].get(job_id, {}), **out}


def start_gemini_job(client, prompt, validator=None):
    """Starts the Gemini call in a daemon thread (no Streamlit calls inside) and returns a job id."""
    store = get_gemini_job_store()
    job_id = uuid.uuid4().hex[:10]
    now = time.time()
    with store["lock"]:
        for jid in [j for j, v in store["jobs"].items() if now - v.get("started_at", now) > 3600]:
            store["jobs"].pop(jid, None)
        store["jobs"][job_id] = {"state": "running", "started_at": now}
    threading.Thread(target=_gemini_worker, args=(store, job_id, client, prompt, validator), daemon=True).start()
    return job_id


def poll_gemini_job(job_id):
    store = get_gemini_job_store()
    with store["lock"]:
        job = store["jobs"].get(job_id)
        return dict(job) if job else None


GEMINI_JOB_TIMEOUT_S = 150


# ==============================================================================
# ANALOGUE: prompt, validator, offline lab fields
# ==============================================================================
ANALOG_JSON_SCHEMA = """{
  "circuit_condition": "NORMAL | WARNING | FAULT | CRITICAL",
  "data_sufficiency": "SUFFICIENT | LIMITED | INSUFFICIENT DATA",
  "operating_correctly": "YES | NO | UNCERTAIN",
  "circuit_health_assessment": "overall health of the circuit in 2-3 sentences",
  "fault_probability": 0,
  "overall_circuit_diagnosis_probability": 0,
  "overall_circuit_guide_probability": 0,
  "what_circuit_should_do": "what this circuit is supposed to do (working principle, student-friendly)",
  "what_measurements_indicate": "what the actual measurements indicate, citing numbers, expected vs measured",
  "diagnosis": "technical analysis: voltages, currents, power, efficiency, voltage drop, deviations and what they mean for THIS topology",
  "detected_problem": "suspected problem, or No problem detected",
  "suspected_component": "suspected component/section from the component list, or None",
  "supporting_evidence": ["numeric evidence for the diagnosis"],
  "component_fault_assessment": [{"component": "D1", "probability_percent": null, "evidence": "why suspected / why not assessable", "verify": "how the student verifies it"}],
  "wiring_fault_assessment": {"probability_percent": null, "evidence": "", "checks": ["wiring / probe-position / grounding checks"]},
  "sensor_reliability": {"rating": "GOOD | QUESTIONABLE | UNKNOWN", "evidence": "sensor calibration / measurement consistency comments"},
  "ripple_assessment": "NOT ASSESSED - no ripple data is available (unless ripple data was supplied)",
  "recommended_steps": ["ordered troubleshooting steps specific to this circuit, ending with a re-test step"],
  "corrective_actions": ["how to correct the suspected problem SAFELY"],
  "verification_procedure": ["how to verify the suspected problem with a multimeter/other test before and after repair"],
  "final_retest_recommendation": "how to repeat the experiment and confirm the result",
""" + TEACHING_SCHEMA + """
  "problem_resolution_percent": 0,
  "resolution_status": "Verification required",
  "reasoning": "why these percentages and this condition were assigned, citing the numbers",
  "limitations": ["limits of the measurements and of this diagnosis"],
  "final_conclusion": "short final conclusion"
}"""


def build_analog_prompt(ctx):
    snap, targets, status, dev = ctx["snap"], ctx["targets"], ctx["status"], ctx["deviations"]
    src, payload, ev = ctx["source"], ctx["payload"], ctx["evidence"]
    info, name, k = ctx["circuit_info"], ctx["circuit_name"], ctx.get("knowledge") or {}
    in_src = "HELD" if src == "HELD" else "LIVE"
    t_in_p = targets["target_input_voltage"] * targets["target_input_current"]
    t_out_p = targets["target_output_voltage"] * targets["target_output_current"]
    t_eff = (t_out_p / t_in_p * 100.0) if t_in_p > 0 else 0.0
    comps = "\n".join(f"- {c['ref_label']}: {c['name']} ({c['value']}) - {c['function']}" for c in k.get("components", [])) or info.get("components", "N/A")
    conns = "\n".join(f"- {x}" for x in k.get("connections", []))
    probes = "\n".join(f"- P{p['step']} {p['name']}: {p['loc']}" for p in (info.get("probes") or []))
    held_note = (f"Input voltage and input current are HELD values captured at {snap.get('captured_at') or 'N/A'} and no longer change. "
                 "Output voltage, output current, frequency and temperature are LIVE readings. Do not treat the held input as a live reading.") if src == "HELD" else "All values are LIVE readings taken at the moment of analysis."
    checks = "\n".join(f"- [{c['level']}] {c['text']}" for c in ev.get("checks", [])) or "- (no consistency flags raised)"
    na = "\n".join(f"- {x}" for x in ev.get("not_assessable", []))
    return f"""{LAB_ASSISTANT_PERSONA}

TASK: Produce a complete laboratory diagnosis of the rectifier circuit below from ONE frozen measurement snapshot. Explain what the circuit should do, what the measurements indicate, whether it operates correctly, which components or sections could be responsible for any abnormal behaviour and why, how the student can verify and safely correct it, and how to repeat the experiment. Then teach: purpose, why each component is used, how the circuit works, what to observe, what abnormal readings mean, precautions, learning outcomes, and the next practical steps.

DATA SOURCES (authoritative JSON - the measured numbers):
{json.dumps(payload, indent=2)}

{held_note}

CIRCUIT DEFINITION (authoritative - do NOT invent components that are not listed):
Circuit = {name}
Objective = {k.get('objective', info.get('description', 'N/A'))}
Working principle = {k.get('working_principle', 'N/A')}
Components:
{comps}
Connections:
{conns}
Probe locations:
{probes}
Database nominal efficiency = {info.get('exp_eff', 'N/A')} %

EXPECTED (USER CONFIGURED / DATABASE) VALUES:
Target Input Voltage = {targets['target_input_voltage']} V
Target Output Voltage = {targets['target_output_voltage']} V
Target Input Current = {targets['target_input_current']} A
Target Output Current = {targets['target_output_current']} A
Target Input Power = {t_in_p:.2f} W
Target Output Power = {t_out_p:.2f} W
Target Efficiency (from targets) = {t_eff:.2f} %

DERIVED VALUES (Python):
Input Power = {_fmt(snap.get('power_in'))} W ({in_src} V x {in_src} I)
Output Power = {_fmt(snap.get('power_out'))} W (LIVE V x LIVE I)
Efficiency = {_fmt(snap.get('efficiency'))} %
Voltage Drop (Vin - Vout) = {_fmt(snap.get('v_drop'))} V
Frequency = {_fmt(ctx['frequency'], 1)} Hz  (0 may mean the sensor does not report it)
Temperature = {_fmt(ctx['temperature'], 1)} C  (0 may mean the sensor does not report it)

PYTHON-COMPUTED DEVIATIONS (|Measured - Target| / Target x 100):
Input Voltage = {dev['Input Voltage']:.2f} %
Output Voltage = {dev['Output Voltage']:.2f} %
Input Current = {dev['Input Current']:.2f} %
Output Current = {dev['Output Current']:.2f} %
PYTHON-COMPUTED OVERALL RESULT = {status}  (PASS: all within +-5 %; WARNING: any >5 % and <=10 %; FAIL: any >10 %). This deterministic result is final. circuit_condition must be consistent with it: PASS -> NORMAL (or WARNING only if temperature/frequency justify it), WARNING -> WARNING, FAIL -> FAULT or CRITICAL.

PYTHON-COMPUTED THEORY REFERENCE:
{json.dumps(ev.get('theory'), indent=2)}

PYTHON-COMPUTED MEASUREMENT CONSISTENCY CHECKS (use them as evidence; they may point to a measurement/calibration problem instead of a circuit fault):
{checks}

NOT ASSESSABLE FROM THE AVAILABLE DATA (say so explicitly; do not diagnose these):
{na}

{AI_PROBABILITY_RULES}
- Do NOT diagnose ripple unless ripple data was supplied (it was not). Do NOT diagnose an individual diode or the filter capacitor as faulty from voltage/current alone; you may list them as possibilities with a verification test and a null probability.
- problem_resolution_percent must be 0 and resolution_status must be "Verification required": nothing has been repaired or re-measured yet.
- recommended_steps must be ordered, specific to this circuit and ending with a re-test step; all corrective actions must be safe for a student (power off, discharge capacitors, mains safety).

Respond with ONLY one JSON object, no code fences, with exactly these keys:
{ANALOG_JSON_SCHEMA}"""


def parse_gemini_json(text, status):
    """Validates/sanitises the analogue Gemini reply. Returns the structured dict (old keys preserved,
    lab-assistant keys added) or None when the reply is unusable."""
    d = _json_from_text(text)
    if d is None:
        return None
    steps = _as_list(d.get("recommended_steps"), 14, 500)
    if not steps:
        return None
    suff = _as_enum(d.get("data_sufficiency"), ("SUFFICIENT", "LIMITED", "INSUFFICIENT DATA"), "LIMITED")
    guide, diag_p = _as_pct(d.get("overall_circuit_guide_probability")), _as_pct(d.get("overall_circuit_diagnosis_probability"))
    if suff != "INSUFFICIENT DATA" and (guide is None or diag_p is None):
        return None
    cond = _normalize_condition(d.get("circuit_condition"), status)
    problem = _as_str(d.get("detected_problem"), 600)
    if not problem:
        problem = "No problem detected" if cond == "NORMAL" else "Not specified by the analysis"
    notes = []
    fault_p = _as_pct(d.get("fault_probability"))
    if suff == "INSUFFICIENT DATA":
        fault_p = guide = diag_p = None
        notes.append("Gemini reported INSUFFICIENT DATA: no probability is shown.")
    else:
        if status == "PASS" and fault_p is not None and fault_p > 30:
            notes.append(f"Gemini's fault probability ({fault_p} %) was rejected because it contradicts the deterministic PASS result.")
            fault_p = None
        elif status == "FAIL" and fault_p is not None and fault_p < 30:
            notes.append(f"Gemini's fault probability ({fault_p} %) was rejected because it contradicts the deterministic FAIL result.")
            fault_p = None
    comps = _clean_components(d.get("component_fault_assessment"))
    wiring = _clean_wiring(d.get("wiring_fault_assessment"))
    if suff == "INSUFFICIENT DATA":
        for c in comps:
            c["probability_percent"] = None
        wiring["probability_percent"] = None
    return {
        "circuit_condition": cond,
        "data_sufficiency": suff,
        "operating_correctly": _as_enum(d.get("operating_correctly"), ("YES", "NO", "UNCERTAIN"), "UNCERTAIN"),
        "circuit_health_assessment": _as_str(d.get("circuit_health_assessment"), 900),
        "overall_circuit_guide_probability": guide,
        "overall_circuit_diagnosis_probability": diag_p,
        "fault_probability": fault_p,
        "what_circuit_should_do": _as_str(d.get("what_circuit_should_do"), 1200),
        "what_measurements_indicate": _as_str(d.get("what_measurements_indicate"), 1500),
        "diagnosis": _as_str(d.get("diagnosis"), 2200),
        "detected_problem": problem,
        "suspected_component": _as_str(d.get("suspected_component"), 300) or "None",
        "supporting_evidence": _as_list(d.get("supporting_evidence"), 10, 500),
        "component_fault_assessment": comps,
        "wiring_fault_assessment": wiring,
        "sensor_reliability": _clean_sensor(d.get("sensor_reliability")),
        "ripple_assessment": _as_str(d.get("ripple_assessment"), 400) or "NOT ASSESSED - no ripple data is available.",
        "recommended_steps": steps,
        "corrective_actions": _as_list(d.get("corrective_actions"), 10, 500),
        "verification_procedure": _as_list(d.get("verification_procedure"), 10, 500),
        "final_retest_recommendation": _as_str(d.get("final_retest_recommendation"), 800),
        "teaching": _clean_teaching(d.get("teaching")),
        "lab_assistant_next_steps": _as_list(d.get("lab_assistant_next_steps"), 10, 500),
        "problem_resolution_percent": 0,
        "resolution_status": "Verification required",
        "reasoning": _as_str(d.get("reasoning"), 2000),
        "limitations": _as_list(d.get("limitations"), 10, 500),
        "final_conclusion": _as_str(d.get("final_conclusion"), 900),
        "validation_notes": notes,
    }


def _fmt_pct(v):
    return f"{v} %" if v is not None else "N/A (not estimated / insufficient data)"


def _bullets(items, numbered=False):
    return "\n".join((f"{i}. {x}" if numbered else f"- {x}") for i, x in enumerate(items, 1)) if items else "(none)"


def _lab_text_sections(s):
    """Common text rendering of the lab-assistant sections (analogue and digital)."""
    t = s.get("teaching") or {}
    comps = "\n".join(f"- {c['component']}: probability {_fmt_pct(c['probability_percent'])}. {c['evidence']} Verify: {c['verify']}"
                      for c in s.get("component_fault_assessment", [])) or "(no component-level estimate - insufficient evidence)"
    w = s.get("wiring_fault_assessment") or {}
    sr = s.get("sensor_reliability") or {}
    return f"""CIRCUIT HEALTH ASSESSMENT:
{s.get('circuit_health_assessment') or 'N/A'}

DATA SUFFICIENCY:
{s.get('data_sufficiency', 'N/A')}

OPERATING CORRECTLY:
{s.get('operating_correctly', 'N/A')}

WHAT THE CIRCUIT SHOULD DO:
{s.get('what_circuit_should_do') or 'N/A'}

WHAT THE MEASUREMENTS INDICATE:
{s.get('what_measurements_indicate') or 'N/A'}

SUPPORTING EVIDENCE:
{_bullets(s.get('supporting_evidence', []))}

COMPONENT-LEVEL FAULT ASSESSMENT:
{comps}

WIRING FAULT ASSESSMENT:
Probability: {_fmt_pct(w.get('probability_percent'))}. {w.get('evidence', '')}
{_bullets(w.get('checks', []))}

SENSOR / MEASUREMENT RELIABILITY:
{sr.get('rating', 'UNKNOWN')} - {sr.get('evidence', '')}

CORRECTIVE ACTIONS:
{_bullets(s.get('corrective_actions', []), True)}

VERIFICATION PROCEDURE:
{_bullets(s.get('verification_procedure', []), True)}

FINAL RETEST RECOMMENDATION:
{s.get('final_retest_recommendation') or 'N/A'}

LAB ASSISTANT - TEACHING NOTES:
Purpose: {t.get('purpose', '')}
How it works: {t.get('how_it_works', '')}
What to observe:
{_bullets(t.get('what_to_observe', []))}
Abnormal readings:
{_bullets(t.get('abnormal_readings', []))}
Precautions:
{_bullets(t.get('precautions', []))}
What you should learn:
{_bullets(t.get('learning_outcomes', []))}

LAB ASSISTANT - WHAT TO DO NEXT:
{_bullets(s.get('lab_assistant_next_steps', []), True)}

LIMITATIONS:
{_bullets(s.get('limitations', []))}

FINAL CONCLUSION:
{s.get('final_conclusion') or 'N/A'}

NOTE ON PERCENTAGES:
{AI_PROBABILITY_NOTICE}
"""


def structured_to_text(measured_block, s, frequency, temperature):
    fp = _fmt_pct(s.get("fault_probability"))
    steps = "\n".join(f"{i}. {x}" for i, x in enumerate(s["recommended_steps"], 1))
    guide, diagp = _fmt_pct(s.get("overall_circuit_guide_probability")), _fmt_pct(s.get("overall_circuit_diagnosis_probability"))
    head = f"""{measured_block}
LIVE FREQUENCY / TEMPERATURE:
{_fmt(frequency, 1)} Hz / {_fmt(temperature, 1)} C

CIRCUIT CONDITION:
{s['circuit_condition']}

TECHNICAL ANALYSIS:
{s['diagnosis']}

DETECTED PROBLEM:
{s['detected_problem']}

SUSPECTED COMPONENT / SECTION:
{s['suspected_component']}

FAULT PROBABILITY (AI estimate that a fault exists):
{fp}

DIAGNOSIS CONFIDENCE (AI estimate that the diagnosis is correct):
{diagp}

CONFIDENCE IN RECOMMENDED PROCEDURE (AI estimate):
{guide}

OVERALL CIRCUIT GUIDE:
{guide}

OVERALL CIRCUIT DIAGNOSIS:
{diagp}

WHY:
{s['reasoning']}

RECOMMENDED TROUBLESHOOTING:
{steps}

PROBLEM RESOLUTION:
{s['problem_resolution_percent']} %
{s['resolution_status']}

"""
    return head + _lab_text_sections(s)


def offline_lab_fields(circuit_name, status, deviations, evidence, snap):
    """Deterministic (no-AI) lab-assistant fields so the offline engine also teaches."""
    k = CIRCUIT_KNOWLEDGE.get(circuit_name, {})
    worst = max(deviations, key=deviations.get)
    flags = [c["text"] for c in (evidence or {}).get("checks", []) if c["level"] in ("ALERT", "WARN")]
    ok = {"PASS": "YES", "WARNING": "UNCERTAIN", "FAIL": "NO"}.get(status, "UNCERTAIN")
    nxt = ["Re-check the schematic and probe positions P1-P3 against the physical wiring (power off first)."]
    if status == "PASS":
        nxt += ["Record the readings in your lab notebook and compare them with the theory (efficiency, voltage drop).",
                "Optionally measure the ripple with an oscilloscope: NEXUS cannot measure ripple."]
    else:
        nxt += [f"Re-measure {worst} with a multimeter and compare it with the NEXUS reading.",
                "Inspect the diodes/capacitor with the multimeter (power off, capacitor discharged).",
                "Press VERIFY / RE-TEST after each correction."]
    return {
        "data_sufficiency": "LIMITED",
        "operating_correctly": ok,
        "circuit_health_assessment": f"Rule-based result {status}: largest deviation is {worst} ({deviations[worst]:.1f} %). Only electrical values were compared.",
        "what_circuit_should_do": k.get("working_principle", ""),
        "what_measurements_indicate": (f"Measured input {_fmt(snap.get('input_v'))} V / {_fmt(snap.get('input_i'), 3)} A, output {_fmt(snap.get('output_v'))} V / "
                                      f"{_fmt(snap.get('output_i'), 3)} A, efficiency {_fmt(snap.get('efficiency'))} %."),
        "supporting_evidence": flags[:6],
        "component_fault_assessment": [],
        "wiring_fault_assessment": {"probability_percent": None, "evidence": "Not assessed by the offline engine.", "checks": []},
        "sensor_reliability": {"rating": "QUESTIONABLE" if any(c["level"] == "ALERT" for c in (evidence or {}).get("checks", [])) else "UNKNOWN",
                               "evidence": flags[0] if flags else "No consistency flag was raised; sensor accuracy was not independently verified."},
        "ripple_assessment": "NOT ASSESSED - no ripple data is available.",
        "corrective_actions": ["Correct only one suspected item at a time, with the power off and the capacitor discharged."] if status != "PASS" else [],
        "verification_procedure": ["Use a multimeter to confirm the suspected item before replacing it.", "Re-run the test and compare with the previous snapshot."],
        "final_retest_recommendation": "Repeat the measurement with HOLD/RELEASE as before and press VERIFY / RE-TEST.",
        "teaching": _teaching_from_knowledge(k),
        "lab_assistant_next_steps": nxt,
        "limitations": ["Offline rule-based engine: electrical values only; no AI interpretation was used.",
                        "Values shown as probability/confidence by the offline engine are rule-of-thumb indicators scaled from the worst deviation, not statistical probabilities."]
                       + (evidence or {}).get("not_assessable", []),
        "final_conclusion": f"Deterministic result: {status}.",
        "validation_notes": [],
    }


def build_offline_structured(circuit_info, snap, status, deviations, circuit_name=None, evidence=None):
    worst = max(deviations, key=deviations.get)
    max_dev = deviations[worst]
    comps = circuit_info.get("components", "N/A")
    if status == "PASS":
        cond, fault_p, conf = "NORMAL", int(round(min(10, max_dev * 1.5))), 80
        problem, suspect = "No problem detected", "None"
    elif status == "WARNING":
        cond, fault_p, conf = "WARNING", int(round(30 + (max_dev - 5.0) / 5.0 * 25)), 60
        problem = f"{worst} deviates {max_dev:.1f} % from its target (HELD input vs LIVE output comparison)."
        suspect = f"Circuit section associated with {worst.lower()}; components: {comps}"
    else:
        cond = "CRITICAL" if max_dev > 30 else "FAULT"
        fault_p, conf = int(round(min(95, 65 + (max_dev - 10.0) * 1.2))), 65
        problem = f"{worst} deviates {max_dev:.1f} % from its target (HELD input vs LIVE output comparison)."
        suspect = f"Circuit section associated with {worst.lower()}; components: {comps}"
    steps = ["Re-check the supply/input connection and the probe points listed for this circuit."]
    if status != "PASS":
        steps += [f"Re-measure {worst} with an independent instrument to confirm the reading.",
                  f"Inspect the components in the affected section for heat, discolouration or loose joints: {comps}",
                  "Check grounding and the load connection, then press VERIFY / RE-TEST."]
    else:
        steps.append("No repair is needed; repeat the test if conditions change.")
    s = {
        "circuit_condition": cond,
        "overall_circuit_guide_probability": conf,
        "overall_circuit_diagnosis_probability": conf,
        "fault_probability": fault_p,
        "diagnosis": (f"[OFFLINE RULES ENGINE - no Gemini key] Largest deviation: {worst} at {max_dev:.2f} %. "
                      f"Input power {_fmt(snap.get('power_in'))} W, output power {_fmt(snap.get('power_out'))} W, "
                      f"efficiency {_fmt(snap.get('efficiency'))} % (database nominal {circuit_info.get('exp_eff', 'N/A')} %), "
                      f"voltage drop {_fmt(snap.get('v_drop'))} V."),
        "detected_problem": problem,
        "suspected_component": suspect,
        "recommended_steps": steps,
        "problem_resolution_percent": 0,
        "resolution_status": "Verification required",
        "reasoning": "Rule-of-thumb indicator scaled from the worst measured deviation (PASS <= 5 %, WARNING <= 10 %, FAIL > 10 %). "
                     "The numbers are NOT statistical probabilities; the offline engine compares electrical values only, so its confidence is limited.",
    }
    s.update(offline_lab_fields(circuit_name or "", status, deviations, evidence, snap))
    return s


# ==============================================================================
# ANALOGUE: prepare -> (call) -> finalize   (generate_automatic_diagnosis keeps its old signature)
# ==============================================================================
def prepare_automatic_diagnosis(circuit_name, circuit_info, sensor_snapshot, probes, frequency, temperature,
                                analysis_source="LIVE", active_targets=None, use_ai=True):
    snap = dict(sensor_snapshot)
    snap["frequency"] = frequency
    snap["temperature"] = temperature
    targets = active_targets if active_targets is not None else get_active_targets(circuit_info)
    status, deviations = evaluate_pass_fail_status(targets, snap)
    source = str(analysis_source).upper()
    ctx = {
        "circuit_name": circuit_name, "circuit_info": circuit_info, "snap": snap, "targets": targets,
        "status": status, "deviations": deviations, "source": source, "frequency": frequency, "temperature": temperature,
        "payload": build_diagnostic_payload(snap, source, frequency, temperature),
        "measured_block": _build_measured_block(circuit_name, source, status, targets, snap, deviations),
        "evidence": compute_rectifier_evidence(circuit_name, snap, targets, source),
        "knowledge": CIRCUIT_KNOWLEDGE.get(circuit_name), "prompt": None,
    }
    if use_ai:
        ctx["prompt"] = build_analog_prompt(ctx)
    return ctx


def finalize_automatic_diagnosis(ctx, raw_text, error):
    """Builds the diagnosis result dict. ctx['prompt'] is None -> offline rules engine (no Gemini key)."""
    snap, status, deviations, targets = ctx["snap"], ctx["status"], ctx["deviations"], ctx["targets"]
    base = {"ok": False, "text": "", "error": None, "engine": "GEMINI", "status": status, "deviations": deviations,
            "targets": targets, "fault_probability": None, "confidence": None, "structured": None,
            "payload": ctx["payload"], "evidence": ctx["evidence"]}
    mb, fr, tp = ctx["measured_block"], ctx["frequency"], ctx["temperature"]
    if ctx.get("prompt") is None:
        s = build_offline_structured(ctx["circuit_info"], snap, status, deviations, ctx["circuit_name"], ctx["evidence"])
        base.update(ok=True, engine="OFFLINE RULES ENGINE", structured=s, text=structured_to_text(mb, s, fr, tp),
                    fault_probability=s["fault_probability"], confidence=s["overall_circuit_diagnosis_probability"])
        return base
    if error:
        base["error"] = error
        return base
    if not raw_text:
        base["error"] = "Gemini returned an empty response."
        return base
    s = parse_gemini_json(raw_text, status)
    if s is None:
        base.update(ok=True, text=raw_text.replace("**", "").strip(),
                    fault_probability=_extract_percent(raw_text, "FAULT PROBABILITY"),
                    confidence=_extract_percent(raw_text, "DIAGNOSIS CONFIDENCE"))
        return base
    base.update(ok=True, structured=s, text=structured_to_text(mb, s, fr, tp),
                fault_probability=s["fault_probability"], confidence=s["overall_circuit_diagnosis_probability"])
    return base


def generate_automatic_diagnosis(circuit_name, circuit_info, sensor_snapshot, probes,
                                 frequency, temperature, analysis_source="LIVE", active_targets=None):
    """Synchronous convenience wrapper (the dashboard uses the background-job path instead)."""
    client = get_gemini_client()
    ctx = prepare_automatic_diagnosis(circuit_name, circuit_info, sensor_snapshot, probes, frequency, temperature,
                                      analysis_source, active_targets, use_ai=client is not None)
    if client is None:
        return finalize_automatic_diagnosis(ctx, None, None)
    try:
        text, _n = call_gemini_json(client, ctx["prompt"], lambda t: parse_gemini_json(t, ctx["status"]) is not None)
    except Exception as exc:  # noqa: BLE001
        return finalize_automatic_diagnosis(ctx, None, friendly_gemini_error(exc))
    return finalize_automatic_diagnosis(ctx, text, None)


# ==============================================================================
# DIGITAL: dataset, prompt, validator, text rendering, finalize
# ==============================================================================
DIGITAL_JSON_SCHEMA = """{
  "circuit_condition": "NORMAL | WARNING | FAULT | CRITICAL | INSUFFICIENT DATA",
  "data_sufficiency": "SUFFICIENT | LIMITED | INSUFFICIENT DATA",
  "operating_correctly": "YES | NO | UNCERTAIN",
  "circuit_health_assessment": "overall health in 2-3 sentences, consistent with the deterministic result",
  "fault_probability": null,
  "overall_circuit_diagnosis_probability": null,
  "overall_circuit_guide_probability": null,
  "what_circuit_should_do": "what this circuit/IC is supposed to do",
  "what_measurements_indicate": "what the measured truth table indicates",
  "matching_rows_summary": "which tested rows/outputs matched",
  "mismatch_analysis": [{"row": 0, "inputs": "A=0, B=1", "output": "Y", "expected": 0, "measured_state": "1", "observation": "what is wrong", "possible_causes": ["hypotheses, not facts"]}],
  "missing_or_invalid_summary": "missing and invalid measurements and how they limit the diagnosis",
  "coverage_comment": "comment on the tested coverage",
  "responsible_section": "gate / IC section that may be responsible, or 'Cannot be determined from the available data'",
  "ic_assessments": [{"ic_ref": "U1", "explanation": "why the evidence-based verdict given to you is what it is", "pin_checks": ["pin-by-pin checks"], "still_unverified": ["what is NOT verified"]}],
  "component_fault_assessment": [{"component": "U1 gate 1", "probability_percent": null, "evidence": "", "verify": ""}],
  "wiring_fault_assessment": {"probability_percent": null, "evidence": "", "checks": ["wiring checks"]},
  "sensor_reliability": {"rating": "GOOD | QUESTIONABLE | UNKNOWN", "evidence": ""},
  "suspected_faulty_component": "IC/gate/wiring suspected, or None",
  "supporting_evidence": ["evidence from the dataset"],
  "recommended_steps": ["step-by-step pin-by-pin troubleshooting"],
  "corrective_actions": ["how to correct the problem safely"],
  "verification_procedure": ["how to verify the suspected problem"],
  "final_retest_recommendation": "how to retest",
""" + TEACHING_SCHEMA + """
  "reasoning": "why these conclusions and percentages",
  "limitations": ["limits of the data and diagnosis"],
  "final_conclusion": "short conclusion"
}"""


def build_digital_dataset(circuit_name, ckt_info, expected_df, ckt_meas, result, input_cols, possible_outputs):
    measured_list = []
    for (m_row, m_out), m_val in sorted(ckt_meas.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if m_row >= len(expected_df) or m_out not in possible_outputs:
            continue
        exp_col_nm = f"Expected {m_out}" if f"Expected {m_out}" in expected_df.columns else m_out
        measured_list.append({
            "row": m_row, "inputs": ", ".join(f"{c}={expected_df.iloc[m_row][c]}" for c in input_cols), "output": m_out,
            "expected_logic": int(expected_df.iloc[m_row][exp_col_nm]), "measured_voltage": m_val["voltage"],
            "measured_logic_state": m_val["logic_state"], "timestamp": str(m_val["timestamp"])})
    return {
        "circuit_name": circuit_name, "circuit_description": ckt_info["description"],
        "logic_thresholds": result["thresholds"], "expected_truth_table": expected_df.to_dict(orient="records"),
        "measured_truth_table": measured_list, "non_matching_cells": result["details"],
        "measurement_summary": {"total_cells": result["total_cells"], "valid_cells": result["valid_cells"],
                                "correct_matches": result["correct_matches"], "missing_cells": result["missing_cells"],
                                "invalid_cells": result["invalid_cells"], "mismatches": result["mismatches"],
                                "coverage_percent": result["coverage_pct"]},
        "deterministic_status": result["det_status"],
    }


def _ic_for_prompt(ica):
    if not ica.get("available"):
        return {"available": False, "reason": ica.get("reason")}
    keep = ("ref", "part_label", "function", "role_in_circuit", "vcc_pin", "gnd_pin", "input_pins", "output_pins", "expected_supply",
            "expected_logic_levels", "measured", "level_notes", "gates_tested_note", "verdict_code", "reasons", "confirmations_needed",
            "alternative_causes", "verification_steps")
    return {"family": ica["family"], "supply_evidence": ica["supply"], "user_reported_context": ica["context"],
            "pin_level_evidence": ica["pin_level_evidence"], "signal_flow": ica["signal_flow"],
            "per_output_summary": ica["outputs"], "ics": [{k: i[k] for k in keep} for i in ica["ics"]], "limitations": ica["limitations"]}


def build_digital_prompt(dataset, analysis, ica, knowledge):
    det = analysis["det_status"]
    k = knowledge or {}
    return f"""{LAB_ASSISTANT_PERSONA}

TASK: Analyse a digital circuit test performed by the NEXUS Electronic Circuit Tester and act as the student's lab assistant. Use the supplied expected truth table, actual measured truth table, raw voltages, classified logic states, comparison results and the Python-computed IC evidence.
The expected truth table and the PASS/FAIL/INCOMPLETE result are computed deterministically by the application: do not recalculate them as if unknown and do NOT override the deterministic result ({det}).

Analyse every provided row and output: identify matching outputs, mismatching outputs, missing and invalid measurements; state the tested coverage; identify which input combination produces an incorrect output; determine which gate or IC section may be responsible; explain possible causes (incorrect wiring, floating inputs, wrong VCC/GND, wrong IC pin mapping, poor connections, incorrect logic thresholds, sensor calibration errors, output loading, a defective gate/IC) and clearly distinguish hypotheses from confirmed evidence; recommend pin-by-pin verification; give a step-by-step correction and retest procedure.

CIRCUIT: {dataset['circuit_name']}
Objective = {k.get('objective', '')}
Working principle = {k.get('working_principle', '')}

DATASET (authoritative):
{json.dumps(dataset, indent=2, default=str)}

IC EVIDENCE COMPUTED BY PYTHON (authoritative). Each IC carries a verdict_code: HEALTHY_TESTED = appears healthy based on the tested gate(s) only; INSUFFICIENT_DATA = cannot be verified; MAY_BE_FAULTY = may be faulty (other causes not excluded); FAULT_STRONGLY_SUSPECTED = strongly suspected. These verdicts are FINAL: explain them, but do not upgrade or downgrade them. Never call an IC defective from one wrong output. NEXUS only measures OUTPUT-pin voltages; VCC, GND and input-pin levels were NOT measured unless listed in user_reported_context (and those are unverified). If pin-level data is missing, say explicitly that IC-level verification is incomplete. Do not claim an untested IC or untested gate has passed.
{json.dumps(_ic_for_prompt(ica), indent=2, default=str)}

{AI_PROBABILITY_RULES}
- If the deterministic result is INCOMPLETE, fault_probability and diagnosis confidence should normally be null (or low-confidence) and data_sufficiency "LIMITED" or "INSUFFICIENT DATA".
- If the deterministic result is PASS with 100 % coverage, say the circuit passed all tested rows; untested gates/internal nets remain unverified.
- ic_assessments must contain one entry per IC (use the ic_ref values above); do not include a verdict field.

Respond with ONLY one JSON object, no code fences, with exactly these keys:
{DIGITAL_JSON_SCHEMA}"""


def parse_digital_json(text, analysis, ica):
    """Validates the digital Gemini reply against the deterministic analysis and IC evidence."""
    d = _json_from_text(text)
    if d is None:
        return None
    steps = _as_list(d.get("recommended_steps"), 16, 600)
    if not steps:
        return None
    det, cov = analysis["det_status"], analysis.get("coverage_pct", 0.0)
    notes = []
    suff = _as_enum(d.get("data_sufficiency"), ("SUFFICIENT", "LIMITED", "INSUFFICIENT DATA"), "LIMITED")
    if det == "INCOMPLETE" and suff == "SUFFICIENT":
        suff = "LIMITED"
        notes.append("Data sufficiency was lowered to LIMITED because the deterministic result is INCOMPLETE.")
    cond = _as_enum(d.get("circuit_condition"), ("NORMAL", "WARNING", "FAULT", "CRITICAL", "INSUFFICIENT DATA"), "WARNING")
    if det == "PASS" and cond in ("FAULT", "CRITICAL"):
        cond = "WARNING"
    elif det == "FAIL" and cond in ("NORMAL", "INSUFFICIENT DATA"):
        cond = "FAULT"
    elif det == "INCOMPLETE" and cond in ("NORMAL", "FAULT", "CRITICAL"):
        cond = "INSUFFICIENT DATA"
    op = _as_enum(d.get("operating_correctly"), ("YES", "NO", "UNCERTAIN"), "UNCERTAIN")
    if det == "INCOMPLETE":
        op = "UNCERTAIN"
    elif det == "PASS" and op == "NO":
        op = "UNCERTAIN"
    elif det == "FAIL":
        op = "NO"
    fault_p, diag_p, guide = _as_pct(d.get("fault_probability")), _as_pct(d.get("overall_circuit_diagnosis_probability")), _as_pct(d.get("overall_circuit_guide_probability"))
    if suff == "INSUFFICIENT DATA":
        fault_p = diag_p = guide = None
    else:
        if det == "PASS" and fault_p is not None and fault_p > 30:
            notes.append(f"Gemini's fault probability ({fault_p} %) was rejected: it contradicts the deterministic PASS result.")
            fault_p = None
        if det == "FAIL" and fault_p is not None and fault_p < 30:
            notes.append(f"Gemini's fault probability ({fault_p} %) was rejected: it contradicts the deterministic FAIL result.")
            fault_p = None
        if cov < 50.0 and diag_p is not None and diag_p > 70:
            notes.append(f"Gemini's diagnosis confidence ({diag_p} %) was rejected: only {cov:.0f} % of the truth table was measured.")
            diag_p = None
    comps = _clean_components(d.get("component_fault_assessment"))
    wiring = _clean_wiring(d.get("wiring_fault_assessment"))
    if suff == "INSUFFICIENT DATA":
        for c in comps:
            c["probability_percent"] = None
        wiring["probability_percent"] = None
    # IC narratives: the verdict always comes from the Python evidence engine
    py_ics = {i["ref"]: i for i in (ica.get("ics", []) if ica else [])}
    ic_ai = []
    for x in (d.get("ic_assessments") if isinstance(d.get("ic_assessments"), list) else []):
        if not isinstance(x, dict):
            continue
        ref = _as_str(x.get("ic_ref"), 20)
        if ref not in py_ics:
            continue
        ai_verdict = _as_str(x.get("verdict"), 60).upper().replace(" ", "_")
        if ai_verdict and ai_verdict in _IC_RANK and ai_verdict != py_ics[ref]["verdict_code"]:
            notes.append(f"Gemini suggested '{ai_verdict}' for {ref}; the evidence-based verdict '{py_ics[ref]['verdict_code']}' is shown instead.")
        ic_ai.append({"ic_ref": ref, "explanation": _as_str(x.get("explanation"), 900), "pin_checks": _as_list(x.get("pin_checks"), 8, 500),
                      "still_unverified": _as_list(x.get("still_unverified"), 8, 400), "verdict_code": py_ics[ref]["verdict_code"]})
    return {
        "circuit_condition": cond, "data_sufficiency": suff, "operating_correctly": op,
        "circuit_health_assessment": _as_str(d.get("circuit_health_assessment"), 900),
        "fault_probability": fault_p, "overall_circuit_diagnosis_probability": diag_p, "overall_circuit_guide_probability": guide,
        "what_circuit_should_do": _as_str(d.get("what_circuit_should_do"), 1200),
        "what_measurements_indicate": _as_str(d.get("what_measurements_indicate"), 1500),
        "matching_rows_summary": _as_str(d.get("matching_rows_summary"), 900),
        "mismatch_analysis": [{"row": _as_str(m.get("row"), 10), "inputs": _as_str(m.get("inputs"), 120), "output": _as_str(m.get("output"), 40),
                               "expected": _as_str(m.get("expected"), 10), "measured_state": _as_str(m.get("measured_state"), 20),
                               "observation": _as_str(m.get("observation"), 500), "possible_causes": _as_list(m.get("possible_causes"), 6, 300)}
                              for m in (d.get("mismatch_analysis") if isinstance(d.get("mismatch_analysis"), list) else []) if isinstance(m, dict)][:24],
        "missing_or_invalid_summary": _as_str(d.get("missing_or_invalid_summary"), 900),
        "coverage_comment": _as_str(d.get("coverage_comment"), 500),
        "responsible_section": _as_str(d.get("responsible_section"), 500) or "Cannot be determined from the available data",
        "ic_assessments": ic_ai, "component_fault_assessment": comps, "wiring_fault_assessment": wiring,
        "sensor_reliability": _clean_sensor(d.get("sensor_reliability")),
        "suspected_component": _as_str(d.get("suspected_faulty_component"), 300) or "None",
        "supporting_evidence": _as_list(d.get("supporting_evidence"), 10, 500),
        "recommended_steps": steps, "corrective_actions": _as_list(d.get("corrective_actions"), 12, 500),
        "verification_procedure": _as_list(d.get("verification_procedure"), 12, 500),
        "final_retest_recommendation": _as_str(d.get("final_retest_recommendation"), 800),
        "teaching": _clean_teaching(d.get("teaching")), "lab_assistant_next_steps": _as_list(d.get("lab_assistant_next_steps"), 10, 500),
        "reasoning": _as_str(d.get("reasoning"), 2000), "limitations": _as_list(d.get("limitations"), 10, 500),
        "final_conclusion": _as_str(d.get("final_conclusion"), 900), "validation_notes": notes,
    }


def digital_structured_to_text(s, analysis):
    mm = "\n".join(f"- Row {m['row']} ({m['inputs']}), output {m['output']}: expected {m['expected']}, measured {m['measured_state']}. {m['observation']} "
                   f"Possible causes: {'; '.join(m['possible_causes'])}" for m in s.get("mismatch_analysis", [])) or "(none reported)"
    ic = "\n".join(f"- {i['ic_ref']} [{IC_VERDICTS.get(i['verdict_code'], i['verdict_code'])}]: {i['explanation']}" for i in s.get("ic_assessments", [])) or "(see the IC health assessment)"
    return f"""DETERMINISTIC RESULT (computed by NEXUS, not by AI):
{analysis['det_status']} - coverage {analysis['coverage_pct']:.1f} % ({analysis['valid_cells']}/{analysis['total_cells']} valid cells)

CIRCUIT CONDITION:
{s['circuit_condition']}

FAULT PROBABILITY (AI estimate that a fault exists):
{_fmt_pct(s.get('fault_probability'))}

DIAGNOSIS CONFIDENCE (AI estimate):
{_fmt_pct(s.get('overall_circuit_diagnosis_probability'))}

CONFIDENCE IN RECOMMENDED PROCEDURE (AI estimate):
{_fmt_pct(s.get('overall_circuit_guide_probability'))}

MATCHING ROWS:
{s.get('matching_rows_summary') or 'N/A'}

MISMATCH ANALYSIS:
{mm}

MISSING / INVALID MEASUREMENTS:
{s.get('missing_or_invalid_summary') or 'N/A'}

COVERAGE:
{s.get('coverage_comment') or 'N/A'}

RESPONSIBLE SECTION:
{s.get('responsible_section')}

SUSPECTED COMPONENT / SECTION:
{s.get('suspected_component')}

IC HEALTH (evidence-based verdicts from NEXUS, explained by AI):
{ic}

WHY:
{s.get('reasoning') or 'N/A'}

RECOMMENDED TROUBLESHOOTING:
{_bullets(s.get('recommended_steps', []), True)}

""" + _lab_text_sections(s)


def finalize_digital_gemini(result, raw_text, error):
    """Writes the Gemini outcome into the (frozen) digital analysis result dict."""
    result["gemini_structured"] = None
    result["gemini_validation_notes"] = []
    if error:
        result["gemini_status"], result["gemini_error"] = "ERROR", error
        return result
    if not raw_text:
        result["gemini_status"], result["gemini_error"] = "ERROR", "Gemini returned an empty response."
        return result
    s = parse_digital_json(raw_text, result, result.get("ic_assessment"))
    result["gemini_status"], result["gemini_error"] = "OK", None
    if s is None:
        result["gemini_report"] = raw_text.replace("**", "").strip()
        result["gemini_validation_notes"] = ["Gemini did not return valid structured JSON; its raw text is shown unvalidated."]
    else:
        result["gemini_structured"] = s
        result["gemini_validation_notes"] = list(s.get("validation_notes", []))
        result["gemini_report"] = digital_structured_to_text(s, result)
    return result


def friendly_pending_text(started_at):
    return f"Gemini is analysing the frozen snapshot... {max(0, int(time.time() - started_at))} s (live telemetry keeps updating)."



def save_gemini_to_history(circuit_name, user_question, answer, metrics=None, status=None):
    if not user_question or not str(user_question).strip():
        return
    if not answer or not str(answer).strip():
        return
    metrics = metrics or {}
    now = datetime.datetime.now()
    st.session_state.historical_tests.append({
        "Date": now.strftime("%Y-%m-%d"),
        "Time": now.strftime("%H:%M:%S"),
        "Circuit": circuit_name,
        "Status": status if status else "N/A",
        "Input Voltage (V)": f"{metrics.get('input_v')} V" if metrics.get('input_v') is not None else "N/A",
        "Output Voltage (V)": f"{metrics.get('output_v')} V" if metrics.get('output_v') is not None else "N/A",
        "Efficiency %": f"{metrics.get('efficiency')} %" if metrics.get('efficiency') is not None else "N/A",
        "AI Answer / Diagnosis": str(answer),
        "User Question": str(user_question)
    })

_PDF_CHAR_MAP = {
    "Ω": " ohm", "Ω": " ohm", "µ": "u", "μ": "u", "—": "-", "–": "-", "→": "->",
    "≤": "<=", "≥": ">=", "±": "+/-", "×": "x", "✓": "", "⚡": "",
    "⊕": "(+)", "≈": "~", "√": "sqrt", "π": "pi", "−": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "•": "-", "…": "...",
}

def _pdf_safe(value):
    text = str(value if value is not None else "N/A")
    for k, v in _PDF_CHAR_MAP.items():
        text = text.replace(k, v)
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

_DIAG_HEADINGS = {
    "NEXUS AI DIAGNOSTIC REPORT", "CIRCUIT", "ANALYSIS SOURCE", "OVERALL RESULT", "MEASURED PARAMETERS",
    "TECHNICAL ANALYSIS", "PROBABLE FAULT", "SUSPECTED COMPONENT / SECTION", "FAULT PROBABILITY",
    "DIAGNOSIS CONFIDENCE", "WHY", "RECOMMENDED TROUBLESHOOTING", "FINAL CONCLUSION",
    "CIRCUIT CONDITION", "DETECTED PROBLEM", "OVERALL CIRCUIT GUIDE", "OVERALL CIRCUIT DIAGNOSIS",
    "PROBLEM RESOLUTION", "LIVE FREQUENCY / TEMPERATURE",
}

def generate_diagnostic_report_pdf(result):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title="NEXUS AI Electronic Circuit Diagnostic Report")
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    small = ParagraphStyle("nx_small", parent=normal, fontSize=9, leading=12)
    h2 = ParagraphStyle("nx_h2", parent=styles["Heading2"], textColor=colors.HexColor("#0b3c5d"), spaceBefore=10, spaceAfter=4)
    sub = ParagraphStyle("nx_sub", parent=normal, alignment=1, fontSize=11, textColor=colors.HexColor("#0b3c5d"))
    title = ParagraphStyle("nx_title", parent=styles["Title"], fontSize=16, leading=20, textColor=colors.HexColor("#0b3c5d"))
    diag_head = ParagraphStyle("nx_dh", parent=normal, fontName="Helvetica-Bold", fontSize=10, spaceBefore=6, textColor=colors.HexColor("#0b3c5d"))
    diag_body = ParagraphStyle("nx_db", parent=normal, fontSize=9.5, leading=13)

    def tbl(rows, widths, header=True, align_right_from=None):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        style = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fb3c8")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3c5d")),
                      ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                      ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        if align_right_from is not None:
            style.append(("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"))
        t.setStyle(TableStyle(style))
        return t

    ts = result["timestamp"]
    info = result["circuit_info"]
    snap = result["sensor"]
    targets = result["targets"]
    dev = result["deviations"]
    el = []

    el.append(Paragraph("NEXUS - AI-BASED ELECTRONIC CIRCUIT TESTER", title))
    el.append(Paragraph("<b>AI ELECTRONIC CIRCUIT DIAGNOSTIC REPORT</b>", sub))
    el.append(Spacer(1, 8))

    el.append(Paragraph("Project Information", h2))
    rows = [
        ["Selected circuit", _pdf_safe(result["circuit"])],
        ["Circuit category", _pdf_safe(result.get("category", "N/A"))],
        ["Date", ts.strftime("%Y-%m-%d")],
        ["Time", ts.strftime("%H:%M:%S")],
        ["Analysis source", _pdf_safe(result["source"])],
        ["ESP32 status", _pdf_safe(result.get("esp32_status", "N/A"))],
        ["MQTT status", _pdf_safe(result.get("mqtt_status", "N/A"))],
        ["Analysis engine", _pdf_safe(result.get("engine", "GEMINI"))],
    ]
    if result["source"] == "HELD" and snap.get("captured_at"):
        rows.insert(5, ["Snapshot captured", snap["captured_at"].strftime("%H:%M:%S")])
    rows = [[Paragraph(f"<b>{a}</b>", small), Paragraph(b, small)] for a, b in rows]
    el.append(tbl(rows, [45 * mm, 130 * mm], header=False))

    el.append(Paragraph("Circuit Information", h2))
    el.append(Paragraph(f"<b>Description:</b> {_pdf_safe(info.get('description'))}", small))
    el.append(Paragraph(f"<b>Components:</b> {_pdf_safe(info.get('components'))}", small))
    el.append(Paragraph(f"<b>Circuit topology:</b> {_pdf_safe(info.get('diagram'))}", small))
    el.append(Paragraph("<b>Probe locations:</b>", small))
    for pr in info.get("probes", []):
        el.append(Paragraph(f"&nbsp;&nbsp;Step {_pdf_safe(pr.get('step'))} - {_pdf_safe(pr.get('name'))}: {_pdf_safe(pr.get('loc'))}", small))

    el.append(Paragraph("Target vs Measured", h2))
    data = [["Parameter", "Target", "Measured", "Deviation"],
            ["Input Voltage", f"{_fmt(targets['target_input_voltage'])} V", f"{_fmt(snap['input_v'])} V", f"{_fmt(dev['Input Voltage'])} %"],
            ["Output Voltage", f"{_fmt(targets['target_output_voltage'])} V", f"{_fmt(snap['output_v'])} V", f"{_fmt(dev['Output Voltage'])} %"],
            ["Input Current", f"{_fmt(targets['target_input_current'])} A", f"{_fmt(snap['input_i'])} A", f"{_fmt(dev['Input Current'])} %"],
            ["Output Current", f"{_fmt(targets['target_output_current'])} A", f"{_fmt(snap['output_i'])} A", f"{_fmt(dev['Output Current'])} %"]]
    el.append(tbl(data, [55 * mm, 40 * mm, 40 * mm, 40 * mm], align_right_from=1))

    el.append(Paragraph("Electrical Calculations", h2))
    calc = [["Quantity", "Value"],
            ["Input Power", f"{_fmt(snap['power_in'])} W"],
            ["Output Power", f"{_fmt(snap['power_out'])} W"],
            ["Efficiency", f"{_fmt(snap['efficiency'])} %"],
            ["Voltage Drop", f"{_fmt(snap['v_drop'])} V"],
            ["Frequency", f"{_fmt(snap['frequency'], 1)} Hz"],
            ["Temperature", f"{_fmt(snap['temperature'], 1)} C"],
            ["Circuit Health", f"{snap.get('health', 0)} %"]]
    el.append(tbl(calc, [80 * mm, 95 * mm], align_right_from=1))

    el.append(Paragraph("AI Diagnosis", h2))
    fp, cf = result.get("fault_probability"), result.get("confidence")
    summary = [["Overall result", "Fault probability", "Diagnosis confidence"],
               [_pdf_safe(result["status"]), f"{fp} %" if fp is not None else "N/A", f"{cf} %" if cf is not None else "N/A"]]
    el.append(tbl(summary, [58 * mm, 58 * mm, 59 * mm]))
    el.append(Spacer(1, 6))

    for line in result["text"].splitlines():
        clean = line.strip()
        if not clean:
            el.append(Spacer(1, 3))
            continue
        key = clean.rstrip(":").strip().upper()
        _is_caps_heading = (clean.endswith(":") and clean == clean.upper()
                            and re.sub(r"[ /\-(),]", "", clean[:-1]).isalpha())
        if key in _DIAG_HEADINGS and clean.endswith(":") or clean.upper() == "NEXUS AI DIAGNOSTIC REPORT" or _is_caps_heading:
            el.append(Paragraph(_pdf_safe(clean), diag_head))
        else:
            el.append(Paragraph(_pdf_safe(clean), diag_body))

    doc.build(el)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def save_analysis_to_history(result):
    snap = result["sensor"]
    ts = result["timestamp"]
    result["test_id"] = new_test_id(ts)
    st.session_state.historical_tests.append({
        "Test ID": result["test_id"],
        "Date": ts.strftime("%Y-%m-%d"),
        "Time": ts.strftime("%H:%M:%S"),
        "Circuit": result["circuit"],
        "Status": result["status"],
        "Input Voltage (V)": f"{snap['input_v']} V",
        "Output Voltage (V)": f"{snap['output_v']} V",
        "Efficiency %": f"{snap['efficiency']} %",
        "AI Answer / Diagnosis": result["text"],
        "Timestamp": ts.isoformat(timespec="seconds"),
        "Analysis Source": result["source"],
        "Input Current (A)": f"{snap['input_i']} A",
        "Output Current (A)": f"{snap['output_i']} A",
        "Fault Probability": f"{result['fault_probability']} %" if result.get("fault_probability") is not None else "N/A",
        "Diagnosis Confidence": f"{result['confidence']} %" if result.get("confidence") is not None else "N/A",
    })
    # Frozen copy of this exact test, selectable on the Generate Report page.
    st.session_state.analysis_records.append({
        "test_id": result["test_id"], "kind": "analogue", "circuit": result["circuit"],
        "category": result.get("category", "N/A"), "timestamp": ts,
        "result": copy.deepcopy({k: v for k, v in result.items() if k != "pdf_bytes"}),
    })
    st.session_state.report_selected_test = result["test_id"]

def run_gemini_analysis(circuit_info, active_targets):
    packet, packet_time = get_latest_packet_and_time()
    if packet is None:
        st.warning("No valid sensor data available for analysis.")
        return
    esp_state, age = get_esp32_status()
    if esp_state != "ONLINE":
        age_txt = f"{age:.0f} s ago" if age is not None else "unknown"
        st.warning(f"ESP32 is {esp_state} (last valid packet: {age_txt}). Analysis needs fresh live output telemetry - wait for the ESP32.")
        return
    if st.session_state.get("gemini_pending"):
        st.warning("A Gemini analysis is already running - wait for it to finish (live readings keep updating).")
        return
    if is_data_held():
        raw = merge_held_input(packet)
        snapshot = build_sensor_data(raw, circuit_info)
        snapshot["packet_time"] = packet_time
        snapshot["captured_at"] = st.session_state.held_input_data["captured_at"]
        source = "HELD"
    else:
        raw = packet
        snapshot = get_live_sensor_data(circuit_info)
        source = "LIVE"

    missing = validate_sensor_packet(raw)
    if missing:
        st.error("Cannot analyse - required measurement(s) missing from the packet: " + ", ".join(missing))
        return

    # Everything below is FROZEN now: the snapshot, targets, circuit and ESP32/MQTT state of this exact test.
    client = get_gemini_client()
    esp_state, esp_age = get_esp32_status()
    esp_txt = esp_state + (f" (last packet {esp_age:.1f} s ago)" if esp_age is not None else "")
    ctx = prepare_automatic_diagnosis(
        st.session_state.selected_circuit, circuit_info, snapshot, circuit_info["probes"],
        snapshot["frequency"], snapshot["temperature"], analysis_source=source, active_targets=active_targets,
        use_ai=client is not None)
    meta = {
        "timestamp": datetime.datetime.now(), "circuit": st.session_state.selected_circuit,
        "category": st.session_state.selected_category,
        "circuit_info": {k: circuit_info.get(k) for k in ("description", "components", "diagram", "probes", "exp_eff")},
        "snapshot": snapshot, "source": source, "esp32_status": esp_txt, "mqtt_status": get_mqtt_connection_status().upper(),
    }
    st.session_state.gemini_notice = None
    if client is None:
        _complete_analysis(ctx, meta, finalize_automatic_diagnosis(ctx, None, None))
        return
    _status = ctx["status"]
    job_id = start_gemini_job(client, ctx["prompt"], lambda t, _s=_status: parse_gemini_json(t, _s) is not None)
    st.session_state.gemini_pending = {"job_id": job_id, "ctx": ctx, "meta": meta, "started": time.time()}

RESOLUTION_TOLERANCE_PCT = 5.0

def make_resolution_baseline(snapshot, deviations, targets):
    return {
        "deviations": dict(deviations),
        "efficiency": snapshot.get("efficiency"),
        "input_v": snapshot.get("input_v"), "input_i": snapshot.get("input_i"),
        "output_v": snapshot.get("output_v"), "output_i": snapshot.get("output_i"),
    }

def initial_resolution(status):
    if status == "PASS":
        return {"percent": 100, "status": "No problem detected - nothing to resolve",
                "reasoning": ["All four measurements were within +-5 % of target when analysed."],
                "terms": [], "verified_at": None, "source": None}
    return {"percent": 0, "status": "Verification required",
            "reasoning": ["Follow the recommended steps, then press VERIFY / RE-TEST to measure the result."],
            "terms": [], "verified_at": None, "source": None}

def _target_efficiency(targets):
    t_in = targets["target_input_voltage"] * targets["target_input_current"]
    t_out = targets["target_output_voltage"] * targets["target_output_current"]
    return (t_out / t_in * 100.0) if t_in > 0 else 0.0

def compute_problem_resolution(baseline, new_snap, targets, new_source):
    tol = RESOLUTION_TOLERANCE_PCT
    new_status, new_dev = evaluate_pass_fail_status(targets, new_snap)
    terms = []

    def add(name, d0, d1):
        if d0 > tol:
            if d1 <= tol:
                r, note = 1.0, "back within tolerance"
            elif d1 >= d0 - 0.05:
                r, note = 0.0, ("worse" if d1 > d0 + 0.05 else "unchanged")
            else:
                r, note = (d0 - d1) / (d0 - tol), "improved, still outside tolerance"
        elif d1 > tol:
            r, note = 0.0, "NEW deviation (was within tolerance)"
        else:
            return
        terms.append({"name": name, "before": d0, "after": d1, "score": r, "note": note})

    for name, d1 in new_dev.items():
        add(name, baseline["deviations"][name], d1)

    t_eff = _target_efficiency(targets)
    e_before, e_after = baseline.get("efficiency"), new_snap.get("efficiency")
    if t_eff > 0 and e_before is not None and e_after is not None:
        add("Efficiency", abs(e_before - t_eff) / t_eff * 100.0, abs(e_after - t_eff) / t_eff * 100.0)

    percent = int(round(sum(t["score"] for t in terms) / len(terms) * 100)) if terms else 100
    any_worse = any(t["note"] in ("worse",) or t["note"].startswith("NEW") for t in terms)

    if not terms:
        status = "Within tolerance - no problem present"
    elif percent >= 100:
        status = "Resolved - verified by measurement"
    elif any_worse and percent == 0:
        status = "Worse than before - problem not resolved"
    elif percent >= 60:
        status = "Substantially improved - re-test after further checks"
    elif percent > 0:
        status = "Partially improved - continue troubleshooting"
    else:
        status = "Not resolved - no measurable improvement"

    lines = [f"{t['name']}: deviation {t['before']:.1f} % -> {t['after']:.1f} % ({t['note']})" for t in terms]
    if not lines:
        lines = ["No quantity was outside +-5 % before or after."]
    lines.append(f"Resolution = mean of {len(terms)} term(s) = {percent} %." if terms else "Nothing to resolve.")
    if new_source == "HELD" and any(t["name"] in ("Input Voltage", "Input Current") and t["score"] < 1 for t in terms):
        lines.append("Note: Input V/I are still HELD at the earlier capture, so their deviation cannot change. "
                     "RELEASE then HOLD again to capture the input after your repair.")
    lines.append("Based on a single live sample taken when VERIFY / RE-TEST was pressed.")
    return {"percent": percent, "status": status, "reasoning": lines, "terms": terms,
            "verified_at": datetime.datetime.now(), "source": new_source,
            "after": {"output_v": new_snap.get("output_v"), "output_i": new_snap.get("output_i"),
                      "input_v": new_snap.get("input_v"), "input_i": new_snap.get("input_i"),
                      "efficiency": new_snap.get("efficiency"), "status": new_status}}

def run_verification(result):
    if st.session_state.selected_circuit != result["circuit"]:
        st.warning(f"The selected circuit changed since the analysis ({result['circuit']}). Re-run ANALYZE for the new circuit.")
        return
    packet, _t = get_latest_packet_and_time()
    esp_state, age = get_esp32_status()
    if packet is None or esp_state != "ONLINE":
        st.warning(f"ESP32 is {esp_state}. Verification needs fresh live output telemetry.")
        return
    missing = validate_sensor_packet(merge_held_input(packet))
    if missing:
        st.error("Cannot verify - measurement(s) missing from the packet: " + ", ".join(missing))
        return
    new_snap = get_testing_sensor_data(get_current_circuit_data())
    res = compute_problem_resolution(result["baseline"], new_snap, result["targets"], new_snap["source"])
    result["resolution"] = res
    result.setdefault("verifications", []).append(res)

_COND_COLORS = {"NORMAL": "#00ff87", "WARNING": "#ffb703", "FAULT": "#ff6b35", "CRITICAL": "#ff0055"}

def _bar_html(label, pct, color):
    _na = pct is None
    pct = 0 if _na else max(0, min(100, int(pct)))
    _lbl = "N/A" if _na else f"{pct}%"
    return (f'<div style="margin:8px 0;"><div style="display:flex; justify-content:space-between; font-family:Orbitron,sans-serif; font-size:0.8rem;">'
            f'<span style="color:#c8d6e5;">{label}</span><span style="color:{color}; font-weight:700;">{_lbl}</span></div>'
            f'<div style="background:rgba(255,255,255,0.08); border-radius:6px; height:12px; overflow:hidden;">'
            f'<div style="width:{pct}%; height:100%; background:{color};"></div></div></div>')

def render_nexus_ai_dashboard(result):
    s = result["structured"]
    cc = _COND_COLORS.get(s["circuit_condition"], "#00f2fe")
    steps_html = "".join(
        f'<div style="margin:6px 0;"><b style="color:#00f2fe; font-family:Orbitron,sans-serif; font-size:0.78rem;">STEP {i}</b>'
        f'<div style="color:#c8d6e5;">{html.escape(x)}</div></div>'
        for i, x in enumerate(s["recommended_steps"], 1))
    st.markdown(f"""
    <div class="os-card" style="border-left: 5px solid {cc} !important;">
        <div style="text-align:center; font-family:Orbitron,sans-serif; color:#00f2fe; letter-spacing:3px; font-weight:700; font-size:1.1rem;">NEXUS AI DIAGNOSIS</div>
        {_bar_html("FAULT PROBABILITY - chance a fault exists (estimate)", s.get("fault_probability"), "#ff6b35")}
        {_bar_html("DIAGNOSIS CONFIDENCE - diagnosis is correct (estimate)", s["overall_circuit_diagnosis_probability"], "#9d4edd")}
        {_bar_html("CONFIDENCE IN RECOMMENDED PROCEDURE (estimate)", s["overall_circuit_guide_probability"], "#00f2fe")}
        <div style="margin:14px 0 6px 0; font-family:Orbitron,sans-serif;">CIRCUIT CONDITION:
            <span style="color:{cc}; font-weight:700; border:1px solid {cc}; border-radius:6px; padding:2px 10px;">{s["circuit_condition"]}</span></div>
        <div style="margin-top:10px;"><b style="color:#00f2fe; font-family:Orbitron,sans-serif; font-size:0.8rem;">DETECTED PROBLEM</b>
            <div style="color:#ffffff;">{html.escape(s["detected_problem"])}</div></div>
        <div style="margin-top:10px;"><b style="color:#00f2fe; font-family:Orbitron,sans-serif; font-size:0.8rem;">DIAGNOSIS</b>
            <div style="color:#c8d6e5;">{html.escape(s["diagnosis"])}</div></div>
        <div style="margin-top:10px;"><b style="color:#00f2fe; font-family:Orbitron,sans-serif; font-size:0.8rem;">RECOMMENDED STEPS</b>{steps_html}</div>
        <div style="margin-top:10px;"><b style="color:#00f2fe; font-family:Orbitron,sans-serif; font-size:0.8rem;">REASONING</b>
            <div style="color:#c8d6e5;">{html.escape(s["reasoning"])}</div></div>
    </div>""", unsafe_allow_html=True)

    render_lab_assistant_cards(s, "analogue", result.get("evidence"))

    st.markdown("#### 🔧 CIRCUIT PROBLEM RESOLUTION")
    if result.get("baseline") is not None and result["status"] != "PASS":
        if st.button("🔁 VERIFY / RE-TEST", key="verify_retest_btn", use_container_width=True,
                     help="Follow the recommended steps first. Compares a NEW measurement (held input + live output) with the values measured at diagnosis."):
            run_verification(result)
    res = result["resolution"]
    rc = "#00ff87" if res["percent"] >= 85 else ("#ffb703" if res["percent"] >= 40 else "#ff0055")
    verified = res.get("verified_at") is not None
    if not verified and result["status"] != "PASS":
        rc = "#8fa3b8"
    n_ver = len(result.get("verifications", []))
    lines_html = "".join(f"<li>{html.escape(x)}</li>" for x in res["reasoning"])
    when = f" | VERIFIED {res['verified_at'].strftime('%H:%M:%S')} ({res['source']} input / LIVE output) | RE-TESTS: {n_ver}" if verified else ""
    st.markdown(f"""
    <div class="os-card" style="border-left: 5px solid {rc} !important;">
        {_bar_html("PROBLEM RESOLUTION", res["percent"], rc)}
        <div style="font-family:Orbitron,sans-serif; color:{rc}; font-weight:700;">{html.escape(res["status"])}<span style="color:#8fa3b8; font-weight:400; font-size:0.75rem;">{when}</span></div>
        <ul style="color:#c8d6e5; margin-top:8px;">{lines_html}</ul>
    </div>""", unsafe_allow_html=True)

def render_analysis_result(result):
    src_color = "#ffb703" if result["source"] == "HELD" else "#00ff87"
    src_note = "HELD INPUT V/I vs LIVE OUTPUT V/I (+ LIVE frequency/temperature)" if result["source"] == "HELD" else "ALL LIVE"
    st.markdown(f"""
    <div class="os-card" style="border-left: 5px solid {src_color} !important;">
        <p style="margin:0;"><b>ANALYSIS SOURCE:</b> <span style="color:{src_color};">{result['source']}</span> ({src_note})
        &nbsp;|&nbsp; <b>ENGINE:</b> {html.escape(result['engine'])}
        &nbsp;|&nbsp; <b>COMPLETED:</b> {result['timestamp'].strftime('%H:%M:%S')}</p>
    </div>
    """, unsafe_allow_html=True)

    if result.get("structured") is not None:
        render_nexus_ai_dashboard(result)
        with st.expander("📋 FULL TEXT REPORT (as saved to history / PDF)"):
            st.markdown(
                f"<pre style='white-space: pre-wrap; font-family: Rajdhani, sans-serif; font-size: 1.0rem; color: #c8d6e5;'>{html.escape(result['text'])}</pre>",
                unsafe_allow_html=True)
        if result.get("payload"):
            with st.expander("📡 DATA SENT TO GEMINI (source map + values)"):
                st.json(result["payload"])
    else:
        st.warning("Gemini did not return structured JSON - showing the raw text. Press ANALYZE WITH GEMINI to retry.")
        st.markdown(
            f"<div class='os-card'><pre style='white-space: pre-wrap; font-family: Rajdhani, sans-serif; font-size: 1.05rem; color: #c8d6e5;'>{html.escape(result['text'])}</pre></div>",
            unsafe_allow_html=True)

    if result.get("pdf_bytes") is None:
        try:
            result["pdf_bytes"] = generate_diagnostic_report_pdf(result)
        except Exception as e:
            st.error(f"PDF generation failed: {e}")
            return
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", result["circuit"])
    st.download_button(
        label="📄 DOWNLOAD DIAGNOSTIC REPORT",
        data=result["pdf_bytes"],
        file_name=f"NEXUS_Diagnostic_{safe_name}_{result['timestamp'].strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf",
        key="download_diagnostic_report_btn",
        use_container_width=True,
    )
    if st.button("📑 CREATE STUDENT TEST REPORT FROM THIS TEST →", key="goto_report_btn", use_container_width=True):
        st.session_state.report_selected_test = result.get("test_id")
        st.session_state.page = "Generate Report"
        st.rerun()

# ==============================================================================
# LOGIC / CIRCUIT DIAGRAM ENGINE (pure Python - no extra dependencies)
# One circuit definition (build_logic_diagram) is rendered twice:
#   * render_diagram_svg()      -> dashboard (inline SVG)
#   * render_diagram_drawing()  -> ReportLab vector Drawing for the PDF report
# ==============================================================================
_DIAG_STROKE = "#1b2a41"
_DIAG_FILL = "#eaf4ff"
_DIAG_WIRE = "#1b2a41"
_DIAG_CAPTION = "#5b6b80"


class LogicDiagram:
    """Tiny scene description: wires, standard gate symbols, dots and text.
    Coordinates are SVG-style (origin top-left, y grows downwards)."""

    GATE_W = 50.0
    GATE_H = 40.0

    def __init__(self, width, height, title="Logic diagram"):
        self.width = float(width)
        self.height = float(height)
        self.title = title
        self.items = []

    # -- primitives ---------------------------------------------------------
    def wire(self, *pts):
        self.items.append(("poly", [(float(x), float(y)) for x, y in pts]))

    def dot(self, x, y):
        self.items.append(("circle", float(x), float(y), 3.2, True))

    def text(self, x, y, s, anchor="middle", size=12, bold=False, color=_DIAG_STROKE):
        self.items.append(("text", float(x), float(y), str(s), anchor, float(size), bool(bold), color))

    def box(self, x, y, w, h, label=None):
        self.items.append(("rect", float(x), float(y), float(w), float(h)))
        if label:
            self.text(x + w / 2.0, y + h / 2.0 + 4, label, size=12, bold=True)

    # -- standard gate symbols ---------------------------------------------
    def gate(self, kind, x, y, caption=None):
        """Draws a standard gate symbol with its top-left body corner at (x, y).
        Returns the pin coordinates: {'a': (x, y), 'b': (x, y), 'out': (x, y)}
        (NOT gates only have 'a')."""
        kind = kind.upper()
        W, H = self.GATE_W, self.GATE_H
        inverted = kind in ("NAND", "NOR", "XNOR", "NOT")
        pins = {}
        if kind == "NOT":
            tri = [("M", x, y + 4), ("L", x, y + H - 4), ("L", x + 36, y + H / 2), ("Z",)]
            self.items.append(("path", tri, True))
            self.items.append(("circle", x + 40, y + H / 2, 4.0, False))
            pins["a"] = (x, y + H / 2)
            pins["out"] = (x + 44, y + H / 2)
            if caption:
                self.text(x + 22, y + H + 12, caption, size=9, color=_DIAG_CAPTION)
            return pins

        base = kind[1:] if kind in ("NAND", "NOR", "XNOR") else kind
        if base == "AND":
            cx, cy = x + 25.0, y + H / 2.0
            cmds = [("M", x, y), ("L", cx, y)]
            steps = 14
            for i in range(1, steps + 1):
                a = math.radians(-90.0 + 180.0 * i / steps)
                cmds.append(("L", cx + 25.0 * math.cos(a), cy + 20.0 * math.sin(a)))
            cmds += [("L", x, y + H), ("Z",)]
            pin_x = x
        else:  # OR / XOR family
            cmds = [("M", x, y), ("Q", x + 28, y, x + W, y + H / 2),
                    ("Q", x + 28, y + H, x, y + H),
                    ("Q", x + 12, y + H / 2, x, y), ("Z",)]
            pin_x = x + 4.5
        self.items.append(("path", cmds, True))
        if base == "XOR":
            self.items.append(("path", [("M", x - 6, y), ("Q", x + 6, y + H / 2, x - 6, y + H)], False))
            pin_x = x - 1.5
        pins["a"] = (pin_x, y + 10)
        pins["b"] = (pin_x, y + 30)
        if inverted:
            self.items.append(("circle", x + W + 4, y + H / 2, 4.0, False))
            pins["out"] = (x + W + 8, y + H / 2)
        else:
            pins["out"] = (x + W, y + H / 2)
        if caption:
            self.text(x + W / 2.0, y + H + 12, caption, size=9, color=_DIAG_CAPTION)
        return pins

    # -- extra primitives used by the analogue (rectifier) schematics ---------------
    def dwire(self, *pts):
        """Dashed polyline - used for measurement-probe leads."""
        self.items.append(("dpoly", [(float(x), float(y)) for x, y in pts]))

    def ring(self, x, y, r=3.8):
        """Open circle = external terminal."""
        self.items.append(("circle", float(x), float(y), float(r), False))

    @staticmethod
    def _frame(x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        u = (dx / length, dy / length)
        n = (-u[1], u[0])
        return length, u, n, (x1 + dx / 2.0, y1 + dy / 2.0)

    def resistor(self, x1, y1, x2, y2, body=46.0, amp=6.0):
        length, u, n, m = self._frame(x1, y1, x2, y2)
        body = min(body, length - 8.0)

        def pt(a, b):
            return (m[0] + u[0] * a + n[0] * b, m[1] + u[1] * a + n[1] * b)
        pts = [pt(-body / 2.0, 0)]
        for i in range(6):
            pts.append(pt(-body / 2.0 + body * (i + 0.5) / 6.0, amp if i % 2 == 0 else -amp))
        pts.append(pt(body / 2.0, 0))
        self.wire((x1, y1), pts[0])
        self.wire(*pts)
        self.wire(pts[-1], (x2, y2))

    def capacitor(self, x1, y1, x2, y2, polarized=True, gap=6.0, plate=18.0):
        """Capacitor between two points. For a polarised capacitor (x1, y1) is the + side."""
        length, u, n, m = self._frame(x1, y1, x2, y2)

        def pt(a, b):
            return (m[0] + u[0] * a + n[0] * b, m[1] + u[1] * a + n[1] * b)
        self.wire((x1, y1), pt(-gap / 2.0, 0))
        self.wire(pt(gap / 2.0, 0), (x2, y2))
        self.wire(pt(-gap / 2.0, -plate / 2.0), pt(-gap / 2.0, plate / 2.0))
        if polarized:
            e1, e2, c = pt(gap / 2.0, -plate / 2.0), pt(gap / 2.0, plate / 2.0), pt(gap / 2.0 + 7.0, 0)
            self.items.append(("path", [("M", e1[0], e1[1]), ("Q", c[0], c[1], e2[0], e2[1])], False))
            px, py = pt(-gap / 2.0 - 5.0, -plate / 2.0 - 3.0)
            self.text(px, py + 4, "+", size=11, bold=True)
        else:
            self.wire(pt(gap / 2.0, -plate / 2.0), pt(gap / 2.0, plate / 2.0))

    def diode(self, x1, y1, x2, y2, size=9.0, length=16.0):
        """Diode with the anode at (x1, y1) and the cathode at (x2, y2)."""
        _l, u, n, m = self._frame(x1, y1, x2, y2)

        def pt(a, b):
            return (m[0] + u[0] * a + n[0] * b, m[1] + u[1] * a + n[1] * b)
        a, b, tip = pt(-length / 2.0, -size), pt(-length / 2.0, size), pt(length / 2.0, 0)
        self.items.append(("path", [("M", a[0], a[1]), ("L", b[0], b[1]), ("L", tip[0], tip[1]), ("Z",)], True))
        self.wire(pt(length / 2.0, -size), pt(length / 2.0, size))
        self.wire((x1, y1), pt(-length / 2.0, 0))
        self.wire(pt(length / 2.0, 0), (x2, y2))

    def ground(self, x, y):
        self.wire((x, y), (x, y + 8))
        self.wire((x - 11, y + 8), (x + 11, y + 8))
        self.wire((x - 7, y + 12.5), (x + 7, y + 12.5))
        self.wire((x - 3, y + 17), (x + 3, y + 17))

    def ac_source(self, x, y, r=16.0):
        self.items.append(("circle", float(x), float(y), float(r), False))
        self.items.append(("path", [("M", x - 9, y), ("Q", x - 4.5, y - 13, x, y),
                                    ("Q", x + 4.5, y + 13, x + 9, y)], False))

    def meter(self, x, y, letter, r=11.0):
        self.items.append(("circle", float(x), float(y), float(r), False))
        self.text(x, y + 4.5, letter, size=12, bold=True)

    def transformer(self, x, y_top, y_bot, loops=4):
        """Primary coil (bulging left) at x, secondary coil (bulging right) at x + 48.
        Returns the terminal coordinates."""
        h = (y_bot - y_top) / float(loops)
        r = 9.0
        for sign, cx in ((-1.0, x), (1.0, x + 48.0)):
            cmds = [("M", cx, y_top)]
            for i in range(loops):
                y0 = y_top + i * h
                cmds.append(("Q", cx + sign * 2.0 * r, y0 + h / 2.0, cx, y0 + h))
            self.items.append(("path", cmds, False))
        self.wire((x + 22, y_top), (x + 22, y_bot))
        self.wire((x + 28, y_top), (x + 28, y_bot))
        ym = (y_top + y_bot) / 2.0
        return {"p_top": (x, y_top), "p_bot": (x, y_bot), "s_top": (x + 48.0, y_top),
                "s_bot": (x + 48.0, y_bot), "s_ct": (x + 48.0, ym)}

    def vwire_hops(self, x, y1, y2, hops=(), r=5.0):
        """Vertical wire with small bridge arcs where it crosses other wires (crossing = no junction)."""
        direction = 1.0 if y2 >= y1 else -1.0
        cur = float(y1)
        for hy in sorted(hops, reverse=(direction < 0)):
            a, b = hy - direction * r, hy + direction * r
            self.wire((x, cur), (x, a))
            self.items.append(("path", [("M", x, a), ("Q", x + 2.0 * r, hy, x, b)], False))
            cur = b
        self.wire((x, cur), (x, y2))



def _bus_inputs(d, names, bus_xs, feed_ys, bus_ends, label_x=30, start_x=36):
    """Draws labelled input feeds and vertical buses. Returns a tap(name, y, to_x) helper."""
    info = {}
    for nm, bx, fy, be in zip(names, bus_xs, feed_ys, bus_ends):
        d.text(label_x, fy + 4, nm, anchor="end", size=13, bold=True)
        d.wire((start_x, fy), (bx, fy), (bx, be))
        info[nm] = (bx, fy)

    def tap(name, y, to_x, dot=True):
        bx, fy = info[name]
        if dot and abs(y - fy) > 0.1:
            d.dot(bx, y)
        d.wire((bx, y), (to_x, y))
    return tap


def _out_label(d, pin, label, length=70):
    x, y = pin
    d.wire((x, y), (x + length, y))
    d.text(x + length + 8, y + 4, label, anchor="start", size=13, bold=True)


def _build_single_gate(kind, label_out="Y"):
    d = LogicDiagram(400, 120, f"{kind} gate")
    gx, gy = 150, 40
    p = d.gate(kind, gx, gy)
    d.text(30, p["a"][1] + 4, "A", anchor="end", size=13, bold=True)
    d.text(30, p["b"][1] + 4, "B", anchor="end", size=13, bold=True)
    d.wire((36, p["a"][1]), p["a"])
    d.wire((36, p["b"][1]), p["b"])
    _out_label(d, p["out"], label_out, 80)
    return d


def _build_not():
    d = LogicDiagram(400, 120, "NOT gate")
    p = d.gate("NOT", 150, 40)
    d.text(30, p["a"][1] + 4, "A", anchor="end", size=13, bold=True)
    d.wire((36, p["a"][1]), p["a"])
    _out_label(d, p["out"], "Y", 90)
    return d


def _build_half_adder():
    d = LogicDiagram(480, 230, "Half adder")
    tap = _bus_inputs(d, ["A", "B"], [70, 90], [30, 50], [150, 170])
    x1 = d.gate("XOR", 220, 70, "XOR")
    a1 = d.gate("AND", 220, 140, "AND")
    tap("A", x1["a"][1], x1["a"][0]); tap("B", x1["b"][1], x1["b"][0])
    tap("A", a1["a"][1], a1["a"][0]); tap("B", a1["b"][1], a1["b"][0])
    _out_label(d, x1["out"], "Sum", 90)
    _out_label(d, a1["out"], "Carry", 90)
    return d


def _build_full_adder():
    d = LogicDiagram(610, 330, "Full adder")
    tap = _bus_inputs(d, ["A", "B", "Cin"], [60, 80, 100], [30, 50, 70], [260, 280, 200])
    x1 = d.gate("XOR", 180, 90, "XOR 1")
    x2 = d.gate("XOR", 320, 90, "XOR 2")
    a1 = d.gate("AND", 180, 250, "AND 1")
    a2 = d.gate("AND", 320, 170, "AND 2")
    o1 = d.gate("OR", 440, 210, "OR")
    # inputs to XOR 1 and AND 1
    tap("A", x1["a"][1], x1["a"][0]); tap("B", x1["b"][1], x1["b"][0])
    tap("A", a1["a"][1], a1["a"][0]); tap("B", a1["b"][1], a1["b"][0])
    # (A xor B) -> XOR 2 (in a) and AND 2 (in a)
    ox, oy = x1["out"]
    d.wire((ox, oy), (290, oy), (290, x2["a"][1]), (x2["a"][0], x2["a"][1]))
    d.dot(260, oy)
    d.wire((260, oy), (260, a2["a"][1]), (a2["a"][0], a2["a"][1]))
    # Cin -> XOR 2 (in b) and AND 2 (in b)
    d.dot(100, 150)
    d.wire((100, 150), (305, 150), (305, x2["b"][1]), (x2["b"][0], x2["b"][1]))
    d.dot(100, a2["b"][1])
    d.wire((100, a2["b"][1]), (a2["b"][0], a2["b"][1]))
    # outputs
    _out_label(d, x2["out"], "Sum", 120)
    ax, ay = a2["out"]
    d.wire((ax, ay), (415, ay), (415, o1["a"][1]), (o1["a"][0], o1["a"][1]))
    bx, by = a1["out"]
    d.wire((bx, by), (430, by), (430, o1["b"][1]), (o1["b"][0], o1["b"][1]))
    _out_label(d, o1["out"], "Carry-out", 40)
    return d


def _build_half_subtractor():
    d = LogicDiagram(520, 250, "Half subtractor")
    tap = _bus_inputs(d, ["A", "B"], [70, 90], [30, 50], [160, 180])
    x1 = d.gate("XOR", 230, 70, "XOR")
    n1 = d.gate("NOT", 130, 140)
    a1 = d.gate("AND", 230, 150, "AND")
    tap("A", x1["a"][1], x1["a"][0]); tap("B", x1["b"][1], x1["b"][0])
    tap("A", n1["a"][1], n1["a"][0])
    d.wire(n1["out"], (a1["a"][0], n1["out"][1]))
    tap("B", a1["b"][1], a1["b"][0])
    _out_label(d, x1["out"], "Difference", 90)
    _out_label(d, a1["out"], "Borrow", 90)
    return d


def _build_full_subtractor():
    d = LogicDiagram(640, 330, "Full subtractor")
    tap = _bus_inputs(d, ["A", "B", "Bin"], [60, 80, 100], [30, 50, 70], [270, 300, 230])
    x1 = d.gate("XOR", 180, 90, "XOR 1")
    x2 = d.gate("XOR", 320, 90, "XOR 2")
    nx = d.gate("NOT", 270, 175)
    a2 = d.gate("AND", 350, 175, "AND 2")
    na = d.gate("NOT", 130, 250)
    a1 = d.gate("AND", 220, 250, "AND 1")
    o1 = d.gate("OR", 440, 210, "OR")
    tap("A", x1["a"][1], x1["a"][0]); tap("B", x1["b"][1], x1["b"][0])
    # (A xor B) -> XOR 2 and NOT
    ox, oy = x1["out"]
    d.wire((ox, oy), (280, oy), (280, x2["a"][1]), (x2["a"][0], x2["a"][1]))
    d.dot(250, oy)
    d.wire((250, oy), (250, nx["a"][1]), nx["a"])
    # Bin -> XOR 2 (b) and AND 2 (b)
    d.dot(100, 150)
    d.wire((100, 150), (300, 150), (300, x2["b"][1]), (x2["b"][0], x2["b"][1]))
    d.dot(100, 230)
    d.wire((100, 230), (335, 230), (335, a2["b"][1]), (a2["b"][0], a2["b"][1]))
    d.wire(nx["out"], (330, nx["out"][1]), (330, a2["a"][1]), (a2["a"][0], a2["a"][1]))
    # NOT A and AND 1
    tap("A", na["a"][1], na["a"][0])
    d.wire(na["out"], (197, na["out"][1]), (197, a1["a"][1]), (a1["a"][0], a1["a"][1]))
    tap("B", 300, 205)
    d.wire((205, 300), (205, a1["b"][1]), (a1["b"][0], a1["b"][1]))
    # outputs
    _out_label(d, x2["out"], "Difference", 90)
    ax, ay = a2["out"]
    d.wire((ax, ay), (420, ay), (420, o1["a"][1]), (o1["a"][0], o1["a"][1]))
    bx, by = a1["out"]
    d.wire((bx, by), (430, by), (430, o1["b"][1]), (o1["b"][0], o1["b"][1]))
    _out_label(d, o1["out"], "Borrow-out", 40)
    return d


def _build_mux_2_1():
    d = LogicDiagram(540, 270, "2:1 multiplexer")
    tap = _bus_inputs(d, ["S", "I0", "I1"], [60, 80, 100], [30, 50, 70], [190, 130, 210])
    n1 = d.gate("NOT", 140, 80)
    a1 = d.gate("AND", 230, 100, "AND 1")
    a2 = d.gate("AND", 230, 180, "AND 2")
    o1 = d.gate("OR", 350, 130, "OR")
    tap("S", n1["a"][1], n1["a"][0])
    d.wire(n1["out"], (207, n1["out"][1]), (207, a1["a"][1]), (a1["a"][0], a1["a"][1]))
    tap("I0", a1["b"][1], a1["b"][0])
    tap("S", a2["a"][1], a2["a"][0])
    tap("I1", a2["b"][1], a2["b"][0])
    ax, ay = a1["out"]
    d.wire((ax, ay), (310, ay), (310, o1["a"][1]), (o1["a"][0], o1["a"][1]))
    bx, by = a2["out"]
    d.wire((bx, by), (325, by), (325, o1["b"][1]), (o1["b"][0], o1["b"][1]))
    _out_label(d, o1["out"], "Y", 80)
    return d


def _build_bin_to_gray(n):
    n = max(2, min(int(n), 4))
    spacing, y0 = 70, 40
    d = LogicDiagram(520, y0 + spacing * (n - 1) + 70, f"{n}-bit binary to Gray converter")
    rows = [y0 + spacing * k for k in range(n)]
    for k in range(n):
        bit = n - 1 - k
        d.text(30, rows[k] + 4, f"B{bit}", anchor="end", size=13, bold=True)
        end_x = 410 if k == 0 else 190
        d.wire((36, rows[k]), (end_x, rows[k]))
    d.text(418, rows[0] + 4, f"G{n - 1}", anchor="start", size=13, bold=True)
    for k in range(n - 1):
        g = d.gate("XOR", 240, rows[k] + 15, "XOR")
        # upper input from row k (via x=150), lower input from row k+1 (via x=190)
        d.dot(150, rows[k])
        d.wire((150, rows[k]), (150, g["a"][1]), g["a"])
        d.dot(190, rows[k + 1])
        d.wire((190, rows[k + 1]), (190, g["b"][1]), g["b"])
        _out_label(d, g["out"], f"G{n - 2 - k}", 60)
    return d


def _build_gray_to_bin(n):
    n = max(2, min(int(n), 4))
    spacing, y0 = 70, 40
    xs = [200 + 100 * (k - 1) for k in range(1, n)]
    x_end = xs[-1] + 50 + 40 + 20
    d = LogicDiagram(x_end + 60, y0 + spacing * (n - 1) + 40, f"{n}-bit Gray to binary converter")
    rows = [y0 + spacing * k for k in range(n)]
    d.text(30, rows[0] + 4, f"G{n - 1}", anchor="end", size=13, bold=True)
    d.wire((36, rows[0]), (x_end, rows[0]))
    d.text(x_end + 8, rows[0] + 4, f"B{n - 1}", anchor="start", size=13, bold=True)
    prev_out = None
    for k in range(1, n):
        gx, gy = xs[k - 1], rows[k] - 30
        g = d.gate("XOR", gx, gy, "XOR")
        d.text(30, rows[k] + 4, f"G{n - 1 - k}", anchor="end", size=13, bold=True)
        d.wire((36, rows[k]), g["b"])
        if k == 1:
            tx = gx - 40
            d.dot(tx, rows[0])
            d.wire((tx, rows[0]), (tx, g["a"][1]), g["a"])
        else:
            ox, oy = prev_out
            bx = ox + 20
            d.dot(bx, oy)
            d.wire((bx, oy), (bx, g["a"][1]), g["a"])
        # output continues to the right-hand label column
        ox, oy = g["out"]
        d.wire((ox, oy), (x_end, oy))
        d.text(x_end + 8, oy + 4, f"B{n - 1 - k}", anchor="start", size=13, bold=True)
        prev_out = g["out"]
    return d


_LOGIC_GATE_KINDS = {"AND": "AND", "NAND": "NAND", "OR": "OR", "NOR": "NOR", "XOR": "XOR", "XNOR": "XNOR"}


def build_logic_diagram(sub_type, width=4):
    """Returns a LogicDiagram for a CIRCUIT_DATABASE digital circuit, or None if unsupported."""
    if sub_type in _LOGIC_GATE_KINDS:
        return _build_single_gate(_LOGIC_GATE_KINDS[sub_type])
    builders = {
        "NOT": _build_not,
        "half_adder": _build_half_adder,
        "full_adder": _build_full_adder,
        "half_subtractor": _build_half_subtractor,
        "full_subtractor": _build_full_subtractor,
        "mux_2_1": _build_mux_2_1,
    }
    if sub_type in builders:
        return builders[sub_type]()
    if sub_type == "bin_to_gray":
        return _build_bin_to_gray(width)
    if sub_type == "gray_to_bin":
        return _build_gray_to_bin(width)
    return None


def get_digital_boolean_expressions(sub_type, width=4):
    """Boolean / functional description lines for a digital circuit (plain ASCII)."""
    simple = {
        "AND": ["Y = A AND B"],
        "NAND": ["Y = NOT (A AND B)"],
        "OR": ["Y = A OR B"],
        "NOR": ["Y = NOT (A OR B)"],
        "XOR": ["Y = A XOR B"],
        "XNOR": ["Y = NOT (A XOR B)"],
        "NOT": ["Y = NOT A"],
        "half_adder": ["Sum = A XOR B", "Carry = A AND B"],
        "full_adder": ["Sum = A XOR B XOR Cin", "Carry-out = (A AND B) OR (Cin AND (A XOR B))"],
        "half_subtractor": ["Difference = A XOR B", "Borrow = (NOT A) AND B"],
        "full_subtractor": ["Difference = A XOR B XOR Bin",
                            "Borrow-out = ((NOT A) AND B) OR ((NOT (A XOR B)) AND Bin)"],
        "mux_2_1": ["Y = ((NOT S) AND I0) OR (S AND I1)"],
    }
    if sub_type in simple:
        return list(simple[sub_type])
    n = max(2, min(int(width), 4))
    if sub_type == "bin_to_gray":
        return [f"G{n - 1} = B{n - 1}"] + [f"G{i} = B{i + 1} XOR B{i}" for i in range(n - 2, -1, -1)]
    if sub_type == "gray_to_bin":
        return [f"B{n - 1} = G{n - 1}"] + [f"B{i} = B{i + 1} XOR G{i}" for i in range(n - 2, -1, -1)]
    return []


def render_diagram_svg(d):
    """Serialises a LogicDiagram to a standalone, responsive SVG string."""
    w, h = d.width, d.height
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="100%" '
           f'style="max-width:{w:g}px;height:auto;" role="img" aria-label="{html.escape(d.title)}">',
           f'<title>{html.escape(d.title)}</title>']
    for it in d.items:
        kind = it[0]
        if kind == "poly":
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in it[1])
            out.append(f'<polyline points="{pts}" fill="none" stroke="{_DIAG_WIRE}" stroke-width="1.8" '
                       f'stroke-linejoin="round" stroke-linecap="round"/>')
        elif kind == "dpoly":
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in it[1])
            out.append(f'<polyline points="{pts}" fill="none" stroke="#b3185a" stroke-width="1.5" stroke-dasharray="5 3" '
                       f'stroke-linejoin="round" stroke-linecap="round"/>')
        elif kind == "path":
            cmds, closed = it[1], it[2]
            seg = []
            for c in cmds:
                if c[0] in ("M", "L"):
                    seg.append(f"{c[0]}{c[1]:.1f},{c[2]:.1f}")
                elif c[0] == "Q":
                    seg.append(f"Q{c[1]:.1f},{c[2]:.1f} {c[3]:.1f},{c[4]:.1f}")
                elif c[0] == "Z":
                    seg.append("Z")
            fill = _DIAG_FILL if closed else "none"
            out.append(f'<path d="{" ".join(seg)}" fill="{fill}" stroke="{_DIAG_STROKE}" stroke-width="2" '
                       f'stroke-linejoin="round"/>')
        elif kind == "circle":
            _, cx, cy, r, filled = it
            fill = _DIAG_WIRE if filled else "#ffffff"
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:g}" fill="{fill}" stroke="{_DIAG_STROKE}" stroke-width="1.8"/>')
        elif kind == "rect":
            _, x, y, rw, rh = it
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{rw:.1f}" height="{rh:.1f}" fill="{_DIAG_FILL}" '
                       f'stroke="{_DIAG_STROKE}" stroke-width="2"/>')
        elif kind == "text":
            _, x, y, s, anchor, size, bold, color = it
            weight = "700" if bold else "400"
            out.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Helvetica, Arial, sans-serif" '
                       f'font-size="{size:g}" font-weight="{weight}" fill="{color}">{html.escape(s)}</text>')
    out.append("</svg>")
    return "".join(out)


def render_diagram_drawing(d, max_width):
    """Builds a vector ReportLab Drawing of the diagram, scaled to fit max_width (points)."""
    from reportlab.graphics.shapes import Drawing, Path, PolyLine, Circle, String, Rect
    sc = min(max_width / d.width, 1.35)
    dr = Drawing(d.width * sc, d.height * sc)
    hx = colors.HexColor

    def X(x):
        return x * sc

    def Y(y):
        return (d.height - y) * sc

    for it in d.items:
        kind = it[0]
        if kind == "poly":
            flat = []
            for x, y in it[1]:
                flat += [X(x), Y(y)]
            dr.add(PolyLine(flat, strokeColor=hx(_DIAG_WIRE), strokeWidth=1.3, strokeLineJoin=1, strokeLineCap=1))
        elif kind == "dpoly":
            flat = []
            for x, y in it[1]:
                flat += [X(x), Y(y)]
            dr.add(PolyLine(flat, strokeColor=hx("#b3185a"), strokeWidth=1.1, strokeDashArray=[4, 3], strokeLineJoin=1, strokeLineCap=1))
        elif kind == "path":
            cmds, closed = it[1], it[2]
            p = Path(fillColor=hx(_DIAG_FILL) if closed else None, strokeColor=hx(_DIAG_STROKE),
                     strokeWidth=1.5, strokeLineJoin=1)
            cur = (0.0, 0.0)
            for c in cmds:
                if c[0] == "M":
                    p.moveTo(X(c[1]), Y(c[2])); cur = (c[1], c[2])
                elif c[0] == "L":
                    p.lineTo(X(c[1]), Y(c[2])); cur = (c[1], c[2])
                elif c[0] == "Q":
                    cx, cy, ex, ey = c[1], c[2], c[3], c[4]
                    c1 = (cur[0] + 2.0 / 3.0 * (cx - cur[0]), cur[1] + 2.0 / 3.0 * (cy - cur[1]))
                    c2 = (ex + 2.0 / 3.0 * (cx - ex), ey + 2.0 / 3.0 * (cy - ey))
                    p.curveTo(X(c1[0]), Y(c1[1]), X(c2[0]), Y(c2[1]), X(ex), Y(ey)); cur = (ex, ey)
                elif c[0] == "Z":
                    p.closePath()
            dr.add(p)
        elif kind == "circle":
            _, cx, cy, r, filled = it
            dr.add(Circle(X(cx), Y(cy), r * sc, fillColor=hx(_DIAG_WIRE) if filled else colors.white,
                          strokeColor=hx(_DIAG_STROKE), strokeWidth=1.3))
        elif kind == "rect":
            _, x, y, rw, rh = it
            dr.add(Rect(X(x), Y(y + rh), rw * sc, rh * sc, fillColor=hx(_DIAG_FILL),
                        strokeColor=hx(_DIAG_STROKE), strokeWidth=1.5))
        elif kind == "text":
            _, x, y, s, anchor, size, bold, color = it
            dr.add(String(X(x), Y(y), _pdf_plain(s), fontName="Helvetica-Bold" if bold else "Helvetica",
                          fontSize=size * sc, textAnchor=anchor, fillColor=hx(color)))
    return dr



# ==============================================================================
# ANALOGUE (RECTIFIER) SCHEMATICS - built on the same LogicDiagram scene description,
# so the SAME drawing is rendered as inline SVG (dashboard) and as a ReportLab vector
# Drawing (PDF). Component values/refs come from CIRCUIT_KNOWLEDGE (which mirrors
# CIRCUIT_DATABASE); probe positions come from the database "probes" list.
# ==============================================================================
_DIAG_PROBE = "#b3185a"


def _cv(circuit_name, ref, default=""):
    for c in CIRCUIT_KNOWLEDGE.get(circuit_name, {}).get("components", []):
        if ref in c.get("refs", [c.get("ref")]):
            return c.get("value", default)
    return default


def _ref_label(d, x, y, ref, val=None, anchor="middle"):
    d.text(x, y, ref, anchor=anchor, size=13, bold=True)
    if val:
        d.text(x, y + 13, val, anchor=anchor, size=10.5, color=_DIAG_CAPTION)


def _probe_v(d, x, y_top, y_bot, ym, label, sub, tx=None, anchor="start"):
    """Voltmeter probe P-n connected across two nodes (dashed leads, V meter symbol)."""
    d.dot(x, y_top)
    d.dot(x, y_bot)
    d.dwire((x, y_top), (x, ym - 11))
    d.dwire((x, ym + 11), (x, y_bot))
    d.meter(x, ym, "V")
    tx = x + 17 if tx is None else tx
    d.text(tx, ym - 2, label, anchor=anchor, size=11, bold=True, color=_DIAG_PROBE)
    d.text(tx, ym + 11, sub, anchor=anchor, size=10, color=_DIAG_CAPTION)


def _ammeter_h(d, x, y, x1, x2, label):
    d.wire((x1, y), (x - 11, y))
    d.wire((x + 11, y), (x2, y))
    d.meter(x, y, "A")
    d.text(x, y - 18, label, size=11, bold=True, color=_DIAG_PROBE)


def _probe_legend(d, info, y0, extra=None):
    y = y0
    for p in (info or {}).get("probes", []):
        d.text(14, y, f"P{p['step']}  {p['name']}: {p['loc']}", anchor="start", size=10.5, color=_DIAG_PROBE)
        y += 14
    for line in (extra or []):
        d.text(14, y, line, anchor="start", size=10, color=_DIAG_CAPTION)
        y += 14
    return y


def _mains_label(d, y):
    d.text(42, y + 36, "AC", anchor="start", size=10, color=_DIAG_CAPTION)
    d.text(42, y + 48, "mains", anchor="start", size=10, color=_DIAG_CAPTION)


_SCHEM_NOTE = ("Dashed lines = measurement-probe leads (ESP32 sensor).  Wires that cross without a dot are not connected.")


def _build_half_wave(name, info):
    d = LogicDiagram(660, 330, "Half-wave rectifier schematic")
    d.text(14, 20, "Half-wave rectifier with capacitor filter - standard configuration", anchor="start", size=13, bold=True)
    yt, yb = 80, 220
    d.ac_source(36, 150)
    _mains_label(d, 150)
    t = d.transformer(84, yt, yb)
    d.wire((36, 134), (36, yt), t["p_top"])
    d.wire((36, 166), (36, yb), t["p_bot"])
    _ref_label(d, 108, 246, "T1", _cv(name, "T1"))
    s1, s2 = t["s_top"], t["s_bot"]
    # top rail: T1 -> P3 ammeter -> D1 -> output rail
    d.wire(s1, (203, yt))
    _ammeter_h(d, 214, yt, 203, 262, "P3 (I)")
    d.diode(262, yt, 306, yt)
    _ref_label(d, 284, 50, "D1", _cv(name, "D1"))
    d.wire((306, yt), (580, yt))
    d.wire(s2, (580, yb))
    # P1: input voltage across the secondary
    _probe_v(d, 168, yt, yb, 150, "P1 Vin", "(across secondary)")
    # C1 and RL
    d.capacitor(380, yt, 380, yb)
    d.dot(380, yt); d.dot(380, yb)
    d.text(366, 148, "C1", anchor="end", size=13, bold=True)
    d.text(366, 161, _cv(name, "C1"), anchor="end", size=10.5, color=_DIAG_CAPTION)
    d.resistor(460, yt, 460, yb)
    d.dot(460, yt); d.dot(460, yb)
    d.text(446, 148, "RL", anchor="end", size=13, bold=True)
    d.text(446, 161, _cv(name, "RL"), anchor="end", size=10.5, color=_DIAG_CAPTION)
    # P2 across the load and output terminals
    _probe_v(d, 520, yt, yb, 150, "P2 Vout", "(across RL)")
    d.ring(580, yt); d.ring(580, yb)
    d.text(592, yt + 4, "OUT +", anchor="start", size=11, bold=True)
    d.text(592, yb + 4, "OUT -", anchor="start", size=11, bold=True)
    d.dot(250, yb)
    d.ground(250, yb)
    d.text(268, yb + 26, "GND (0 V)", anchor="start", size=10, color=_DIAG_CAPTION)
    _probe_legend(d, info, 276, [_SCHEM_NOTE])
    return d


def _build_center_tap(name, info):
    d = LogicDiagram(660, 410, "Full-wave centre-tap rectifier schematic")
    d.text(14, 20, "Full-wave rectifier (centre-tap transformer, 2 diodes) with capacitor filter", anchor="start", size=13, bold=True)
    yt, yb, ycl = 60, 270, 312
    d.ac_source(36, 165)
    _mains_label(d, 165)
    t = d.transformer(84, yt, yb, loops=8)
    d.wire((36, 149), (36, yt), t["p_top"])
    d.wire((36, 181), (36, yb), t["p_bot"])
    _ref_label(d, 108, 296, "T1", _cv(name, "T1"))
    s1, ct, s2 = t["s_top"], t["s_ct"], t["s_bot"]
    # upper half -> D1 -> cathode bus
    d.wire(s1, (200, yt))
    d.diode(200, yt, 244, yt)
    d.text(214, 42, "D1", anchor="end", size=13, bold=True)
    d.text(220, 42, _cv(name, "D1"), anchor="start", size=10.5, color=_DIAG_CAPTION)
    d.wire((244, yt), (300, yt))
    # lower half -> D2 -> cathode bus
    d.wire(s2, (200, yb))
    d.diode(200, yb, 244, yb)
    d.text(214, 296, "D2", anchor="end", size=13, bold=True)
    d.text(220, 296, _cv(name, "D2"), anchor="start", size=10.5, color=_DIAG_CAPTION)
    d.wire((244, yb), (300, yb))
    d.wire((300, yt), (300, yb))
    d.dot(300, 165)
    d.wire((300, 165), (580, 165))
    # centre tap = return line (with P3 ammeter), crossing the lower-half wire
    d.wire(ct, (176, 165))
    d.wire((176, 165), (176, 204))
    d.meter(176, 215, "A")
    d.text(192, 213, "P3 (I)", anchor="start", size=11, bold=True, color=_DIAG_PROBE)
    d.text(192, 226, "(CT return)", anchor="start", size=10, color=_DIAG_CAPTION)
    d.vwire_hops(176, 226, ycl, hops=[yb])
    d.wire((176, ycl), (580, ycl))
    # P1: upper half winding to centre tap
    _probe_v(d, 160, yt, 165, 112, "P1 Vin", "(upper half to CT)", tx=177)
    # C1, RL, P2, terminals
    d.capacitor(380, 165, 380, ycl)
    d.dot(380, 165); d.dot(380, ycl)
    d.text(366, 238, "C1", anchor="end", size=13, bold=True)
    d.text(366, 251, _cv(name, "C1"), anchor="end", size=10.5, color=_DIAG_CAPTION)
    d.resistor(460, 165, 460, ycl)
    d.dot(460, 165); d.dot(460, ycl)
    d.text(446, 238, "RL", anchor="end", size=13, bold=True)
    d.text(446, 251, _cv(name, "RL"), anchor="end", size=10.5, color=_DIAG_CAPTION)
    _probe_v(d, 520, 165, ycl, 238, "P2 Vout", "(across RL)")
    d.ring(580, 165); d.ring(580, ycl)
    d.text(592, 169, "OUT +", anchor="start", size=11, bold=True)
    d.text(592, ycl + 4, "OUT -", anchor="start", size=11, bold=True)
    d.dot(250, ycl)
    d.ground(250, ycl)
    d.text(268, ycl + 26, "GND (0 V)", anchor="start", size=10, color=_DIAG_CAPTION)
    _probe_legend(d, info, 352, [_SCHEM_NOTE])
    return d


def _build_bridge(name, info):
    d = LogicDiagram(810, 420, "Bridge rectifier schematic")
    d.text(14, 20, "Bridge rectifier (4 diodes) with filter capacitor", anchor="start", size=13, bold=True)
    yt, yb = 70, 250
    d.ac_source(36, 160)
    _mains_label(d, 160)
    t = d.transformer(84, yt, yb, loops=6)
    d.wire((36, 144), (36, yt), t["p_top"])
    d.wire((36, 176), (36, yb), t["p_bot"])
    _ref_label(d, 108, 276, "T1", _cv(name, "T1"))
    L, Tp, R, Bt = (320, 160), (400, 100), (480, 160), (400, 220)
    # AC feed (secondary -> bridge AC nodes)
    d.wire(t["s_top"], (272, yt), (272, 160), L)
    d.wire(t["s_bot"], (530, yb), (530, 160), R)
    _probe_v(d, 170, yt, yb, 160, "P1 Vin", "(AC terminals)")
    # diodes
    d.diode(L[0], L[1], Tp[0], Tp[1])
    d.diode(R[0], R[1], Tp[0], Tp[1])
    d.diode(Bt[0], Bt[1], L[0], L[1])
    d.diode(Bt[0], Bt[1], R[0], R[1])
    dv = _cv(name, "D1")
    d.text(340, 114, "D1", anchor="end", size=13, bold=True)
    d.text(340, 127, dv, anchor="end", size=10.5, color=_DIAG_CAPTION)
    d.text(460, 114, "D2", anchor="start", size=13, bold=True)
    d.text(460, 127, dv, anchor="start", size=10.5, color=_DIAG_CAPTION)
    d.text(340, 204, "D3", anchor="end", size=13, bold=True)
    d.text(340, 217, dv, anchor="end", size=10.5, color=_DIAG_CAPTION)
    d.text(460, 204, "D4", anchor="start", size=13, bold=True)
    d.text(460, 217, dv, anchor="start", size=10.5, color=_DIAG_CAPTION)
    for p in (L, R, Tp, Bt):
        d.dot(*p)
    # DC output: + rail (with P3 ammeter) and - rail (hop over the AC feed wire)
    d.wire(Tp, (400, 50))
    d.text(414, 80, "+", anchor="start", size=13, bold=True)
    d.wire((400, 50), (459, 50))
    d.meter(470, 50, "A")
    d.text(470, 32, "P3 (I)", size=11, bold=True, color=_DIAG_PROBE)
    d.wire((481, 50), (760, 50))
    d.vwire_hops(400, 220, 300, hops=[yb])
    d.text(414, 244, "-", anchor="start", size=13, bold=True)
    d.wire((400, 300), (760, 300))
    d.dot(440, 300)
    d.ground(440, 300)
    d.text(458, 326, "GND (0 V)", anchor="start", size=10, color=_DIAG_CAPTION)
    # C1, RL, P2, terminals
    d.capacitor(600, 50, 600, 300)
    d.dot(600, 50); d.dot(600, 300)
    d.text(584, 168, "C1", anchor="end", size=13, bold=True)
    d.text(584, 181, _cv(name, "C1"), anchor="end", size=10.5, color=_DIAG_CAPTION)
    d.resistor(668, 50, 668, 300)
    d.dot(668, 50); d.dot(668, 300)
    d.text(654, 168, "RL", anchor="end", size=13, bold=True)
    d.text(654, 181, _cv(name, "RL"), anchor="end", size=10.5, color=_DIAG_CAPTION)
    _probe_v(d, 728, 50, 300, 175, "P2 Vout", "(across RL)", tx=741)
    d.ring(760, 50); d.ring(760, 300)
    d.text(772, 54, "OUT +", anchor="start", size=11, bold=True)
    d.text(772, 304, "OUT -", anchor="start", size=11, bold=True)
    _probe_legend(d, info, 350, [_SCHEM_NOTE,
                                  "D1-D4 may be one 4-pin bridge module (e.g. 1B4B42): its AC~ pins go to T1, its +/- pins to the load."])
    return d


def build_analog_schematic(circuit_name):
    """LogicDiagram of a rectifier circuit, or None if unsupported."""
    info = CIRCUIT_DATABASE.get("Rectifiers", {}).get(circuit_name)
    builders = {"Half Wave Rectifier": _build_half_wave,
                "Full Wave Rectifier (Center Tap)": _build_center_tap,
                "Bridge Rectifier": _build_bridge}
    fn = builders.get(circuit_name)
    return fn(circuit_name, info) if fn else None



# ==============================================================================
# STUDENT REPORT: validation, report data preparation, offline digital diagnosis,
# PDF generation (pure functions - no Streamlit dependency,
# so they can be unit tested; the UI lives in the "Generate Report" page).
# ==============================================================================
REPORT_YEAR_OPTIONS = ["First Year", "Second Year", "Third Year", "Final Year", "Other (type below)"]
_DIVISION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{0,9}$")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _clean_text(value, max_len=120):
    """Trims, collapses whitespace and strips control characters (no header/PDF injection)."""
    text = _CTRL_RE.sub(" ", str(value if value is not None else ""))
    return re.sub(r"\s+", " ", text).strip()[:max_len]


def validate_student_details(raw):
    """Validates the Student Details form. Returns (clean_dict, errors_dict).
    errors maps a field name to a message; an empty dict means the details are valid."""
    raw = raw or {}
    errors = {}
    name = _clean_text(raw.get("name"), 80)
    if not name:
        errors["name"] = "Student name is required."
    elif not re.search(r"[A-Za-z]", name):
        errors["name"] = "Student name must contain letters."

    year_choice = _clean_text(raw.get("year"), 40)
    if year_choice.startswith("Other"):
        year = _clean_text(raw.get("year_other"), 40)
        if not year:
            errors["year"] = "Please type the academic year (e.g. 2025-26)."
    else:
        year = year_choice
        if not year or year.startswith(("-", "\u2014")):
            year = ""
            errors["year"] = "Select the year / academic year."

    division = _clean_text(raw.get("division"), 10)
    if not division:
        errors["division"] = "Division is required (e.g. A, B, C)."
    elif not _DIVISION_RE.match(division):
        errors["division"] = "Division may contain only letters, digits, space or hyphen (max 10 characters)."

    clean = {
        "name": name, "year": year, "division": division.upper() if division else "",
        "roll_no": _clean_text(raw.get("roll_no"), 40),
        "college": _clean_text(raw.get("college"), 120),
        "branch": _clean_text(raw.get("branch"), 80),
        "report_title": _clean_text(raw.get("report_title"), 120),
    }
    return clean, errors


def sanitize_filename_part(text, max_len=40):
    part = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_")
    return (part[:max_len].strip("_")) or "NA"


def build_report_filename(student_name, circuit_name, when):
    return (f"NEXUS_Test_Report_{sanitize_filename_part(student_name)}_"
            f"{sanitize_filename_part(circuit_name)}_{when.strftime('%Y%m%d_%H%M%S')}.pdf")


def new_test_id(ts):
    return f"NX-{ts.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


# ------------------------------------------------------------------------------
# OFFLINE DIGITAL DIAGNOSIS (local, deterministic - works without Gemini/internet)
# ------------------------------------------------------------------------------
def build_offline_digital_diagnosis(analysis):
    """Builds the offline diagnosis text blocks from a compute_digital_analysis() result."""
    status = analysis["det_status"]
    cells = analysis.get("cells", [])
    th = analysis.get("thresholds", {"v_il": 0.8, "v_ih": 2.0})
    findings, actions, limits = [], [], []

    if status == "PASS":
        summary = (f"All {analysis['total_cells']} required output cells were measured with valid logic levels and every "
                   f"measured output matches the expected truth table.")
    elif status == "FAIL":
        summary = (f"All required output cells have valid measurements, but {analysis['mismatches']} of "
                   f"{analysis['total_cells']} outputs do not match the expected truth table.")
    else:
        summary = (f"A complete determination is not possible: {analysis['missing_cells']} required cell(s) are missing and "
                   f"{analysis['invalid_cells']} cell(s) have an invalid logic level. "
                   f"Only {analysis['valid_cells']} of {analysis['total_cells']} cells ({analysis['coverage_pct']:.1f} %) are valid.")

    def _lim(items, n=20):
        shown = items[:n]
        if len(items) > n:
            shown.append(f"... and {len(items) - n} more.")
        return shown

    mism = [c for c in cells if c["status"] == "MISMATCH"]
    for c in _lim([f"MISMATCH - Row {c['row']} ({c['inputs']}), output {c['output']}: expected {c['expected']}, "
                   f"measured logic {c['state']} ({c['voltage']})." for c in mism]):
        findings.append(c)
    inval = [c for c in cells if c["status"] == "INVALID"]
    for c in _lim([f"INVALID - Row {c['row']} ({c['inputs']}), output {c['output']}: measured {c['voltage']}, which is "
                   f"not a valid logic level (logic 0 <= {th['v_il']} V, logic 1 >= {th['v_ih']} V)." for c in inval]):
        findings.append(c)
    miss = [c for c in cells if c["status"] == "MISSING"]
    if miss:
        for c in _lim([f"MISSING - Row {c['row']} ({c['inputs']}), output {c['output']}: no measurement saved." for c in miss]):
            findings.append(c)

    # pattern hints (hypotheses derived only from the measured states)
    outputs = []
    for c in cells:
        if c["output"] not in outputs:
            outputs.append(c["output"])
    for out in outputs:
        valid = [c for c in cells if c["output"] == out and c["status"] in ("MATCH", "MISMATCH")]
        if len(valid) >= 2:
            states = {c["state"] for c in valid}
            expected_vals = {c["expected"] for c in valid}
            if len(states) == 1 and len(expected_vals) > 1:
                findings.append(f"PATTERN - Output {out} reads logic {next(iter(states))} in all {len(valid)} valid "
                                f"measurements although the expected value changes (possible stuck-at condition: open/short "
                                f"on the output, missing supply, or heavy loading). This is a hypothesis, not a confirmed fault.")
            elif all(c["status"] == "MISMATCH" for c in valid):
                findings.append(f"PATTERN - Output {out} is the opposite of the expected value in all {len(valid)} valid "
                                f"measurements (possible inverted output, wrong gate/IC type, or swapped wiring). "
                                f"This is a hypothesis, not a confirmed fault.")
    if not findings:
        findings.append("No mismatches, invalid levels or missing cells were found.")

    if status == "PASS":
        actions.append("No corrective action is required. Keep this report as the record of the verified truth table.")
    else:
        if miss or inval:
            actions.append("Measure every missing cell and re-measure every INVALID cell, then run ANALYSE again.")
        if mism or inval:
            actions.append("Confirm the input switches/pins are set exactly to the input combination of the row being measured.")
            actions.append("Check the supply voltage and common ground between the circuit and the ESP32 sensor input.")
            actions.append("Check the IC pin-out and wiring against the circuit diagram in this report.")
            actions.append("Measure the output pin directly; look for floating inputs, loading on the output, or a damaged IC.")
        actions.append("Re-test the failing rows after each correction.")
    limits.append("This diagnosis is a local rule-based comparison of the saved measurements with the expected truth table; "
                  "it identifies where the outputs differ but cannot confirm the physical cause.")
    if status == "INCOMPLETE":
        limits.append("The result is INCOMPLETE: it must not be read as PASS or FAIL until all cells are measured and valid.")
    return {"summary": summary, "findings": findings, "actions": actions, "limitations": limits}


# ------------------------------------------------------------------------------
# REPORT DATA PREPARATION (from a stored test record)
# ------------------------------------------------------------------------------
# ==============================================================================
# PDF PARTS: vector IC pin diagram (ReportLab), unified "lab view" of a diagnosis
# ==============================================================================
def render_ic_drawing(ic, max_width):
    """Vector ReportLab Drawing of a DIP package (top view, notch up, pin 1 top-left) with pin numbers,
    pin names, roles (colour coded), the connection used in this test, VCC and GND."""
    from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Wedge, Group
    from reportlab.pdfbase.pdfmetrics import stringWidth
    hx = colors.HexColor
    part = IC_PARTS[ic["part"]]
    pins = part["pins"]
    n = len(pins)
    m = n // 2
    W = float(max_width)
    pitch, bw, top, legend_h = 21.0, 78.0, 36.0, 34.0
    body_h = m * pitch + 14.0
    H = top + body_h + legend_h
    d = Drawing(W, H)
    cx = W / 2.0
    bx = cx - bw / 2.0
    ytop = H - top
    d.add(String(cx, H - 13, _pdf_plain(f"{ic['ref']} - {part['label']} (DIP-{n})"), fontName="Helvetica-Bold", fontSize=10, textAnchor="middle", fillColor=hx("#102027")))
    d.add(String(cx, H - 25, _pdf_plain(f"{part['func']} - top view, notch at top, pin 1 at top-left (dot)"), fontName="Helvetica", fontSize=7.5, textAnchor="middle", fillColor=hx("#455a64")))
    d.add(Rect(bx, ytop - body_h, bw, body_h, rx=4, ry=4, fillColor=hx("#eceff1"), strokeColor=hx("#263238"), strokeWidth=1.4))
    d.add(Wedge(cx, ytop, 8, 180, 360, fillColor=colors.white, strokeColor=hx("#263238"), strokeWidth=1.2))
    d.add(Circle(bx + 9, ytop - 9, 3, fillColor=hx("#263238"), strokeColor=hx("#263238")))
    g = Group(String(0, 0, _pdf_plain(ic["part_short"]), fontName="Helvetica-Bold", fontSize=11, textAnchor="middle", fillColor=hx("#90a4ae")))
    g.transform = (0, 1, -1, 0, cx, ytop - body_h / 2.0)
    d.add(g)
    conn = ic.get("conn", {})
    avail = (W - bw) / 2.0 - 44.0
    for r in range(m):
        yc = ytop - 7.0 - pitch * (r + 0.5)
        for side in ("L", "R"):
            pno = r + 1 if side == "L" else n - r
            pname = pins[pno - 1]
            text, kind = conn.get(pname, _ic_default_label(pname))
            col = hx(_IC_COLORS.get(kind, "#000000"))
            txt = _pdf_plain(text)
            fs = min(7.6, 7.6 * avail / max(1.0, stringWidth(txt, "Helvetica-Bold", 7.6)))
            if side == "L":
                x0 = bx - 20
                d.add(Rect(x0, yc - 6.5, 20, 13, fillColor=hx("#cfd8dc"), strokeColor=hx("#263238"), strokeWidth=0.9))
                d.add(String(x0 + 10, yc - 2.8, str(pno), fontName="Helvetica-Bold", fontSize=7.8, textAnchor="middle"))
                d.add(Line(x0 - 14, yc, x0, yc, strokeColor=col, strokeWidth=2))
                d.add(String(x0 - 18, yc - 2.7, txt, fontName="Helvetica-Bold", fontSize=fs, textAnchor="end", fillColor=col))
                d.add(String(bx + 4, yc - 2.8, _pdf_plain(pname), fontName="Helvetica-Bold", fontSize=7.8, textAnchor="start", fillColor=hx("#102027")))
            else:
                x0 = bx + bw
                d.add(Rect(x0, yc - 6.5, 20, 13, fillColor=hx("#cfd8dc"), strokeColor=hx("#263238"), strokeWidth=0.9))
                d.add(String(x0 + 10, yc - 2.8, str(pno), fontName="Helvetica-Bold", fontSize=7.8, textAnchor="middle"))
                d.add(Line(x0 + 20, yc, x0 + 34, yc, strokeColor=col, strokeWidth=2))
                d.add(String(x0 + 38, yc - 2.7, txt, fontName="Helvetica-Bold", fontSize=fs, textAnchor="start", fillColor=col))
                d.add(String(bx + bw - 4, yc - 2.8, _pdf_plain(pname), fontName="Helvetica-Bold", fontSize=7.8, textAnchor="end", fillColor=hx("#102027")))
    lx = 10.0
    for lab, k in _IC_LEGEND:
        d.add(Rect(lx, 12, 7, 7, fillColor=hx(_IC_COLORS[k]), strokeColor=hx(_IC_COLORS[k])))
        d.add(String(lx + 10, 12.5, _pdf_plain(lab), fontName="Helvetica", fontSize=7, fillColor=hx("#37474f")))
        lx += 10 + stringWidth(lab, "Helvetica", 7) + 14
    return d


def _offline_digital_next_steps(analysis, ica):
    st_ = analysis["det_status"]
    if st_ == "PASS":
        return ["Record the verified truth table in your lab notebook.",
                "Optionally verify the unused gates of the IC with a separate test - this test did not exercise them.",
                "Measure VCC and GND at the IC once to confirm the supply was correct."]
    steps = []
    bad = [c for c in analysis.get("cells", []) if c["status"] in ("MISMATCH", "INVALID")]
    miss = [c for c in analysis.get("cells", []) if c["status"] == "MISSING"]
    if miss:
        steps.append(f"Measure the {len(miss)} missing cell(s) first - the result stays INCOMPLETE until every cell is measured.")
    if bad:
        c = bad[0]
        steps.append(f"Power off and re-check the wiring against the IC pin diagram, then measure Row {c['row']} ({c['inputs']}), output {c['output']} again with a multimeter.")
        steps.append("Measure VCC and GND directly at the IC pins and confirm all unused inputs are tied (not floating).")
        steps.append("Fix one thing at a time and re-measure only the failing rows, then re-run ANALYSE.")
    if not steps:
        steps.append("Complete the measurements and press ANALYSE DIGITAL CIRCUIT again.")
    return steps


def _lab_view(data):
    """Unified dict of the diagnosis fields used by the PDF, from Gemini (validated) or the offline engine."""
    if data["kind"] == "digital":
        s = data.get("lab")
        off = data["offline"]
        k = data.get("knowledge") or {}
        a, ica = data["analysis"], data.get("ic_assessment") or {}
        if s:
            v = dict(s)
            v["ai"] = True
            v["fault"], v["diag"], v["guide"] = s.get("fault_probability"), s.get("overall_circuit_diagnosis_probability"), s.get("overall_circuit_guide_probability")
            return v
        return {"ai": False, "circuit_condition": {"PASS": "NORMAL", "FAIL": "FAULT"}.get(a["det_status"], "INSUFFICIENT DATA"),
                "data_sufficiency": "SUFFICIENT" if a["det_status"] != "INCOMPLETE" else "INSUFFICIENT DATA",
                "operating_correctly": {"PASS": "YES", "FAIL": "NO"}.get(a["det_status"], "UNCERTAIN"),
                "circuit_health_assessment": off["summary"], "what_circuit_should_do": k.get("working_principle", ""),
                "what_measurements_indicate": off["summary"], "supporting_evidence": off["findings"][:8],
                "component_fault_assessment": [], "wiring_fault_assessment": {"probability_percent": None, "evidence": "Not assessed without Gemini.", "checks": []},
                "sensor_reliability": {"rating": "UNKNOWN", "evidence": "No independent sensor check was possible."},
                "suspected_component": "Not determined (rule-based comparison only)",
                "recommended_steps": off["actions"], "corrective_actions": [], "verification_procedure": [],
                "final_retest_recommendation": "Re-measure the failing rows after each correction and run ANALYSE again.",
                "teaching": _teaching_from_knowledge(k), "lab_assistant_next_steps": _offline_digital_next_steps(a, ica),
                "reasoning": "Local rule-based comparison of the measured truth table with the expected truth table.",
                "limitations": off["limitations"], "final_conclusion": "", "validation_notes": [],
                "fault": None, "diag": None, "guide": None}
    s = data.get("structured") or {}
    k = data.get("knowledge") or {}
    ai = str(data.get("engine", "")).upper().startswith("GEMINI") and bool(s)
    v = {"ai": ai, "circuit_condition": s.get("circuit_condition", "N/A"), "data_sufficiency": s.get("data_sufficiency", "LIMITED"),
         "operating_correctly": s.get("operating_correctly", "UNCERTAIN"),
         "circuit_health_assessment": s.get("circuit_health_assessment", ""), "what_circuit_should_do": s.get("what_circuit_should_do") or k.get("working_principle", ""),
         "what_measurements_indicate": s.get("what_measurements_indicate", ""), "supporting_evidence": s.get("supporting_evidence", []),
         "component_fault_assessment": s.get("component_fault_assessment", []),
         "wiring_fault_assessment": s.get("wiring_fault_assessment") or {"probability_percent": None, "evidence": "", "checks": []},
         "sensor_reliability": s.get("sensor_reliability") or {"rating": "UNKNOWN", "evidence": ""},
         "suspected_component": s.get("suspected_component", "N/A"), "recommended_steps": s.get("recommended_steps", []),
         "corrective_actions": s.get("corrective_actions", []), "verification_procedure": s.get("verification_procedure", []),
         "final_retest_recommendation": s.get("final_retest_recommendation", ""),
         "teaching": s.get("teaching") or _teaching_from_knowledge(k), "lab_assistant_next_steps": s.get("lab_assistant_next_steps", []),
         "reasoning": s.get("reasoning", ""), "limitations": s.get("limitations", []), "final_conclusion": s.get("final_conclusion", ""),
         "detected_problem": s.get("detected_problem", ""), "diagnosis": s.get("diagnosis", ""), "ripple_assessment": s.get("ripple_assessment", "NOT ASSESSED - no ripple data is available."),
         "validation_notes": s.get("validation_notes", []),
         "fault": s.get("fault_probability", data.get("fault_probability")), "diag": s.get("overall_circuit_diagnosis_probability", data.get("confidence")),
         "guide": s.get("overall_circuit_guide_probability")}
    if not v["teaching"].get("purpose") and k:
        v["teaching"] = _teaching_from_knowledge(k)
    return v



def _gemini_block_digital(res):
    st_ = res.get("gemini_status", "NOT_RUN")
    if st_ == "OK" and res.get("gemini_report"):
        return {"status": "GENERATED", "text": res["gemini_report"], "note": "AI-generated engineering interpretation for this exact test."}
    if st_ == "PENDING":
        return {"status": "NOT COMPLETED", "text": "", "note": "The Gemini analysis was still running when this report was generated; regenerate the report after it finishes."}
    if st_ == "NO_KEY":
        return {"status": "NOT RUN", "text": "", "note": "Gemini was not run for this test (no API key configured at analysis time)."}
    if st_ == "ERROR":
        return {"status": "UNAVAILABLE", "text": "", "note": str(res.get("gemini_error") or "Gemini request failed.")}
    return {"status": "NOT RUN", "text": "", "note": "Gemini analysis has not been run for this test."}


def build_report_data(record, student, generated_at=None):
    """Converts a stored test record into the plain data structure used by the PDF.
    Only values frozen in the record are used - nothing is measured or invented here, and no live
    sensor value is ever read (old records without the newer fields are completed deterministically
    from their own frozen snapshot)."""
    generated_at = generated_at or datetime.datetime.now()
    res = record["result"]
    data = {
        "kind": record["kind"], "student": dict(student), "generated_at": generated_at,
        "test_id": record["test_id"], "circuit": record["circuit"], "category": record["category"],
        "test_time": record["timestamp"], "warnings": [],
    }
    if record["kind"] == "digital":
        info = res.get("circuit_info", {})
        sub = info.get("sub_type")
        width = res.get("bit_width", 4)
        ica = res.get("ic_assessment")
        if not ica:
            try:
                ica = compute_ic_assessment(sub, width, res, res.get("ic_context"))
            except Exception as exc:  # never fail the report because of the IC assessment
                ica = {"available": False, "reason": f"IC assessment could not be computed ({exc}).", "ics": []}
        plan = build_ic_plan(sub, width)
        data.update({
            "overall_status": res["det_status"],
            "circuit_type": info.get("type", "N/A"),
            "description": info.get("description", "N/A"),
            "boolean_expressions": get_digital_boolean_expressions(sub, width),
            "diagram": build_logic_diagram(sub, width),
            "analysis": res,
            "expected_rows": res.get("expected_rows", []),
            "offline": build_offline_digital_diagnosis(res),
            "gemini": _gemini_block_digital(res),
            "knowledge": get_circuit_knowledge(record["category"], record["circuit"], width),
            "ic_plan": plan, "ic_assessment": ica, "lab": res.get("gemini_structured"),
        })
        if res["det_status"] == "INCOMPLETE":
            data["warnings"].append(f"INCOMPLETE test: {res['missing_cells']} missing and {res['invalid_cells']} invalid cell(s). "
                                    f"The circuit can be neither passed nor failed.")
        if data["diagram"] is None:
            data["warnings"].append("No logic diagram is available for this circuit type.")
    else:
        snap = res["sensor"]
        eng = str(res.get("engine", "GEMINI"))
        if eng.upper().startswith("GEMINI"):
            gem = {"status": "GENERATED", "text": res.get("text", ""), "note": "AI-generated interpretation for this exact test."}
        else:
            gem = {"status": "NOT USED", "text": res.get("text", ""),
                   "note": f"Gemini was not used for this test; the diagnosis below was produced by the {eng} (rule-based, local)."}
        ev = res.get("evidence")
        if not ev:
            ev = compute_rectifier_evidence(record["circuit"], snap, res["targets"], res.get("source", "LIVE"))
        data.update({
            "overall_status": res["status"], "info": res.get("circuit_info", {}), "targets": res["targets"],
            "snapshot": snap, "deviations": res.get("deviations", {}), "source": res.get("source", "N/A"),
            "engine": eng, "fault_probability": res.get("fault_probability"), "confidence": res.get("confidence"),
            "structured": res.get("structured"), "gemini": gem, "evidence": ev,
            "knowledge": get_circuit_knowledge(record["category"], record["circuit"]),
            "schematic": build_analog_schematic(record["circuit"]),
        })
        if res.get("source") == "HELD":
            data["warnings"].append("Input voltage/current were HELD values captured earlier; output values were live readings.")
        if str(snap.get("frequency", 0)) in ("0", "0.0") and str(snap.get("temperature", 0)) in ("0", "0.0"):
            data["warnings"].append("Frequency and temperature are 0: the sensor may not report them.")
        if data["structured"] is not None and "teaching" not in data["structured"]:
            data["warnings"].append("This record was created by an earlier NEXUS version: the AI diagnosis has no lab-assistant sections; the teaching notes below come from the NEXUS knowledge base.")
    data["lab_view"] = _lab_view(data)
    return data


def report_summary_lines(data):
    """Short plain-text outcome summary (used by the PDF and the UI)."""
    if data["kind"] == "digital":
        a = data["analysis"]
        lines = [f"Overall result: {data['overall_status']}",
                 f"Coverage: {a['coverage_pct']:.1f}% ({a['valid_cells']}/{a['total_cells']} valid output cells)",
                 f"Correct matches: {a['correct_matches']}, mismatches: {a['mismatches']}, "
                 f"missing: {a['missing_cells']}, invalid: {a['invalid_cells']}"]
        ica = data.get("ic_assessment") or {}
        if ica.get("available"):
            lines.append(f"IC health (evidence-based): {ica['overall_verdict']}")
        return lines
    s = data["snapshot"]
    return [f"Overall result: {data['overall_status']}",
            f"Measured input {_fmt(s.get('input_v'))} V / {_fmt(s.get('input_i'))} A, "
            f"output {_fmt(s.get('output_v'))} V / {_fmt(s.get('output_i'))} A, efficiency {_fmt(s.get('efficiency'))} %"]


def build_report_conclusion(data):
    if data["kind"] == "digital":
        a = data["analysis"]
        if data["overall_status"] == "PASS":
            return (f"The {data['circuit']} produced the expected output in all {a['total_cells']} required truth-table cells "
                    f"(coverage 100 %). The circuit passed the test.")
        if data["overall_status"] == "FAIL":
            return (f"The {data['circuit']} was fully measured but {a['mismatches']} of {a['total_cells']} outputs differ from the "
                    f"expected truth table. The circuit failed the test.")
        return (f"The test of the {data['circuit']} is INCOMPLETE ({a['coverage_pct']:.1f} % coverage, {a['missing_cells']} missing, "
                f"{a['invalid_cells']} invalid). No PASS or FAIL decision can be made until every cell is measured with a valid logic level.")
    s = data["snapshot"]
    return (f"For the {data['circuit']}, the measured output voltage was {_fmt(s.get('output_v'))} V against a target of "
            f"{_fmt(data['targets'].get('target_output_voltage'))} V. The deterministic comparison of the four measured quantities "
            f"with their targets gives the overall result {data['overall_status']}.")


# ------------------------------------------------------------------------------
# PDF GENERATION
# ------------------------------------------------------------------------------
_STATUS_COLORS = {"PASS": "#1a8f4c", "NORMAL": "#1a8f4c", "MATCH": "#1a8f4c", "FAIL": "#c62828", "MISMATCH": "#c62828",
                  "INCOMPLETE": "#b26a00", "WARNING": "#b26a00", "INVALID": "#b26a00", "MISSING": "#b26a00"}


def _make_numbered_canvas(meta):
    from reportlab.pdfgen import canvas as rl_canvas

    class _NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_pages = []

        def showPage(self):
            self._saved_pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_pages)
            for state in self._saved_pages:
                self.__dict__.update(state)
                self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total):
            w, h = A4
            self.setStrokeColor(colors.HexColor("#9fb3c8"))
            self.setLineWidth(0.5)
            self.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#4a5a6e"))
            self.drawString(18 * mm, 10.5 * mm, _pdf_plain(f"NEXUS Test Report | {meta['student']} | Test ID {meta['test_id']}"))
            self.drawRightString(w - 18 * mm, 10.5 * mm, f"Page {self._pageNumber} of {total}")
            self.drawString(18 * mm, 6.5 * mm, _pdf_plain(f"Report generated: {meta['generated']}"))
            self.drawRightString(w - 18 * mm, h - 10 * mm, "NEXUS - AI-Based Electronic Circuit Tester")
            self.drawString(18 * mm, h - 10 * mm, _pdf_plain(f"Laboratory Report | Test ID {meta['test_id']}"))
            self.line(18 * mm, h - 12.5 * mm, w - 18 * mm, h - 12.5 * mm)

    return _NumberedCanvas


def _pdf_plain(value):
    """latin-1 safe text WITHOUT XML escaping (for canvas.drawString)."""
    text = str(value if value is not None else "N/A")
    for k, v in _PDF_CHAR_MAP.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def _md_to_para(line):
    """Escapes a Gemini/markdown line for ReportLab and converts **bold**."""
    safe = _pdf_safe(line)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)


def _text_block(text, body, head, bullet):
    out = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            out.append(Spacer(1, 3))
            continue
        m = re.match(r"^#{1,6}\s*(.*)$", line)
        if m:
            out.append(Paragraph(_md_to_para(m.group(1)), head))
        elif re.match(r"^[\*\-]\s+", line):
            out.append(Paragraph("- " + _md_to_para(re.sub(r"^[\*\-]\s+", "", line)), bullet))
        else:
            clean = line.replace("```", "")
            out.append(Paragraph(_md_to_para(clean), body))
    return out


def generate_test_report_pdf(data):
    """Creates the professional A4 laboratory report (circuit schematic / logic diagram, IC pin diagrams,
    component list, calculations, deterministic status, AI lab-assistant analysis, IC health, teaching notes)
    and returns the PDF bytes. Pure function of `data` (a frozen test record) - never reads live sensors."""
    from reportlab.platypus import CondPageBreak, KeepTogether
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            title=f"NEXUS Electronic Circuit Laboratory Report - {_pdf_plain(data['circuit'])}",
                            author="NEXUS - AI-Based Electronic Circuit Tester",
                            subject=f"Test ID {data['test_id']}")
    CW = 174 * mm
    base = getSampleStyleSheet()
    S = {
        "band1": ParagraphStyle("band1", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#9fd8ff"), leading=14),
        "band2": ParagraphStyle("band2", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=20, textColor=colors.white, leading=24),
        "band3": ParagraphStyle("band3", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#d6e6f5"), leading=12),
        "h1": ParagraphStyle("h1", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=colors.HexColor("#0b3c5d"), spaceBefore=10, spaceAfter=5, keepWithNext=1),
        "h2": ParagraphStyle("h2", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, textColor=colors.HexColor("#0b3c5d"), spaceBefore=7, spaceAfter=3, keepWithNext=1),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12),
        "small": ParagraphStyle("small", parent=base["Normal"], fontName="Helvetica", fontSize=8.5, leading=11),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontName="Helvetica", fontSize=8.3, leading=10.5),
        "cellb": ParagraphStyle("cellb", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.3, leading=10.5),
        "cellh": ParagraphStyle("cellh", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.3, leading=10.5, textColor=colors.white),
        "note": ParagraphStyle("note", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=8, leading=10.5, textColor=colors.HexColor("#4a5a6e")),
        "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12, leftIndent=10, firstLineIndent=-0),
        "mono": ParagraphStyle("mono", parent=base["Normal"], fontName="Courier", fontSize=9, leading=12, leftIndent=6),
    }

    def P(text, style="body"):
        return Paragraph(_md_to_para(text), S[style])

    def tbl(rows, widths, header=True, align_right_from=None, extra=None, repeat=1):
        t = Table(rows, colWidths=widths, repeatRows=repeat if header else 0)
        style = [("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fb3c8")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                 ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3c5d")),
                      ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f7fb")])]
        if align_right_from is not None:
            style.append(("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"))
        if extra:
            style += extra
        t.setStyle(TableStyle(style))
        return t

    def C(text, style="cell"):
        return Paragraph(_md_to_para(text), S[style])

    def kv_rows(pairs):
        return [[Paragraph(f"<b>{_pdf_safe(a)}</b>", S["cell"]), C(str(b))] for a, b in pairs]

    def head_row(labels):
        return [Paragraph(_pdf_safe(x), S["cellh"]) for x in labels]

    def BL(items, numbered=False):
        return [Paragraph((f"{i}. " if numbered else "- ") + _md_to_para(x), S["bullet"]) for i, x in enumerate(items, 1)]

    el = []
    sec = [0]

    def SEC(title, min_space=45):
        sec[0] += 1
        el.append(CondPageBreak(min_space * mm))
        el.append(Paragraph(f"{sec[0]}. {_pdf_safe(title)}", S["h1"]))

    def FIG(drawing, caption):
        el.append(KeepTogether([drawing, Spacer(1, 2), P(caption, "note")]))

    stu = data["student"]
    status = data["overall_status"]
    scol = colors.HexColor(_STATUS_COLORS.get(status, "#0b3c5d"))
    lab = data.get("lab_view") or _lab_view(data)
    k = data.get("knowledge") or {}
    digital = data["kind"] == "digital"

    # ------------------------------------------------------------ cover band + status
    title_txt = stu.get("report_title") or "Electronic Circuit Laboratory Report"
    band = Table([[Paragraph("NEXUS - AI-BASED ELECTRONIC CIRCUIT TESTER", S["band1"])],
                  [Paragraph(_pdf_safe(title_txt), S["band2"])],
                  [Paragraph(_pdf_safe(f"{data['category']} | {data['circuit']}"), S["band3"])]], colWidths=[CW])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0b3c5d")),
                              ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (0, 0), 12),
                              ("BOTTOMPADDING", (0, -1), (-1, -1), 12)]))
    el += [band, Spacer(1, 10)]
    badge = Table([[Paragraph("<b>OVERALL TEST RESULT (deterministic)</b>", S["cellb"]),
                    Paragraph(f"<font color='white'><b>{_pdf_safe(status)}</b></font>", ParagraphStyle("badge", parent=S["body"], fontSize=15, leading=18, alignment=1))]],
                  colWidths=[CW * 0.6, CW * 0.4])
    badge.setStyle(TableStyle([("BACKGROUND", (1, 0), (1, 0), scol), ("BOX", (0, 0), (-1, -1), 0.8, scol),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    el += [badge, Spacer(1, 4)]

    # ------------------------------------------------------------ 1 student & test information
    SEC("Student and Test Information", 30)
    srows = [("Student name", stu["name"]), ("Year / Academic year", stu["year"]), ("Division", stu["division"])]
    for key, lab_ in (("roll_no", "Roll number"), ("college", "College"), ("branch", "Branch")):
        if stu.get(key):
            srows.append((lab_, stu[key]))
    irows = [("Test ID", data["test_id"]), ("Test date and time", data["test_time"].strftime("%Y-%m-%d %H:%M:%S")),
             ("Report generated", data["generated_at"].strftime("%Y-%m-%d %H:%M:%S")),
             ("Selected circuit", data["circuit"]), ("Circuit category", data["category"])]
    if digital:
        irows.append(("Circuit type", data["circuit_type"]))
    else:
        irows.append(("Analysis source", f"{data['source']} ({'held input + live output' if data['source'] == 'HELD' else 'all live'})"))
        irows.append(("Analysis engine", data["engine"]))
    el.append(tbl(kv_rows(srows + irows), [55 * mm, 119 * mm], header=False))
    el.append(Spacer(1, 4))
    for x in report_summary_lines(data):
        el.append(P(x))
    el.append(P("How to read this report: MEASURED values come from the NEXUS ESP32 sensor telemetry of the frozen test snapshot; EXPECTED values come from "
                "the circuit database / configured targets or the deterministic truth table; CALCULATED values are derived by NEXUS; AI-GENERATED text is an "
                "interpretation that never changes the deterministic result.", "note"))

    # ------------------------------------------------------------ 2 objective & working principle
    SEC("Circuit Objective and Working Principle", 40)
    el.append(P("Objective", "h2"))
    el.append(P(k.get("objective") or data.get("description") or (data.get("info") or {}).get("description", "N/A")))
    el.append(P("Working principle", "h2"))
    el.append(P(k.get("working_principle") or data.get("description") or "N/A"))
    if digital and data.get("boolean_expressions"):
        el.append(P("Boolean expression / functional description", "h2"))
        for ex in data["boolean_expressions"]:
            el.append(Paragraph(_pdf_safe(ex), S["mono"]))

    # ------------------------------------------------------------ 3 schematic / logic diagram
    SEC("Complete Circuit Schematic" if not digital else "Complete Logic Diagram", 80)
    if digital:
        if data.get("diagram") is not None:
            try:
                FIG(render_diagram_drawing(data["diagram"], CW),
                    f"Figure 1: Logic gate diagram of the {data['circuit']} (generated from the NEXUS circuit definition; a functional logic diagram - "
                    f"the verified IC-level wiring is given in the IC pin diagrams below).")
            except Exception as exc:
                el.append(P(f"Diagram could not be rendered: {exc}", "note"))
        else:
            el.append(P("No logic diagram is available for this circuit.", "note"))
        flow = (data.get("ic_assessment") or {}).get("signal_flow") or []
        if flow:
            el.append(P("Expected logic signal flow (gate by gate, with IC pin numbers)", "h2"))
            el += BL(flow)
    else:
        sch = data.get("schematic")
        if sch is not None:
            try:
                FIG(render_diagram_drawing(sch, CW),
                    f"Figure 1: Schematic of the {data['circuit']} in its standard configuration, generated from the NEXUS circuit definition "
                    f"(component references, values and probe positions P1-P3 come from the database). It shows the INTENDED configuration; "
                    f"NEXUS cannot verify the physical wiring of the student's board.")
            except Exception as exc:
                el.append(P(f"Schematic could not be rendered: {exc}", "note"))
        else:
            el.append(P("A drawn schematic is not available for this circuit; only a functional description is given: "
                        + str((data.get("info") or {}).get("diagram", "N/A")), "note"))
        el.append(P("IC pin diagram", "h2"))
        el.append(P("Not applicable: this analogue circuit is built from discrete components (transformer, diodes, capacitor, resistor). "
                    "If a 4-pin bridge module (1B4B42) is used, connect its AC~ pins to the transformer and its +/- pins to the load."))

    if digital and data.get("ic_plan"):
        SEC("IC Pin Diagram (DIP, top view)", 85)
        el.append(P("Pin numbers follow the manufacturer pin-out of each IC type (taken from the NEXUS IC database; 7400/7408/7432/7486, 7402, 7404, 74LS266 and 74157 have DIFFERENT pin-outs). "
                    "Pin 1 is at the notch/dot marker. VCC and GND, inputs and outputs are colour coded.", "note"))
        for i, ic in enumerate(data["ic_plan"]["ics"], 1):
            try:
                FIG(render_ic_drawing(ic, CW), f"Figure 2.{i}: {ic['ref']} - {IC_PARTS[ic['part']]['label']} ({ic['role']}). Colour = role; text = connection used in this test.")
            except Exception as exc:
                el.append(P(f"IC pin diagram for {ic['ref']} could not be rendered: {exc}", "note"))

    # ------------------------------------------------------------ component list
    SEC("Component List and Function of Each Component", 60)
    comps = k.get("components") or []
    if comps:
        rows = [head_row(["Ref.", "Component", "Value / type", "Function"])]
        for c in comps:
            rows.append([C(c["ref_label"], "cellb"), C(c["name"]), C(c["value"]), C(c["function"])])
        el.append(tbl(rows, [18 * mm, 50 * mm, 26 * mm, 80 * mm]))
    else:
        el.append(P(f"Components (from the database): {(data.get('info') or {}).get('components', 'N/A')}"))

    # ------------------------------------------------------------ connections
    SEC("Circuit Connection Details", 50)
    if digital:
        ica = data.get("ic_assessment") or {}
        rows_w = ica.get("wiring_rows") or (ic_wiring_rows(data["ic_plan"]) if data.get("ic_plan") else [])
        if rows_w:
            body = [head_row(["IC", "Pin", "Pin name", "Role", "Connect to"])]
            for r in rows_w:
                body.append([C(r["IC"]), C(str(r["Pin"])), C(r["Pin name"]), C(r["Role"]), C(r["Connect to"])])
            el.append(tbl(body, [34 * mm, 10 * mm, 20 * mm, 28 * mm, 82 * mm]))
        if ica.get("nets"):
            el.append(P("Internal nets (wire these between ICs)", "h2"))
            body = [head_row(["Net", "Meaning", "Driven by", "Goes to"])]
            ref_part = {i["ref"]: i["part"] for i in (data.get("ic_plan") or {}).get("ics", [])}
            for nt in ica["nets"]:
                dr, dp = nt["driver"]
                loads = ", ".join(f"{lr} pin {_ic_pin_no(ref_part[lr], lp)} ({lp})" for lr, lp in nt["loads"] if lr in ref_part)
                body.append([C(nt["net"], "cellb"), C(nt["meaning"]), C(f"{dr} pin {_ic_pin_no(ref_part[dr], dp)} ({dp})" if dr in ref_part else str(dr)), C(loads)])
            el.append(tbl(body, [16 * mm, 50 * mm, 45 * mm, 63 * mm]))
        if ica.get("notes"):
            el.append(P("Wiring notes", "h2"))
            el += BL(ica["notes"])
    else:
        el += BL(k.get("connections", []))
        el.append(P("Measurement probe positions (P1-P3 on the schematic)", "h2"))
        prow = [head_row(["Probe", "Name", "Location"])]
        for pr in (data.get("info") or {}).get("probes", []) or []:
            prow.append([C(f"P{pr.get('step')}", "cellb"), C(str(pr.get("name"))), C(str(pr.get("loc")))])
        el.append(tbl(prow, [16 * mm, 45 * mm, 113 * mm]))

    # ------------------------------------------------------------ expected parameters / truth table
    if digital:
        a = data["analysis"]
        SEC("Expected Truth Table and Logic Thresholds", 50)
        rows_exp = data.get("expected_rows", [])
        if rows_exp:
            cols = list(rows_exp[0].keys())
            body = [head_row(cols)] + [[C(str(r.get(c, ""))) for c in cols] for r in rows_exp]
            el.append(tbl(body, [CW / len(cols)] * len(cols)))
        el.append(P(f"Logic thresholds used for classification: logic 0 <= {a['thresholds']['v_il']} V, logic 1 >= {a['thresholds']['v_ih']} V, otherwise INVALID.", "note"))
    else:
        info, tg, dev, snap, ev = data["info"], data["targets"], data["deviations"], data["snapshot"], data["evidence"]
        SEC("Expected Electrical Parameters", 55)
        t_in_p = tg["target_input_voltage"] * tg["target_input_current"]
        t_out_p = tg["target_output_voltage"] * tg["target_output_current"]
        t_eff = (t_out_p / t_in_p * 100.0) if t_in_p > 0 else 0.0
        db_ripple = CIRCUIT_DATABASE["Rectifiers"].get(data["circuit"], {}).get("exp_ripple")
        rows = [head_row(["Parameter", "Expected value", "Source"]),
                [C("Input voltage"), C(f"{_fmt(tg['target_input_voltage'])} V"), C("database / configured target")],
                [C("Input current"), C(f"{_fmt(tg['target_input_current'], 3)} A"), C("database / configured target")],
                [C("Output voltage"), C(f"{_fmt(tg['target_output_voltage'])} V"), C("database / configured target")],
                [C("Output current"), C(f"{_fmt(tg['target_output_current'], 3)} A"), C("database / configured target")],
                [C("Input power"), C(f"{_fmt(t_in_p)} W"), C("calculated: Vin x Iin")],
                [C("Output power"), C(f"{_fmt(t_out_p)} W"), C("calculated: Vout x Iout")],
                [C("Efficiency (from targets)"), C(f"{_fmt(t_eff)} %"), C("calculated: Pout / Pin x 100")],
                [C("Nominal efficiency (database)"), C(f"{info.get('exp_eff', 'N/A')} %"), C("database")]]
        if db_ripple is not None:
            rows.append([C("Ripple factor (theory, no filter)"), C(f"{db_ripple} %"), C("database - NOT measured by NEXUS")])
        el.append(tbl(rows, [55 * mm, 45 * mm, 74 * mm]))
        th = ev.get("theory") or {}
        if th.get("unfiltered_average_dc_v") is not None or th.get("target_unfiltered_average_dc_v") is not None:
            el.append(P("Theory reference (calculated from the measured input voltage)", "h2"))
            trow = [head_row(["Quantity", "Value"])]
            for lab_, key, unit in (("Secondary peak voltage (Vrms x 1.414)", "secondary_peak_v", "V"),
                                     ("Assumed diode drop (total in path)", "diode_drop_v", "V"),
                                     ("No-load filtered peak limit (C1 connected)", "no_load_filtered_peak_limit_v", "V"),
                                     ("Unfiltered average DC (no C1)", "unfiltered_average_dc_v", "V"),
                                     ("Unfiltered average DC at the TARGET input", "target_unfiltered_average_dc_v", "V"),
                                     ("Maximum theoretical rectification efficiency", "max_efficiency_percent", "%"),
                                     ("Ripple frequency (from measured mains frequency)", "ripple_frequency_hz", "Hz")):
                if th.get(key) is not None:
                    trow.append([C(lab_), C(f"{th[key]} {unit}")])
            el.append(tbl(trow, [105 * mm, 69 * mm]))
            el.append(P(th.get("assumptions", ""), "note"))
        for c in ev.get("checks", []):
            if c["id"] == "target_is_unfiltered":
                el.append(P("Note on the expected output value: " + c["text"], "note"))

    # ------------------------------------------------------------ measured parameters, comparison, calculations
    if digital:
        SEC("Measured Truth-Table Results", 60)
        stats = [head_row(["Quantity", "Value"])] + kv_rows([
            ("Total required output cells", a["total_cells"]), ("Valid measured cells", a["valid_cells"]),
            ("Correct matches", a["correct_matches"]), ("Mismatches", a["mismatches"]),
            ("Missing cells", a["missing_cells"]), ("Invalid logic levels", a["invalid_cells"]),
            ("Test coverage", f"{a['coverage_pct']:.1f} %"), ("Deterministic result", a["det_status"])])
        el.append(KeepTogether([tbl(stats, [70 * mm, 104 * mm])]))
        el.append(P("Measured results - cell-by-cell comparison", "h2"))
        crow = [head_row(["Row", "Input combination", "Output", "Expected", "Measured V", "State", "Result"])]
        extra = []
        for i, c in enumerate(a.get("cells", []), start=1):
            crow.append([C(str(c["row"])), C(c["inputs"]), C(c["output"]), C(str(c["expected"])), C(c["voltage"]), C(c["state"]), C(c["status"], "cellb")])
            extra.append(("TEXTCOLOR", (6, i), (6, i), colors.HexColor(_STATUS_COLORS.get(c["status"], "#000000"))))
        el.append(tbl(crow, [12 * mm, 52 * mm, 20 * mm, 20 * mm, 26 * mm, 20 * mm, 24 * mm], extra=extra))
        el.append(P("Result key: MATCH = measured logic equals expected; MISMATCH = measured logic differs; INVALID = voltage between the thresholds or unusable; MISSING = no measurement saved.", "note"))
        SEC("Test Status (PASS / FAIL / INCOMPLETE)", 35)
        el.append(Paragraph(f"<b>{_pdf_safe(status)}</b> - {_pdf_safe(data['offline']['summary'])}", S["body"]))
        el.append(P("Deterministic rule: PASS only when every required cell is measured with a valid logic level and matches; INCOMPLETE when any cell is missing or invalid; FAIL when all cells are valid but at least one does not match. This result is computed by Python and is never changed by the AI.", "note"))
    else:
        SEC("Actual Measured Parameters and Comparison", 60)
        srcn = snap.get("captured_at")
        el.append(P(f"Snapshot analysed: {data['source']} input (V, I) with LIVE output (V, I), frequency and temperature"
                    + (f"; input captured at {srcn.strftime('%H:%M:%S')}" if (data['source'] == 'HELD' and srcn) else "") + ". "
                    "This is the exact snapshot sent to the analysis; later sensor values are not used."))

        def devtxt(key):
            return f"{_fmt(dev.get(key))} %" if key in dev else "N/A"
        rows = [head_row(["Parameter", "Expected (target)", "Measured", "Deviation"]),
                [C("Input voltage"), C(f"{_fmt(tg.get('target_input_voltage'))} V"), C(f"{_fmt(snap.get('input_v'))} V"), C(devtxt("Input Voltage"))],
                [C("Output voltage"), C(f"{_fmt(tg.get('target_output_voltage'))} V"), C(f"{_fmt(snap.get('output_v'))} V"), C(devtxt("Output Voltage"))],
                [C("Input current"), C(f"{_fmt(tg.get('target_input_current'), 3)} A"), C(f"{_fmt(snap.get('input_i'), 3)} A"), C(devtxt("Input Current"))],
                [C("Output current"), C(f"{_fmt(tg.get('target_output_current'), 3)} A"), C(f"{_fmt(snap.get('output_i'), 3)} A"), C(devtxt("Output Current"))],
                [C("Frequency"), C("-"), C(f"{_fmt(snap.get('frequency'), 1)} Hz"), C("-")],
                [C("Temperature"), C("-"), C(f"{_fmt(snap.get('temperature'), 1)} C"), C("-")]]
        el.append(tbl(rows, [50 * mm, 42 * mm, 42 * mm, 40 * mm], align_right_from=1))
        el.append(P("Deviation = |measured - target| / target x 100 (calculated). Ripple was NOT measured.", "note"))
        SEC("Voltage, Current, Power and Efficiency Calculations", 60)
        vi, vo, ii, io_ = snap.get("input_v"), snap.get("output_v"), snap.get("input_i"), snap.get("output_i")
        calc = [head_row(["Quantity", "Formula", "Calculation", "Result"]),
                [C("Voltage drop"), C("Vin - Vout"), C(f"{_fmt(vi)} - {_fmt(vo)}"), C(f"{_fmt(snap.get('v_drop'))} V")],
                [C("Input power"), C("Pin = Vin x Iin"), C(f"{_fmt(vi)} x {_fmt(ii, 3)}"), C(f"{_fmt(snap.get('power_in'))} W")],
                [C("Output power"), C("Pout = Vout x Iout"), C(f"{_fmt(vo)} x {_fmt(io_, 3)}"), C(f"{_fmt(snap.get('power_out'))} W")],
                [C("Efficiency"), C("Pout / Pin x 100"), C(f"{_fmt(snap.get('power_out'))} / {_fmt(snap.get('power_in'))} x 100"), C(f"{_fmt(snap.get('efficiency'))} %  (nominal {info.get('exp_eff', 'N/A')} %)")],
                [C("Power lost"), C("Pin - Pout"), C(f"{_fmt(snap.get('power_in'))} - {_fmt(snap.get('power_out'))}"),
                 C(f"{_fmt((snap.get('power_in') or 0) - (snap.get('power_out') or 0))} W")]]
        try:
            if io_ and float(io_) > 1e-4:
                calc.append([C("Implied load resistance"), C("Vout / Iout"), C(f"{_fmt(vo)} / {_fmt(io_, 3)}"), C(f"{_fmt(float(vo) / float(io_), 1)} ohm")])
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        calc.append([C("Circuit health indicator"), C("100 - output-voltage deviation"), C("-"), C(f"{snap.get('health', 'N/A')} %")])
        el.append(tbl(calc, [34 * mm, 38 * mm, 58 * mm, 44 * mm]))
        SEC("Test Status (PASS / WARNING / FAIL)", 45)
        el.append(Paragraph(f"<b>{_pdf_safe(status)}</b> - computed by comparing the four measured quantities with their targets.", S["body"]))
        el.append(P("Deterministic rule: PASS when every parameter is within +/-5 % of its target, WARNING above 5 % up to 10 %, FAIL above 10 %. This result is never changed by the AI.", "note"))
        if ev.get("checks"):
            el.append(P("Measurement consistency checks (calculated by NEXUS)", "h2"))
            crow = [head_row(["Level", "Observation"])] + [[C(c["level"], "cellb"), C(c["text"])] for c in ev["checks"]]
            el.append(tbl(crow, [18 * mm, 156 * mm]))

    # ------------------------------------------------------------ AI / lab assistant analysis
    gem = data["gemini"]
    SEC("Gemini Complete Circuit Analysis" if lab["ai"] else "Circuit Analysis (rule-based; Gemini not used)", 60)
    el.append(P(gem["note"], "note"))
    if not lab["ai"] and gem.get("text") and not digital and data.get("structured") is None:
        el.append(P("Offline diagnosis text", "h2"))
        el += _text_block(gem["text"], S["small"], S["cellb"], S["bullet"])
    for title, key in (("Circuit health assessment", "circuit_health_assessment"), ("What the circuit is supposed to do", "what_circuit_should_do"),
                       ("What the actual measurements indicate", "what_measurements_indicate")):
        if lab.get(key):
            el.append(P(title, "h2"))
            el.append(P(lab[key], "small"))
    el.append(Paragraph(f"<b>Is the circuit operating correctly?</b> {_pdf_safe(lab.get('operating_correctly', 'UNCERTAIN'))} &nbsp;|&nbsp; "
                        f"<b>Overall circuit condition:</b> {_pdf_safe(lab.get('circuit_condition', 'N/A'))} &nbsp;|&nbsp; "
                        f"<b>Data sufficiency:</b> {_pdf_safe(lab.get('data_sufficiency', 'N/A'))}", S["small"]))
    if digital:
        for title, key in (("Matching outputs", "matching_rows_summary"), ("Missing and invalid measurements", "missing_or_invalid_summary"),
                           ("Coverage", "coverage_comment"), ("Gate / IC section that may be responsible", "responsible_section")):
            if lab.get(key):
                el.append(P(title, "h2"))
                el.append(P(lab[key], "small"))
        mmx = lab.get("mismatch_analysis") or []
        if mmx:
            el.append(P("Mismatching / invalid cells - analysis (causes are hypotheses, not confirmed faults)", "h2"))
            body = [head_row(["Row", "Inputs", "Out", "Exp.", "Meas.", "Observation and possible causes"])]
            for m_ in mmx:
                body.append([C(m_["row"]), C(m_["inputs"]), C(m_["output"]), C(m_["expected"]), C(m_["measured_state"]),
                             C(m_["observation"] + (" Possible causes: " + "; ".join(m_["possible_causes"]) if m_["possible_causes"] else ""))])
            el.append(tbl(body, [10 * mm, 30 * mm, 12 * mm, 11 * mm, 11 * mm, 100 * mm]))
        if not lab["ai"]:
            off = data["offline"]
            el.append(P("Offline digital diagnosis (local truth-table comparison)", "h2"))
            el += BL(off["findings"])
        if gem["status"] == "GENERATED" and not data.get("lab") and gem.get("text"):
            el.append(P("Gemini text (not structured - shown unvalidated)", "h2"))
            el += _text_block(gem["text"], S["small"], S["cellb"], S["bullet"])
    else:
        if lab.get("detected_problem"):
            el.append(P("Detected problem / suspected component", "h2"))
            el.append(P(f"{lab['detected_problem']}  |  Suspected: {lab.get('suspected_component', 'N/A')}", "small"))
        if lab.get("diagnosis"):
            el.append(P("Technical analysis", "h2"))
            el.append(P(lab["diagnosis"], "small"))
        el.append(P("Ripple", "h2"))
        el.append(P(lab.get("ripple_assessment") or "NOT ASSESSED - no ripple data is available.", "small"))
        if gem["status"] == "GENERATED" and data.get("structured") is None and gem.get("text"):
            el.append(P("Gemini text (not structured - shown unvalidated)", "h2"))
            el += _text_block(gem["text"], S["small"], S["cellb"], S["bullet"])

    # ------------------------------------------------------------ IC health assessment
    SEC("IC Health Assessment", 55)
    ica = data.get("ic_assessment") if digital else None
    if not digital:
        el.append(P("Not applicable: the rectifier circuits are built from discrete components; no logic IC is tested. Individual diode health cannot be assessed from the available measurements "
                    "(see the component-level assessment)."))
    elif not ica or not ica.get("available"):
        el.append(P((ica or {}).get("reason", "No IC assessment is available for this circuit."), "note"))
    else:
        vcol = {"HEALTHY_TESTED": "#1a8f4c", "INSUFFICIENT_DATA": "#b26a00", "MAY_BE_FAULTY": "#d35400", "FAULT_STRONGLY_SUSPECTED": "#c62828"}
        el.append(Paragraph(f"<b>Overall (evidence-based, computed by NEXUS):</b> <font color='{vcol.get(ica['overall_code'], '#000000')}'><b>{_pdf_safe(ica['overall_verdict'])}</b></font>", S["body"]))
        el.append(P(f"Pin-level evidence available: {ica['pin_level_evidence']}.", "small"))
        el.append(P(f"IC family: {ica['family']}.  Supply: {ica['supply']['text']}", "small"))
        if ica.get("family_levels"):
            el.append(P("Expected logic levels (typical datasheet): " + ica["family_levels"]["note"], "small"))
        ai_ic = {x["ic_ref"]: x for x in (lab.get("ic_assessments") or [])}
        for ic in ica["ics"]:
            blk = [P(f"{ic['ref']} - {ic['part_label']} ({ic['function']})", "h2")]
            colr = vcol.get(ic["verdict_code"], "#000000")
            blk.append(Paragraph(f"<b>Verdict:</b> <font color='{colr}'><b>{_pdf_safe(ic['verdict'])}</b></font>"
                                 + (f" &nbsp;(suspicion: {_pdf_safe(ic['suspicion'])})" if ic["suspicion"] not in ("NONE", None) else ""), S["body"]))
            mrows = [head_row(["Item", "Detail"]), [C("IC function / role"), C(f"{ic['function']} - {ic['role_in_circuit']}")],
                     [C("Package"), C(ic["package"])], [C("VCC pin / GND pin"), C(f"pin {ic['vcc_pin']} (VCC) / pin {ic['gnd_pin']} (GND)")],
                     [C("Input pins used"), C("; ".join(f"pin {p['pin']} ({p['name']}) {p['signal']}" for p in ic["input_pins"]) or "-")],
                     [C("Output pins used"), C("; ".join(f"pin {p['pin']} ({p['name']}) {p['signal']}" for p in ic["output_pins"]) or "-")],
                     [C("Expected supply voltage"), C(ic["expected_supply"])], [C("Expected logic levels"), C(ic["expected_logic_levels"])]]
            m_ = ic["measured"]
            lv1 = f"logic 1: {m_['logic1_levels_v'][0]}-{m_['logic1_levels_v'][1]} V" if m_["logic1_levels_v"] else "logic 1: not measured"
            lv0 = f"logic 0: {m_['logic0_levels_v'][0]}-{m_['logic0_levels_v'][1]} V" if m_["logic0_levels_v"] else "logic 0: not measured"
            mrows.append([C("Measured logic levels (output pin)"), C(lv1 + "; " + lv0)])
            mrows.append([C("Expected vs measured output"), C(f"{m_['matches']} match, {m_['mismatches']} mismatch, {m_['invalid']} invalid, {m_['missing']} missing "
                                                              f"({m_['cells_depending_on_ic']} cell(s) depend on this IC)")])
            mrows.append([C("Gates tested"), C(ic["gates_tested_note"])])
            blk.append(tbl(mrows, [48 * mm, 126 * mm]))
            blk += BL(ic["reasons"])
            for ln in ic["level_notes"]:
                blk.append(Paragraph("- " + _md_to_para("Level indicator: " + ln), S["bullet"]))
            el.append(KeepTogether(blk))
            if ic["alternative_causes"]:
                el.append(P("Other possible causes (must be excluded before blaming the IC)", "h2"))
                arow = [head_row(["Possible cause", "Status", "How to check"])] + [[C(a_["cause"]), C(a_["status"], "cellb"), C(a_["check"])] for a_ in ic["alternative_causes"]]
                el.append(tbl(arow, [58 * mm, 32 * mm, 84 * mm]))
            if ic["confirmations_needed"]:
                el.append(P("To upgrade or settle the verdict:", "h2"))
                el += BL(ic["confirmations_needed"])
            if ic["ref"] in ai_ic and ai_ic[ic["ref"]]["explanation"]:
                el.append(P("AI explanation", "h2"))
                el.append(P(ai_ic[ic["ref"]]["explanation"], "small"))
                el += BL(ai_ic[ic["ref"]]["still_unverified"])
        el.append(P("Limits of the IC assessment", "h2"))
        el += BL(ica["limitations"])

    # ------------------------------------------------------------ component-level fault assessment
    SEC("Component-Level and Wiring Fault Assessment", 45)
    comps_a = lab.get("component_fault_assessment") or []
    if comps_a:
        rows = [head_row(["Component", "Fault probability (AI est.)", "Evidence", "How to verify"])]
        for c in comps_a:
            rows.append([C(c["component"], "cellb"), C(_fmt_pct(c["probability_percent"]).replace(" (not estimated / insufficient data)", " (insufficient evidence)")), C(c["evidence"]), C(c["verify"])])
        el.append(tbl(rows, [32 * mm, 28 * mm, 62 * mm, 52 * mm]))
    else:
        el.append(P("No component-level probability is given: the available measurements are not sufficient to rate individual components."
                    + (" Individual diodes, the filter capacitor and the transformer cannot be assessed from voltage/current readings alone." if not digital else "")))
    w_ = lab.get("wiring_fault_assessment") or {}
    el.append(P("Wiring fault assessment", "h2"))
    el.append(P(f"Probability (AI estimate): {_fmt_pct(w_.get('probability_percent')).replace(' (not estimated / insufficient data)', ' (insufficient evidence)')}. {w_.get('evidence', '')}", "small"))
    el += BL(w_.get("checks", []))
    sr_ = lab.get("sensor_reliability") or {}
    el.append(P("Sensor / measurement reliability", "h2"))
    el.append(P(f"{sr_.get('rating', 'UNKNOWN')} - {sr_.get('evidence', '')}", "small"))
    if not digital and data.get("evidence", {}).get("not_assessable"):
        el.append(P("Cannot be assessed from the available data", "h2"))
        el += BL(data["evidence"]["not_assessable"])

    # ------------------------------------------------------------ probability & confidence
    SEC("Fault Probability and Diagnosis Confidence", 45)
    ai_lbl = "AI estimate" if lab["ai"] else "rule-based indicator"
    na = "N/A"

    def pc(v):
        return f"{v} %" if v is not None else na
    el.append(tbl([head_row(["Deterministic result", f"Fault probability ({ai_lbl})", f"Diagnosis confidence ({ai_lbl})", f"Confidence in recommended procedure ({ai_lbl})"]),
                   [C(status, "cellb"), C(pc(lab.get("fault"))), C(pc(lab.get("diag"))), C(pc(lab.get("guide")))]], [38 * mm, 42 * mm, 46 * mm, 48 * mm]))
    el.append(Spacer(1, 3))
    el.append(P("Fault probability = estimated chance that a real fault exists. Diagnosis confidence = confidence that the diagnosis is correct. Confidence in the procedure = confidence that the recommended steps are the right guidance. N/A means INSUFFICIENT DATA or not estimated.", "note"))
    el.append(P(AI_PROBABILITY_NOTICE, "note"))
    if not lab["ai"] and not digital:
        el.append(P("The offline rules engine derives these numbers from the worst measured deviation (rule of thumb); they are not statistical probabilities.", "note"))
    for nt in lab.get("validation_notes", []):
        el.append(P("Validation note: " + nt, "note"))

    # ------------------------------------------------------------ reasoning
    SEC("Technical Reasoning and Supporting Evidence", 40)
    if lab.get("reasoning"):
        el.append(P(lab["reasoning"], "small"))
    if lab.get("supporting_evidence"):
        el.append(P("Evidence supporting the diagnosis", "h2"))
        el += BL(lab["supporting_evidence"])
    if not lab.get("reasoning") and not lab.get("supporting_evidence"):
        el.append(P("No additional reasoning is available for this test."))

    # ------------------------------------------------------------ troubleshooting / corrective / verification
    SEC("Step-by-Step Troubleshooting Procedure", 40)
    el += BL(lab.get("recommended_steps") or ["No troubleshooting steps were generated."], numbered=True)
    if digital and ica and ica.get("available"):
        for ic in ica["ics"]:
            if ic["verdict_code"] in ("MAY_BE_FAULTY", "FAULT_STRONGLY_SUSPECTED", "INSUFFICIENT_DATA") and ic["verification_steps"]:
                el.append(P(f"Pin-by-pin verification for {ic['ref']} ({ic['part_label']})", "h2"))
                el += BL(ic["verification_steps"], numbered=True)
    SEC("Recommended Corrective Actions", 35)
    el += BL(lab.get("corrective_actions") or ["No corrective action is recommended on the available evidence; confirm any suspected item by measurement before replacing it."])
    SEC("Verification and Retesting Procedure", 35)
    el += BL(lab.get("verification_procedure") or ["Confirm the suspected item with a multimeter, then repeat the NEXUS test."], numbered=True)
    if lab.get("final_retest_recommendation"):
        el.append(P("Final retest recommendation", "h2"))
        el.append(P(lab["final_retest_recommendation"], "small"))

    # ------------------------------------------------------------ teaching / lab assistant
    SEC("Lab Assistant - Teaching Notes and What To Do Next", 60)
    t_ = lab.get("teaching") or {}
    for title, key in (("Purpose of this experiment", "purpose"), ("How the circuit works", "how_it_works")):
        if t_.get(key):
            el.append(P(title, "h2"))
            el.append(P(t_[key], "small"))
    for title, key in (("Why the components are used", "why_components"), ("What you should observe", "what_to_observe"),
                       ("What abnormal readings indicate", "abnormal_readings"), ("How to troubleshoot", "troubleshooting_tips"),
                       ("Precautions", "precautions"), ("What you should learn", "learning_outcomes")):
        if t_.get(key):
            el.append(P(title, "h2"))
            el += BL(t_[key])
    el.append(P("LAB ASSISTANT - WHAT TO DO NEXT", "h2"))
    el += BL(lab.get("lab_assistant_next_steps") or ["Re-check the wiring against the diagrams in this report and repeat the measurement."], numbered=True)

    # ------------------------------------------------------------ conclusion & limitations
    SEC("Final Conclusion", 35)
    el.append(P(build_report_conclusion(data)))
    if lab.get("final_conclusion"):
        el.append(P(lab["final_conclusion"], "small"))
    SEC("Limitations of the Measurements and Diagnosis", 40)
    limits = list(data["warnings"]) + list(lab.get("limitations") or [])
    if digital and ica and ica.get("available"):
        limits += ica["limitations"]
    limits += ["Measurements come from a single ESP32 sensor channel; sensor accuracy and calibration were not independently verified.",
               "AI-generated text is an interpretation and does not change the deterministic result.", AI_PROBABILITY_NOTICE]
    seen_l = set()
    uniq = [x for x in limits if not (x in seen_l or seen_l.add(x))]
    el += BL(uniq)

    meta = {"student": stu["name"], "test_id": data["test_id"], "generated": data["generated_at"].strftime("%Y-%m-%d %H:%M:%S")}
    doc.build(el, canvasmaker=_make_numbered_canvas(meta))
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def report_revision_key(student_clean, record):
    """Fingerprint of everything a generated report depends on (details + exact test record)."""
    payload = json.dumps({"student": student_clean, "test_id": record["test_id"], "kind": record["kind"],
                          "gem": record["result"].get("gemini_status", "")}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_history_pdf(record):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    elements = []

    user_question = record.get("User Question", "")

    elements.append(Paragraph("NEXUS AI ELECTRONIC CIRCUIT TEST REPORT", styles["Title"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Date:</b> {record.get('Date', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Time:</b> {record.get('Time', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Circuit:</b> {record.get('Circuit', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Status:</b> {record.get('Status', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Input Voltage:</b> {record.get('Input Voltage (V)', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Output Voltage:</b> {record.get('Output Voltage (V)', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Efficiency:</b> {record.get('Efficiency %', 'N/A')}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    if user_question:
        elements.append(Paragraph("<b>User Question:</b>", styles["Normal"]))
        safe_q = str(user_question).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        elements.append(Paragraph(safe_q, styles["Normal"]))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Gemini AI Response:</b>", styles["Normal"]))
    else:
        elements.append(Paragraph("<b>AI Answer / Diagnosis:</b>", styles["Normal"]))

    diag_text = record.get("AI Answer / Diagnosis", "N/A")
    safe_diag = str(diag_text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    elements.append(Paragraph(safe_diag, styles["Normal"]))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# ------------------------------------------------------------------------------
# 4. HOLLYWOOD-QUALITY AI OPERATING SYSTEM INTERFACE & GRAPHICS
# ------------------------------------------------------------------------------
st.set_page_config(page_title="NEXUS AI OS v2.3", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
# ==============================================================================
# IC PIN DIAGRAMS (DIP-14 / DIP-16, top view) FOR EVERY DIGITAL CIRCUIT
# Pin tables below were checked against manufacturer datasheets / pinout references:
#   7400/7408/7432/7486 (+74HC/74LS): 1A,1B,1Y,2A,2B,2Y,GND | 3Y,3A,3B,4Y,4A,4B,VCC
#   7402 (NOR) has the OUTPUT first: 1Y,1A,1B,2Y,2A,2B,GND | 3A,3B,3Y,4A,4B,4Y,VCC
#   7404 (hex inverter): 1A,1Y,2A,2Y,3A,3Y,GND | 4Y,4A,5Y,5A,6Y,6A,VCC
#   74LS266 (quad XNOR, open collector): 1A,1B,1Y,2Y,2A,2B,GND | 3A,3B,3Y,4Y,4A,4B,VCC
#   74HC157/74LS157 (quad 2:1 mux): S,1I0,1I1,1Y,2I0,2I1,2Y,GND | 3Y,3I1,3I0,4Y,4I1,4I0,/E,VCC
# The 7400/7408/7432/7486 family is NOT pin-identical to 7402/7404/74266 - do not reuse one table.
# ==============================================================================
IC_PARTS = {
    "08": {"label": "7408 / 74HC08 / 74LS08", "func": "Quad 2-input AND",
           "pins": ["1A", "1B", "1Y", "2A", "2B", "2Y", "GND", "3Y", "3A", "3B", "4Y", "4A", "4B", "VCC"]},
    "00": {"label": "7400 / 74HC00 / 74LS00", "func": "Quad 2-input NAND",
           "pins": ["1A", "1B", "1Y", "2A", "2B", "2Y", "GND", "3Y", "3A", "3B", "4Y", "4A", "4B", "VCC"]},
    "32": {"label": "7432 / 74HC32 / 74LS32", "func": "Quad 2-input OR",
           "pins": ["1A", "1B", "1Y", "2A", "2B", "2Y", "GND", "3Y", "3A", "3B", "4Y", "4A", "4B", "VCC"]},
    "86": {"label": "7486 / 74HC86 / 74LS86", "func": "Quad 2-input XOR",
           "pins": ["1A", "1B", "1Y", "2A", "2B", "2Y", "GND", "3Y", "3A", "3B", "4Y", "4A", "4B", "VCC"]},
    "02": {"label": "7402 / 74HC02 / 74LS02", "func": "Quad 2-input NOR",
           "pins": ["1Y", "1A", "1B", "2Y", "2A", "2B", "GND", "3A", "3B", "3Y", "4A", "4B", "4Y", "VCC"]},
    "04": {"label": "7404 / 74HC04 / 74LS04", "func": "Hex inverter (NOT)",
           "pins": ["1A", "1Y", "2A", "2Y", "3A", "3Y", "GND", "4Y", "4A", "5Y", "5A", "6Y", "6A", "VCC"]},
    "266": {"label": "74LS266", "func": "Quad 2-input XNOR, open-collector outputs",
            "pins": ["1A", "1B", "1Y", "2Y", "2A", "2B", "GND", "3A", "3B", "3Y", "4Y", "4A", "4B", "VCC"]},
    "157": {"label": "74HC157 / 74LS157", "func": "Quad 2:1 multiplexer (one shared select, active-LOW enable)",
            "pins": ["S", "1I0", "1I1", "1Y", "2I0", "2I1", "2Y", "GND", "3Y", "3I1", "3I0", "4Y", "4I1", "4I0", "/E", "VCC"]},
}

_IC_COLORS = {"in": "#1565c0", "out": "#2e7d32", "vcc": "#c62828", "gnd": "#37474f",
              "en": "#ef6c00", "sel": "#ef6c00", "tie": "#6a1b9a", "nc": "#9e9e9e", "net": "#00838f"}
_IC_LEGEND = [("Input", "in"), ("Output", "out"), ("VCC", "vcc"), ("GND", "gnd"),
              ("Select / enable", "en"), ("Unused input (tie)", "tie"), ("Internal net", "net")]


def _ic_pin_role(name):
    if name == "VCC":
        return "vcc"
    if name == "GND":
        return "gnd"
    if name.startswith("/"):
        return "en"
    if name == "S":
        return "sel"
    if name.endswith("Y"):
        return "out"
    return "in"


def _ic_pin_no(part, pin_name):
    return IC_PARTS[part]["pins"].index(pin_name) + 1


def _ic_default_label(name):
    role = _ic_pin_role(name)
    if role == "vcc":
        return ("VCC (+5 V, or 2-6 V for HC)", "vcc")
    if role == "gnd":
        return ("GND (0 V)", "gnd")
    if role == "out":
        return ("not used - leave open", "nc")
    return ("tie to GND (unused)", "tie")


def render_ic_svg(ic):
    """ic = {"ref","part","conn"}. Returns an SVG string of a top-view DIP package."""
    part = IC_PARTS[ic["part"]]
    pins = part["pins"]
    n = len(pins)
    m = n // 2
    pitch, W = 34, 640
    bx, bw, by = 250, 140, 52
    bh = 24 + (m - 1) * pitch + 24
    H = by + bh + 48
    esc = html.escape
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
         f'style="max-width:{W}px; font-family:Arial,Helvetica,sans-serif;">']
    o.append(f'<text x="{W/2}" y="20" text-anchor="middle" font-size="15" font-weight="bold" fill="#102027">'
             f'{esc(ic["ref"])} - {esc(part["label"])} (DIP-{n})</text>')
    o.append(f'<text x="{W/2}" y="38" text-anchor="middle" font-size="11" fill="#455a64">'
             f'{esc(part["func"])} · top view, notch up, pin 1 at top-left</text>')
    # package body, notch and pin-1 marker
    o.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6" fill="#eceff1" stroke="#263238" stroke-width="2.2"/>')
    cx = bx + bw / 2
    o.append(f'<path d="M {cx-12} {by} A 12 12 0 0 0 {cx+12} {by}" fill="#ffffff" stroke="#263238" stroke-width="2.2"/>')
    o.append(f'<circle cx="{bx+11}" cy="{by+11}" r="4.5" fill="#263238"/>')
    o.append(f'<text x="{cx}" y="{by+bh/2}" transform="rotate(-90 {cx} {by+bh/2})" text-anchor="middle" '
             f'dominant-baseline="middle" font-size="15" font-weight="bold" fill="#90a4ae">{esc(ic["part_short"])}</text>')
    conn = ic.get("conn", {})
    for r in range(m):
        y = by + 24 + r * pitch
        for side in ("L", "R"):
            pno = r + 1 if side == "L" else n - r
            pname = pins[pno - 1]
            text, kind = conn.get(pname, _ic_default_label(pname))
            col = _IC_COLORS.get(kind, "#000")
            if side == "L":
                sx = bx - 26
                o.append(f'<rect x="{sx}" y="{y-9}" width="26" height="18" fill="#cfd8dc" stroke="#263238" stroke-width="1.5"/>')
                o.append(f'<text x="{sx+13}" y="{y+4.5}" text-anchor="middle" font-size="12" font-weight="bold" fill="#000">{pno}</text>')
                o.append(f'<line x1="{sx-16}" y1="{y}" x2="{sx}" y2="{y}" stroke="{col}" stroke-width="3"/>')
                o.append(f'<text x="{sx-22}" y="{y+4}" text-anchor="end" font-size="11.5" font-weight="bold" fill="{col}">{esc(text)}</text>')
                o.append(f'<text x="{bx+10}" y="{y+4.5}" text-anchor="start" font-size="12" font-weight="bold" fill="#102027">{esc(pname)}</text>')
            else:
                sx = bx + bw
                o.append(f'<rect x="{sx}" y="{y-9}" width="26" height="18" fill="#cfd8dc" stroke="#263238" stroke-width="1.5"/>')
                o.append(f'<text x="{sx+13}" y="{y+4.5}" text-anchor="middle" font-size="12" font-weight="bold" fill="#000">{pno}</text>')
                o.append(f'<line x1="{sx+26}" y1="{y}" x2="{sx+42}" y2="{y}" stroke="{col}" stroke-width="3"/>')
                o.append(f'<text x="{sx+48}" y="{y+4}" text-anchor="start" font-size="11.5" font-weight="bold" fill="{col}">{esc(text)}</text>')
                o.append(f'<text x="{bx+bw-10}" y="{y+4.5}" text-anchor="end" font-size="12" font-weight="bold" fill="#102027">{esc(pname)}</text>')
    # legend
    ly = by + bh + 26
    lx = 12
    for lab, k in _IC_LEGEND:
        o.append(f'<rect x="{lx}" y="{ly-8}" width="10" height="10" fill="{_IC_COLORS[k]}"/>')
        o.append(f'<text x="{lx+14}" y="{ly+1}" font-size="10" fill="#37474f">{esc(lab)}</text>')
        lx += 14 + 6.3 * len(lab) + 14
    o.append('</svg>')
    return "".join(o)


def _IN(x):
    return (f"IN {x}", "in")


def _OUT(x, extra=""):
    return (f"OUT {x}{extra}", "out")


def _NET(x, driven=False):
    return (f"{'→ ' if driven else ''}{x}", "net")


_SIMPLE_GATE_PART = {"AND": "08", "NAND": "00", "OR": "32", "NOR": "02", "XOR": "86", "XNOR": "266"}


def build_ic_plan(sub_type, width=4):
    """Returns {"ics": [...], "nets": [...], "notes": [...]} for a digital circuit, or None if unsupported.
    ic = {"ref", "part", "part_short", "role", "conn": {pin_name: (label, kind)}}"""
    ics, nets, notes = [], [], []

    def add(ref, part, role, conn):
        ics.append({"ref": ref, "part": part, "part_short": IC_PARTS[part]["label"].split(" / ")[0],
                    "role": role, "conn": conn})

    def net(name, meaning, driver, loads):
        nets.append({"net": name, "meaning": meaning, "driver": driver, "loads": loads})

    if sub_type in _SIMPLE_GATE_PART:
        part = _SIMPLE_GATE_PART[sub_type]
        ypin = "1Y"
        y_extra = " (+1 kΩ pull-up to VCC)" if part == "266" else ""
        add("U1", part, f"{sub_type} gate (gate 1 of 4)",
            {"1A": _IN("A"), "1B": _IN("B"), ypin: _OUT("Y", y_extra)})
        notes.append("Only gate 1 is used; the other three gates are unused - their inputs are tied to GND so they cannot float.")
        if part == "266":
            notes.append("74LS266 has OPEN-COLLECTOR outputs: it cannot drive a HIGH by itself. Connect a 1 kΩ (1-10 kΩ) "
                         "pull-up resistor from output pin 3 to VCC, otherwise the output never reads logic 1.")
            notes.append("Alternative with push-pull outputs: build XNOR from a 7486 (XOR) followed by a 7404 inverter.")
        if part == "02":
            notes.append("Caution: the 7402 NOR has a different pinout from 7400/7408/7432/7486 - the output of each gate comes first (pin 1 = 1Y).")
    elif sub_type == "NOT":
        add("U1", "04", "Inverter 1 of 6", {"1A": _IN("A"), "1Y": _OUT("Y")})
        notes.append("Only inverter 1 is used; the other five inverters have their inputs tied to GND.")
    elif sub_type == "bin_to_gray":
        n = max(2, min(int(width), 4))
        conn = {}
        for k, i in enumerate(range(n - 2, -1, -1), start=1):
            conn[f"{k}A"] = _IN(f"B{i+1}")
            conn[f"{k}B"] = _IN(f"B{i}")
            conn[f"{k}Y"] = _OUT(f"G{i}")
        add("U1", "86", f"{n - 1} XOR gate(s): G(i) = B(i+1) ⊕ B(i)", conn)
        notes.append(f"The MSB needs no gate: G{n-1} = B{n-1}. Use the same wire for input B{n-1} and output G{n-1}.")
        if n > 2:
            fan = ", ".join(f"B{i}" for i in range(n - 2, 0, -1))
            notes.append(f"{fan} each feed two XOR gates (fan-out of 2), and B{n-1} feeds one gate plus the G{n-1} output wire - join those wires on the breadboard.")
        else:
            notes.append("B1 feeds the XOR gate and also the G1 output wire - join them on the breadboard.")
        notes.append(f"Bit width follows the 'Select Bit Width' control ({n} bits).")
    elif sub_type == "gray_to_bin":
        n = max(2, min(int(width), 4))
        conn = {}
        for k in range(1, n):
            out_bit = n - 1 - k
            conn[f"{k}A"] = _IN(f"G{n-1}") if k == 1 else _NET(f"B{out_bit+1}")
            conn[f"{k}B"] = _IN(f"G{out_bit}")
            conn[f"{k}Y"] = _OUT(f"B{out_bit}", " → next" if k < n - 1 else "")
            if k > 1:
                net(f"B{out_bit+1}", f"Binary bit B{out_bit+1} (output of gate {k-1})",
                    ("U1", f"{k-1}Y"), [("U1", f"{k}A")])
        add("U1", "86", f"{n - 1} cascaded XOR gate(s): B(i) = B(i+1) ⊕ G(i)", conn)
        notes.append(f"The MSB needs no gate: B{n-1} = G{n-1} (use the same wire). Gate 1 takes G{n-1} and G{n-2}.")
        notes.append("This is a ripple chain: each gate's output is wired into the A input of the next gate.")
        notes.append(f"Bit width follows the 'Select Bit Width' control ({n} bits).")
    elif sub_type == "half_adder":
        add("U1", "86", "Sum = A ⊕ B", {"1A": _IN("A"), "1B": _IN("B"), "1Y": _OUT("Sum")})
        add("U2", "08", "Carry = A · B", {"1A": _IN("A"), "1B": _IN("B"), "1Y": _OUT("Carry")})
        notes.append("Inputs A and B each go to BOTH ICs (U1 and U2) - join them on the breadboard.")
    elif sub_type == "full_adder":
        add("U1", "86", "XOR gates: N1 = A ⊕ B, Sum = N1 ⊕ Cin",
            {"1A": _IN("A"), "1B": _IN("B"), "1Y": _NET("N1", True),
             "2A": _NET("N1"), "2B": _IN("Cin"), "2Y": _OUT("Sum")})
        add("U2", "08", "AND gates: N2 = A · B, N3 = N1 · Cin",
            {"1A": _IN("A"), "1B": _IN("B"), "1Y": _NET("N2", True),
             "2A": _NET("N1"), "2B": _IN("Cin"), "2Y": _NET("N3", True)})
        add("U3", "32", "OR gate: Cout = N2 + N3",
            {"1A": _NET("N2"), "1B": _NET("N3"), "1Y": _OUT("Carry-out")})
        net("N1", "A ⊕ B", ("U1", "1Y"), [("U1", "2A"), ("U2", "2A")])
        net("N2", "A · B", ("U2", "1Y"), [("U3", "1A")])
        net("N3", "Cin · (A ⊕ B)", ("U2", "2Y"), [("U3", "1B")])
        notes.append("Needs three ICs (7486, 7408, 7432). A, B and Cin each fan out to two gates; N1 fans out to U1 and U2.")
    elif sub_type == "half_subtractor":
        add("U1", "86", "Difference = A ⊕ B", {"1A": _IN("A"), "1B": _IN("B"), "1Y": _OUT("Difference")})
        add("U2", "04", "Inverter: N1 = A'", {"1A": _IN("A"), "1Y": _NET("N1", True)})
        add("U3", "08", "Borrow = A' · B", {"1A": _NET("N1"), "1B": _IN("B"), "1Y": _OUT("Borrow")})
        net("N1", "A' (NOT A)", ("U2", "1Y"), [("U3", "1A")])
        notes.append("A goes to U1 and U2; B goes to U1 and U3.")
    elif sub_type == "full_subtractor":
        add("U1", "86", "XOR gates: N1 = A ⊕ B, Difference = N1 ⊕ Bin",
            {"1A": _IN("A"), "1B": _IN("B"), "1Y": _NET("N1", True),
             "2A": _NET("N1"), "2B": _IN("Bin"), "2Y": _OUT("Difference")})
        add("U2", "04", "Inverters: N2 = A', N3 = (A ⊕ B)'",
            {"1A": _IN("A"), "1Y": _NET("N2", True), "2A": _NET("N1"), "2Y": _NET("N3", True)})
        add("U3", "08", "AND gates: N4 = A' · B, N5 = N3 · Bin",
            {"1A": _NET("N2"), "1B": _IN("B"), "1Y": _NET("N4", True),
             "2A": _NET("N3"), "2B": _IN("Bin"), "2Y": _NET("N5", True)})
        add("U4", "32", "OR gate: Borrow-out = N4 + N5",
            {"1A": _NET("N4"), "1B": _NET("N5"), "1Y": _OUT("Borrow-out")})
        net("N1", "A ⊕ B", ("U1", "1Y"), [("U1", "2A"), ("U2", "2A")])
        net("N2", "A'", ("U2", "1Y"), [("U3", "1A")])
        net("N3", "(A ⊕ B)'", ("U2", "2Y"), [("U3", "2A")])
        net("N4", "A' · B", ("U3", "1Y"), [("U4", "1A")])
        net("N5", "(A ⊕ B)' · Bin", ("U3", "2Y"), [("U4", "1B")])
        notes.append("Needs four ICs (7486, 7404, 7408, 7432). Borrow-out = A'·B + (A ⊕ B)'·Bin, matching the truth table in this module.")
    elif sub_type == "mux_2_1":
        add("U1", "157", "2:1 mux, section 1 of 4",
            {"S": ("IN S (select)", "sel"), "1I0": _IN("I0"), "1I1": _IN("I1"), "1Y": _OUT("Y"),
             "/E": ("GND (enable, active LOW)", "en")})
        notes.append("The 74157 contains FOUR 2:1 multiplexers that share ONE select pin (pin 1) and ONE enable pin (pin 15). "
                     "This test uses section 1 only (1I0 = pin 2, 1I1 = pin 3, 1Y = pin 4).")
        notes.append("Select S = 0 routes I0 to Y; S = 1 routes I1 to Y - same as Y = S'·I0 + S·I1.")
        notes.append("The enable pin /E (pin 15) is ACTIVE LOW: it MUST be tied to GND. If it is HIGH (or floating) all outputs are forced LOW and the mux will appear dead.")
        notes.append("The unused data inputs of sections 2-4 are tied to GND; their outputs (pins 7, 9, 12) are left open.")
    else:
        return None
    return {"ics": ics, "nets": nets, "notes": notes}


def ic_wiring_rows(plan):
    rows = []
    for ic in plan["ics"]:
        pins = IC_PARTS[ic["part"]]["pins"]
        used = {}
        for pname, (text, kind) in ic["conn"].items():
            used[_ic_pin_no(ic["part"], pname)] = (pname, text, kind)
        used[14 if len(pins) == 14 else 16] = ("VCC", "+5 V supply (decouple with 0.1 µF to GND)", "vcc")
        used[7 if len(pins) == 14 else 8] = ("GND", "GND (common ground with ESP32 / sensor)", "gnd")
        for pno in sorted(used):
            pname, text, kind = used[pno]
            rows.append({"IC": f"{ic['ref']} ({ic['part_short']})", "Pin": pno, "Pin name": pname,
                         "Role": {"in": "Input", "out": "Output", "vcc": "Power", "gnd": "Power", "en": "Enable/Select",
                                  "sel": "Select", "net": "Internal net", "tie": "Unused input", "nc": "Unused"}.get(kind, kind),
                         "Connect to": text})
    return rows


def ic_unused_pin_notes(plan):
    out = []
    for ic in plan["ics"]:
        pins = IC_PARTS[ic["part"]]["pins"]
        tie, openp = [], []
        for i, pname in enumerate(pins, start=1):
            if pname in ic["conn"] or pname in ("VCC", "GND"):
                continue
            (tie if _ic_pin_role(pname) in ("in",) else openp if _ic_pin_role(pname) == "out" else tie).append(i)
        part_txt = f"{ic['ref']} ({ic['part_short']})"
        if tie:
            out.append(f"{part_txt}: tie unused input pins {', '.join(map(str, tie))} to GND.")
        if openp:
            out.append(f"{part_txt}: leave unused output pins {', '.join(map(str, openp))} unconnected.")
    return out


def render_ic_pin_section(sub_type, width=4):
    plan = build_ic_plan(sub_type, width)
    if plan is None:
        st.warning(f"No IC pin diagram is defined for sub-type '{sub_type}'.")
        return
    ics = plan["ics"]
    st.markdown("**ICs required:**")
    for ic in ics:
        p = IC_PARTS[ic["part"]]
        st.markdown(f"- **{ic['ref']} - {p['label']}** ({p['func']}) → {ic['role']}")
    cols_n = 1 if len(ics) == 1 else 2
    for start in range(0, len(ics), cols_n):
        chunk = ics[start:start + cols_n]
        cols = st.columns(cols_n)
        for col, ic in zip(cols, chunk):
            m = len(IC_PARTS[ic["part"]]["pins"]) // 2
            h = 52 + (24 + (m - 1) * 34 + 24) + 48 + 24
            with col:
                st.components.v1.html(
                    f'<div style="background:#ffffff; border-radius:10px; padding:8px; box-sizing:border-box;">{render_ic_svg(ic)}</div>',
                    height=int(h) + 16, scrolling=True)
    st.markdown("**Wiring table**")
    st.dataframe(pd.DataFrame(ic_wiring_rows(plan)), use_container_width=True, hide_index=True)
    if plan["nets"]:
        st.markdown("**Internal nets (wire these between ICs)**")
        net_rows = []
        for nt in plan["nets"]:
            drv_ref, drv_pin = nt["driver"]
            dpart = next(i for i in ics if i["ref"] == drv_ref)["part"]
            loads = []
            for lref, lpin in nt["loads"]:
                lpart = next(i for i in ics if i["ref"] == lref)["part"]
                loads.append(f"{lref} pin {_ic_pin_no(lpart, lpin)} ({lpin})")
            net_rows.append({"Net": nt["net"], "Meaning": nt["meaning"],
                             "From": f"{drv_ref} pin {_ic_pin_no(dpart, drv_pin)} ({drv_pin})", "To": ", ".join(loads)})
        st.dataframe(pd.DataFrame(net_rows), use_container_width=True, hide_index=True)
    st.markdown("**Notes**")
    for line in plan["notes"] + ic_unused_pin_notes(plan):
        st.markdown(f"- {line}")
    st.caption("Power: 74LS/7400 parts need +5 V; 74HC parts run from 2-6 V (use 3.3 V HC if your ESP32 inputs are not 5 V tolerant). "
               "Add a 0.1 µF capacitor close to each IC's VCC/GND pins and join all grounds. Pin numbers are for the DIP package, top view.")


# ==============================================================================
# LAB KNOWLEDGE BASE (objective, working principle, components, connections,
# teaching content) - reuses CIRCUIT_DATABASE values; nothing here is measured.
# ==============================================================================
_RECT_PRECAUTIONS = [
    "The transformer primary is connected to the mains: use a fused, insulated supply and never touch the primary side while it is powered.",
    "Switch off and wait before changing any wire; discharge C1 through RL (or a resistor) before touching it.",
    "Electrolytic capacitor C1 is polarised: the + lead must go to the positive rail. The wrong polarity can make it overheat or burst.",
    "Check that C1's voltage rating is above the peak secondary voltage (Vpeak = 1.414 x Vrms) with a safety margin.",
    "Check the power rating of RL (P = V^2 / R) and the current rating of the diodes and transformer before connecting the load.",
]

_RECT_COMMON_TROUBLESHOOT = [
    "Power off, then check every connection against the schematic in this report (including the probe positions P1-P3).",
    "Measure the secondary voltage directly with a multimeter and compare it with the NEXUS input reading.",
    "Check each diode with the multimeter diode-test range (about 0.5-0.7 V forward, open in reverse) with the circuit unpowered and the diode isolated.",
    "Check C1 polarity and, if possible, its capacitance; an open C1 raises ripple, a leaky or shorted C1 lowers the output.",
    "Confirm the load resistor value and that the current probe is wired in SERIES at the position given in the probe list.",
]

CIRCUIT_KNOWLEDGE = {
    "Half Wave Rectifier": {
        "objective": ("To study half-wave rectification: convert the AC voltage of a transformer secondary into pulsating DC "
                      "using one diode, observe the smoothing effect of a filter capacitor, and compare the measured input/output "
                      "voltage, current, power and efficiency with the expected values."),
        "working_principle": ("During the positive half-cycle of the secondary voltage D1 is forward biased and conducts, supplying the load RL "
                              "and charging C1. During the negative half-cycle D1 is reverse biased and blocks, so the load is fed only by the "
                              "energy stored in C1. Only one half-cycle per period is used, so the output ripple frequency equals the mains "
                              "frequency. Without C1 the theoretical average output is Vdc = Vpeak/pi (about 0.318 Vpeak), the ripple factor is "
                              "1.21 and the maximum rectification efficiency is 40.6 %."),
        "components": [
            {"refs": ["T1"], "ref_label": "T1", "name": "Step-down transformer", "value": "12 V AC",
             "function": "Steps the mains down to a safe 12 V AC and isolates the circuit from the mains."},
            {"refs": ["D1"], "ref_label": "D1", "name": "Rectifier diode", "value": "1N4007",
             "function": "Conducts only in the positive half-cycle (1 A, 1000 V reverse rating) - this is the rectifying element."},
            {"refs": ["C1"], "ref_label": "C1", "name": "Filter capacitor (electrolytic)", "value": "100 \u00b5F",
             "function": "Stores charge at the voltage peaks and releases it between them, smoothing the pulsating DC."},
            {"refs": ["RL"], "ref_label": "RL", "name": "Load resistor", "value": "1 k\u03a9",
             "function": "Represents the load drawing current from the rectifier."},
        ],
        "connections": [
            "T1 primary -> AC mains (through a fuse / isolated supply).",
            "T1 secondary terminal S1 -> P3 current probe (series) -> D1 anode.",
            "D1 cathode -> OUT+ node (C1 positive lead and top of RL).",
            "T1 secondary terminal S2 -> GND / OUT- node (C1 negative lead and bottom of RL).",
            "P1 voltmeter across the T1 secondary (input voltage); P2 voltmeter across RL (output voltage).",
        ],
        "theory": {"n_diodes": 1, "avg_factor": 1.0 / math.pi, "eff_max": 40.6, "ripple_unfiltered": 121.0,
                   "ripple_freq_mult": 1, "label": "half-wave"},
        "teaching": {
            "purpose": "Learn how a single diode converts AC to DC and why the result is only pulsating DC that needs filtering.",
            "why_components": ["The diode gives one-way conduction.", "C1 smooths the pulses by storing charge.",
                               "RL provides a defined load so current and efficiency can be measured."],
            "observe": ["Output DC voltage lower than the transformer peak voltage by about one diode drop (0.6-0.7 V).",
                        "Output current and voltage change together according to Ohm's law across RL.",
                        "Efficiency well below 50 % for an unfiltered half-wave rectifier."],
            "abnormal": ["Output voltage near 0 V: open diode, open connection or missing supply.",
                         "Output voltage about half of the expected value with no smoothing: C1 open or missing.",
                         "Output much higher than the theoretical peak: input reading is not RMS, or the sensor calibration is wrong.",
                         "Efficiency above 100 %: a measurement or calibration error - power out cannot exceed power in."],
            "troubleshooting": _RECT_COMMON_TROUBLESHOOT,
            "precautions": _RECT_PRECAUTIONS,
            "learning": ["Half-wave rectification uses only one half of each AC cycle.",
                         "A filter capacitor raises the average output and reduces ripple; ripple (p-p) is about I_load / (f x C).",
                         "Rectifier efficiency can be calculated from measured input and output power."],
        },
    },
    "Full Wave Rectifier (Center Tap)": {
        "objective": ("To study full-wave rectification with a centre-tapped transformer and two diodes, and compare the measured input/output "
                      "voltage, current, power and efficiency with the expected values."),
        "working_principle": ("The centre-tapped secondary gives two equal voltages, 180 degrees out of phase, measured from the centre tap (CT). "
                              "When the upper end S1 is positive D1 conducts; when the lower end S2 is positive D2 conducts. Both half-cycles "
                              "therefore drive current through RL in the same direction and the output ripple frequency is twice the mains "
                              "frequency. Without C1 the theoretical average output is Vdc = 2 Vpeak/pi (about 0.637 Vpeak, where Vpeak is "
                              "the peak of ONE half-winding), the ripple factor is 0.482 and the maximum efficiency is 81.2 %. Each diode must "
                              "withstand a reverse voltage of about 2 Vpeak."),
        "components": [
            {"refs": ["T1"], "ref_label": "T1", "name": "Centre-tap transformer", "value": "12-0-12 V",
             "function": "Provides two equal secondary voltages referenced to the centre tap and isolates the circuit from the mains."},
            {"refs": ["D1", "D2"], "ref_label": "D1, D2", "name": "Rectifier diodes", "value": "1N4007",
             "function": "Each conducts during one half-cycle so both halves of the AC wave are used."},
            {"refs": ["C1"], "ref_label": "C1", "name": "Filter capacitor (electrolytic)", "value": "470 \u00b5F",
             "function": "Smooths the output by storing charge at the peaks."},
            {"refs": ["RL"], "ref_label": "RL", "name": "Load resistor", "value": "1 k\u03a9",
             "function": "Represents the load drawing current from the rectifier."},
        ],
        "connections": [
            "T1 primary -> AC mains (through a fuse / isolated supply).",
            "T1 secondary upper end S1 -> D1 anode; T1 secondary lower end S2 -> D2 anode.",
            "D1 cathode and D2 cathode joined together -> OUT+ node (C1 positive lead and top of RL).",
            "T1 centre tap (CT) -> P3 current probe (series) -> GND / OUT- node (C1 negative lead and bottom of RL).",
            "P1 voltmeter between the upper secondary winding and CT (input voltage); P2 voltmeter across RL (output voltage).",
        ],
        "theory": {"n_diodes": 1, "avg_factor": 2.0 / math.pi, "eff_max": 81.2, "ripple_unfiltered": 48.0,
                   "ripple_freq_mult": 2, "label": "full-wave centre-tap"},
        "teaching": {
            "purpose": "Learn how two diodes and a centre-tapped transformer use both half-cycles of the AC wave.",
            "why_components": ["The centre tap provides the common return for both half-cycles.", "D1 and D2 conduct alternately.",
                               "C1 smooths the doubled-frequency ripple; RL is the test load."],
            "observe": ["Output DC close to 0.637 x Vpeak of one half-winding minus one diode drop (unfiltered).",
                        "Higher efficiency (up to 81.2 %) than the half-wave circuit.",
                        "Ripple at twice the mains frequency, i.e. 100 Hz on 50 Hz mains."],
            "abnormal": ["Output about half of expected with strong 50 Hz ripple: one diode (D1 or D2) open, or one half of the secondary not connected.",
                         "Output near 0 V: centre tap not connected, both diodes open, or no supply.",
                         "Excess heat in the transformer or one diode: shorted diode or shorted C1.",
                         "Efficiency above 100 %: measurement or calibration error."],
            "troubleshooting": _RECT_COMMON_TROUBLESHOOT + ["Measure the voltage from CT to S1 and from CT to S2 separately; they should be equal."],
            "precautions": _RECT_PRECAUTIONS,
            "learning": ["Full-wave rectification uses both half-cycles, so output and efficiency are higher than half-wave.",
                         "The centre tap is the common reference for both diodes.",
                         "The ripple frequency doubles, which makes filtering easier."],
        },
    },
    "Bridge Rectifier": {
        "objective": ("To study the bridge rectifier, which gives full-wave rectification without a centre-tapped transformer, "
                      "and compare the measured input/output voltage, current, power and efficiency with the expected values."),
        "working_principle": ("Four diodes are connected in a bridge. When AC terminal 1 is positive, D1 and D4 conduct; when AC terminal 2 "
                              "is positive, D2 and D3 conduct. In both half-cycles the current flows through RL in the same direction, so "
                              "the output ripple frequency is twice the mains frequency. Two diodes are in the current path at any instant, so "
                              "the output is about 1.2-1.4 V lower than the peak input. Without C1 the theoretical average output is "
                              "Vdc = 2 Vpeak/pi, the ripple factor is 0.482 and the maximum efficiency is 81.2 %. Each diode only has to "
                              "withstand about Vpeak in reverse."),
        "components": [
            {"refs": ["T1"], "ref_label": "T1", "name": "Step-down transformer", "value": "12 V AC",
             "function": "Steps the mains down to 12 V AC and isolates the circuit from the mains."},
            {"refs": ["D1", "D2", "D3", "D4"], "ref_label": "D1-D4", "name": "Bridge diodes (4 x 1N4007 or bridge module 1B4B42)", "value": "1N4007",
             "function": "Steer both half-cycles through the load in the same direction (two diodes conduct at a time)."},
            {"refs": ["C1"], "ref_label": "C1", "name": "Filter capacitor (electrolytic)", "value": "1000 \u00b5F",
             "function": "Smooths the output by storing charge at the peaks."},
            {"refs": ["RL"], "ref_label": "RL", "name": "Load resistor", "value": "1 k\u03a9",
             "function": "Represents the load drawing current from the rectifier."},
        ],
        "connections": [
            "T1 primary -> AC mains (through a fuse / isolated supply).",
            "T1 secondary S1 -> bridge AC node 1 (D1 anode and D3 cathode); T1 secondary S2 -> bridge AC node 2 (D2 anode and D4 cathode).",
            "D1 and D2 cathodes joined -> DC+ node -> P3 current probe (series) -> OUT+ (C1 positive lead and top of RL).",
            "D3 and D4 anodes joined -> DC- node -> GND / OUT- (C1 negative lead and bottom of RL).",
            "P1 voltmeter across the bridge AC terminals (input voltage); P2 voltmeter across the DC output rails (output voltage).",
        ],
        "theory": {"n_diodes": 2, "avg_factor": 2.0 / math.pi, "eff_max": 81.2, "ripple_unfiltered": 48.0,
                   "ripple_freq_mult": 2, "label": "bridge"},
        "teaching": {
            "purpose": "Learn how four diodes rectify both half-cycles without needing a centre-tapped transformer.",
            "why_components": ["Four diodes route the current through RL in one direction for either polarity of the input.",
                               "C1 smooths the output; RL is the test load; the transformer isolates and steps down the mains."],
            "observe": ["Output DC about 2 x Vpeak/pi minus two diode drops (unfiltered).",
                        "Ripple at twice the mains frequency.",
                        "Efficiency up to 81.2 % for a resistive load."],
            "abnormal": ["Output about half of expected with 50 Hz ripple: one diode open (or one bridge arm disconnected).",
                         "Output near 0 V with a blown fuse or hot transformer: a shorted diode or a short across the output.",
                         "Output near 0 V without heating: open connection, wrong bridge wiring (AC and DC pins swapped), or no supply.",
                         "Efficiency above 100 %: measurement or calibration error."],
            "troubleshooting": _RECT_COMMON_TROUBLESHOOT + ["If a bridge module is used, confirm that its AC~ pins go to the transformer and its +/- pins go to the load."],
            "precautions": _RECT_PRECAUTIONS,
            "learning": ["A bridge gives full-wave rectification from a plain transformer winding.",
                         "Two diode drops are lost in a bridge, which matters at low voltages.",
                         "Diode failures show up as a characteristic loss of output and an increase of ripple."],
        },
    },
}


# ---- digital circuit teaching content (keyed by CIRCUIT_DATABASE sub_type) ---------------
def _gate_teach(fn_name, rule, abnormal_hint):
    return {
        "objective": f"To verify the truth table of the {fn_name} logic function using an IC, by measuring the output voltage for every input combination.",
        "principle": rule,
        "observe": ["The output voltage should be close to 0 V for logic 0 and close to the supply (or at least above the logic-1 threshold) for logic 1.",
                    "Every input combination in the truth table must be measured once."],
        "abnormal": [abnormal_hint,
                     "A voltage between the logic thresholds (invalid level) means a floating input, a weak/loaded output or a supply problem."],
        "learning": [f"The {fn_name} truth table and its Boolean expression.",
                     "How to relate the voltage on an IC pin to a logic level and verify an IC with a truth table."],
    }


DIGITAL_TEACHING = {
    "AND": _gate_teach("AND", "The output is HIGH only when both inputs are HIGH (Y = A . B).", "Output stuck HIGH or LOW for all rows: wrong gate pins, output shorted, or missing supply."),
    "NAND": _gate_teach("NAND", "The output is LOW only when both inputs are HIGH (Y = NOT(A . B)). NAND is a universal gate.", "Output never goes LOW: inputs not reaching HIGH, or wrong gate pins."),
    "OR": _gate_teach("OR", "The output is HIGH when at least one input is HIGH (Y = A + B).", "Output HIGH for (0,0): floating input or wrong pins."),
    "NOR": _gate_teach("NOR", "The output is HIGH only when both inputs are LOW (Y = NOT(A + B)). NOR is a universal gate. NOTE: the 7402 pin-out differs from 7400/7408/7432/7486.", "Wrong results for all rows: the common mistake is wiring the 7402 like a 7400 (its outputs are on pins 1, 4, 10, 13)."),
    "XOR": _gate_teach("XOR", "The output is HIGH when the two inputs are different (Y = A xor B).", "Output follows only one input: the other input is floating or disconnected."),
    "XNOR": _gate_teach("XNOR", "The output is HIGH when both inputs are the same (Y = NOT(A xor B)). The 74LS266 has open-collector outputs and needs a pull-up resistor.", "Output never reads HIGH: missing pull-up resistor on the 74LS266 output."),
    "NOT": _gate_teach("NOT (inverter)", "The output is the complement of the input (Y = NOT A).", "Output equals the input or stays constant: wrong pins, or a floating input."),
    "bin_to_gray": {
        "objective": "To verify a binary-to-Gray code converter built from XOR gates, for the selected bit width.",
        "principle": "The MSB is copied unchanged (G(n-1) = B(n-1)); every other Gray bit is the XOR of two neighbouring binary bits (G(i) = B(i+1) xor B(i)). Consecutive Gray codes differ in only one bit.",
        "observe": ["Gray output changes by exactly one bit between successive binary inputs.", "All 2^n input combinations must be measured for each Gray output bit."],
        "abnormal": ["One Gray bit wrong in half of the rows: that XOR gate has a floating or swapped input.", "G(n-1) wrong: the MSB feed-through wire is missing."],
        "learning": ["Gray code and its single-bit-change property.", "How XOR gates implement code conversion."]},
    "gray_to_bin": {
        "objective": "To verify a Gray-to-binary converter built from cascaded XOR gates, for the selected bit width.",
        "principle": "The MSB is copied unchanged (B(n-1) = G(n-1)); each lower binary bit is the XOR of the next higher binary bit and the Gray bit (B(i) = B(i+1) xor G(i)).",
        "observe": ["Binary output counts up as the Gray input sequence advances.", "Errors in an upper stage propagate to all lower bits (ripple chain)."],
        "abnormal": ["Several lower bits wrong together: the first XOR stage (or its output wire) is faulty, because later stages depend on it.", "Only the last bit wrong: the last XOR gate or its wiring."],
        "learning": ["How the cascaded XOR chain converts Gray code to binary.", "Why a fault in an early stage corrupts later outputs."]},
    "half_adder": {
        "objective": "To verify a half adder that adds two 1-bit numbers and produces Sum and Carry.",
        "principle": "Sum = A xor B and Carry = A . B. The XOR gate gives the sum bit and the AND gate gives the carry.",
        "observe": ["For A=B=1 the Sum is 0 and the Carry is 1 (1+1 = 10 in binary)."],
        "abnormal": ["Sum wrong but Carry correct: the XOR gate (or its wiring) is suspect.", "Carry wrong but Sum correct: the AND gate (or its wiring) is suspect."],
        "learning": ["Binary addition of two bits.", "The roles of the XOR and AND gates."]},
    "full_adder": {
        "objective": "To verify a full adder that adds A, B and a carry-in (Cin) and produces Sum and Carry-out.",
        "principle": "Sum = A xor B xor Cin; Carry-out = A.B + Cin.(A xor B). The first XOR gives N1 = A xor B, the second XOR gives Sum, two AND gates form A.B and Cin.N1, and an OR gate combines them.",
        "observe": ["Sum is 1 when an odd number of inputs is 1.", "Carry-out is 1 when two or more inputs are 1."],
        "abnormal": ["Both outputs wrong: the shared XOR (N1) or a shared input wire is suspect.", "Only Carry-out wrong: the AND/OR stage is suspect."],
        "learning": ["How a full adder is built from half-adder style gates.", "How internal nets (N1, N2, N3) connect the stages."]},
    "half_subtractor": {
        "objective": "To verify a half subtractor that subtracts B from A and produces Difference and Borrow.",
        "principle": "Difference = A xor B and Borrow = (NOT A) . B.",
        "observe": ["Borrow is 1 only when A=0 and B=1."],
        "abnormal": ["Borrow wrong, Difference correct: the inverter or the AND gate is suspect.", "Difference wrong: the XOR gate is suspect."],
        "learning": ["Binary subtraction of two bits.", "The difference between borrow and carry logic."]},
    "full_subtractor": {
        "objective": "To verify a full subtractor that computes A - B - Bin and produces Difference and Borrow-out.",
        "principle": "Difference = A xor B xor Bin; Borrow-out = (NOT A).B + (NOT(A xor B)).Bin.",
        "observe": ["Difference is 1 when an odd number of inputs is 1.", "Borrow-out is 1 when A is smaller than B + Bin."],
        "abnormal": ["Both outputs wrong: the shared XOR (N1) or a shared input wire is suspect.", "Only Borrow-out wrong: the inverters, AND gates or OR gate are suspect."],
        "learning": ["How a full subtractor is built from XOR, NOT, AND and OR gates.", "How borrow propagates between stages."]},
    "mux_2_1": {
        "objective": "To verify a 2:1 multiplexer that routes one of two data inputs (I0 or I1) to the output Y under control of the select input S.",
        "principle": "Y = (NOT S).I0 + S.I1. S=0 selects I0; S=1 selects I1. The 74157 has an active-LOW enable pin (/E, pin 15) that must be tied to GND.",
        "observe": ["Y follows I0 when S=0 and I1 when S=1."],
        "abnormal": ["Y stuck LOW for every row: the enable pin /E is HIGH or floating (it must be tied to GND).", "Y follows the wrong input: S is connected to the wrong pin."],
        "learning": ["How a multiplexer selects data using a select line.", "The role of the enable pin."]},
}

_DIGITAL_PRECAUTIONS = [
    "Switch the supply off before changing wires and double-check the IC orientation (pin 1 marker/notch) before powering up.",
    "Use the correct supply for the IC family: +5 V for 74LS/standard TTL/74HCT, 2-6 V for 74HC. Never exceed the datasheet maximum.",
    "Connect all grounds together (IC, input switches, ESP32 sensor). A missing common ground gives random readings.",
    "Tie unused IC inputs to GND (or VCC) - never leave them floating. Leave unused outputs unconnected.",
    "Add a 0.1 \u00b5F decoupling capacitor between VCC and GND close to each IC.",
    "The ESP32 inputs are 3.3 V devices: a 5 V logic output must reach the sensor through the divider/scaling that NEXUS was calibrated with.",
]


def get_circuit_knowledge(category, circuit, width=4):
    """Unified knowledge dict for any circuit in CIRCUIT_DATABASE (analogue or digital).
    Contains only descriptive/teaching content - never measured values."""
    if category == "Rectifiers" and circuit in CIRCUIT_KNOWLEDGE:
        k = copy.deepcopy(CIRCUIT_KNOWLEDGE[circuit])
        k["kind"] = "analogue"
        return k
    info = CIRCUIT_DATABASE.get(category, {}).get(circuit)
    if not info:
        return None
    sub = info.get("sub_type")
    t = DIGITAL_TEACHING.get(sub, {})
    plan = build_ic_plan(sub, width)
    comps, conns = [], []
    if plan:
        for ic in plan["ics"]:
            p = IC_PARTS[ic["part"]]
            comps.append({"refs": [ic["ref"]], "ref_label": ic["ref"], "name": f"{p['label']} - {p['func']}",
                          "value": ic["part_short"], "function": ic["role"]})
        comps.append({"refs": ["Cdec"], "ref_label": "C-dec", "name": "Decoupling capacitor (one per IC)", "value": "0.1 \u00b5F",
                      "function": "Placed between VCC and GND close to each IC to suppress supply spikes."})
        if any(i["part"] == "266" for i in plan["ics"]):
            comps.append({"refs": ["Rpu"], "ref_label": "R-pu", "name": "Pull-up resistor", "value": "1 k\u03a9",
                          "function": "Required by the open-collector 74LS266: pulls the output HIGH to VCC."})
        conns = [f"{r['IC']} pin {r['Pin']} ({r['Pin name']}) -> {r['Connect to']}" for r in ic_wiring_rows(plan)]
    comps.append({"refs": ["SW"], "ref_label": "SW", "name": "Input switches / logic sources", "value": "-",
                  "function": "Set each input to logic 0 (GND) or logic 1 (VCC) for the truth-table row being measured."})
    comps.append({"refs": ["ESP32"], "ref_label": "ESP32", "name": "NEXUS ESP32 voltage sensor", "value": "-",
                  "function": "Measures the voltage on the output pin under test and reports it over MQTT."})
    return {
        "kind": "digital",
        "objective": t.get("objective", info.get("description", "")),
        "working_principle": t.get("principle", info.get("description", "")),
        "components": comps,
        "connections": conns,
        "teaching": {
            "purpose": t.get("objective", ""),
            "why_components": [f"{c['ref_label']}: {c['function']}" for c in comps[:4]],
            "observe": t.get("observe", []),
            "abnormal": t.get("abnormal", []),
            "troubleshooting": ["Re-check IC orientation and every pin against the IC pin diagram in this report.",
                                "Measure VCC (pin 14/16) and GND (pin 7/8) at the IC pins with a multimeter.",
                                "Check each input pin voltage for the failing row with a multimeter or logic probe.",
                                "Check for floating inputs, loose breadboard contacts and missing common ground.",
                                "Swap in a known-good IC of the same type and repeat only the failing rows."],
            "precautions": _DIGITAL_PRECAUTIONS,
            "learning": t.get("learning", []),
        },
    }


# ==============================================================================
# DETERMINISTIC EVIDENCE ENGINES (computed by Python from the frozen test snapshot;
# Gemini receives these results and may explain them but may not overrule them).
#   1. compute_rectifier_evidence()  - theory references + measurement consistency checks
#   2. compute_ic_assessment()       - evidence-tiered IC health assessment (digital circuits)
# ==============================================================================
AI_PROBABILITY_NOTICE = ("Percentages shown for AI diagnosis are AI-generated estimates based on the supplied measurements. "
                         "They are NOT statistically validated probabilities: NEXUS has not been calibrated against a labelled fault dataset.")


def _parse_ohms(text):
    m = re.search(r"([\d.]+)\s*(k|M)?", str(text or "").replace("\u03a9", "").replace("\u2126", ""))
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return v * {"k": 1e3, "M": 1e6}.get(m.group(2), 1.0)


def compute_rectifier_evidence(circuit_name, snap, targets, source="LIVE"):
    """Theory reference values and measurement-consistency checks for a rectifier snapshot.
    Uses ONLY the supplied snapshot/targets (never live data)."""
    k = CIRCUIT_KNOWLEDGE.get(circuit_name)
    checks, theory = [], None

    def add(level, cid, text):
        checks.append({"level": level, "id": cid, "text": text})

    def num(key):
        try:
            v = float(snap.get(key))
            return v if math.isfinite(v) else None
        except (TypeError, ValueError):
            return None

    vin, vout, iin, iout = num("input_v"), num("output_v"), num("input_i"), num("output_i")
    pin_w, pout_w, eff = num("power_in"), num("power_out"), num("efficiency")
    freq, temp = num("frequency"), num("temperature")

    if k:
        th = k["theory"]
        drop = 0.7 * th["n_diodes"]
        theory = {
            "assumptions": ("Input reading is taken as the AC RMS voltage of the secondary (for the centre-tap rectifier: of ONE half-winding). "
                            "Silicon diode drop assumed 0.7 V per conducting diode."),
            "diode_drop_v": round(drop, 2),
            "max_efficiency_percent": th["eff_max"],
            "unfiltered_ripple_factor_percent": th["ripple_unfiltered"],
        }
        if vin is not None and vin > 0.5:
            vm = vin * math.sqrt(2.0)
            peak = max(0.0, vm - drop)
            theory.update({"secondary_peak_v": round(vm, 2), "no_load_filtered_peak_limit_v": round(peak, 2),
                           "unfiltered_average_dc_v": round(th["avg_factor"] * peak, 2)})
            if freq and freq > 0:
                theory["ripple_frequency_hz"] = round(freq * th["ripple_freq_mult"], 1)
            if vout is not None and vout > peak * 1.05 + 0.3:
                add("ALERT", "vout_above_peak",
                    f"Output voltage {vout:.2f} V is above the theoretical no-load peak limit {peak:.2f} V "
                    f"(Vin x 1.414 minus diode drop). A passive rectifier cannot exceed this: suspect sensor calibration, "
                    f"wrong probe position, or an input reading that is not the RMS secondary voltage.")
        # database target vs theory
        t_in, t_out = targets.get("target_input_voltage"), targets.get("target_output_voltage")
        if t_in and t_out and t_in > 0:
            unf_nom = th["avg_factor"] * max(0.0, t_in * math.sqrt(2.0) - drop)
            theory["target_unfiltered_average_dc_v"] = round(unf_nom, 2)
            if abs(unf_nom - t_out) / t_out <= 0.08:
                add("INFO", "target_is_unfiltered",
                    f"The expected output ({t_out:.2f} V) matches the theoretical UNFILTERED average DC value ({unf_nom:.2f} V) for a "
                    f"{th['label']} rectifier. With the filter capacitor C1 connected the output rises towards the peak value "
                    f"({max(0.0, t_in * math.sqrt(2.0) - drop):.2f} V at no load), so a higher-than-expected output can be normal and is "
                    f"not by itself evidence of a fault.")

    if pin_w is not None and pin_w > 0 and eff is not None and eff > 100.5:
        add("ALERT", "eff_over_100", f"Calculated efficiency {eff:.1f} % is above 100 %: output power cannot exceed input power. "
            "Suspect measurement/calibration error, mismatched probe positions, or held-input vs live-output timing.")
    if vout is not None and vin is not None and vin > 1.0 and vout < 0.1:
        add("ALERT", "no_output", f"Input is present ({vin:.2f} V) but the output is about 0 V: open path (diode, connection, load) or output probe not connected.")
    if iin is not None and vin is not None and vin > 1.0 and abs(iin) < 1e-3:
        add("WARN", "no_input_current", "Input voltage is present but input current is about 0 A: open circuit in the supply path, or the current probe is not in series.")
    if k and vout is not None and iout is not None and iout > 1e-4 and vout > 0.05:
        r_imp = vout / iout
        rl = next((_parse_ohms(c["value"]) for c in k["components"] if "RL" in c["refs"]), None)
        if rl and abs(r_imp - rl) / rl > 0.25:
            t_out, t_oi = targets.get("target_output_voltage"), targets.get("target_output_current")
            tr = (t_out / t_oi) if (t_out and t_oi) else None
            add("WARN", "load_mismatch",
                f"Vout / Iout = {r_imp:.1f} ohm, but the listed load resistor RL is {rl:.0f} ohm"
                + (f" (and the database current target implies {tr:.1f} ohm)" if tr else "")
                + ". Either the real load differs from the listed one, the current probe is measuring something else, or the voltage/current "
                  "sensors are not calibrated consistently.")
    if freq is not None:
        if freq <= 0:
            add("INFO", "freq_missing", "Frequency is 0 Hz: the sensor may not report it, so mains-frequency problems cannot be assessed.")
        elif not 45.0 <= freq <= 65.0:
            add("WARN", "freq_range", f"Measured frequency {freq:.1f} Hz is outside the normal 50/60 Hz mains range.")
    if temp is not None and temp <= 0:
        add("INFO", "temp_missing", "Temperature is 0 C: the sensor may not report it, so overheating cannot be assessed.")
    elif temp is not None and temp > 70:
        add("WARN", "temp_high", f"Temperature {temp:.1f} C is high: check for a shorted diode/capacitor or an overloaded transformer.")
    if str(source).upper() == "HELD":
        add("INFO", "held_input", "Input voltage/current are HELD values captured earlier; output values were live. A change of mains voltage after the capture is not visible in the input values.")
    return {
        "theory": theory,
        "checks": checks,
        "not_assessable": ["Ripple and filter-capacitor condition (no ripple measurement is available)",
                           "Individual diode health (no per-diode voltage/current measurement)",
                           "Transformer secondary loaded/unloaded voltage separately (only one input reading)",
                           "Capacitor value / ESR and diode forward voltage (no component-level test)"],
    }


# ------------------------------------------------------------------------------
# IC FAMILY SPECIFICATIONS (typical datasheet values - verify against the exact part's datasheet)
# ------------------------------------------------------------------------------
IC_FAMILY_NONE = "Not specified"
IC_FAMILY_OPTIONS = [IC_FAMILY_NONE, "74LS / standard TTL (5 V)", "74HC (CMOS)", "74HCT (TTL-compatible CMOS, 5 V)"]
IC_FAMILY_SPECS = {
    "74LS / standard TTL (5 V)": {"vcc_min": 4.75, "vcc_max": 5.25, "vcc_text": "4.75-5.25 V (nominal 5 V)"},
    "74HC (CMOS)": {"vcc_min": 2.0, "vcc_max": 6.0, "vcc_text": "2-6 V"},
    "74HCT (TTL-compatible CMOS, 5 V)": {"vcc_min": 4.5, "vcc_max": 5.5, "vcc_text": "4.5-5.5 V (nominal 5 V)"},
}
DEFAULT_IC_CONTEXT = {"family": IC_FAMILY_NONE, "vcc_measured": None, "unused_inputs_tied": "Unknown",
                      "inputs_verified": "Unknown", "pullup_fitted": "Unknown", "enable_tied_gnd": "Unknown"}
IC_GATE_FUNC = {"08": "AND", "00": "NAND", "32": "OR", "86": "XOR", "02": "NOR", "04": "NOT", "266": "XNOR", "157": "2:1 MUX"}


def ic_family_levels(family, vcc=None):
    """Typical logic-level limits for a family (light load). None when the family is not specified."""
    if family not in IC_FAMILY_SPECS:
        return None
    if family.startswith("74LS"):
        return {"vih_min": 2.0, "vil_max": 0.8, "voh_min": 2.7, "vol_max": 0.5,
                "note": "74LS/TTL: VIH >= 2.0 V, VIL <= 0.8 V, VOH >= 2.7 V (2.4 V for standard 74xx), VOL <= 0.5 V."}
    v = float(vcc) if vcc else 5.0
    if family.startswith("74HCT"):
        return {"vih_min": 2.0, "vil_max": 0.8, "voh_min": round(v - 0.1, 2), "vol_max": 0.1,
                "note": "74HCT: VIH >= 2.0 V, VIL <= 0.8 V, outputs swing to within about 0.1 V of the rails at light load."}
    return {"vih_min": round(0.7 * v, 2), "vil_max": round(0.3 * v, 2), "voh_min": round(v - 0.1, 2), "vol_max": 0.1,
            "note": f"74HC at VCC = {v:g} V: VIH >= 0.7 x VCC, VIL <= 0.3 x VCC, outputs swing to within about 0.1 V of the rails at light load."}


def ic_supply_text(part_id):
    p = IC_PARTS[part_id]["label"]
    if part_id == "266":
        return "74LS266 (TTL, open-collector outputs): VCC 4.75-5.25 V (nominal 5 V)."
    return (f"{p}: 7400/74LS series VCC 4.75-5.25 V (nominal 5 V); 74HC series VCC 2-6 V; 74HCT series VCC 4.5-5.5 V. "
            f"Use the datasheet of the exact IC family you fitted.")


IC_VERDICTS = {
    "HEALTHY_TESTED": "IC APPEARS HEALTHY (based on the tested gate(s) only)",
    "INSUFFICIENT_DATA": "IC CANNOT BE VERIFIED - insufficient measurements",
    "MAY_BE_FAULTY": "IC MAY BE FAULTY",
    "FAULT_STRONGLY_SUSPECTED": "IC FAULT STRONGLY SUSPECTED",
}
_IC_RANK = {"HEALTHY_TESTED": 0, "INSUFFICIENT_DATA": 1, "MAY_BE_FAULTY": 2, "FAULT_STRONGLY_SUSPECTED": 3}
_IC_TYPE_OF_KIND = {"in": "Input", "out": "Output", "vcc": "Power (VCC)", "gnd": "Power (GND)", "en": "Enable",
                    "sel": "Select input", "net": "Internal net", "tie": "Unused input", "nc": "Unused output"}


def _label_of(text):
    """'IN A' -> 'A'; 'OUT Y (+1 kohm...)' -> 'Y'; '-> N1' / 'N1' -> 'N1'; 'IN S (select)' -> 'S'."""
    t = str(text).replace("\u2192", "").strip()
    for pre in ("IN ", "OUT "):
        if t.startswith(pre):
            t = t[len(pre):]
    return t.split()[0] if t.split() else t


def _plan_output_map(plan):
    m = {}
    for ic in plan["ics"]:
        for pname, (text, kind) in ic["conn"].items():
            if kind == "out" and str(text).startswith("OUT "):
                m[_label_of(text)] = {"ic": ic["ref"], "pin": pname, "pin_no": _ic_pin_no(ic["part"], pname)}
    return m


def _plan_input_map(plan):
    m = {}
    for ic in plan["ics"]:
        for pname, (text, kind) in ic["conn"].items():
            if kind in ("in", "sel") and str(text).startswith("IN "):
                m.setdefault(_label_of(text), []).append((ic["ref"], _ic_pin_no(ic["part"], pname), pname))
    return m


def _upstream_gates(plan, ic_ref, out_pin):
    """Gates (ref, gate-number) feeding the given output gate through internal nets."""
    nets = {n["net"]: n for n in plan["nets"]}
    seen, stack = [], [(ic_ref, out_pin)]
    while stack:
        r, p = stack.pop()
        gate = p[:-1]
        ic = next(i for i in plan["ics"] if i["ref"] == r)
        for q, (text, kind) in ic["conn"].items():
            if q.startswith(gate) and not q.endswith("Y") and kind == "net":
                n = nets.get(text)
                if n:
                    dref, dpin = n["driver"]
                    key = (dref, dpin[:-1])
                    if key not in seen:
                        seen.append(key)
                        stack.append((dref, dpin))
    return seen


def _ic_gate_counts(ic):
    pins = IC_PARTS[ic["part"]]["pins"]
    total = sum(1 for p in pins if p.endswith("Y"))
    used = sorted({int(p[0]) for p in ic["conn"] if p.endswith("Y") and p[0].isdigit()})
    return total, used


def ic_pin_table(ic):
    """Complete pin configuration of one IC of a plan (all pins, DIP top view numbering)."""
    pins = IC_PARTS[ic["part"]]["pins"]
    rows = []
    for i, pname in enumerate(pins, start=1):
        if pname in ic["conn"]:
            text, kind = ic["conn"][pname]
        elif pname == "VCC":
            text, kind = "+5 V supply (decouple with 0.1 uF to GND)", "vcc"
        elif pname == "GND":
            text, kind = "GND (common ground with ESP32 / sensor)", "gnd"
        else:
            text, kind = _ic_default_label(pname)
        rows.append({"pin": i, "name": pname, "type": _IC_TYPE_OF_KIND.get(kind, kind), "connection": text})
    return rows


def ic_signal_flow(plan):
    """One line per gate: inputs (with IC pin numbers) -> output (with IC pin number)."""
    lines = []
    for ic in plan["ics"]:
        func = IC_GATE_FUNC.get(ic["part"], "gate")
        for pin in sorted((p for p in ic["conn"] if p.endswith("Y")), key=lambda p: _ic_pin_no(ic["part"], p)):
            g = pin[:-1]
            ins = [p for p in ic["conn"] if p.startswith(g) and not p.endswith("Y")]
            if ic["part"] == "157" and "S" in ic["conn"]:
                ins.append("S")
            ins.sort(key=lambda p: _ic_pin_no(ic["part"], p))
            in_txt = ", ".join(f"{_label_of(ic['conn'][p][0])} (pin {_ic_pin_no(ic['part'], p)})" for p in ins)
            out_txt = f"{_label_of(ic['conn'][pin][0])} (pin {_ic_pin_no(ic['part'], pin)})"
            lines.append(f"{ic['ref']} gate {g} [{func}]: {in_txt}  ->  {out_txt}")
    return lines


def _cell_voltage(cell):
    if cell.get("status") not in ("MATCH", "MISMATCH", "INVALID"):
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", str(cell.get("voltage", "")))
    return float(m.group(0)) if m else None


def _row_check_steps(plan, cell, outmap, inmap):
    """Pin-by-pin check for one failing truth-table cell."""
    kv = dict(re.findall(r"([A-Za-z][A-Za-z0-9]*)=([01])(?![0-9])", str(cell.get("inputs", ""))))
    parts = []
    for lab, val in kv.items():
        for ref, pno, pname in inmap.get(lab, []):
            parts.append(f"{ref} pin {pno} ({pname}, input {lab}) = logic {val}")
    out = outmap.get(cell["output"])
    out_txt = (f"{out['ic']} pin {out['pin_no']} ({out['pin']}, output {cell['output']})" if out
               else f"output {cell['output']} (direct wire, no gate)")
    return (f"Row {cell['row']} ({cell['inputs']}): with the inputs set, confirm with a multimeter that "
            + ("; ".join(parts) if parts else "the input pins carry the intended levels")
            + f". Then measure {out_txt}: expected logic {cell['expected']}, NEXUS measured {cell['voltage']} (logic {cell['state']}).")


def compute_ic_assessment(sub_type, width, analysis, ic_context=None):
    """Evidence-tiered IC health assessment for a digital circuit test.

    Verdict tiers (never stronger than the evidence allows):
      HEALTHY_TESTED / INSUFFICIENT_DATA / MAY_BE_FAULTY / FAULT_STRONGLY_SUSPECTED.
    Only OUTPUT-pin voltages are measured by NEXUS; VCC, GND and input-pin levels are only
    known when the student supplies them in `ic_context` (user-reported, not verified)."""
    plan = build_ic_plan(sub_type, width)
    if plan is None:
        return {"available": False, "reason": f"No IC plan is defined for sub-type '{sub_type}'.", "ics": []}
    ctx = dict(DEFAULT_IC_CONTEXT)
    for key in DEFAULT_IC_CONTEXT:
        if ic_context and key in ic_context:
            ctx[key] = ic_context[key]
    cells = list(analysis.get("cells", []))
    th = analysis.get("thresholds", {"v_il": 0.8, "v_ih": 2.0})
    outmap, inmap = _plan_output_map(plan), _plan_input_map(plan)
    family = ctx["family"]
    spec = IC_FAMILY_SPECS.get(family)
    try:
        vcc_m = float(ctx["vcc_measured"]) if ctx["vcc_measured"] not in (None, "") else None
    except (TypeError, ValueError):
        vcc_m = None
    levels = ic_family_levels(family, vcc_m)

    # ---- supply evidence (user-reported) --------------------------------------------------
    if vcc_m is None:
        supply = {"status": "NOT_MEASURED", "text": "VCC at the IC pin was not measured/entered: supply voltage is UNVERIFIED."}
    elif spec:
        ok = spec["vcc_min"] <= vcc_m <= spec["vcc_max"]
        supply = {"status": "IN_RANGE" if ok else "OUT_OF_RANGE",
                  "text": f"User-reported VCC = {vcc_m:g} V; {family} requires {spec['vcc_text']} -> {'within' if ok else 'OUTSIDE'} the allowed range."}
    else:
        ok = 2.0 <= vcc_m <= 6.0
        supply = {"status": "UNJUDGED" if ok else "OUT_OF_RANGE",
                  "text": f"User-reported VCC = {vcc_m:g} V; the IC family was not specified, so it cannot be judged exactly "
                          f"({'it is inside the 2-6 V window of every 74-series family' if ok else 'it is outside the 2-6 V window of every 74-series family'})."}

    # ---- per-output summary ------------------------------------------------------------------
    labels = []
    for c in cells:
        if c["output"] not in labels:
            labels.append(c["output"])
    outputs = {}
    for lab in labels:
        oc = [c for c in cells if c["output"] == lab]
        valid = [c for c in oc if c["status"] in ("MATCH", "MISMATCH")]
        states, exps = {c["state"] for c in valid}, {c["expected"] for c in valid}
        mm = [c for c in oc if c["status"] == "MISMATCH"]
        pattern = "NONE"
        if len(valid) >= 2 and len(states) == 1 and len(exps) > 1:
            pattern = f"STUCK_AT_{next(iter(states))}"
        elif len(valid) >= 2 and valid and all(c["status"] == "MISMATCH" for c in valid):
            pattern = "INVERTED"
        elif mm:
            pattern = "PARTIAL"
        outputs[lab] = {"driver": outmap.get(lab), "cells": len(oc), "valid": len(valid),
                        "match": sum(1 for c in oc if c["status"] == "MATCH"), "mismatch": len(mm),
                        "invalid": sum(1 for c in oc if c["status"] == "INVALID"),
                        "missing": sum(1 for c in oc if c["status"] == "MISSING"), "pattern": pattern,
                        "mismatch_rows": [f"Row {c['row']} ({c['inputs']}): expected {c['expected']}, measured logic {c['state']} ({c['voltage']})" for c in mm]}

    ics = []
    for ic in plan["ics"]:
        ref, part_id = ic["ref"], ic["part"]
        part = IC_PARTS[part_id]
        direct = [lab for lab, m in outmap.items() if m["ic"] == ref]
        cone = set(direct)
        upstream_ics = set()
        for lab, m in outmap.items():
            for (uref, _g) in _upstream_gates(plan, m["ic"], m["pin"]):
                if uref == ref:
                    cone.add(lab)
        has_upstream = False
        for lab in direct:
            ups = _upstream_gates(plan, ref, outmap[lab]["pin"])
            if ups:
                has_upstream = True
                upstream_ics.update(u[0] for u in ups)
        dcells = [c for c in cells if c["output"] in direct]
        ccells = [c for c in cells if c["output"] in cone]
        n = lambda lst, s: sum(1 for c in lst if c["status"] == s)
        n_mm, n_inv, n_miss, n_match = n(ccells, "MISMATCH"), n(ccells, "INVALID"), n(ccells, "MISSING"), n(ccells, "MATCH")
        d_mm = [c for c in dcells if c["status"] == "MISMATCH"]
        total_g, used_g = _ic_gate_counts(ic)

        reasons, confirmations_needed = [], []
        if not ccells:
            code, rank = "INSUFFICIENT_DATA", "NONE"
            reasons.append("No measured truth-table output depends on this IC, so nothing can be said about it.")
        elif n_mm == 0:
            rank = "NONE"
            if n_inv == 0 and n_miss == 0:
                code = "HEALTHY_TESTED"
                reasons.append(f"All {n_match} measured output cell(s) that depend on this IC are valid and match the expected truth table.")
                if not direct:
                    reasons.append("This IC has no directly measured output; it is judged only through the downstream outputs that use it (internal nets are not measured).")
            else:
                code = "INSUFFICIENT_DATA"
                reasons.append(f"{n_match} cell(s) matched, but {n_miss} are missing and {n_inv} have an invalid logic level, so the IC cannot be verified.")
        else:
            code = "MAY_BE_FAULTY"
            rank = "PRIMARY" if d_mm else "SECONDARY"
            if d_mm:
                reasons.append(f"{len(d_mm)} mismatching cell(s) on output(s) driven directly by this IC: "
                               + "; ".join(sorted({c['output'] for c in d_mm})) + ".")
            else:
                reasons.append("A failing output depends on this IC only through an internal net; the fault could equally be in an upstream/other section "
                               "(internal nets are not measured).")
            strong_ok = bool(d_mm) and len(d_mm) >= 2 and not any(c["status"] in ("INVALID", "MISSING") for c in dcells) and not has_upstream
            need = []
            if family == IC_FAMILY_NONE or vcc_m is None or supply["status"] != "IN_RANGE":
                need.append("measure VCC at the IC pin, enter the IC family and confirm VCC is within the family range")
            if ctx["unused_inputs_tied"] != "Yes":
                need.append("confirm that all unused inputs are tied to GND/VCC (none floating)")
            if ctx["inputs_verified"] != "Yes":
                need.append("confirm with a multimeter/logic probe that the IC input pins carried the intended levels for each measured row")
            if part_id == "266" and ctx["pullup_fitted"] != "Yes":
                need.append("confirm that a 1 kohm pull-up resistor is fitted on the open-collector output")
            if part_id == "157" and ctx["enable_tied_gnd"] != "Yes":
                need.append("confirm that the enable pin /E (pin 15) is tied to GND")
            if has_upstream:
                need.append("measure the internal net(s) feeding this gate to separate this IC from the upstream IC(s) " + ", ".join(sorted(upstream_ics)))
            if len(d_mm) < 2 and d_mm:
                need.append("measure further truth-table rows - only one mismatching cell is available")
            if any(c["status"] in ("INVALID", "MISSING") for c in dcells):
                need.append("complete/repair the missing or invalid cells of this IC's outputs")
            confirmations_needed = need
            if strong_ok and not need:
                code = "FAULT_STRONGLY_SUSPECTED"
                reasons.append("Wiring, supply, floating-input and input-level causes were reported as excluded by the student, the failing outputs are fully measured "
                               "and repeatedly wrong, so an internal fault in this IC is strongly suspected (still confirm by swapping the IC).")
            else:
                reasons.append("A defective IC is possible but NOT established: other causes have not been excluded (see the alternative causes below).")

        # alternative causes (never claim an IC defect from one wrong output)
        alts = []
        if n_mm or n_inv:
            vcc_pin = IC_PARTS[part_id]["pins"].index("VCC") + 1
            gnd_pin = IC_PARTS[part_id]["pins"].index("GND") + 1
            alts.append({"cause": f"Supply problem (VCC pin {vcc_pin} / GND pin {gnd_pin})",
                         "status": "EXCLUDED (user-reported)" if supply["status"] == "IN_RANGE" else "NOT EXCLUDED",
                         "check": f"Measure VCC (pin {vcc_pin}) to GND (pin {gnd_pin}) at the IC itself; confirm the family range."})
            alts.append({"cause": "Floating / untied unused inputs",
                         "status": "EXCLUDED (user-reported)" if ctx["unused_inputs_tied"] == "Yes" else "NOT EXCLUDED",
                         "check": "Tie every unused input to GND (see the unused-pin notes); a floating input gives an invalid or random level."})
            alts.append({"cause": "Input pins not at the intended logic levels for the measured row",
                         "status": "EXCLUDED (user-reported)" if ctx["inputs_verified"] == "Yes" else "NOT EXCLUDED",
                         "check": "Measure each input pin with a multimeter/logic probe for the failing row."})
            alts.append({"cause": "Wrong pin mapping / wrong gate wired (pin-out differs between 74xx ICs)",
                         "status": "NOT EXCLUDED", "check": "Compare every wire with the IC pin diagram in this report (pin 1 at the notch/dot)."})
            alts.append({"cause": "Loose breadboard contact / broken jumper", "status": "NOT EXCLUDED",
                         "check": "Re-seat the IC and jumpers; test continuity pin-to-pin."})
            alts.append({"cause": "Output loading or sensor input (ESP32 divider/scaling, wrong measuring point)", "status": "NOT EXCLUDED",
                         "check": "Measure the output pin with a multimeter and compare with the NEXUS reading; check the sensor ground is common."})
            alts.append({"cause": f"Logic thresholds / sensor calibration (V_IL = {th['v_il']} V, V_IH = {th['v_ih']} V)", "status": "NOT EXCLUDED",
                         "check": "Check that the thresholds suit the IC family and that the reading matches a multimeter."})
            if part_id == "266":
                alts.append({"cause": "Missing pull-up on the open-collector output (74LS266)",
                             "status": "EXCLUDED (user-reported)" if ctx["pullup_fitted"] == "Yes" else "NOT EXCLUDED",
                             "check": "Fit 1 kohm from output pin 3 to VCC - without it the output cannot reach logic 1."})
            if part_id == "157":
                alts.append({"cause": "Enable pin /E (pin 15) not tied to GND",
                             "status": "EXCLUDED (user-reported)" if ctx["enable_tied_gnd"] == "Yes" else "NOT EXCLUDED",
                             "check": "Tie pin 15 to GND; if it is HIGH/floating all outputs are forced LOW."})
            if part_id == "02":
                alts.append({"cause": "7402 wired with the 7400 pin-out (its outputs are pins 1, 4, 10, 13)", "status": "NOT EXCLUDED",
                             "check": "Verify gate 1 uses 1Y = pin 1, 1A = pin 2, 1B = pin 3."})

        # measured logic levels on the directly measured outputs
        highs = [v for c in dcells if c.get("state") == "1" for v in [_cell_voltage(c)] if v is not None]
        lows = [v for c in dcells if c.get("state") == "0" for v in [_cell_voltage(c)] if v is not None]
        level_notes = []
        if levels:
            if highs and min(highs) < levels["voh_min"]:
                level_notes.append(f"Lowest measured logic-1 level {min(highs):.2f} V is below the typical {family} VOH minimum {levels['voh_min']:.2f} V "
                                   f"(weak HIGH: heavy loading, low VCC, sensor loading or a degraded output stage).")
            if lows and max(lows) > levels["vol_max"]:
                level_notes.append(f"Highest measured logic-0 level {max(lows):.2f} V is above the typical {family} VOL maximum {levels['vol_max']:.2f} V "
                                   f"(elevated LOW: loading, poor ground or a degraded output stage).")
        measured = {"logic1_levels_v": [round(min(highs), 3), round(max(highs), 3)] if highs else None,
                    "logic0_levels_v": [round(min(lows), 3), round(max(lows), 3)] if lows else None,
                    "directly_measured_outputs": direct, "cells_depending_on_ic": len(ccells),
                    "matches": n_match, "mismatches": n_mm, "invalid": n_inv, "missing": n_miss}

        gates_txt = (f"Gate(s) {', '.join(map(str, used_g))} of {total_g} are used in this test; the other {total_g - len(used_g)} gate(s) are NOT tested."
                     if total_g and total_g > len(used_g) else f"All {total_g} gate(s) of the package are used in this test.")
        steps = [f"Power off. Confirm IC orientation: pin 1 at the notch/dot marker ({part['label']}, DIP-{len(part['pins'])}).",
                 f"Power on and measure VCC (pin {IC_PARTS[part_id]['pins'].index('VCC') + 1}) to GND (pin {IC_PARTS[part_id]['pins'].index('GND') + 1}) at the IC: "
                 f"expected {ic_supply_text(part_id)}"]
        bad_cells = [c for c in cells if c["output"] in cone and c["status"] in ("MISMATCH", "INVALID")][:4]
        steps += [_row_check_steps(plan, c, outmap, inmap) for c in bad_cells]
        if bad_cells:
            steps.append("If every input pin level and VCC/GND are correct but the output is still wrong, swap in a known-good IC of the same type and repeat only the failing rows.")
        ics.append({
            "ref": ref, "part_id": part_id, "part_label": part["label"], "function": part["func"], "role_in_circuit": ic["role"],
            "package": f"DIP-{len(part['pins'])}, top view, pin 1 at the notch/dot",
            "vcc_pin": part["pins"].index("VCC") + 1, "gnd_pin": part["pins"].index("GND") + 1,
            "input_pins": [{"pin": _ic_pin_no(part_id, p), "name": p, "signal": t} for p, (t, k) in ic["conn"].items() if k in ("in", "sel", "net") and not p.endswith("Y")],
            "output_pins": [{"pin": _ic_pin_no(part_id, p), "name": p, "signal": t} for p, (t, k) in ic["conn"].items() if k == "out" or p.endswith("Y")],
            "pin_table": ic_pin_table(ic),
            "expected_supply": ic_supply_text(part_id),
            "expected_logic_levels": (levels["note"] if levels else
                                      "IC family not specified: 74LS/TTL logic 1 >= 2.7 V (2.4 V std), logic 0 <= 0.5 V; 74HC/HCT outputs swing to within ~0.1 V of the rails at light load."),
            "measured": measured, "level_notes": level_notes,
            "gates_tested_note": gates_txt,
            "verdict_code": code, "verdict": IC_VERDICTS[code], "suspicion": rank if n_mm else "NONE",
            "reasons": reasons, "confirmations_needed": confirmations_needed,
            "alternative_causes": alts, "verification_steps": steps,
        })

    worst = max((i["verdict_code"] for i in ics), key=lambda c: _IC_RANK[c]) if ics else "INSUFFICIENT_DATA"
    pin_level = "OUTPUT-PIN VOLTAGE ONLY (one probe, measured per truth-table cell)"
    limitations = [
        "NEXUS measures only the voltage of ONE output pin at a time. Input-pin levels, VCC and GND are not measured automatically.",
        "VCC, IC-family, tied-input and pull-up/enable information is user-reported and has not been verified by NEXUS." if (vcc_m is not None or ctx['unused_inputs_tied'] != 'Unknown') else
        "No VCC / wiring confirmation was supplied, so supply and wiring causes cannot be excluded.",
        "Gates that were not part of this test are never verified; a healthy verdict applies only to the gate(s) actually exercised.",
        "Internal nets of multi-IC circuits (N1, N2, ...) are not measured, so a fault cannot be pinned to one IC of a cascade with certainty.",
        "Expected logic levels are typical datasheet values and depend on the family; the NEXUS reading is assumed to equal the true pin voltage.",
    ]
    return {
        "available": True, "family": family, "family_levels": levels, "supply": supply, "context": ctx,
        "thresholds": dict(th), "pin_level_evidence": pin_level, "ics": ics, "outputs": outputs,
        "overall_code": worst, "overall_verdict": IC_VERDICTS[worst],
        "limitations": limitations, "signal_flow": ic_signal_flow(plan), "notes": list(plan["notes"]) + ic_unused_pin_notes(plan),
        "wiring_rows": ic_wiring_rows(plan), "nets": [{"net": n["net"], "meaning": n["meaning"], "driver": list(n["driver"]), "loads": [list(x) for x in n["loads"]]} for n in plan["nets"]],
    }


# ==============================================================================
# UI HELPERS FOR THE LAB-ASSISTANT FEATURES (all dynamic text is HTML-escaped)
# ==============================================================================
_IC_VERDICT_COLORS = {"HEALTHY_TESTED": "#00ff87", "INSUFFICIENT_DATA": "#ffb703", "MAY_BE_FAULTY": "#ff6b35", "FAULT_STRONGLY_SUSPECTED": "#ff0055"}


def _esc(x):
    return html.escape(str(x if x is not None else ""))


def _li(items):
    return "".join(f"<li>{_esc(i)}</li>" for i in items) or "<li>(none)</li>"


def _lab_head(title):
    return f'<b style="color:#00f2fe; font-family:Orbitron,sans-serif; font-size:0.8rem;">{title}</b>'


def render_lab_assistant_cards(s, kind="analogue", evidence=None):
    """Lab-assistant sections of a structured diagnosis: health, what it should do, what the
    measurements indicate, assessments, procedures, teaching mode and WHAT TO DO NEXT."""
    if not s:
        return
    op = s.get("operating_correctly", "UNCERTAIN")
    opc = {"YES": "#00ff87", "NO": "#ff0055"}.get(op, "#ffb703")
    st.markdown(f"""
    <div class="os-card" style="border-left: 5px solid {opc} !important;">
        <div>{_lab_head("OPERATING CORRECTLY?")} <span style="color:{opc}; font-weight:700; border:1px solid {opc}; border-radius:6px; padding:1px 10px;">{_esc(op)}</span>
             &nbsp; {_lab_head("DATA SUFFICIENCY")} <span style="color:#c8d6e5;">{_esc(s.get("data_sufficiency", "N/A"))}</span></div>
        <div style="margin-top:8px;">{_lab_head("CIRCUIT HEALTH ASSESSMENT")}<div style="color:#c8d6e5;">{_esc(s.get("circuit_health_assessment") or "N/A")}</div></div>
        <div style="margin-top:8px;">{_lab_head("WHAT THE CIRCUIT SHOULD DO")}<div style="color:#c8d6e5;">{_esc(s.get("what_circuit_should_do") or "N/A")}</div></div>
        <div style="margin-top:8px;">{_lab_head("WHAT THE MEASUREMENTS INDICATE")}<div style="color:#c8d6e5;">{_esc(s.get("what_measurements_indicate") or "N/A")}</div></div>
        <div style="margin-top:8px;">{_lab_head("EVIDENCE")}<ul style="color:#c8d6e5;">{_li(s.get("supporting_evidence", []))}</ul></div>
    </div>""", unsafe_allow_html=True)

    if evidence and evidence.get("checks"):
        with st.expander("🔎 MEASUREMENT CONSISTENCY CHECKS (calculated by NEXUS)"):
            st.dataframe(pd.DataFrame([{"Level": c["level"], "Observation": c["text"]} for c in evidence["checks"]]), use_container_width=True, hide_index=True)
            th = evidence.get("theory") or {}
            if th:
                st.json({k: v for k, v in th.items() if k != "assumptions"})
                st.caption(th.get("assumptions", ""))
    with st.expander("🧩 COMPONENT / WIRING / SENSOR ASSESSMENT"):
        comps = s.get("component_fault_assessment") or []
        if comps:
            st.dataframe(pd.DataFrame([{"Component": c["component"], "Fault probability (AI est.)": (f"{c['probability_percent']} %" if c["probability_percent"] is not None else "N/A - insufficient evidence"),
                                        "Evidence": c["evidence"], "How to verify": c["verify"]} for c in comps]), use_container_width=True, hide_index=True)
        else:
            st.info("No component-level probability: the available measurements are not sufficient to rate individual components.")
        w = s.get("wiring_fault_assessment") or {}
        wp = f"{w['probability_percent']} %" if w.get("probability_percent") is not None else "N/A - insufficient evidence"
        st.markdown(f"**Wiring fault probability (AI estimate):** {_esc(wp)}  \n{_esc(w.get('evidence', ''))}")
        for c in w.get("checks", []):
            st.markdown(f"- {_esc(c)}")
        sr = s.get("sensor_reliability") or {}
        st.markdown(f"**Sensor / measurement reliability:** {_esc(sr.get('rating', 'UNKNOWN'))} - {_esc(sr.get('evidence', ''))}")
        if kind == "analogue":
            st.markdown(f"**Ripple:** {_esc(s.get('ripple_assessment') or 'NOT ASSESSED - no ripple data is available.')}")
    with st.expander("🛠 CORRECTIVE ACTIONS • VERIFICATION • RETEST"):
        st.markdown("**Corrective actions**")
        for i, x in enumerate(s.get("corrective_actions", []), 1):
            st.markdown(f"{i}. {_esc(x)}")
        st.markdown("**Verification procedure**")
        for i, x in enumerate(s.get("verification_procedure", []), 1):
            st.markdown(f"{i}. {_esc(x)}")
        st.markdown(f"**Final retest recommendation:** {_esc(s.get('final_retest_recommendation') or 'N/A')}")
    t = s.get("teaching") or {}
    with st.expander("🎓 STUDENT TEACHING MODE - purpose, working, observations, precautions"):
        for title, key in (("Purpose of the experiment", "purpose"), ("How it works", "how_it_works")):
            if t.get(key):
                st.markdown(f"**{title}:** {_esc(t[key])}")
        for title, key in (("Why the components are used", "why_components"), ("What you should observe", "what_to_observe"),
                           ("What abnormal readings indicate", "abnormal_readings"), ("How to troubleshoot", "troubleshooting_tips"),
                           ("Precautions", "precautions"), ("What you should learn", "learning_outcomes")):
            if t.get(key):
                st.markdown(f"**{title}**")
                for x in t[key]:
                    st.markdown(f"- {_esc(x)}")
    nxt = s.get("lab_assistant_next_steps") or []
    st.markdown(f"""
    <div class="os-card" style="border-left: 5px solid #9d4edd !important;">
        <div style="font-family:Orbitron,sans-serif; color:#9d4edd; letter-spacing:2px; font-weight:700;">LAB ASSISTANT - WHAT TO DO NEXT</div>
        <ol style="color:#c8d6e5; margin-top:8px;">{_li(nxt) if nxt else "<li>Re-check the wiring against the diagram and repeat the measurement.</li>"}</ol>
    </div>""", unsafe_allow_html=True)
    if s.get("limitations"):
        with st.expander("⚠ LIMITATIONS OF THE MEASUREMENTS AND DIAGNOSIS"):
            for x in s["limitations"]:
                st.markdown(f"- {_esc(x)}")
    for nt in s.get("validation_notes", []):
        st.caption(f"Validation note: {nt}")
    st.caption(AI_PROBABILITY_NOTICE)


def render_ic_assessment_cards(ica, ai_ic=None):
    """Evidence-based IC health assessment (deterministic) with optional AI explanations."""
    if not ica or not ica.get("available"):
        st.info((ica or {}).get("reason", "No IC assessment is available for this circuit."))
        return
    oc = _IC_VERDICT_COLORS.get(ica["overall_code"], "#00f2fe")
    st.markdown(f"""
    <div class="os-card" style="border-left: 5px solid {oc} !important;">
        <div style="font-family:Orbitron,sans-serif; color:{oc}; font-weight:700;">IC HEALTH (evidence-based, computed by NEXUS): {_esc(ica['overall_verdict'])}</div>
        <div style="color:#c8d6e5;">Pin-level evidence: {_esc(ica['pin_level_evidence'])}</div>
        <div style="color:#c8d6e5;">IC family: {_esc(ica['family'])} &nbsp;|&nbsp; {_esc(ica['supply']['text'])}</div>
    </div>""", unsafe_allow_html=True)
    ai_ic = {x["ic_ref"]: x for x in (ai_ic or [])}
    for ic in ica["ics"]:
        col = _IC_VERDICT_COLORS.get(ic["verdict_code"], "#00f2fe")
        with st.expander(f"{ic['ref']} - {ic['part_label']} ({ic['function']}) → {ic['verdict']}", expanded=ic["verdict_code"] in ("MAY_BE_FAULTY", "FAULT_STRONGLY_SUSPECTED")):
            st.markdown(f'<span style="color:{col}; font-weight:700;">{_esc(ic["verdict"])}</span>', unsafe_allow_html=True)
            for r in ic["reasons"]:
                st.markdown(f"- {_esc(r)}")
            st.markdown(f"**VCC pin {ic['vcc_pin']} / GND pin {ic['gnd_pin']}** - {_esc(ic['expected_supply'])}")
            st.markdown(f"**Expected logic levels:** {_esc(ic['expected_logic_levels'])}")
            m = ic["measured"]
            st.markdown(f"**Measured:** logic 1 {_esc(m['logic1_levels_v'] or 'not measured')} V, logic 0 {_esc(m['logic0_levels_v'] or 'not measured')} V; "
                        f"{m['matches']} match / {m['mismatches']} mismatch / {m['invalid']} invalid / {m['missing']} missing. {_esc(ic['gates_tested_note'])}")
            for ln in ic["level_notes"]:
                st.markdown(f"- Level indicator: {_esc(ln)}")
            st.dataframe(pd.DataFrame(ic["pin_table"]).rename(columns={"pin": "Pin", "name": "Pin name", "type": "Type", "connection": "Connection"}), use_container_width=True, hide_index=True)
            if ic["alternative_causes"]:
                st.markdown("**Other possible causes (exclude them before blaming the IC)**")
                st.dataframe(pd.DataFrame(ic["alternative_causes"]).rename(columns={"cause": "Possible cause", "status": "Status", "check": "How to check"}), use_container_width=True, hide_index=True)
            if ic["confirmations_needed"]:
                st.markdown("**To settle the verdict:**")
                for x in ic["confirmations_needed"]:
                    st.markdown(f"- {_esc(x)}")
            if ic["verification_steps"] and ic["verdict_code"] != "HEALTHY_TESTED":
                st.markdown("**Pin-by-pin verification**")
                for i, x in enumerate(ic["verification_steps"], 1):
                    st.markdown(f"{i}. {_esc(x)}")
            if ic["ref"] in ai_ic and ai_ic[ic["ref"]]["explanation"]:
                st.markdown(f"**AI explanation:** {_esc(ai_ic[ic['ref']]['explanation'])}")
    with st.expander("Limits of the IC assessment"):
        for x in ica["limitations"]:
            st.markdown(f"- {_esc(x)}")


def _queue_speech(text):
    st.session_state.pending_speech = text


def _complete_analysis(ctx, meta, diag):
    """Builds, saves and publishes an analogue result (called when the Gemini job - or the offline engine - is done)."""
    if not diag["ok"]:
        st.session_state.gemini_notice = ("error", f"⚠️ {diag['error']}  Your {'held ' if meta['source'] == 'HELD' else ''}measurement is unchanged - press ANALYZE WITH GEMINI to retry.")
        return
    snapshot = meta["snapshot"]
    result = {
        "timestamp": meta["timestamp"], "circuit": meta["circuit"], "category": meta["category"],
        "circuit_info": meta["circuit_info"], "targets": diag["targets"], "sensor": snapshot,
        "deviations": diag["deviations"], "status": diag["status"], "source": meta["source"],
        "esp32_status": meta["esp32_status"], "mqtt_status": meta["mqtt_status"], "engine": diag["engine"],
        "text": diag["text"], "fault_probability": diag["fault_probability"], "confidence": diag["confidence"],
        "pdf_bytes": None, "structured": diag.get("structured"), "payload": diag.get("payload"), "evidence": diag.get("evidence"),
        "baseline": make_resolution_baseline(snapshot, diag["deviations"], diag["targets"]),
        "resolution": initial_resolution(diag["status"]), "verifications": [], "schema_version": 2,
    }
    st.session_state.last_gemini_result = result
    st.session_state.gemini_notice = None
    save_analysis_to_history(result)
    _queue_speech(result["text"])


@st.fragment(run_every="1s")
def render_gemini_pending():
    """Polls the background Gemini job; the live telemetry fragments keep refreshing meanwhile."""
    pend = st.session_state.get("gemini_pending")
    if not pend:
        return
    job = poll_gemini_job(pend["job_id"])
    elapsed = time.time() - pend["started"]
    if job is None or (job["state"] != "done" and elapsed > GEMINI_JOB_TIMEOUT_S):
        st.session_state.gemini_pending = None
        st.session_state.gemini_notice = ("error", "⚠️ Gemini did not answer in time. Your measurement is unchanged - press ANALYZE WITH GEMINI to retry.")
        st.rerun()
        return
    if job["state"] == "done":
        diag = finalize_automatic_diagnosis(pend["ctx"], job.get("text"), job.get("error"))
        _complete_analysis(pend["ctx"], pend["meta"], diag)
        st.session_state.gemini_pending = None
        st.rerun()
        return
    st.info(f"⏳ {friendly_pending_text(pend['started'])}")


def complete_digital_gemini(pend, job):
    """Writes the finished Gemini job into the digital analysis AND its frozen report record."""
    raw, err = job.get("text"), job.get("error")
    cur = st.session_state.digital_analysis.get(pend["circuit"])
    if cur is not None and cur.get("test_id") == pend["test_id"]:
        finalize_digital_gemini(cur, raw, err)
    for rec in st.session_state.analysis_records:
        if rec["test_id"] == pend["test_id"] and rec["kind"] == "digital":
            finalize_digital_gemini(rec["result"], raw, err)
    if not err and raw:
        _queue_speech("Digital circuit analysis complete.")


@st.fragment(run_every="1s")
def render_digital_pending():
    pend = st.session_state.get("digital_pending")
    if not pend:
        return
    job = poll_gemini_job(pend["job_id"])
    elapsed = time.time() - pend["started"]
    if job is None or (job["state"] != "done" and elapsed > GEMINI_JOB_TIMEOUT_S):
        complete_digital_gemini(pend, {"text": "", "error": "Gemini did not answer in time. The deterministic result is still valid; press ANALYSE DIGITAL CIRCUIT to retry."})
        st.session_state.digital_pending = None
        st.rerun()
        return
    if job["state"] == "done":
        complete_digital_gemini(pend, job)
        st.session_state.digital_pending = None
        st.rerun()
        return
    st.info(f"⏳ {friendly_pending_text(pend['started'])}")


def render_ic_context_inputs(ckt_name, ckt_info):
    """Optional, user-reported IC context (family, VCC, wiring confirmations) - frozen into the analysis."""
    ctxs = st.session_state.digital_ic_context
    cur = dict(DEFAULT_IC_CONTEXT)
    cur.update(ctxs.get(ckt_name, {}))
    with st.expander("🧩 IC Family, Supply & Wiring Confirmation (optional - lets the IC health assessment exclude other causes)"):
        st.caption("NEXUS measures only the output pin. Anything entered here is USER-REPORTED, is not verified by NEXUS, and is applied (frozen) when you press ANALYSE.")
        fam = st.selectbox("IC family fitted", IC_FAMILY_OPTIONS, index=IC_FAMILY_OPTIONS.index(cur["family"]) if cur["family"] in IC_FAMILY_OPTIONS else 0, key=f"dig_icfam_{ckt_name}")
        yn = ["Unknown", "Yes", "No"]
        c1, c2 = st.columns(2)
        with c1:
            use_v = st.checkbox("I measured VCC at the IC pin with a multimeter", value=cur["vcc_measured"] is not None, key=f"dig_icvcc_chk_{ckt_name}")
            vcc = st.number_input("Measured VCC (V)", min_value=0.0, max_value=15.0, value=float(cur["vcc_measured"]) if cur["vcc_measured"] is not None else 5.0,
                                  step=0.05, key=f"dig_icvcc_{ckt_name}", disabled=not use_v)
            unused = st.selectbox("All unused inputs are tied to GND/VCC", yn, index=yn.index(cur["unused_inputs_tied"]), key=f"dig_icun_{ckt_name}")
        with c2:
            verified = st.selectbox("I verified the IC input pin levels for each measured row", yn, index=yn.index(cur["inputs_verified"]), key=f"dig_icin_{ckt_name}")
            pull = cur["pullup_fitted"]
            if ckt_info.get("sub_type") == "XNOR":
                pull = st.selectbox("1 kΩ pull-up fitted on the 74LS266 output", yn, index=yn.index(cur["pullup_fitted"]), key=f"dig_icpu_{ckt_name}")
            en = cur["enable_tied_gnd"]
            if ckt_info.get("sub_type") == "mux_2_1":
                en = st.selectbox("Enable pin /E (pin 15) tied to GND", yn, index=yn.index(cur["enable_tied_gnd"]), key=f"dig_icen_{ckt_name}")
        ctxs[ckt_name] = {"family": fam, "vcc_measured": float(vcc) if use_v else None, "unused_inputs_tied": unused,
                          "inputs_verified": verified, "pullup_fitted": pull, "enable_tied_gnd": en}



init_session_state()

# Canvas Background JS
canvas_background_js = """
<canvas id="fui-canvas" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -10; pointer-events: none; opacity: 0.85;"></canvas>
<div id="fui-cursor-glow" style="position: fixed; width: 250px; height: 250px; border-radius: 50%; background: radial-gradient(circle, rgba(0, 242, 254, 0.12) 0%, rgba(0, 242, 254, 0) 70%); pointer-events: none; transform: translate(-50%, -50%); z-index: -9; transition: width 0.3s, height 0.3s;"></div>

<script>
(function() {
    const cursorGlow = document.getElementById('fui-cursor-glow');
    window.addEventListener('mousemove', (e) => {
        if(cursorGlow) {
            cursorGlow.style.left = e.clientX + 'px';
            cursorGlow.style.top = e.clientY + 'px';
        }
    });

    const canvas = document.getElementById('fui-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let w = canvas.width = window.innerWidth;
    let h = canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    });

    const particles = [];
    const count = 55;
    for (let i = 0; i < count; i++) {
        particles.push({
            x: Math.random() * w,
            y: Math.random() * h,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            radius: Math.random() * 2 + 1,
            alpha: Math.random() * 0.6 + 0.2
        });
    }

    let angle = 0;
    function draw() {
        ctx.clearRect(0, 0, w, h);

        angle += 0.005;
        ctx.strokeStyle = 'rgba(0, 242, 254, 0.03)';
        ctx.lineWidth = 1;
        const gridStep = 70;
        for (let x = 0; x < w; x += gridStep) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
        }
        for (let y = 0; y < h; y += gridStep) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
        }

        for (let i = 0; i < count; i++) {
            let p = particles[i];
            p.x += p.vx; p.y += p.vy;
            if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
            if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;

            ctx.fillStyle = `rgba(0, 242, 254, ${p.alpha})`;
            ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2); ctx.fill();

            for (let j = i + 1; j < count; j++) {
                let p2 = particles[j];
                let dist = Math.hypot(p.x - p2.x, p.y - p2.y);
                if (dist < 140) {
                    ctx.strokeStyle = `rgba(0, 242, 254, ${0.15 * (1 - dist / 140)})`;
                    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
                }
            }
        }
        requestAnimationFrame(draw);
    }
    draw();
})();
</script>
"""

FUI_STYLING = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

header[data-testid="stHeader"] {
    background-color: #02050e !important;
}
header[data-testid="stHeader"] button, 
header[data-testid="stHeader"] svg,
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapseButton"] svg {
    color: #00f2fe !important;
    fill: #00f2fe !important;
    stroke: #00f2fe !important;
}

html, body, .stApp {
    background: #02050e !important;
    color: #c8d6e5 !important;
    font-family: 'Rajdhani', sans-serif !important;
    overflow-x: hidden;
}

.stAppMain {
    animation: fadeInScale 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes fadeInScale {
    0% { opacity: 0; transform: scale(0.98) translateY(10px); filter: blur(6px); }
    100% { opacity: 1; transform: scale(1) translateY(0); filter: blur(0); }
}

.os-card {
    background: rgba(6, 12, 26, 0.65) !important;
    backdrop-filter: blur(25px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(25px) saturate(200%) !important;
    border: 1px solid rgba(0, 242, 254, 0.22) !important;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.8), inset 0 0 15px rgba(0, 242, 254, 0.05) !important;
    border-radius: 12px !important;
    padding: 22px !important;
    margin-bottom: 20px !important;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    position: relative;
    overflow: hidden;
    animation: floatPanel 6s ease-in-out infinite alternate;
}

.os-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; width: 4px; height: 100%;
    background: linear-gradient(180deg, #00f2fe, #7928ca);
    opacity: 0.8;
}

.os-card:hover {
    transform: translateY(-6px) rotate(0.5deg) scale(1.008);
    border-color: rgba(0, 242, 254, 0.6) !important;
    box-shadow: 0 15px 35px -5px rgba(0, 242, 254, 0.3), inset 0 0 20px rgba(0, 242, 254, 0.15) !important;
}

@keyframes floatPanel {
    0% { transform: translateY(0px) rotate(0deg); }
    100% { transform: translateY(-4px) rotate(0.4deg); }
}

.os-header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(4, 8, 18, 0.85);
    border: 1px solid rgba(0, 242, 254, 0.3);
    border-radius: 8px;
    padding: 10px 20px;
    margin-bottom: 22px;
    font-family: 'Orbitron', sans-serif;
    font-size: 0.78rem;
    letter-spacing: 1.2px;
    box-shadow: 0 0 20px rgba(0, 242, 254, 0.15);
}

.sys-tag {
    display: flex;
    align-items: center;
    gap: 8px;
}

.os-indicator-dot {
    width: 9px; height: 9px;
    border-radius: 50%;
    box-shadow: 0 0 12px currentColor;
    animation: pulseGlow 1.8s infinite;
}

@keyframes pulseGlow {
    0% { transform: scale(0.9); }
    50% { transform: scale(1.3); }
    100% { transform: scale(0.9); }
}

.core-container {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 35px 0;
    perspective: 1000px;
}

.core-reactor {
    width: 170px;
    height: 170px;
    border-radius: 50%;
    border: 2px dashed #00f2fe;
    display: flex;
    justify-content: center;
    align-items: center;
    animation: rotateCore 16s linear infinite;
    box-shadow: 0 0 40px rgba(0, 242, 254, 0.35), inset 0 0 30px rgba(0, 242, 254, 0.35);
    position: relative;
}

.core-ring-2 {
    position: absolute;
    width: 140px; height: 140px;
    border-radius: 50%;
    border: 2px dotted #00ff87;
    animation: rotateCoreRev 10s linear infinite;
}

.core-ring-3 {
    position: absolute;
    width: 110px; height: 110px;
    border-radius: 50%;
    border: 2px solid #7928ca;
    border-left: 2px solid transparent;
    animation: rotateCore 6s linear infinite;
}

.core-ring-4 {
    position: absolute;
    width: 80px; height: 80px;
    border-radius: 50%;
    border: 2px dashed #ff0055;
    animation: rotateCoreRev 4s linear infinite;
}

.core-center-node {
    position: absolute;
    width: 50px; height: 50px;
    border-radius: 50%;
    background: radial-gradient(circle, #00ff87 0%, #00f2fe 60%, rgba(0,242,254,0) 100%);
    box-shadow: 0 0 30px #00ff87;
    animation: corePulse 1.5s ease-in-out infinite alternate;
}

@keyframes rotateCore { 100% { transform: rotate(360deg); } }
@keyframes rotateCoreRev { 100% { transform: rotate(-360deg); } }
@keyframes corePulse { 0% { transform: scale(0.8); opacity: 0.7; } 100% { transform: scale(1.2); opacity: 1.0; } }

.pipeline-flow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px;
    background: rgba(3, 7, 18, 0.85);
    border: 1px solid rgba(0, 242, 254, 0.25);
    border-radius: 10px;
    margin: 20px 0;
}

.node-box {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.78rem;
    padding: 9px 16px;
    background: rgba(0, 242, 254, 0.12);
    border: 1px solid #00f2fe;
    border-radius: 6px;
    color: #00f2fe;
    box-shadow: 0 0 12px rgba(0, 242, 254, 0.25);
    transition: transform 0.2s;
}

.node-box:hover {
    transform: scale(1.08);
}

.pipe-connector {
    flex-grow: 1;
    height: 3px;
    background: linear-gradient(90deg, #00f2fe, #00ff87);
    margin: 0 10px;
    position: relative;
    overflow: hidden;
}

.pipe-connector::after {
    content: '';
    position: absolute;
    top: 0; left: -100%; width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, #ffffff, transparent);
    animation: flowData 1.2s linear infinite;
}

@keyframes flowData { 0% { left: -100%; } 100% { left: 100%; } }

[data-testid="stSidebar"] {
    background: rgba(2, 5, 14, 0.96) !important;
    border-right: 1px solid rgba(0, 242, 254, 0.25) !important;
}

h1, h2, h3 {
    font-family: 'Orbitron', sans-serif !important;
    letter-spacing: 1.6px !important;
    text-transform: uppercase;
}

h1 {
    background: linear-gradient(90deg, #00f2fe 0%, #00ff87 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.2rem !important;
    font-weight: 900 !important;
}

div.stButton > button {
    background: linear-gradient(135deg, rgba(0, 242, 254, 0.2) 0%, rgba(121, 40, 202, 0.3) 100%) !important;
    color: #00f2fe !important;
    font-family: 'Orbitron', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 1.5px !important;
    border: 1px solid #00f2fe !important;
    border-radius: 6px !important;
    padding: 12px 24px !important;
    box-shadow: 0 0 15px rgba(0, 242, 254, 0.2) !important;
    transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
}

div.stButton > button:hover {
    background: linear-gradient(135deg, #00f2fe 0%, #7928ca 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 0 30px rgba(0, 242, 254, 0.7) !important;
    transform: translateY(-3px) scale(1.02) !important;
}

div.stButton > button:active {
    transform: translateY(1px) scale(0.98) !important;
}

div[data-baseweb="select"] {
    background-color: rgba(3, 7, 18, 0.9) !important;
    border: 1px solid rgba(0, 242, 254, 0.3) !important;
    border-radius: 6px !important;
}

div[data-testid="stDataFrame"] {
    background: rgba(3, 7, 18, 0.7) !important;
    border: 1px solid rgba(0, 242, 254, 0.25) !important;
    border-radius: 8px !important;
}
</style>
"""
st.markdown(FUI_STYLING, unsafe_allow_html=True)
st.components.v1.html(canvas_background_js, height=0, width=0)

if not st.session_state.loaded_once:
    boot_placeholder = st.empty()
    with boot_placeholder.container():
        st.markdown("""
        <div style="height: 70vh; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
            <h2 style="font-family: Orbitron; color: #00f2fe; font-size: 2rem; margin-bottom: 10px;">NEXUS AI OPERATING SYSTEM</h2>
            <p style="color: #00ff87; font-family: Orbitron; letter-spacing: 2px;">INITIALIZING CORE MATRIX...</p>
            <div style="width: 300px; height: 6px; background: rgba(0,242,254,0.1); border-radius: 3px; overflow: hidden; border: 1px solid #00f2fe;">
                <div style="width: 100%; height: 100%; background: linear-gradient(90deg, #00f2fe, #00ff87); animation: bootProgress 1.5s ease-in-out;"></div>
            </div>
            <div style="margin-top: 15px; font-size: 0.8rem; color: #64748b; font-family: Orbitron;">
                ESP32 LINK STANDBY | MQTT INITIALIZING | DATABASE READY | GEMINI STANDBY
            </div>
        </div>
        <style>
        @keyframes bootProgress { 0% { width: 0%; } 100% { width: 100%; } }
        </style>
        """, unsafe_allow_html=True)
        time.sleep(1.2)
    boot_placeholder.empty()
    st.session_state.loaded_once = True

# ------------------------------------------------------------------------------
# TOP HEADER HUD CONTROL BAR (AUTOMATIC 1-SECOND REFRESH FRAGMENT)
# ------------------------------------------------------------------------------
@st.fragment(run_every="1s")
def render_os_header():
    now = datetime.datetime.now()

    if get_mqtt_connection_status() == "Connected":
        mqtt_display, mqtt_color = "CONNECTED", "#00ff87"
    else:
        mqtt_display, mqtt_color = "DISCONNECTED", "#ff0055"

    esp_state, _esp_age = get_esp32_status()
    if esp_state == "ONLINE":
        esp_display, esp_color = "ONLINE", "#00ff87"
    elif esp_state == "WAITING":
        esp_display, esp_color = "WAITING FOR DATA", "#ffb703"
    else:
        esp_display, esp_color = "OFFLINE", "#ff0055"

    st.markdown(f"""
    <div class="os-header-bar">
        <div class="sys-tag"><span class="os-indicator-dot" style="background-color:{mqtt_color}; color:{mqtt_color};"></span> <b>SYSTEM:</b> NEXUS AI OS</div>
        <div><b>DATE:</b> {now.strftime("%Y-%m-%d")}</div>
        <div><b>TIME:</b> {now.strftime("%H:%M:%S")}</div>
        <div><b>ESP32:</b> <span style="color:{esp_color};">{esp_display}</span></div>
        <div><b>MQTT:</b> <span style="color:{mqtt_color};">{mqtt_display}</span></div>
        <div><b>GEMINI:</b> <span style="color:#00ff87;">ACTIVE</span></div>
        <div><b>CPU:</b> 12.4%</div>
        <div><b>RAM:</b> 3.2 GB</div>
        <div><b>FPS:</b> 60.0</div>
    </div>
    """, unsafe_allow_html=True)

render_os_header()

# Sidebar System Menu
st.sidebar.markdown('<div style="font-family:Orbitron; font-size:1.1rem; color:#00f2fe; margin-bottom:15px; font-weight:700;">⚡ OS NAVIGATION</div>', unsafe_allow_html=True)
pages = ["Home", "Circuit Type", "Configuration", "Probe Guide", "Testing Dashboard", "Digital Circuit Tester", "Generate Report", "History", "Settings", "About"]
page_choice = st.sidebar.radio("DIRECTIVE", pages, index=pages.index(st.session_state.page if st.session_state.page in pages else "Home"))
st.session_state.page = page_choice

# Audio Voice Mute/Unmute Control Toggle
st.sidebar.markdown("---")
is_mute = st.sidebar.checkbox("🔇 Mute Audio Speech Output", value=st.session_state.is_muted)
if is_mute != st.session_state.is_muted:
    st.session_state.is_muted = is_mute
    if is_mute:
        speak_text("")

curr_circuit = get_current_circuit_data()   # None when the stored selection is invalid (never substituted)

# ------------------------------------------------------------------------------
# STEP 1: HOME PAGE
# ------------------------------------------------------------------------------
if st.session_state.page == "Home":
    st.title("⚡ NEXUS ELECTRONIC DIAGNOSTIC OS")
    st.caption("AI Operating System Platform | Autonomous Circuit Intelligence")

    speak_text("Welcome to Nexus AI Operating System")

    st.markdown("""
    <div class="core-container">
        <div class="core-reactor">
            <div class="core-ring-2"></div>
            <div class="core-ring-3"></div>
            <div class="core-ring-4"></div>
            <div class="core-center-node"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    api_key = st.session_state.get("api_key") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.warning("⚠️ **STANDBY MODE**: Gemini AI Engine is running in offline mode. Configure API key in OS Settings.")

    st.markdown("### 🎛️ Circuit System Selection")
    # selected_category / selected_circuit are the single source of truth. Widget keys are re-synced
    # from them BEFORE the widgets are created (legal), and the on_change callbacks write back.
    ensure_valid_selection()
    st.session_state["home_cat_select"] = st.session_state.selected_category
    st.session_state["home_ckt_select"] = st.session_state.selected_circuit

    st.markdown('<div class="os-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.selectbox(
            "SYSTEM CATEGORY",
            list(CIRCUIT_DATABASE.keys()),
            key="home_cat_select",
            on_change=cb_home_category_changed,
        )

    with c2:
        st.selectbox(
            "TARGET CIRCUIT TOPOLOGY",
            list(CIRCUIT_DATABASE[st.session_state.selected_category].keys()),
            key="home_ckt_select",
            on_change=cb_home_circuit_changed,
        )

    curr_circuit = get_current_circuit_data()

    st.markdown(f"""
        <hr style='border:0; height:1px; background: rgba(0,242,254,0.2); margin:18px 0;'>
        <h3 style="color:#00ff87 !important; margin-top:0;">LOADED TOPOLOGY: {st.session_state.selected_circuit}</h3>
        <p style="font-size: 1.05rem;"><b>CATEGORY:</b> {st.session_state.selected_category}</p>
        <p style="font-size: 1.05rem;"><b>FUNCTION:</b> {curr_circuit['description']}</p>
        <p style="font-size: 1.0rem; color:#00f2fe;"><b>COMPONENTS:</b> {curr_circuit.get('components', curr_circuit.get('diagram', 'N/A'))}</p>
        <p><b>SCHEMATIC VECTOR:</b> <code style="color:#00ff87; background:rgba(0,0,0,0.6); padding:6px 12px; border-radius:4px; border:1px solid rgba(0,255,135,0.3);">{curr_circuit['diagram']}</code></p>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    c_h1, c_h2 = st.columns(2)
    with c_h1:
        dest = route_for(st.session_state.selected_category, st.session_state.selected_circuit)
        st.button("LAUNCH / TEST SELECTED CIRCUIT →", key="home_launch_btn", use_container_width=True,
                  on_click=cb_launch_selected,
                  help=f"Opens the {dest} for exactly: {st.session_state.selected_circuit}")
    with c_h2:
        st.button("OPEN DIGITAL TESTER MODULE →", key="home_launch_digital_btn", use_container_width=True,
                  on_click=cb_launch_digital_module,
                  help="Opens the digital module. If the selected circuit is not digital, the last-used (or first) digital circuit is opened and clearly labelled.")

# ------------------------------------------------------------------------------
# STEP 2: CATEGORY / TYPE BROWSER PAGE
# ------------------------------------------------------------------------------
elif st.session_state.page == "Circuit Type":
    ensure_valid_selection()
    st.header(f"📂 CIRCUIT CATALOG ARCHIVE: {st.session_state.selected_category}")
    cols = st.columns(2)
    for idx, (c_name, c_info) in enumerate(CIRCUIT_DATABASE[st.session_state.selected_category].items()):
        with cols[idx % 2]:
            st.markdown(f"""
            <div class='os-card'>
                <h3 style="color:#00f2fe !important;">⚡ {c_name}</h3>
                <p><b>Description:</b> {c_info['description']}</p>
                <p style="color:#00ff87;"><b>Details:</b> {c_info.get('components', c_info.get('diagram', 'N/A'))}</p>
            </div>
            """, unsafe_allow_html=True)
            st.button(f"LOAD {c_name.upper()}", key=f"btn_{st.session_state.selected_category}_{c_name}",
                      on_click=cb_load_circuit, args=(st.session_state.selected_category, c_name))

# ------------------------------------------------------------------------------
# STEP 3: CONFIGURATION
# ------------------------------------------------------------------------------
elif st.session_state.page == "Configuration":
    if curr_circuit is None:
        render_no_selection_message("Configuration")
        st.stop()
    if route_for(st.session_state.selected_category, st.session_state.selected_circuit) == "Digital Circuit Tester":
        st.session_state.page = "Digital Circuit Tester"
        st.rerun()
    st.header(f"⚙️ TARGET CONFIGURATION - {st.session_state.selected_circuit}")
    st.markdown('<div class="os-card">', unsafe_allow_html=True)
    
    st.markdown(f"**HARDWARE MATRIX SPEC:** `{curr_circuit.get('components', 'N/A')}`")
    st.markdown("<hr style='border:0; height:1px; background: rgba(0,242,254,0.2);'>", unsafe_allow_html=True)
    
    default_in_v = st.session_state.target_input_voltage if st.session_state.target_input_voltage is not None else float(curr_circuit['exp_input_v'])
    default_out_v = st.session_state.target_output_voltage if st.session_state.target_output_voltage is not None else float(curr_circuit['exp_output_v'])
    default_in_i = st.session_state.target_input_current if st.session_state.target_input_current is not None else float(curr_circuit['exp_input_i'])
    default_out_i = st.session_state.target_output_current if st.session_state.target_output_current is not None else float(curr_circuit['exp_output_i'])

    cfg_c1, cfg_c2 = st.columns(2)
    with cfg_c1:
        in_v = st.number_input("Target Input Voltage (V)", value=default_in_v, key="cfg_input_v")
        in_i = st.number_input("Target Input Current (A)", value=default_in_i, key="cfg_input_i")
    with cfg_c2:
        out_v = st.number_input("Target Output Voltage (V)", value=default_out_v, key="cfg_output_v")
        out_i = st.number_input("Target Output Current (A)", value=default_out_i, key="cfg_output_i")
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Save / Apply Configuration", use_container_width=True):
        st.session_state.target_input_voltage = float(in_v)
        st.session_state.target_output_voltage = float(out_v)
        st.session_state.target_input_current = float(in_i)
        st.session_state.target_output_current = float(out_i)
        st.success("✅ Target values successfully updated and active!")

    st.markdown('</div>', unsafe_allow_html=True)

    c_prev, c_next = st.columns(2)
    with c_prev:
        if st.button("← SYSTEM MATRIX"):
            st.session_state.page = "Home"
            st.rerun()
    with c_next:
        if st.button("PROBE MAPPING SETUP →"):
            st.session_state.page = "Probe Guide"
            st.rerun()

# ------------------------------------------------------------------------------
# STEP 4: PROBE GUIDE
# ------------------------------------------------------------------------------
elif st.session_state.page == "Probe Guide":
    if curr_circuit is None:
        render_no_selection_message("Probe Guide")
        st.stop()
    if route_for(st.session_state.selected_category, st.session_state.selected_circuit) == "Digital Circuit Tester":
        st.session_state.page = "Digital Circuit Tester"
        st.rerun()
    st.header(f"📍 SENSOR PROBE CALIBRATION - {st.session_state.selected_circuit}")
    st.info(f"🧩 **ACTIVE LAYOUT CONFIGURATION**: {curr_circuit.get('components', 'N/A')}")
    for probe in curr_circuit.get("probes", []):
        st.markdown(f"""
        <div class="os-card" style="border-left: 4px solid #00f2fe !important;">
            <h4 style="color:#00ff87 !important;">PROBE STEP {probe['step']}: {probe['name']}</h4>
            <p>Connect Acquisition Hardware Terminal to Node: <b style="color:#00f2fe;">{probe['loc']}</b></p>
        </div>
        """, unsafe_allow_html=True)

    _psch = build_analog_schematic(st.session_state.selected_circuit)
    if _psch is not None:
        st.markdown("### 📐 Circuit schematic with probe positions")
        st.components.v1.html(
            f'<div style="background:#ffffff; border-radius:10px; padding:10px; box-sizing:border-box;">{render_diagram_svg(_psch)}</div>',
            height=int(_psch.height * 1.1) + 40, scrolling=True)

    if st.button("ENGAGE DIAGNOSTIC SYSTEM →", use_container_width=True):
        st.session_state.page = "Testing Dashboard"
        st.rerun()

# ------------------------------------------------------------------------------
# STEP 5: TESTING DASHBOARD (AUTOMATIC 1-SECOND LIVE TELEMETRY REFRESH)
# ------------------------------------------------------------------------------
elif st.session_state.page == "Testing Dashboard":
    if curr_circuit is None:
        render_no_selection_message("Testing Dashboard")
        st.stop()
    if route_for(st.session_state.selected_category, st.session_state.selected_circuit) == "Digital Circuit Tester":
        st.session_state.page = "Digital Circuit Tester"
        st.rerun()
    render_selection_banner(st.session_state.selected_category, st.session_state.selected_circuit,
                            curr_circuit, "ELECTRICAL TESTING DASHBOARD")
    with st.expander("📘 Circuit details: components, expected values, probe instructions", expanded=False):
        st.markdown(f"**Components:** {curr_circuit.get('components', 'N/A')}")
        st.markdown(f"**Schematic:** `{curr_circuit.get('diagram', 'N/A')}`")
        st.markdown(f"**Expected (nominal):** Vin {curr_circuit.get('exp_input_v')} V · Iin {curr_circuit.get('exp_input_i')} A · "
                    f"Vout {curr_circuit.get('exp_output_v')} V · Iout {curr_circuit.get('exp_output_i')} A · "
                    f"Efficiency {curr_circuit.get('exp_eff')} % · Ripple {curr_circuit.get('exp_ripple')} %")
        for _p in curr_circuit.get("probes", []):
            st.markdown(f"- **Probe {_p['step']} - {_p['name']}:** {_p['loc']}")
        _sch = build_analog_schematic(st.session_state.selected_circuit)
        if _sch is not None:
            st.markdown("**Circuit schematic with probe positions P1-P3** (standard configuration; physical wiring is not verified by NEXUS)")
            st.components.v1.html(
                f'<div style="background:#ffffff; border-radius:10px; padding:10px; box-sizing:border-box;">{render_diagram_svg(_sch)}</div>',
                height=int(_sch.height * 1.1) + 40, scrolling=True)
    st.header(f"📊 LIVE AI OS DIAGNOSTIC MATRIX - {st.session_state.selected_circuit}")
    st.caption(f"Hardware Topology Specs: {curr_circuit.get('components', 'N/A')}")
    
    active_targets = get_active_targets(curr_circuit)
    
    st.info(f"🎯 **ACTIVE USER TARGETS**: Input: **{active_targets['target_input_voltage']} V / {active_targets['target_input_current']} A** | Output: **{active_targets['target_output_voltage']} V / {active_targets['target_output_current']} A**")

    st.markdown("""
    <div class="pipeline-flow">
        <div class="node-box">CIRCUIT</div>
        <div class="pipe-connector"></div>
        <div class="node-box">ESP32</div>
        <div class="pipe-connector"></div>
        <div class="node-box">MQTT</div>
        <div class="pipe-connector"></div>
        <div class="node-box">STREAMLIT</div>
        <div class="pipe-connector"></div>
        <div class="node-box">GEMINI AI</div>
        <div class="pipe-connector"></div>
        <div class="node-box" style="border-color:#00ff87; color:#00ff87;">DIAGNOSIS</div>
    </div>
    """, unsafe_allow_html=True)

    if is_data_held() and st.session_state.held_input_data.get("circuit") != st.session_state.selected_circuit:
        release_testing_data()

    held_now = is_data_held()
    with st.container(border=True):
        st.markdown('<div style="text-align:center; font-family:Orbitron, sans-serif; color:#00f2fe; letter-spacing:2px; font-weight:700; margin-bottom:8px;">TEST ACQUISITION CONTROL</div>', unsafe_allow_html=True)
        ctl1, ctl2, ctl3 = st.columns(3)
        with ctl1:
            st.button("⏸ HOLD", key="hold_data_btn", on_click=hold_testing_data, disabled=held_now, use_container_width=True)
        with ctl2:
            st.button("▶ RELEASE", key="release_data_btn", on_click=release_testing_data, disabled=not held_now, use_container_width=True)
        with ctl3:
            analyze_clicked = st.button("🤖 ANALYZE WITH GEMINI", key="analyze_gemini_btn", use_container_width=True)

        if held_now:
            cap_str = st.session_state.hold_timestamp.strftime("%H:%M:%S") if st.session_state.hold_timestamp else "—"
            st.markdown(f'<div style="text-align:center; font-family:Orbitron, sans-serif;"><span style="color:#ffb703; font-weight:700;">STATUS: INPUT V/I HELD</span><br><span style="color:#c8d6e5; font-size:0.85rem;">CAPTURED: {cap_str} | OUTPUT LIVE</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="text-align:center; font-family:Orbitron, sans-serif;"><span style="color:#00ff87; font-weight:700;">STATUS: LIVE</span></div>', unsafe_allow_html=True)

    if st.session_state.get("hold_error"):
        st.warning(st.session_state.hold_error)

    @st.fragment(run_every="1s")
    def render_live_testing_dashboard():
        sensor_data = get_testing_sensor_data(curr_circuit)
        data_is_held = sensor_data["source"] == "HELD"
        frozen_note = ' | <span style="color:#ffb703;">❄ INPUT V/I FROZEN — OUTPUT LIVE — MQTT STILL RECEIVING</span>' if data_is_held else ''
        sensor_status, _ = evaluate_pass_fail_status(active_targets, sensor_data)

        last_time_str = datetime.datetime.now().strftime("%H:%M:%S")
        st.markdown(f"""
        <div style="text-align: right; font-family: 'Orbitron', sans-serif; font-size: 0.75rem; color: #00f2fe; margin-bottom: 8px;">
            📡 LAST MQTT SYNC: <span style="color:#00ff87;">{last_time_str}</span> | PACKETS PROCESSED: <span style="color:#00ff87;">{get_mqtt_packet_count()}</span>{frozen_note}
        </div>
        """, unsafe_allow_html=True)

        st.subheader("📡 SENSOR ACQUISITION METRICS")
        g1, g2, g3 = st.columns(3)
        with g1:
            st.plotly_chart(create_circular_gauge(("HELD " if data_is_held else "") + "Input Voltage", sensor_data['input_v'], max(30.0, active_targets['target_input_voltage'] * 1.5), "V", "#00f2fe"), use_container_width=True)
        with g2:
            st.plotly_chart(create_circular_gauge("Live Output Voltage", sensor_data['output_v'], max(30.0, active_targets['target_output_voltage'] * 1.5), "V", "#00ff87"), use_container_width=True)
        with g3:
            st.plotly_chart(create_circular_gauge("Circuit Health", sensor_data['health'], 100, "%", "#ff0055" if sensor_data['health'] < 80 else "#00ff87"), use_container_width=True)

        st.markdown('<div class="os-card">', unsafe_allow_html=True)
        col5, col6, col7, col8 = st.columns(4)
        col5.metric("HELD INPUT CURRENT" if data_is_held else "INPUT CURRENT", f"{sensor_data['input_i']:.3f} A")
        col6.metric("LIVE OUTPUT CURRENT", f"{sensor_data['output_i']:.3f} A")
        col7.metric("FREQUENCY", f"{sensor_data['frequency']:.1f} Hz")
        col8.metric("TEMPERATURE", f"{sensor_data['temperature']:.1f} °C")
        col9, col10, col11, col12 = st.columns(4)
        col9.metric("INPUT POWER", f"{sensor_data['power_in']:.2f} W")
        col10.metric("OUTPUT POWER", f"{sensor_data['power_out']:.2f} W")
        col11.metric("VOLTAGE DROP", f"{sensor_data['v_drop']:.2f} V")
        col12.metric("TEST RESULT", sensor_status)
        st.markdown('</div>', unsafe_allow_html=True)

        render_nexus_telemetry(sensor_data)

    render_live_testing_dashboard()

    mqtt_status = get_mqtt_status()
    latest_packet = get_latest_sensor_packet()
    valid_mqtt_data = latest_packet is not None
    data_available = valid_mqtt_data or is_data_held()

    st.markdown("---")
    st.subheader("🤖 GEMINI AI DIAGNOSIS ENGINE")

    if analyze_clicked:
        run_gemini_analysis(curr_circuit, active_targets)

    _notice = st.session_state.get("gemini_notice")
    if _notice:
        st.error(_notice[1])
    if st.session_state.get("gemini_pending"):
        render_gemini_pending()   # background job: live telemetry above keeps refreshing

    _last = st.session_state.last_gemini_result
    if _last is not None and _last.get("circuit") == st.session_state.selected_circuit:
        render_analysis_result(_last)
        _sp = st.session_state.pop("pending_speech", None)
        if _sp:
            speak_text(_sp)
    elif not data_available:
        st.info("No valid sensor data available for analysis. Waiting for ESP32 telemetry.")
    else:
        st.caption("Press ⏸ HOLD to freeze Input V/I only (optional), then 🤖 ANALYZE WITH GEMINI.")

    st.markdown("---")
    st.subheader("💬 GEMINI AI OS COPILOT TERMINAL")
    
    user_query = st.text_input("INPUT DIRECTIVE FOR GEMINI AI:", placeholder="e.g., Explain causes for voltage degradation on diode branch", key="dashboard_gemini_query")
    
    if st.button("EXECUTE DIRECTIVE", key="dashboard_ask_btn"):
        if user_query.strip():
            client = get_gemini_client()
            if client:
                try:
                    with st.spinner("Processing neural query..."):
                        sensor_data_snapshot = get_testing_sensor_data(curr_circuit) if data_available else {}
                        context_prompt = f"""
                        Circuit Name: {st.session_state.selected_circuit}
                        Active User Targets: {active_targets}
                        Sensor Telemetry (source: {sensor_data_snapshot.get('source', 'N/A')}): {sensor_data_snapshot}
                        MQTT Status: {mqtt_status}
                        
                        User Question: {user_query}
                        
                        Provide a concise, expert engineering response comparing measurements to active target specs.
                        """
                        response = client.models.generate_content(
                            model=GEMINI_MODEL_NAME,
                            contents=context_prompt
                        )
                        answer = response.text

                        gemini_status_snapshot = None
                        try:
                            if data_available:
                                gemini_status_snapshot, _ = evaluate_pass_fail_status(active_targets, sensor_data_snapshot)
                        except Exception:
                            gemini_status_snapshot = None
                        save_gemini_to_history(
                            st.session_state.selected_circuit,
                            user_query,
                            answer,
                            metrics=sensor_data_snapshot,
                            status=gemini_status_snapshot
                        )

                        st.markdown(f"""
                        <div class="os-card" style="border-left: 4px solid #9d4edd !important;">
                            <h4 style="color:#9d4edd !important;">🤖 GEMINI AI RESPONSE:</h4>
                            <div>{html.escape(str(answer))}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        speak_text(answer)

                except Exception as e:
                    st.error(f"Error querying Gemini API: {e}")
            else:
                st.warning("⚠️ Gemini API Key missing. Please set key in Settings tab.")

# ------------------------------------------------------------------------------
# STEP 6: DIGITAL CIRCUIT TESTER MODULE
# ------------------------------------------------------------------------------
elif st.session_state.page == "Digital Circuit Tester":
    st.header("🔬 NEXUS DIGITAL CIRCUITS TESTING MODULE")
    st.caption("Verify logic gates, code converters, arithmetic circuits, and the mandatory 2:1 multiplexer using live single-voltage sensor telemetry.")

    digital_circuits_list = list(CIRCUIT_DATABASE["Digital Circuits"].keys())

    # Authoritative state -> widget. Nothing here ever overwrites the selection with index=0.
    if st.session_state.selected_category != "Digital Circuits" or \
            not is_valid_selection("Digital Circuits", st.session_state.selected_circuit):
        # Arrived (e.g. via the sidebar) while a non-digital circuit is selected: ask, don't substitute.
        _prev = st.session_state.get("selected_circuit")
        st.warning(f"The currently selected circuit ({st.session_state.get('selected_category')} → {_prev}) "
                   "is not a digital circuit. Choose a digital circuit below, or go back to Home.")
        st.session_state.pop("dig_ckt_select", None)
        st.selectbox("SELECT DIGITAL CIRCUIT", digital_circuits_list, index=None,
                     placeholder="Choose a digital circuit…", key="dig_ckt_select",
                     on_change=cb_digital_circuit_changed)
        st.button("← RETURN TO HOME", key="dig_no_sel_home", on_click=cb_go_home)
        st.stop()

    st.session_state["dig_ckt_select"] = st.session_state.selected_circuit
    st.selectbox("SELECT DIGITAL CIRCUIT", digital_circuits_list, key="dig_ckt_select",
                 on_change=cb_digital_circuit_changed)
    selected_dig_ckt = st.session_state.selected_circuit
    st.session_state.last_digital_circuit = selected_dig_ckt
    ckt_info = CIRCUIT_DATABASE["Digital Circuits"][selected_dig_ckt]

    render_selection_banner("Digital Circuits", selected_dig_ckt, ckt_info, "DIGITAL TESTING DASHBOARD")
    st.markdown(f"""
    <div class="os-card">
        <p><b>Schematic:</b> <code style="color:#00ff87; background:rgba(0,0,0,0.6); padding:4px 10px;">{ckt_info['diagram']}</code></p>
        <p><b>Inputs:</b> {", ".join(ckt_info.get("inputs", []))} &nbsp;|&nbsp; <b>Outputs:</b> {", ".join(ckt_info.get("outputs", []))}</p>
    </div>
    """, unsafe_allow_html=True)

    bit_width = 4
    if ckt_info.get("sub_type") in ["bin_to_gray", "gray_to_bin"]:
        bit_width = st.selectbox("Select Bit Width", [2, 3, 4], index=2, key="dig_bit_width_select")
        st.session_state.digital_bit_width = bit_width

    with st.expander("⚙️ Logic Voltage Threshold Configuration"):
        th_col1, th_col2 = st.columns(2)
        with th_col1:
            v_il = st.number_input("Max Voltage for Logic 0 (V_IL)", value=0.8, step=0.1, key="thresh_vil")
        with th_col2:
            v_ih = st.number_input("Min Voltage for Logic 1 (V_IH)", value=2.0, step=0.1, key="thresh_vih")
        st.session_state.digital_thresholds = {"v_il": v_il, "v_ih": v_ih}
    render_ic_context_inputs(selected_dig_ckt, ckt_info)

    @st.fragment(run_every="1s")
    def render_digital_live_sensor():
        packet, _ = get_latest_packet_and_time()
        live_v = None
        try:
            if packet is not None:
                live_v = float(packet.get("output_voltage", packet.get("output_v")))
                if not math.isfinite(live_v):
                    live_v = None
        except (TypeError, ValueError):
            live_v = None
        logic_state = classify_digital_voltage(live_v if live_v is not None else float("nan"), st.session_state.digital_thresholds["v_il"], st.session_state.digital_thresholds["v_ih"])
        
        live_v_txt = f"{live_v:.3f} V" if live_v is not None else "NO DATA"
        logic_txt = logic_state if live_v is not None else "—"
        state_color = "#00ff87" if logic_state == "1" else ("#00f2fe" if logic_state == "0" else "#ff0055")
        st.markdown(f"""
        <div class="os-card" style="border-left: 5px solid {state_color} !important; display: flex; justify-content: space-around; align-items: center; text-align: center;">
            <div>
                <div style="font-family: Orbitron; font-size: 0.75rem; color: #8fa3b8;">LATEST SENSOR VOLTAGE</div>
                <div style="font-family: Orbitron; font-size: 1.8rem; color: #ffffff;">{live_v_txt}</div>
            </div>
            <div>
                <div style="font-family: Orbitron; font-size: 0.75rem; color: #8fa3b8;">CLASSIFIED LOGIC STATE</div>
                <div style="font-family: Orbitron; font-size: 1.8rem; color: {state_color}; font-weight: 700;">{logic_txt}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return live_v, logic_state

    render_digital_live_sensor()
    expected_df = generate_expected_truth_table(selected_dig_ckt, width=st.session_state.digital_bit_width)
    input_cols, output_cols, possible_outputs = get_digital_table_layout(expected_df)

    # If the truth-table shape changed (e.g. converter bit width), previously saved cells
    # no longer describe the same rows/outputs -> clear only this circuit's test data.
    cur_sig = digital_table_signature(expected_df)
    prev_sig = st.session_state.digital_table_sigs.get(selected_dig_ckt)
    if prev_sig is not None and prev_sig != cur_sig:
        st.session_state.digital_measurements[selected_dig_ckt] = {}
        digital_invalidate_analysis(selected_dig_ckt)
        st.session_state.digital_selected_cells.pop(selected_dig_ckt, None)
        st.session_state.digital_save_notice.pop(selected_dig_ckt, None)
        st.warning("Truth-table size changed (bit width). Saved measurements for this circuit were cleared because they no longer match the table.")
    st.session_state.digital_table_sigs[selected_dig_ckt] = cur_sig

    st.markdown("### 🧩 Circuit Diagram / Logic Gate Diagram")
    try:
        _diag = build_logic_diagram(ckt_info.get("sub_type"), st.session_state.digital_bit_width)
        if _diag is None:
            st.warning(f"No logic diagram is defined for {selected_dig_ckt}.")
            st.code(ckt_info.get("diagram", ""), language=None)
        else:
            st.components.v1.html(
                f'<div style="background:#ffffff; border-radius:10px; padding:10px; box-sizing:border-box;">{render_diagram_svg(_diag)}</div>',
                height=int(_diag.height) + 40, scrolling=True)
            _exprs = get_digital_boolean_expressions(ckt_info.get("sub_type"), st.session_state.digital_bit_width)
            if _exprs:
                st.code("\n".join(_exprs), language=None)
    except Exception as _diag_err:
        st.warning(f"The circuit diagram could not be rendered ({_diag_err}). Schematic summary: {ckt_info.get('diagram', 'N/A')}")

    st.markdown("### 🔌 IC Pin Diagram and Wiring")
    try:
        render_ic_pin_section(ckt_info.get("sub_type"), st.session_state.digital_bit_width)
    except Exception as _ic_err:
        st.warning(f"The IC pin diagram could not be rendered ({_ic_err}).")

    st.markdown("### 📋 Expected Truth Table (Deterministic)")
    st.dataframe(expected_df, use_container_width=True)

    st.markdown("### 🎮 Interactive Measured Truth Table")
    st.info("Click any output cell in the grid below to select it as the save destination, then press **SAVE CELL** to store the live sensor voltage there. Cells can be measured in any order.")

    if selected_dig_ckt not in st.session_state.digital_measurements:
        st.session_state.digital_measurements[selected_dig_ckt] = {}
    ckt_meas = st.session_state.digital_measurements[selected_dig_ckt]

    # Active destination (kept in session state so it survives reruns)
    sel = st.session_state.digital_selected_cells.get(selected_dig_ckt)
    if sel is None or sel[0] >= len(expected_df) or sel[1] not in possible_outputs:
        sel = (0, possible_outputs[0])
        st.session_state.digital_selected_cells[selected_dig_ckt] = sel
    sel_row, sel_out = sel

    dest_slot = st.empty()
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        save_clicked = st.button("💾 SAVE CELL", key="dig_save_btn", use_container_width=True)
    with btn_col2:
        reset_clicked = st.button("🔄 RESET CURRENT DIGITAL TEST", key="dig_reset_btn", use_container_width=True)

    sel_inputs_txt = ", ".join(f"{c}={expected_df.iloc[sel_row][c]}" for c in input_cols)

    if save_clicked:
        # Read the live sensor NOW (never reuse a displayed/stale value, never fabricate 0 V).
        saved_v, saved_pkt_time, save_err = get_fresh_output_measurement()
        if save_err:
            st.session_state.digital_save_notice[selected_dig_ckt] = (
                "error", f"Cannot save to Row {sel_row}, Output '{sel_out}': {save_err} Nothing was saved.")
        else:
            th = st.session_state.digital_thresholds
            saved_state = classify_digital_voltage(saved_v, th["v_il"], th["v_ih"])
            # Only the selected cell is written; every other saved cell is left untouched.
            ckt_meas[(sel_row, sel_out)] = {
                "voltage": saved_v,
                "logic_state": saved_state,
                "timestamp": datetime.datetime.now(),
                "sensor_packet_time": saved_pkt_time,
            }
            # Test data changed -> any previous analysis/Gemini report is now out of date.
            digital_invalidate_analysis(selected_dig_ckt)
            level = "success" if saved_state in ("0", "1") else "warning"
            state_txt = f"Logic {saved_state}" if saved_state in ("0", "1") else "INVALID logic level (between V_IL and V_IH)"
            st.session_state.digital_save_notice[selected_dig_ckt] = (
                level, f"Saved {saved_v:.3f} V ({state_txt}) to Row {sel_row} [{sel_inputs_txt}], Output '{sel_out}'.")

    if reset_clicked:
        # Clears ONLY this circuit's digital measurements, selection and analysis.
        st.session_state.digital_measurements[selected_dig_ckt] = {}
        ckt_meas = st.session_state.digital_measurements[selected_dig_ckt]
        digital_invalidate_analysis(selected_dig_ckt)
        sel_row, sel_out = 0, possible_outputs[0]
        st.session_state.digital_selected_cells[selected_dig_ckt] = (sel_row, sel_out)
        sel_inputs_txt = ", ".join(f"{c}={expected_df.iloc[sel_row][c]}" for c in input_cols)
        st.session_state.digital_save_notice[selected_dig_ckt] = ("success", "Digital measurements for this circuit were reset.")

    notice = st.session_state.digital_save_notice.get(selected_dig_ckt)
    if notice:
        if notice[0] == "success":
            st.success(notice[1])
        elif notice[0] == "warning":
            st.warning(notice[1])
        else:
            st.error(notice[1])

    existing_m = ckt_meas.get((sel_row, sel_out))
    existing_txt = (f"currently saved: {existing_m['voltage']:.3f} V (state {existing_m['logic_state']}) - will be overwritten"
                    if existing_m is not None else "currently empty")
    dest_slot.markdown(f"""
    <div class="os-card" style="border-left: 5px solid #00f2fe !important;">
        <div style="font-family: Orbitron; font-size: 0.75rem; color: #8fa3b8;">ACTIVE SAVE DESTINATION</div>
        <div style="font-family: Orbitron; font-size: 1.1rem; color: #ffffff;">Row {sel_row} &nbsp;|&nbsp; {html.escape(sel_inputs_txt)} &nbsp;|&nbsp; Output <span style="color:#00ff87;">{html.escape(str(sel_out))}</span></div>
        <div style="color:#8fa3b8;">{html.escape(existing_txt)}</div>
    </div>
    """, unsafe_allow_html=True)

    # ---- Clickable measured truth-table grid (one button per output cell) ----
    grid_weights = [0.6] + [1.0] * len(input_cols) + [1.6] * len(possible_outputs)
    hdr_cols = st.columns(grid_weights)
    hdr_cols[0].markdown("**Row**")
    for ci, c in enumerate(input_cols):
        hdr_cols[1 + ci].markdown(f"**{c}**")
    for oi, out_l in enumerate(possible_outputs):
        hdr_cols[1 + len(input_cols) + oi].markdown(f"**{out_l} (measured)**")

    for i in range(len(expected_df)):
        row_cols = st.columns(grid_weights)
        row_cols[0].markdown(f"`{i}`")
        for ci, c in enumerate(input_cols):
            row_cols[1 + ci].markdown(f"`{expected_df.iloc[i][c]}`")
        for oi, out_l in enumerate(possible_outputs):
            m_info = ckt_meas.get((i, out_l))
            is_selected = (i == sel_row and out_l == sel_out)
            if m_info is not None:
                cell_label = f"{m_info['logic_state']} · {m_info['voltage']:.2f} V"
            else:
                cell_label = "—"
            if is_selected:
                cell_label = "🎯 " + cell_label
            row_cols[1 + len(input_cols) + oi].button(
                cell_label,
                key=f"dig_cell_{selected_dig_ckt}_{i}_{out_l}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
                on_click=digital_select_cell,
                args=(selected_dig_ckt, i, out_l),
            )

    st.caption("Measured values are shown here as saved. The PASS / FAIL / INCOMPLETE result is calculated only when you press ANALYSE DIGITAL CIRCUIT.")

    # ---- ANALYSE: the only place the deterministic result and Gemini report are produced ----
    analyse_clicked = st.button("🤖 ANALYSE DIGITAL CIRCUIT", key="dig_gemini_btn", use_container_width=True)

    if analyse_clicked:
        result = compute_digital_analysis(selected_dig_ckt, expected_df, dict(ckt_meas))
        # Everything the student report needs is frozen into this analysis (exact test, circuit, table and cells).
        result["test_id"] = new_test_id(result["analysed_at"])
        result["circuit_info"] = {k: ckt_info.get(k) for k in ("type", "sub_type", "description", "diagram")}
        result["expected_rows"] = expected_df.to_dict(orient="records")
        result["bit_width"] = st.session_state.digital_bit_width
        result["measurements_snapshot"] = copy.deepcopy(dict(ckt_meas))
        ic_ctx = dict(st.session_state.digital_ic_context.get(selected_dig_ckt, {}))
        result["ic_context"] = ic_ctx
        try:
            result["ic_assessment"] = compute_ic_assessment(ckt_info.get("sub_type"), st.session_state.digital_bit_width, result, ic_ctx)
        except Exception as _ic_exc:
            result["ic_assessment"] = {"available": False, "reason": f"IC assessment could not be computed ({_ic_exc}).", "ics": []}
        knowledge = get_circuit_knowledge("Digital Circuits", selected_dig_ckt, st.session_state.digital_bit_width)
        client = get_gemini_client()
        if not client:
            result["gemini_status"] = "NO_KEY"
            result["gemini_error"] = "Gemini API key missing. Configure the key in the Settings tab to get an engineering diagnosis."
        else:
            dataset = build_digital_dataset(selected_dig_ckt, ckt_info, expected_df, ckt_meas, result, input_cols, possible_outputs)
            prompt = build_digital_prompt(dataset, result, result["ic_assessment"], knowledge)
            _an = {"det_status": result["det_status"], "coverage_pct": result["coverage_pct"]}
            _ica = copy.deepcopy(result["ic_assessment"])
            result["gemini_status"] = "PENDING"
            job_id = start_gemini_job(client, prompt, lambda t, a=_an, i=_ica: parse_digital_json(t, a, i) is not None)
            st.session_state.digital_pending = {"job_id": job_id, "test_id": result["test_id"], "circuit": selected_dig_ckt, "started": time.time()}
        st.session_state.digital_analysis[selected_dig_ckt] = result
        st.session_state.analysis_records.append({
            "test_id": result["test_id"], "kind": "digital", "circuit": selected_dig_ckt,
            "category": "Digital Circuits", "timestamp": result["analysed_at"], "result": copy.deepcopy(result),
        })
        st.session_state.report_selected_test = result["test_id"]

    if st.session_state.get("digital_pending"):
        render_digital_pending()   # background job: the live sensor card keeps refreshing

    # ---- Persisted analysis display (current circuit + current table only) ----
    analysis = st.session_state.digital_analysis.get(selected_dig_ckt)
    if analysis is not None and analysis.get("signature") != cur_sig:
        digital_invalidate_analysis(selected_dig_ckt)
        analysis = None

    if analysis is not None:
        det_status = analysis["det_status"]
        status_color = "#00ff87" if det_status == "PASS" else ("#ff0055" if det_status == "FAIL" else "#ffb703")
        st.markdown(f"""
        <div class="os-card" style="border-left: 5px solid {status_color} !important;">
            <h4 style="color:{status_color}; margin-top:0;">DETERMINISTIC TEST RESULT: {det_status}</h4>
            <p><b>Measurement Coverage:</b> {analysis['coverage_pct']:.1f}% ({analysis['valid_cells']}/{analysis['total_cells']} valid required cells)</p>
            <p style="color:#8fa3b8;">Analysed at {analysis['analysed_at'].strftime('%Y-%m-%d %H:%M:%S')} using V_IL={analysis['thresholds']['v_il']} V, V_IH={analysis['thresholds']['v_ih']} V. Saving or overwriting any cell invalidates this result.</p>
        </div>
        """, unsafe_allow_html=True)

        mt1, mt2, mt3, mt4 = st.columns(4)
        mt1.metric("Deterministic Result", det_status)
        mt2.metric("Measurement Coverage", f"{analysis['coverage_pct']:.1f}%")
        mt3.metric("Total Required Output Cells", analysis["total_cells"])
        mt4.metric("Valid Measured Cells", analysis["valid_cells"])
        mt5, mt6, mt7, mt8 = st.columns(4)
        mt5.metric("Correct Matches", analysis["correct_matches"])
        mt6.metric("Mismatches", analysis["mismatches"])
        mt7.metric("Missing Cells", analysis["missing_cells"])
        mt8.metric("Invalid Logic Levels", analysis["invalid_cells"])

        if analysis.get("cells"):
            with st.expander("📊 Truth table results: expected vs measured (MATCH / MISMATCH / INVALID / MISSING)", expanded=True):
                _cells_df = pd.DataFrame(analysis["cells"]).rename(columns={
                    "row": "Row", "inputs": "Inputs", "output": "Output", "expected": "Expected",
                    "voltage": "Measured V", "state": "Measured State", "status": "Result"})
                st.dataframe(_cells_df, use_container_width=True)
        if analysis["details"]:
            with st.expander(f"Cells needing attention ({len(analysis['details'])})"):
                st.dataframe(pd.DataFrame(analysis["details"]), use_container_width=True)

        _off = build_offline_digital_diagnosis(analysis)
        st.markdown("### 🧮 Offline Digital Diagnosis (local - works without Gemini)")
        _find_html = "".join(f"<li>{html.escape(x)}</li>" for x in _off["findings"])
        _act_html = "".join(f"<li>{html.escape(x)}</li>" for x in _off["actions"])
        _lim_html = " ".join(html.escape(x) for x in _off["limitations"])
        st.markdown(f"""
        <div class="os-card" style="border-left: 5px solid #9d4edd !important;">
            <p><b>{html.escape(_off['summary'])}</b></p>
            <ul style="color:#c8d6e5;">{_find_html}</ul>
            <p style="margin-bottom:2px;"><b>Suggested actions</b></p>
            <ul style="color:#c8d6e5;">{_act_html}</ul>
            <p style="color:#8fa3b8; font-size:0.85rem;">{_lim_html}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🔌 IC Health Assessment (evidence-based)")
        render_ic_assessment_cards(analysis.get("ic_assessment"), (analysis.get("gemini_structured") or {}).get("ic_assessments"))

        st.markdown("### 🤖 Gemini Digital Diagnostic Report")
        _gs = analysis["gemini_status"]
        _gst = analysis.get("gemini_structured")
        if _gs == "PENDING":
            st.info("⏳ Gemini is analysing the frozen truth-table snapshot. The deterministic result and IC assessment above are already final.")
        elif _gs == "OK" and _gst:
            _cc = _COND_COLORS.get(_gst["circuit_condition"], "#9d4edd")
            st.markdown(f"""
            <div class="os-card" style="border-left: 5px solid {_cc} !important;">
                <div style="font-family:Orbitron,sans-serif; color:#00f2fe; letter-spacing:2px; font-weight:700;">NEXUS AI DIGITAL DIAGNOSIS</div>
                {_bar_html("FAULT PROBABILITY - chance a fault exists (estimate)", _gst.get("fault_probability"), "#ff6b35")}
                {_bar_html("DIAGNOSIS CONFIDENCE (estimate)", _gst.get("overall_circuit_diagnosis_probability"), "#9d4edd")}
                {_bar_html("CONFIDENCE IN RECOMMENDED PROCEDURE (estimate)", _gst.get("overall_circuit_guide_probability"), "#00f2fe")}
                <div style="margin-top:10px; font-family:Orbitron,sans-serif;">CONDITION: <span style="color:{_cc}; font-weight:700;">{html.escape(_gst["circuit_condition"])}</span></div>
                <div style="margin-top:8px;"><b>RESPONSIBLE SECTION:</b> <span style="color:#c8d6e5;">{html.escape(_gst["responsible_section"])}</span></div>
                <div style="margin-top:8px;"><b>MATCHING ROWS:</b> <span style="color:#c8d6e5;">{html.escape(_gst["matching_rows_summary"] or "N/A")}</span></div>
                <div style="margin-top:8px;"><b>MISSING / INVALID:</b> <span style="color:#c8d6e5;">{html.escape(_gst["missing_or_invalid_summary"] or "N/A")}</span></div>
            </div>""", unsafe_allow_html=True)
            if _gst["mismatch_analysis"]:
                with st.expander(f"Mismatching / invalid cells - AI analysis ({len(_gst['mismatch_analysis'])})", expanded=True):
                    st.dataframe(pd.DataFrame([{"Row": m["row"], "Inputs": m["inputs"], "Output": m["output"], "Expected": m["expected"],
                                                "Measured": m["measured_state"], "Observation": m["observation"],
                                                "Possible causes (hypotheses)": "; ".join(m["possible_causes"])} for m in _gst["mismatch_analysis"]]),
                                 use_container_width=True, hide_index=True)
            st.markdown("**Troubleshooting (pin by pin)**")
            for _i, _x in enumerate(_gst["recommended_steps"], 1):
                st.markdown(f"{_i}. {html.escape(_x)}")
            render_lab_assistant_cards(_gst, "digital")
            with st.expander("📋 FULL TEXT REPORT (as saved to the PDF report)"):
                st.markdown(f"<pre style='white-space: pre-wrap; font-family: Rajdhani, sans-serif; color: #c8d6e5;'>{html.escape(analysis['gemini_report'] or '')}</pre>", unsafe_allow_html=True)
        elif _gs == "OK" and analysis["gemini_report"]:
            st.warning("Gemini did not return valid structured JSON - showing its raw text, unvalidated. Press ANALYSE DIGITAL CIRCUIT to retry.")
            safe_report = html.escape(analysis["gemini_report"])
            st.markdown(f"""<div class="os-card"><pre style="white-space: pre-wrap; font-family: Rajdhani; color: #c8d6e5;">{safe_report}</pre></div>""", unsafe_allow_html=True)
        elif _gs == "NO_KEY":
            st.warning(f"⚠️ {analysis['gemini_error']} The deterministic result above is still valid.")
        elif _gs == "ERROR":
            st.error(f"{analysis['gemini_error']} The deterministic result above is still valid.")
        _sp = st.session_state.pop("pending_speech", None)
        if _sp:
            speak_text(_sp)
        if st.button("📑 CREATE STUDENT TEST REPORT FROM THIS TEST →", key="dig_goto_report_btn", use_container_width=True):
            st.session_state.report_selected_test = analysis.get("test_id")
            st.session_state.page = "Generate Report"
            st.rerun()


# ------------------------------------------------------------------------------
# GENERATE REPORT PAGE (student details, PDF generation, download)
# ------------------------------------------------------------------------------
elif st.session_state.page == "Generate Report":
    st.header("📑 GENERATE TEST REPORT")
    st.caption("Create a professional PDF report from a completed NEXUS test, and download it.")

    sd = st.session_state.student_details
    records = list(reversed(st.session_state.analysis_records))

    # ---- 1. choose the exact test record -------------------------------------
    st.markdown("### 🧪 Select Completed Test")
    selected_rec = None
    if not records:
        st.info("No completed test is available yet. Run a test first: **Testing Dashboard → ANALYZE WITH GEMINI** "
                "(rectifier / analogue circuits) or **Digital Circuit Tester → ANALYSE DIGITAL CIRCUIT** (digital circuits). "
                "Then return here to generate the report.")
    else:
        rec_ids = [r["test_id"] for r in records]
        rec_by_id = {r["test_id"]: r for r in records}

        def _rec_label(tid):
            r = rec_by_id[tid]
            res_status = r["result"]["det_status"] if r["kind"] == "digital" else r["result"]["status"]
            return f"{tid} | {r['circuit']} | {r['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} | {res_status}"
        prev_sel = st.session_state.report_selected_test
        sel_index = rec_ids.index(prev_sel) if prev_sel in rec_ids else 0
        chosen_id = st.selectbox("Test record (circuit | date/time | result)", rec_ids, index=sel_index,
                                 format_func=_rec_label, key="rep_test_select")
        st.session_state.report_selected_test = chosen_id
        selected_rec = rec_by_id[chosen_id]
        rr = selected_rec["result"]
        r_status = rr["det_status"] if selected_rec["kind"] == "digital" else rr["status"]
        r_color = "#00ff87" if r_status in ("PASS", "NORMAL") else ("#ff0055" if r_status == "FAIL" else "#ffb703")
        st.markdown(f"""
        <div class="os-card" style="border-left: 5px solid {r_color} !important;">
            <b>{html.escape(selected_rec['circuit'])}</b> ({html.escape(selected_rec['category'])}) &nbsp;|&nbsp;
            Test ID <code>{html.escape(chosen_id)}</code> &nbsp;|&nbsp;
            {selected_rec['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
            Result: <b style="color:{r_color};">{html.escape(str(r_status))}</b>
        </div>
        """, unsafe_allow_html=True)
        if selected_rec["kind"] == "digital":
            cur_snapshot = st.session_state.digital_measurements.get(selected_rec["circuit"], {})
            if cur_snapshot != rr.get("measurements_snapshot", {}):
                st.warning("The saved measurements for this circuit have changed since this analysis. The report will use the "
                           "analysed snapshot of this test record. Re-run ANALYSE on the Digital Circuit Tester page to report the newer measurements.")

    # ---- 2. student details -----------------------------------------------------
    st.markdown("### 🎓 Student Details & Report Generation")

    def _mark_attempted():
        st.session_state.report_validate_attempted = True

    def _field_error(field, value_present):
        msg = rep_errors.get(field)
        if msg and (st.session_state.report_validate_attempted or value_present):
            st.markdown(f'<span style="color:#ff4b4b; font-size:0.9rem;">⚠ {html.escape(msg)}</span>', unsafe_allow_html=True)

    f_col1, f_col2 = st.columns(2)
    with f_col1:
        in_name = st.text_input("Student Name *", value=sd.get("name", ""), key="rep_name", max_chars=80)
        name_slot = st.empty()
        year_opts = ["— Select year —"] + REPORT_YEAR_OPTIONS
        year_idx = year_opts.index(sd["year"]) if sd.get("year") in year_opts else 0
        in_year = st.selectbox("Year / Academic Year *", year_opts, index=year_idx, key="rep_year")
        in_year_other = sd.get("year_other", "")
        if in_year.startswith("Other"):
            in_year_other = st.text_input("Type academic year (e.g. 2025-26) *", value=sd.get("year_other", ""), key="rep_year_other", max_chars=40)
        year_slot = st.empty()
    with f_col2:
        in_div = st.text_input("Division *", value=sd.get("division", ""), key="rep_division", max_chars=10, help="For example A, B or C")
        div_slot = st.empty()
    with st.expander("Optional details (roll number, college, branch, report title)"):
        o1, o2 = st.columns(2)
        with o1:
            in_roll = st.text_input("Roll number", value=sd.get("roll_no", ""), key="rep_roll", max_chars=40)
            in_branch = st.text_input("Branch", value=sd.get("branch", ""), key="rep_branch", max_chars=80)
        with o2:
            in_college = st.text_input("College name", value=sd.get("college", ""), key="rep_college", max_chars=120)
            in_title = st.text_input("Report title", value=sd.get("report_title", ""), key="rep_title", max_chars=120)

    # keep the entered details across reruns / page changes
    sd.update({"name": in_name, "year": in_year, "year_other": in_year_other, "division": in_div,
               "roll_no": in_roll, "college": in_college, "branch": in_branch, "report_title": in_title})
    rep_clean, rep_errors = validate_student_details(sd)

    with name_slot.container():
        _field_error("name", bool(in_name.strip()))
    with year_slot.container():
        _field_error("year", bool(in_year_other.strip()) if in_year.startswith("Other") else False)
    with div_slot.container():
        _field_error("division", bool(in_div.strip()))

    # ---- 3. generate -------------------------------------------------------------
    gen_clicked = st.button("📄 Generate PDF Report", key="rep_gen_btn", use_container_width=True,
                            disabled=(selected_rec is None), on_click=_mark_attempted)
    if gen_clicked:
        if rep_errors:
            st.error("Please correct the highlighted student details before generating the report.")
        elif selected_rec is None:
            st.error("No completed test is selected.")
        else:
            try:
                gen_at = datetime.datetime.now()
                with st.spinner("Generating PDF report..."):
                    report_data = build_report_data(selected_rec, rep_clean, gen_at)
                    pdf_bytes = generate_test_report_pdf(report_data)
                if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
                    raise ValueError("The PDF generator returned no valid PDF data.")
                st.session_state.report_state = {
                    "pdf_bytes": pdf_bytes,
                    "filename": build_report_filename(rep_clean["name"], selected_rec["circuit"], gen_at),
                    "revision_key": report_revision_key(rep_clean, selected_rec),
                    "test_id": selected_rec["test_id"], "circuit": selected_rec["circuit"],
                    "student": dict(rep_clean), "generated_at": gen_at, "data": report_data,
                }
            except Exception as exc:
                st.session_state.report_state = None
                st.error(f"PDF generation failed: {exc}")

    # ---- 4. status and download ---------------------------------------------
    rs = st.session_state.report_state
    if rs is not None:
        cur_key = report_revision_key(rep_clean, selected_rec) if (selected_rec is not None and not rep_errors) else None
        if rs["revision_key"] != cur_key:
            st.warning(f"A report was generated earlier for **{html.escape(rs['circuit'])}** (Test ID {rs['test_id']}), but the student details or "
                       f"selected test have changed since. Press **Generate PDF Report** again to download an up-to-date report.")
        else:
            rd = rs["data"]
            st.success(f"PDF report generated at {rs['generated_at'].strftime('%H:%M:%S')} - ready to download.")
            st.markdown(f"""
            <div class="os-card" style="border-left: 5px solid #00f2fe !important;">
                <b>REPORT SUMMARY</b><br>
                <b>File:</b> {html.escape(rs['filename'])} ({len(rs['pdf_bytes']) / 1024:.1f} KB)<br>
                <b>Student:</b> {html.escape(rs['student']['name'])} | {html.escape(rs['student']['year'])} | Division {html.escape(rs['student']['division'])}<br>
                <b>Circuit:</b> {html.escape(rs['circuit'])} | <b>Test ID:</b> {html.escape(rs['test_id'])}<br>
                <b>Gemini section:</b> {html.escape(rd['gemini']['status'])} &nbsp;|&nbsp;
                <b>Contents:</b> cover &amp; student details, {'logic diagram, IC pin diagrams, truth tables, IC health assessment, AI lab analysis, teaching notes' if rd['kind'] == 'digital' else 'circuit schematic, expected vs measured parameters, calculations, AI lab analysis, teaching notes'}, recommendations, conclusion
            </div>
            """, unsafe_allow_html=True)
            for line in report_summary_lines(rd):
                st.markdown(f"- {line}")

            st.download_button("⬇️ Download Test Report", data=rs["pdf_bytes"], file_name=rs["filename"],
                               mime="application/pdf", key="rep_download_btn", use_container_width=True)

# ------------------------------------------------------------------------------
# STEP 7: HISTORY PAGE
# ------------------------------------------------------------------------------
elif st.session_state.page == "History":
    st.header("📜 MISSION LOG ARCHIVE & TELEMETRY DATABASE")
    
    if not st.session_state.historical_tests:
        st.info("No saved telemetry records found in mission archive.")
    else:
        top_c1, top_c2 = st.columns([3, 1])
        with top_c2:
            if st.button("🗑️ PURGE ARCHIVE", use_container_width=True):
                st.session_state.historical_tests = []
                st.rerun()

        df_history = pd.DataFrame(st.session_state.historical_tests)
        st.dataframe(df_history, use_container_width=True)

        st.markdown("### 🔍 LOG ENTRY BREAKDOWN")
        for idx, record in enumerate(reversed(st.session_state.historical_tests)):
            actual_index = len(st.session_state.historical_tests) - 1 - idx
            with st.expander(f"📌 [{record['Date']} {record['Time']}] {record['Circuit']} - Status: {record['Status']}"):
                st.markdown(f"**Circuit Type:** {record['Circuit']}")
                st.markdown(f"**Input Voltage:** {record['Input Voltage (V)']}")
                st.markdown(f"**Output Voltage:** {record['Output Voltage (V)']}")
                st.markdown(f"**Efficiency:** {record['Efficiency %']}")
                st.markdown(f"**Status:** {record['Status']}")
                st.markdown(f"**AI Response / Diagnosis:**")
                st.info(record['AI Answer / Diagnosis'])

                pdf_bytes = generate_history_pdf(record)
                pdf_file_name = f"NEXUS_Report_{record.get('Date', 'NA')}_{str(record.get('Time', 'NA')).replace(':', '-')}.pdf"
                st.download_button(
                    label="📄 CREATE PDF",
                    data=pdf_bytes,
                    file_name=pdf_file_name,
                    mime="application/pdf",
                    key=f"pdf_{actual_index}"
                )

                if st.button(f"Delete Record #{actual_index + 1}", key=f"del_{actual_index}"):
                    st.session_state.historical_tests.pop(actual_index)
                    st.success("Record purged.")
                    st.rerun()

# ------------------------------------------------------------------------------
# SETTINGS & ABOUT
# ------------------------------------------------------------------------------
elif st.session_state.page == "Settings":
    st.header("🛠️ OS SYSTEM SETTINGS")
    st.markdown('<div class="os-card">', unsafe_allow_html=True)
    st.session_state.api_key = st.text_input("GEMINI API KEY", value=st.session_state.api_key, type="password", help="Add your Gemini API Key here to enable AI features.")
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == "About":
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

    .about-heading {
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 800 !important;
        background: linear-gradient(90deg, #00f2fe 0%, #00ff87 50%, #7928ca 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 2px !important;
        text-transform: uppercase;
        margin-bottom: 12px !important;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .about-card {
        background: rgba(6, 12, 26, 0.65) !important;
        backdrop-filter: blur(25px) saturate(200%) !important;
        -webkit-backdrop-filter: blur(25px) saturate(200%) !important;
        border: 1px solid rgba(0, 242, 254, 0.25) !important;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.8), inset 0 0 15px rgba(0, 242, 254, 0.05) !important;
        border-radius: 14px !important;
        padding: 24px !important;
        margin-bottom: 24px !important;
        position: relative;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
    }

    .about-card:hover {
        transform: translateY(-5px) scale(1.01);
        border-color: rgba(0, 242, 254, 0.6) !important;
        box-shadow: 0 15px 35px -5px rgba(0, 242, 254, 0.35), inset 0 0 20px rgba(0, 242, 254, 0.2) !important;
    }

    .about-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 100%; height: 2px;
        background: linear-gradient(90deg, #00f2fe, #00ff87, #7928ca, #00f2fe);
        background-size: 300% 100%;
        animation: borderGlow 4s linear infinite;
    }

    @keyframes borderGlow {
        0% { background-position: 0% 0%; }
        100% { background-position: 300% 0%; }
    }

    .team-card {
        background: rgba(10, 18, 38, 0.75);
        border: 1px solid rgba(0, 255, 135, 0.3);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 0 15px rgba(0, 255, 135, 0.1);
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        overflow: hidden;
    }

    .team-card:hover {
        transform: translateY(-8px) scale(1.03);
        border-color: #00ff87;
        box-shadow: 0 0 25px rgba(0, 255, 135, 0.4);
    }

    .team-avatar {
        font-size: 2.2rem;
        margin-bottom: 8px;
    }

    .team-name {
        font-family: 'Orbitron', sans-serif;
        font-size: 1.15rem;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: 1px;
    }

    .team-role {
        font-size: 0.85rem;
        color: #00f2fe;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
        text-transform: uppercase;
        margin-top: 4px;
    }

    .tech-pill {
        display: inline-block;
        background: rgba(0, 242, 254, 0.08);
        border: 1px solid rgba(0, 242, 254, 0.3);
        color: #00f2fe;
        padding: 8px 16px;
        border-radius: 20px;
        font-family: 'Orbitron', sans-serif;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 5px;
        box-shadow: 0 0 10px rgba(0, 242, 254, 0.1);
        transition: all 0.3s ease;
    }

    .tech-pill:hover {
        background: rgba(0, 242, 254, 0.25);
        border-color: #00f2fe;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.5);
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
        <h2 class="about-heading">⚡ AI-Based Electronic & Digital Circuit Tester</h2>
        <p style="font-size: 1.1rem; line-height: 1.6; color: #c8d6e5; margin-top: 10px;">
            An intelligent AI-powered electronic and digital circuit diagnostic platform developed as a <b>Final Year B.Tech Project</b>. 
            The system combines <b>ESP32 hardware</b>, <b>MQTT communication</b>, <b>Streamlit dashboard</b>, and <b>Google Gemini AI</b> 
            to analyze both power rectifiers and digital logic circuits in real time.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
        <h2 class="about-heading">⭐ TEAM: Achiver's ⭐</h2>
        <div style="margin-top: 20px;">
    """, unsafe_allow_html=True)

    t_col1, t_col2, t_col3, t_col4 = st.columns(4)

    team_members = [
        {"name": "Joshi Samarth", "role": "Hardware & Embedded Systems"},
        {"name": "Kamate Sumit", "role": "Full Stack & System Architect"},
        {"name": "Yedave Ganesh", "role": "AI Integration & Telemetry"},
        {"name": "Kale Krishna", "role": "IoT & Cloud Communications"}
    ]

    cols = [t_col1, t_col2, t_col3, t_col4]

    for idx, member in enumerate(team_members):
        with cols[idx]:
            st.markdown(f"""
            <div class="team-card">
                <div class="team-avatar">👨‍💻</div>
                <div class="team-name">{member['name']}</div>
                <div class="team-role">{member['role']}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)

    technologies = [
        "Python", "Streamlit", "ESP32", "MQTT", 
        "Google Gemini AI", "NumPy", "Pandas", 
        "Plotly", "JSON", "HTML", "CSS"
    ]

    tech_html = "".join([f'<span class="tech-pill">🔹 {tech}</span>' for tech in technologies])

    st.markdown(f"""
    <div class="about-card">
        <h2 class="about-heading">🛠️ TECHNOLOGIES USED</h2>
        <div style="margin-top: 15px; display: flex; flex-wrap: wrap; gap: 4px;">
            {tech_html}
        </div>
    </div>
    """, unsafe_allow_html=True)
