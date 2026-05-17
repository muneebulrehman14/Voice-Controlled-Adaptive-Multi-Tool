import speech_recognition as sr
import os
import time
import signal
import sys
import threading
import difflib
import tkinter as tk
from tkinter import ttk, font, scrolledtext
import numpy as np
import pyttsx3
try:
    from PIL import Image, ImageDraw, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

# Text-to-speech engine setup with queue
tts_engine = None
speech_queue = []
speech_lock = threading.Lock()
speech_thread = None

def init_tts():
    """Initialize text-to-speech engine with Windows-specific fixes"""
    global tts_engine
    try:
        # Try different drivers for Windows
        drivers_to_try = ['sapi5', None]  # sapi5 is Windows default
        
        for driver in drivers_to_try:
            try:
                if driver:
                    tts_engine = pyttsx3.init(driverName=driver)
                else:
                    tts_engine = pyttsx3.init()
                print(f"[TTS] Initialized with driver: {driver if driver else 'default'}")
                break
            except Exception as e:
                print(f"[TTS] Driver {driver} failed: {e}")
                continue
        
        if not tts_engine:
            raise Exception("No TTS driver available")
        
        # Configure voice
        tts_engine.setProperty('rate', 180)  # Slightly faster
        tts_engine.setProperty('volume', 1.0)  # Maximum volume
        
        # Get and list voices
        voices = tts_engine.getProperty('voices')
        print(f"[TTS] Available voices: {len(voices)}")
        
        # Try to find a good voice
        for i, voice in enumerate(voices):
            print(f"  Voice {i}: {voice.name}")
            # Prefer English voices
            if 'english' in voice.name.lower() or 'david' in voice.name.lower() or 'zira' in voice.name.lower():
                tts_engine.setProperty('voice', voice.id)
                print(f"[TTS] Selected voice: {voice.name}")
                break
        else:
            # Use first available voice
            if voices:
                tts_engine.setProperty('voice', voices[0].id)
                print(f"[TTS] Using first voice: {voices[0].name}")
        
        # Windows-specific: Test audio
        print(f"[TTS] Voice engine initialized successfully")
        
    except Exception as e:
        print(f"[TTS ERROR] Voice engine init error: {e}")
        import traceback
        traceback.print_exc()
        tts_engine = None

def speech_worker():
    """Worker thread that processes speech queue one item at a time"""
    global tts_engine, speech_queue, speech_lock
    
    while True:
        text = None
        with speech_lock:
            if speech_queue:
                text = speech_queue.pop(0)
        
        if text and tts_engine:
            try:
                print(f"[TTS] Speaking: {text}")
                
                # Update GUI speaking status
                if gui:
                    try:
                        gui.root.after(0, lambda t=text: gui.update_speaking_status(True, t))
                    except:
                        pass
                
                # Create a new engine instance for each speech (prevents hanging)
                try:
                    local_engine = pyttsx3.init()
                    local_engine.setProperty('rate', 180)
                    local_engine.setProperty('volume', 1.0)
                    
                    # Copy voice from main engine if possible
                    if tts_engine:
                        try:
                            current_voice = tts_engine.getProperty('voice')
                            local_engine.setProperty('voice', current_voice)
                        except:
                            pass
                    
                    local_engine.say(text)
                    local_engine.runAndWait()
                    local_engine.stop()
                    del local_engine  # Clean up
                    
                except Exception as e:
                    print(f"[TTS ERROR] Speech failed: {e}")
                    # Fallback to original engine
                    try:
                        tts_engine.say(text)
                        tts_engine.runAndWait()
                    except Exception as e2:
                        print(f"[TTS ERROR] Fallback also failed: {e2}")
                
                print(f"[TTS] Finished: {text}")
                
                # Update GUI status back
                if gui:
                    try:
                        gui.root.after(0, lambda: gui.update_speaking_status(False, ""))
                    except:
                        pass
                        
            except Exception as e:
                print(f"[TTS ERROR] {e}")
                import traceback
                traceback.print_exc()
        else:
            # No speech to process, sleep briefly
            time.sleep(0.1)

def speak(text):
    """Add text to speech queue - thread safe"""
    global tts_engine, speech_queue, speech_lock, speech_thread
    
    print(f"[SPEAK REQUEST] {text}")
    
    if not tts_engine:
        print(f"[TTS MISSING] J.A.R.V.I.S. would say: {text}")
        return
    
    # Start speech worker thread if not running
    if speech_thread is None or not speech_thread.is_alive():
        speech_thread = threading.Thread(target=speech_worker, daemon=True)
        speech_thread.start()
        print("[TTS] Speech worker thread started")
    
    # Add to queue
    with speech_lock:
        speech_queue.append(text)
        print(f"[TTS] Added to queue. Queue size: {len(speech_queue)}")

# =========================================================
# J.A.R.V.I.S. GUI CONFIGURATION - Iron Man Theme
# =========================================================
GUI_CONFIG = {
    'colors': {
        'bg_dark': '#0a0a0f',
        'bg_panel': '#1a1a2e',
        'bg_card': '#16162a',
        'red_iron': '#b22222',
        'red_glow': '#ff3333',
        'gold': '#ffd700',
        'gold_dim': '#b8860b',
        'arc_blue': '#00d4ff',
        'arc_glow': '#66f0ff',
        'text_white': '#ffffff',
        'text_gray': '#a0a0a0',
        'border': '#2a2a3e',
        'success': '#00ff88',
        'warning': '#ffaa00',
        'error': '#ff4444'
    },
    'fonts': {
        'main': ('Segoe UI', 10),
        'header': ('Segoe UI', 12, 'bold'),
        'arc': ('Consolas', 9),
        'status': ('Segoe UI', 11, 'bold'),
        'command': ('Consolas', 11)
    }
}

# 1. J.A.R.V.I.S. INTENT CLASSIFIER (Machine Learning)

# 2. FUZZY KEYWORD MAP with phonetic variations for better speech recognition
KEYWORD_MAP = {
    "HAMMER": [
        "hammer", "hathoda", "hathora", "hathodi", "hatora", "hatoda", "smash", "mallet",
        "hamar", "hamer", "humar", "amor", "amar",  # Phonetic variations
        "hathor", "hatura", "hatara",
        # Urdu/Arabic script variations
        "ہتھوڑا", "ہتھوڑہ", "ہتھوڑی", "ہتھوڑا", "ہتھوڑی"
    ],
    "WRENCH": [
        "wrench", "pana", "panna", "panni", "rinch", "ranch", "winch", "peich", "paana",
        "range", "wench", "rench", "wranch", "vranch",  # Common misrecognitions
        "raanch", "wanch", "rach", "paan",
        # Urdu/Arabic script variations
        "پانا", "پنہ", "پن", "رینچ", "پانا"
    ],
    "SWORD": [
        "sword", "talwar", "talvar", "shamsheer", "kirpan", "tegh", "blade", "khanjar", "kataar",
        "sord", "swod", "sort", "sol",  # Phonetic variations
        "talwer", "talbar", "kirpan", "kripan",
        # Urdu/Arabic script variations
        "تلوار", "شمشیر", "تلوار", "تہوار", "کرپان"
    ],
    "SCREWDRIVER": [
        "screwdriver", "pechkas", "pichkas", "pechkash", "pichkash", "driver", "screw",
        "scru driver", "screw driver", "skrudriver",  # Phonetic variations
        "pech", "pich", "pikash",
        # Urdu/Arabic script variations
        "پیچ کس", "پیچکس", "پیچ", "پچ کس"
    ],
    "IDLE": [
        "idle", "band kar", "roko", "bas", "khatam", "chup", "shant", "khamosh", "stop", "reset", "clear",
        "idol", "idul", "aydol",  # Phonetic variations
        "band", "roak", "bas karo", "bandh",
        # Urdu/Arabic script variations
        "بند کرو", "روکو", "بس", "ختم", "چپ", "خاموش", "بند"
    ],
    "BIGGER": [
        "bada", "varda", "increase", "bigger", "mota", "bhari", "large", "enlarge", "big", "transform", "morph",
        "badaa", "burda", "barr", "barra",  # Phonetic variations
        "enlarge", "large", "bigar",
        # Urdu/Arabic script variations
        "بڑا", "بڑا کرو", "موٹا", "بھاری", "وڈا", "وڈا کرو"
    ],
    "SMALLER": [
        "chota", "nikka", "decrease", "smaller", "halka", "tiny", "shrink", "small",
        "chhota", "chhotta", "nukka", "smalla",  # Phonetic variations
        "kam", "kam karo", "chhotu",
        # Urdu/Arabic script variations
        "چھوٹا", "نکا", "ہلکا", "چھوٹا کرو", "کم"
    ],
    "BREAK": [
        "todo", "tor do", "phat", "break", "destroy", "tabah", "barbad", "shatter", "explode",
        "brake", "brek", "breek",  # Phonetic variations
        "todd", "tore", "phad",
        # Urdu/Arabic script variations
        "توڑ دو", "توڑ", "پھٹ", "تباہ", "برباد", "توڑ دو"
    ],
    "REPAIR": [
        "jodo", "theek", "thik", "fix", "repair", "rebuild", "durust", "shahi", "restore",
        "repear", "repir", "fixit",  # Phonetic variations
        "jore", "jor", "thek", "thik karo",
        # Urdu/Arabic script variations
        "جوڑ دو", "ٹھیک", "درست", "شاہی", "جوڑ", "ٹھیک کرو"
    ],
    "REGENERATE": [
        "regenerate", "regen", "punah", "firse", "dubara", "rebirth", "revive", "restore all", "heal", "recover", "renew", "refresh", "ultimate", "power up",
        "regenrate", "regenarat", "punar", "phirse",  # Phonetic variations
        "dobara", "shuru", "restart",
        # Urdu/Arabic script variations
        "پھر سے", "دوبارہ", "شروع", "نو", "دوبارہ شروع", "جانو بے"
    ],
    "GREETING": [
        "hello", "hi", "hey", "greetings", "salam", "namaste", "assalamu alaikum",
        "hi jarvis", "hello jarvis", "hey jarvis", "jarvis", "good morning", "good evening",
        "how are you", "what's up", "sup", "yo", "hola", "bonjour", "salaam",
        # Urdu/Arabic script variations
        "سلام", "السلام علیکم", "نمستے", "ہیلو", "ہائے", "کیسے ہو"
    ],
    "STATUS": [
        "status", "how are you", "what is your status", "report", "system status",
        "are you there", "you there", "jarvis you there", "status report",
        # Urdu/Arabic script variations
        "حالت", "کیسی حال ہے", "رپورٹ", "سٹیٹس", "تم وہاں ہو"
    ]
}

# Common speech recognition error corrections - EXTENDED
PHONETIC_CORRECTIONS = {
    # WRENCH variations (most common errors)
    "range": "WRENCH",
    "wench": "WRENCH",
    "rench": "WRENCH",
    "raanch": "WRENCH",
    "raach": "WRENCH",
    "rent": "WRENCH",
    "rant": "WRENCH",
    "ranche": "WRENCH",
    "wranch": "WRENCH",
    "rinch": "WRENCH",
    "ranch": "WRENCH",
    "rinj": "WRENCH",
    "wrench": "WRENCH",
    "wanch": "WRENCH",
    "rach": "WRENCH",
    "ranj": "WRENCH",
    "pech": "WRENCH",
    "peich": "WRENCH",
    "pana": "WRENCH",
    
    # HAMMER variations
    "hamar": "HAMMER",
    "humar": "HAMMER",
    "amar": "HAMMER",
    "amor": "HAMMER",
    "hamer": "HAMMER",
    "hammar": "HAMMER",
    "hamera": "HAMMER",
    "hamor": "HAMMER",
    "hamar": "HAMMER",
    "hamera": "HAMMER",
    "hathoda": "HAMMER",
    "hathor": "HAMMER",
    "hatura": "HAMMER",
    "smash": "HAMMER",
    
    # SWORD variations
    "sord": "SWORD",
    "swod": "SWORD",
    "swad": "SWORD",
    "swad": "SWORD",
    "sawod": "SWORD",
    "swerd": "SWORD",
    "sowrd": "SWORD",
    "talwer": "SWORD",
    "talvar": "SWORD",
    "talwar": "SWORD",
    "shamsheer": "SWORD",
    "tegh": "SWORD",
    "kirpan": "SWORD",
    "kripan": "SWORD",
    
    # SCREWDRIVER variations
    "scru": "SCREWDRIVER",
    "skru": "SCREWDRIVER",
    "skrew": "SCREWDRIVER",
    "scrudriver": "SCREWDRIVER",
    "driver": "SCREWDRIVER",
    "screw": "SCREWDRIVER",
    "scroo": "SCREWDRIVER",
    "pich": "SCREWDRIVER",
    "pech": "SCREWDRIVER",
    
    # IDLE variations
    "idle": "IDLE",
    "idol": "IDLE",
    "idul": "IDLE",
    "aydol": "IDLE",
    "idil": "IDLE",
    "idill": "IDLE",
    "aydel": "IDLE",
    "stop": "IDLE",
    "band": "IDLE",
    "roko": "IDLE",
    "bas": "IDLE",
    
    # BIGGER variations
    "bada": "BIGGER",
    "burda": "BIGGER",
    "barr": "BIGGER",
    "barra": "BIGGER",
    "bigger": "BIGGER",
    "bigar": "BIGGER",
    "badaa": "BIGGER",
    "badi": "BIGGER",
    "varda": "BIGGER",
    "mota": "BIGGER",
    
    # SMALLER variations
    "chota": "SMALLER",
    "chhota": "SMALLER",
    "chotta": "SMALLER",
    "chotu": "SMALLER",
    "chotaa": "SMALLER",
    "chhota": "SMALLER",
    "chhotu": "SMALLER",
    "nukka": "SMALLER",
    "nikka": "SMALLER",
    "chota": "SMALLER",
    "kam": "SMALLER",
    
    # BREAK variations
    "brake": "BREAK",
    "brek": "BREAK",
    "breek": "BREAK",
    "brak": "BREAK",
    "brek": "BREAK",
    "break": "BREAK",
    "todo": "BREAK",
    "tor": "BREAK",
    "phat": "BREAK",
    "destroy": "BREAK",
    
    # REPAIR variations
    "repear": "REPAIR",
    "repir": "REPAIR",
    "repar": "REPAIR",
    "repaer": "REPAIR",
    "repeir": "REPAIR",
    "repair": "REPAIR",
    "jodo": "REPAIR",
    "jore": "REPAIR",
    "theek": "REPAIR",
    "thik": "REPAIR",
    "fix": "REPAIR",
    
    # REGENERATE variations
    "regenrate": "REGENERATE",
    "regenarat": "REGENERATE",
    "regen": "REGENERATE",
    "regenerate": "REGENERATE",
    "punar": "REGENERATE",
    "phirse": "REGENERATE",
    "firse": "REGENERATE",
    "dobara": "REGENERATE",
    "dubara": "REGENERATE",
    "restart": "REGENERATE",
    "shuru": "REGENERATE",
    "ultimate": "REGENERATE",
    
    # Urdu/Arabic script words - HAMMER (ہتھوڑا family)
    "ہتھوڑا": "HAMMER",
    "ہتھوڑہ": "HAMMER",
    "ہتھوڑی": "HAMMER",
    "ہتھوڑے": "HAMMER",
    "ہتھوڑوں": "HAMMER",
    
    # Urdu/Arabic script words - WRENCH (پانا family)
    "پانا": "WRENCH",
    "پنہ": "WRENCH",
    "پن": "WRENCH",
    "پانی": "WRENCH",
    "پیمر": "WRENCH",  # Common misrecognition
    
    # Urdu/Arabic script words - SWORD (تلوار family)
    "تلوار": "SWORD",
    "شمشیر": "SWORD",
    "تہوار": "SWORD",
    "تلواریں": "SWORD",
    "تلواروں": "SWORD",
    
    # Urdu/Arabic script words - SCREWDRIVER (پیچ کس family)
    "پیچ": "SCREWDRIVER",
    "پیچ کس": "SCREWDRIVER",
    "پیچکس": "SCREWDRIVER",
    "پچ": "SCREWDRIVER",
    "پچ کس": "SCREWDRIVER",
    
    # Urdu/Arabic script words - IDLE (بند family)
    "بند": "IDLE",
    "بند کرو": "IDLE",
    "روکو": "IDLE",
    "بس": "IDLE",
    "ختم": "IDLE",
    "چپ": "IDLE",
    "خاموش": "IDLE",
    
    # Urdu/Arabic script words - BIGGER (بڑا family)
    "بڑا": "BIGGER",
    "بڑا کرو": "BIGGER",
    "بڑی": "BIGGER",
    "بڑے": "BIGGER",
    "موٹا": "BIGGER",
    "موٹی": "BIGGER",
    "موٹے": "BIGGER",
    "بھاری": "BIGGER",
    "وڈا": "BIGGER",
    "وڈا کرو": "BIGGER",
    
    # Urdu/Arabic script words - SMALLER (چھوٹا family)
    "چھوٹا": "SMALLER",
    "چھوٹی": "SMALLER",
    "چھوٹے": "SMALLER",
    "چھوٹا کرو": "SMALLER",
    "نکا": "SMALLER",
    "نکی": "SMALLER",
    "نکے": "SMALLER",
    "ہلکا": "SMALLER",
    "ہلکی": "SMALLER",
    "ہلکے": "SMALLER",
    "کم": "SMALLER",
    
    # Urdu/Arabic script words - BREAK (توڑ family)
    "توڑ": "BREAK",
    "توڑ دو": "BREAK",
    "توڑے": "BREAK",
    "توڑی": "BREAK",
    "توڑوں": "BREAK",
    "پھٹ": "BREAK",
    "پھٹی": "BREAK",
    "پھٹے": "BREAK",
    "تباہ": "BREAK",
    "برباد": "BREAK",
    
    # Urdu/Arabic script words - REPAIR (جوڑ family)
    "جوڑ": "REPAIR",
    "جوڑ دو": "REPAIR",
    "جوڑی": "REPAIR",
    "جوڑے": "REPAIR",
    "جوڑوں": "REPAIR",
    "ٹھیک": "REPAIR",
    "ٹھیک کرو": "REPAIR",
    "درست": "REPAIR",
    "درست کرو": "REPAIR",
    "شاہی": "REPAIR",
    
    # Urdu/Arabic script words - REGENERATE (دوبارہ family)
    "پھر سے": "REGENERATE",
    "دوبارہ": "REGENERATE",
    "شروع": "REGENERATE",
    "شروع کرو": "REGENERATE",
    "نو": "REGENERATE",
    "نیا": "REGENERATE",
    "نئی": "REGENERATE",
    "دوبارہ شروع": "REGENERATE",
    "جانو بے": "REGENERATE",  # Common misrecognition
    
    # Urdu/Arabic script words - GREETING (سلام family)
    "سلام": "GREETING",
    "السلام علیکم": "GREETING",
    "وعلیکم السلام": "GREETING",
    "نمستے": "GREETING",
    "ہیلو": "GREETING",
    "ہائے": "GREETING",
    "کیسے ہو": "GREETING",
    "کیسی ہو": "GREETING",
    
    # Urdu/Arabic script words - STATUS (حالت family)
    "حالت": "STATUS",
    "کیسی حال ہے": "STATUS",
    "کیسا ہے": "STATUS",
    "رپورٹ": "STATUS",
    "سٹیٹس": "STATUS",
    "تم وہاں ہو": "STATUS",
    "تم یہاں ہو": "STATUS"
}
data = [
    # HAMMER (Hathoda/Hammer/Variations)
    ("hathoda", "HAMMER"), ("hathodi", "HAMMER"), ("hathora", "HAMMER"), ("hatora", "HAMMER"),
    ("hammer", "HAMMER"), ("hammar", "HAMMER"), ("hamer", "HAMMER"), ("hamm", "HAMMER"),
    ("smash", "HAMMER"), ("mallet", "HAMMER"), ("mollat", "HAMMER"), ("hathoda mode", "HAMMER"),
    ("give me the hammer", "HAMMER"), ("deploy hammer", "HAMMER"), ("hammer time", "HAMMER"),
    ("hathoda lao", "HAMMER"), ("hathoda dikhao", "HAMMER"), ("hathoda chahiye", "HAMMER"),
    ("make a hammer", "HAMMER"), ("build the hammer", "HAMMER"), ("hammer mode please", "HAMMER"),
    
    # WRENCH (Pana/Wrench/Variations)
    ("pana", "WRENCH"), ("panna", "WRENCH"), ("panni", "WRENCH"), ("panne", "WRENCH"),
    ("wrench", "WRENCH"), ("rinch", "WRENCH"), ("ranch", "WRENCH"), ("winch", "WRENCH"),
    ("fix it", "WRENCH"), ("panner", "WRENCH"), ("peich", "WRENCH"), ("paana", "WRENCH"),
    ("give me the wrench", "WRENCH"), ("wrench mode", "WRENCH"), ("pana lao", "WRENCH"),
    ("fix the bolts", "WRENCH"), ("tighten it", "WRENCH"), ("wrench please", "WRENCH"),
    ("pana chahiye", "WRENCH"), ("use the pana", "WRENCH"), ("build the wrench", "WRENCH"),
    
    # SWORD (Talwar/Kirpan/Variations)
    ("talwar", "SWORD"), ("talvar", "SWORD"), ("shamsheer", "SWORD"), ("kirpan", "SWORD"),
    ("sword", "SWORD"), ("blade", "SWORD"), ("tegh", "SWORD"), ("khanjar", "SWORD"),
    ("kataar", "SWORD"), ("sward", "SWORD"), ("soard", "SWORD"), ("sod", "SWORD"),
    ("deploy sword", "SWORD"), ("combat mode", "SWORD"), ("talwar lao", "SWORD"),
    ("time to fight", "SWORD"), ("get the blade", "SWORD"), ("sword mode", "SWORD"),
    ("talwar dikhao", "SWORD"), ("talwar chahiye", "SWORD"), ("make a sword", "SWORD"),
    
    # SCREWDRIVER (Pechkas/Screwdriver/Variations)
    ("pechkas", "SCREWDRIVER"), ("pichkas", "SCREWDRIVER"), ("pechkash", "SCREWDRIVER"),
    ("pichkash", "SCREWDRIVER"), ("screwdriver", "SCREWDRIVER"), ("driver", "SCREWDRIVER"),
    ("screw", "SCREWDRIVER"), ("scru", "SCREWDRIVER"), ("screwdriver mode", "SCREWDRIVER"),
    ("pechkas lao", "SCREWDRIVER"), ("open the panel", "SCREWDRIVER"), ("fix the screw", "SCREWDRIVER"),
    ("give me the screwdriver", "SCREWDRIVER"), ("pechkas chahiye", "SCREWDRIVER"), ("pechkas dikhao", "SCREWDRIVER"),
    
    # IDLE/CONTROL (Band/Roko/Variations)
    ("band kar", "IDLE"), ("roko", "IDLE"), ("bas", "IDLE"), ("khatam", "IDLE"),
    ("chup", "IDLE"), ("shant", "IDLE"), ("khamosh", "IDLE"), ("idle", "IDLE"),
    ("stop", "IDLE"), ("reset", "IDLE"), ("clear", "IDLE"), ("hide", "IDLE"),
    ("stop animation", "IDLE"), ("go to base", "IDLE"), ("base mode", "IDLE"),
    ("retract all", "IDLE"), ("hide tools", "IDLE"), ("band karo", "IDLE"),
    ("bas karo", "IDLE"), ("ab bas", "IDLE"), ("reset everything", "IDLE"),
    
    # SCALE (Bada/Chota/Variations)
    ("bada kar", "BIGGER"), ("bada", "BIGGER"), ("varda", "BIGGER"), ("mota", "BIGGER"),
    ("bhari", "BIGGER"), ("increase", "BIGGER"), ("bigger", "BIGGER"), ("large", "BIGGER"),
    ("make it bigger", "BIGGER"), ("enlarge", "BIGGER"), ("increase size", "BIGGER"),
    ("bada karo", "BIGGER"), ("size badao", "BIGGER"), ("zyada", "BIGGER"),
    ("big", "BIGGER"), ("transform", "BIGGER"), ("morph", "BIGGER"),
    ("chota kar", "SMALLER"), ("chota", "SMALLER"), ("nikka", "SMALLER"), ("halka", "SMALLER"),
    ("decrease", "SMALLER"), ("smaller", "SMALLER"), ("tiny", "SMALLER"),
    ("make it smaller", "SMALLER"), ("shrink", "SMALLER"), ("decrease size", "SMALLER"),
    ("chota karo", "SMALLER"), ("size kam kar", "SMALLER"), ("kam kar", "SMALLER"),
    ("small", "SMALLER"),
    
    # DESTRUCT/REPAIR (Todo/Jodo/Variations)
    ("todo", "BREAK"), ("tor do", "BREAK"), ("phat", "BREAK"), ("tabah", "BREAK"),
    ("barbad", "BREAK"), ("break", "BREAK"), ("destroy", "BREAK"), ("explode", "BREAK"),
    ("break the tool", "BREAK"), ("shatter", "BREAK"), ("self destruct", "BREAK"),
    ("tor do isko", "BREAK"), ("tabah kar do", "BREAK"), ("phttt", "BREAK"),
    ("jodo", "REPAIR"), ("theek kar", "REPAIR"), ("thik kar", "REPAIR"), ("durust", "REPAIR"),
    ("shahi", "REPAIR"), ("repair", "REPAIR"), ("fix", "REPAIR"), ("restore", "REPAIR"),
    ("repair yourself", "REPAIR"), ("fix damage", "REPAIR"), ("rebuild", "REPAIR"),
    ("jodo isko", "REPAIR"), ("theek karo", "REPAIR"), ("back to normal", "REPAIR"),
    
    # REGENERATE (Ultimate Restoration/Variations)
    ("regenerate", "REGENERATE"), ("regen", "REGENERATE"), ("punah", "REGENERATE"), 
    ("firse", "REGENERATE"), ("dubara", "REGENERATE"), ("rebirth", "REGENERATE"),
    ("revive", "REGENERATE"), ("restore all", "REGENERATE"), ("heal", "REGENERATE"),
    ("recover", "REGENERATE"), ("renew", "REGENERATE"), ("refresh", "REGENERATE"),
    ("ultimate", "REGENERATE"), ("power up", "REGENERATE"), ("full restore", "REGENERATE"),
    ("complete heal", "REGENERATE"), ("maximum power", "REGENERATE"), ("overcharge", "REGENERATE"),
    ("punah jiyo", "REGENERATE"), ("firse shuru", "REGENERATE"), ("dubara ban", "REGENERATE"),
    ("regenerate now", "REGENERATE"), ("ultimate regeneration", "REGENERATE"), ("heal all", "REGENERATE")
]

texts, labels = zip(*data)
vectorizer = CountVectorizer()
X = vectorizer.fit_transform(texts)
clf = MultinomialNB()
clf.fit(X, labels)

# =========================================================
# J.A.R.V.I.S. CONFIGURATION
# =========================================================
# Hardcoded to project folder for absolute reliability on Windows
BASE_DIR = r"E:\New folder\blend"
COMMAND_FILE = os.path.join(BASE_DIR, "jarvis_cmd.txt")
HEARTBEAT_FILE = os.path.join(BASE_DIR, "jarvis_heartbeat.txt")

print(f"[Internal] System Path: {BASE_DIR}")

# ON WINDOWS: device_index=None usually picks the 'Stereo Mix' or 'Default Mic'
MIC_INDEX = None 
# =========================================================

def heartbeat_loop():
    while True:
        try:
            with open(HEARTBEAT_FILE, "w") as f:
                f.write(str(time.time()))
        except:
            pass
        time.sleep(5)

class JarvisGUI:
    """Professional Iron Man themed J.A.R.V.I.S. Interface"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S. - Just A Rather Very Intelligent System")
        self.root.geometry("1200x800")
        self.root.configure(bg=GUI_CONFIG['colors']['bg_dark'])
        self.root.minsize(1000, 700)
        
        # Command queue for thread-safe GUI updates
        self.command_queue = []
        self.queue_lock = threading.Lock()
        
        self.setup_styles()
        self.create_main_layout()
        self.start_update_loop()
        
    def setup_styles(self):
        """Configure ttk styles for Iron Man theme"""
        self.style = ttk.Style()
        colors = GUI_CONFIG['colors']
        
        # Configure styles
        self.style.configure('Iron.TFrame', background=colors['bg_panel'])
        self.style.configure('Card.TFrame', background=colors['bg_card'])
        self.style.configure('Arc.TButton', 
                           background=colors['arc_blue'],
                           foreground=colors['bg_dark'],
                           font=GUI_CONFIG['fonts']['header'])
        self.style.configure('Iron.TLabel',
                           background=colors['bg_panel'],
                           foreground=colors['text_white'],
                           font=GUI_CONFIG['fonts']['main'])
        self.style.configure('Gold.TLabel',
                           background=colors['bg_panel'],
                           foreground=colors['gold'],
                           font=GUI_CONFIG['fonts']['header'])
        self.style.configure('Status.TLabel',
                           background=colors['bg_panel'],
                           foreground=colors['arc_blue'],
                           font=GUI_CONFIG['fonts']['status'])
        
    def create_main_layout(self):
        """Create the main Iron Man themed interface"""
        colors = GUI_CONFIG['colors']
        
        # Main container with padding
        main_container = tk.Frame(self.root, bg=colors['bg_dark'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # TOP HEADER - JARVIS Title with Arc Reactor
        header_frame = tk.Frame(main_container, bg=colors['bg_panel'], 
                               highlightbackground=colors['arc_blue'],
                               highlightthickness=2, bd=0)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Arc Reactor Animation Canvas
        self.arc_canvas = tk.Canvas(header_frame, width=80, height=80,
                                    bg=colors['bg_panel'], highlightthickness=0)
        self.arc_canvas.pack(side=tk.LEFT, padx=20, pady=10)
        self.arc_angle = 0
        self.draw_arc_reactor()
        
        # Title
        title_frame = tk.Frame(header_frame, bg=colors['bg_panel'])
        title_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True)
        
        tk.Label(title_frame, text="J.A.R.V.I.S.", 
                font=('Segoe UI', 24, 'bold'),
                bg=colors['bg_panel'], fg=colors['arc_blue']).pack()
        tk.Label(title_frame, text="Just A Rather Very Intelligent System",
                font=GUI_CONFIG['fonts']['arc'],
                bg=colors['bg_panel'], fg=colors['text_gray']).pack()
        
        # Status indicators
        status_frame = tk.Frame(header_frame, bg=colors['bg_panel'])
        status_frame.pack(side=tk.RIGHT, padx=20)
        
        self.connection_status = tk.Label(status_frame, text="● ONLINE",
                                         font=GUI_CONFIG['fonts']['status'],
                                         bg=colors['bg_panel'], fg=colors['success'])
        self.connection_status.pack()
        
        self.mic_status = tk.Label(status_frame, text="MIC: STANDBY",
                                  font=GUI_CONFIG['fonts']['arc'],
                                  bg=colors['bg_panel'], fg=colors['text_gray'])
        self.mic_status.pack()
        
        self.speaking_status = tk.Label(status_frame, text="",
                                       font=GUI_CONFIG['fonts']['arc'],
                                       bg=colors['bg_panel'], fg=colors['arc_glow'])
        self.speaking_status.pack()
        
        # CENTER CONTENT AREA
        content_frame = tk.Frame(main_container, bg=colors['bg_dark'])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # LEFT PANEL - Command History
        left_panel = tk.Frame(content_frame, bg=colors['bg_panel'],
                             highlightbackground=colors['border'],
                             highlightthickness=1)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_panel, text="📜 COMMAND HISTORY",
                font=GUI_CONFIG['fonts']['header'],
                bg=colors['bg_panel'], fg=colors['gold']).pack(pady=10)
        
        # Command history with custom styling
        history_frame = tk.Frame(left_panel, bg=colors['bg_card'])
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.history_text = tk.Text(history_frame,
                                   font=GUI_CONFIG['fonts']['arc'],
                                   bg=colors['bg_card'],
                                   fg=colors['text_white'],
                                   wrap=tk.WORD,
                                   state=tk.DISABLED,
                                   padx=10, pady=10,
                                   relief=tk.FLAT)
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, 
                                 command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=scrollbar.set)
        
        self.history_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # RIGHT PANEL - Controls & Visualizer
        right_panel = tk.Frame(content_frame, bg=colors['bg_panel'],
                              highlightbackground=colors['border'],
                              highlightthickness=1)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Audio Visualizer
        viz_frame = tk.LabelFrame(right_panel, text=" AUDIO VISUALIZER ",
                                 font=GUI_CONFIG['fonts']['header'],
                                 bg=colors['bg_panel'], fg=colors['arc_blue'],
                                 relief=tk.GROOVE, bd=2)
        viz_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.viz_canvas = tk.Canvas(viz_frame, height=120, bg=colors['bg_dark'],
                                     highlightthickness=0)
        self.viz_canvas.pack(fill=tk.X, padx=5, pady=5)
        self.audio_levels = [0] * 20
        self.draw_visualizer()
        
        # Voice Command Display
        cmd_frame = tk.LabelFrame(right_panel, text=" VOICE COMMAND ",
                                 font=GUI_CONFIG['fonts']['header'],
                                 bg=colors['bg_panel'], fg=colors['gold'],
                                 relief=tk.GROOVE, bd=2)
        cmd_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.command_display = tk.Label(cmd_frame, text="Initializing...",
                                       font=('Segoe UI', 14, 'bold'),
                                       bg=colors['bg_card'],
                                       fg=colors['arc_blue'],
                                       wraplength=300, height=2)
        self.command_display.pack(fill=tk.X, padx=10, pady=10)
        
        # MIC ENERGY LEVEL DISPLAY
        energy_frame = tk.Frame(cmd_frame, bg=colors['bg_card'])
        energy_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(energy_frame, text="MIC ENERGY:",
                font=GUI_CONFIG['fonts']['arc'],
                bg=colors['bg_card'], fg=colors['text_gray']).pack(side=tk.LEFT)
        
        self.energy_display = tk.Label(energy_frame, text="WAITING...",
                                      font=GUI_CONFIG['fonts']['arc'],
                                      bg=colors['bg_card'], fg=colors['arc_blue'])
        self.energy_display.pack(side=tk.LEFT, padx=5)
        
        # Mic Test Button
        self.mic_test_btn = tk.Button(cmd_frame, text="🎤 TEST MICROPHONE",
                                     command=self.test_microphone,
                                     bg=colors['gold'], fg=colors['bg_dark'],
                                     font=GUI_CONFIG['fonts']['header'],
                                     activebackground=colors['red_iron'],
                                     relief=tk.RAISED, bd=2)
        self.mic_test_btn.pack(fill=tk.X, padx=10, pady=5)
        
        # Quick Command Buttons
        btn_frame = tk.LabelFrame(right_panel, text=" QUICK COMMANDS ",
                                 font=GUI_CONFIG['fonts']['header'],
                                 bg=colors['bg_panel'], fg=colors['red_iron'],
                                 relief=tk.GROOVE, bd=2)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        commands = [
            ("HAMMER", colors['red_iron'], lambda: self.send_command("HAMMER")),
            ("WRENCH", colors['gold'], lambda: self.send_command("WRENCH")),
            ("SWORD", colors['arc_blue'], lambda: self.send_command("SWORD")),
            ("BREAK", colors['error'], lambda: self.send_command("BREAK")),
            ("REPAIR", colors['success'], lambda: self.send_command("REPAIR")),
            ("IDLE", colors['text_gray'], lambda: self.send_command("IDLE"))
        ]
        
        for i, (cmd, color, action) in enumerate(commands):
            btn = tk.Button(btn_frame, text=cmd, command=action,
                          bg=colors['bg_card'], fg=color,
                          font=GUI_CONFIG['fonts']['header'],
                          activebackground=color,
                          activeforeground=colors['bg_dark'],
                          relief=tk.RAISED, bd=2, width=10)
            btn.grid(row=i//3, column=i%3, padx=5, pady=5, sticky="nsew")
        
        # Text Input
        input_frame = tk.Frame(right_panel, bg=colors['bg_panel'])
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(input_frame, text="Text Command:",
                font=GUI_CONFIG['fonts']['main'],
                bg=colors['bg_panel'], fg=colors['text_gray']).pack(anchor=tk.W)
        
        self.text_input = tk.Entry(input_frame,
                                  font=GUI_CONFIG['fonts']['command'],
                                  bg=colors['bg_card'],
                                  fg=colors['text_white'],
                                  insertbackground=colors['arc_blue'],
                                  relief=tk.SUNKEN, bd=2)
        self.text_input.pack(fill=tk.X, pady=5)
        self.text_input.bind('<Return>', lambda e: self.send_text_command())
        
        send_btn = tk.Button(input_frame, text="SEND COMMAND",
                           command=self.send_text_command,
                           bg=colors['arc_blue'], fg=colors['bg_dark'],
                           font=GUI_CONFIG['fonts']['header'],
                           activebackground=colors['arc_glow'],
                           relief=tk.RAISED, bd=2)
        send_btn.pack(fill=tk.X, pady=5)
        
        # BOTTOM FOOTER
        footer_frame = tk.Frame(main_container, bg=colors['bg_panel'])
        footer_frame.pack(fill=tk.X, pady=(15, 0))
        
        # System metrics
        metrics_text = f"System: ACTIVE | AI Engine: ML+Bayes | Audio: Google Speech API | Path: {BASE_DIR}"
        tk.Label(footer_frame, text=metrics_text,
                font=GUI_CONFIG['fonts']['arc'],
                bg=colors['bg_panel'], fg=colors['text_gray']).pack(side=tk.LEFT, padx=10, pady=5)
        
        self.time_label = tk.Label(footer_frame, text="",
                                  font=GUI_CONFIG['fonts']['arc'],
                                  bg=colors['bg_panel'], fg=colors['arc_blue'])
        self.time_label.pack(side=tk.RIGHT, padx=10, pady=5)
        
    def draw_arc_reactor(self):
        """Draw animated arc reactor on canvas"""
        colors = GUI_CONFIG['colors']
        self.arc_canvas.delete("all")
        
        cx, cy = 40, 40
        # Outer ring (pulsing)
        pulse = 1 + 0.2 * np.sin(self.arc_angle)
        r1 = int(35 * pulse)
        self.arc_canvas.create_oval(cx-r1, cy-r1, cx+r1, cy+r1,
                                   outline=colors['arc_blue'], width=2)
        
        # Middle ring
        r2 = 25
        self.arc_canvas.create_oval(cx-r2, cy-r2, cx+r2, cy+r2,
                                   outline=colors['arc_glow'], width=3)
        
        # Inner core (glowing)
        r3 = 15
        self.arc_canvas.create_oval(cx-r3, cy-r3, cx+r3, cy+r3,
                                   fill=colors['arc_blue'],
                                   outline=colors['arc_glow'], width=2)
        
        # Center glow
        r4 = 5
        self.arc_canvas.create_oval(cx-r4, cy-r4, cx+r4, cy+r4,
                                   fill=colors['arc_glow'], outline="")
        
    def draw_visualizer(self):
        """Draw audio level visualizer"""
        colors = GUI_CONFIG['colors']
        self.viz_canvas.delete("all")
        
        width = self.viz_canvas.winfo_width() or 350
        height = self.viz_canvas.winfo_height() or 120
        
        bar_width = width / len(self.audio_levels)
        
        for i, level in enumerate(self.audio_levels):
            x = i * bar_width + 2
            bar_height = height * level * 0.9
            y = height - bar_height
            
            # Color gradient based on level
            if level > 0.7:
                color = colors['red_glow']
            elif level > 0.4:
                color = colors['gold']
            else:
                color = colors['arc_blue']
            
            self.viz_canvas.create_rectangle(x, y, x + bar_width - 4, height,
                                            fill=color, outline="")
    def update_visualizer(self, audio_level=0):
        """Update audio visualizer with new level"""
        # Shift and add new level
        self.audio_levels = self.audio_levels[1:] + [audio_level]
        # Decay old levels
        self.audio_levels = [max(0, l * 0.95) for l in self.audio_levels]
        self.draw_visualizer()
        
    def send_command(self, cmd):
        """Send command from button click"""
        self.log_command(f"[BUTTON] {cmd}")
        try:
            with open(COMMAND_FILE, "w") as f:
                f.write(cmd)
            self.update_command_display(cmd, "EXECUTED")
        except Exception as e:
            self.update_command_display(f"Error: {e}", "ERROR")
            
    def send_text_command(self):
        """Send command from text input"""
        text = self.text_input.get().strip()
        if text:
            intent = get_intent(text)
            if intent:
                self.log_command(f"[TEXT] {text} → {intent}")
                try:
                    with open(COMMAND_FILE, "w") as f:
                        f.write(intent)
                    self.update_command_display(f"{text}", f"→ {intent}")
                except Exception as e:
                    self.update_command_display(f"Error: {e}", "ERROR")
            else:
                self.update_command_display(text, "NOT RECOGNIZED")
            self.text_input.delete(0, tk.END)
            
    def update_command_display(self, command, status):
        """Update the voice command display"""
        colors = GUI_CONFIG['colors']
        if status == "EXECUTED" or "→" in status:
            fg = colors['success']
        elif status == "ERROR":
            fg = colors['error']
        elif status == "NOT RECOGNIZED":
            fg = colors['warning']
        else:
            fg = colors['arc_blue']
            
        display_text = f"{command}\n{status}"
        self.command_display.config(text=display_text, fg=fg)
        
    def update_speaking_status(self, is_speaking, text):
        """Update speaking status indicator"""
        if is_speaking:
            self.speaking_status.config(text="🔊 SPEAKING...", fg=GUI_CONFIG['colors']['arc_glow'])
            # Also update command display
            self.command_display.config(text=f"JARVIS: {text[:50]}...", fg=GUI_CONFIG['colors']['arc_glow'])
        else:
            self.speaking_status.config(text="", fg=GUI_CONFIG['colors']['bg_panel'])
            self.command_display.config(text="Listening...", fg=GUI_CONFIG['colors']['arc_blue'])
            
    def update_mic_status(self, is_listening):
        """Update microphone status"""
        if is_listening:
            self.mic_status.config(text="🎤 LISTENING", fg=GUI_CONFIG['colors']['gold'])
        else:
            self.mic_status.config(text="MIC: STANDBY", fg=GUI_CONFIG['colors']['text_gray'])
            
    def log_command(self, message):
        """Add command to history log"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.history_text.config(state=tk.NORMAL)
        self.history_text.insert(tk.END, log_entry)
        self.history_text.see(tk.END)
        self.history_text.config(state=tk.DISABLED)
        
    def start_update_loop(self):
        """Start GUI update loop"""
        self.update_gui()
        
    def update_gui(self):
        """Main GUI update loop"""
        # Update arc reactor animation
        self.arc_angle += 0.3
        self.draw_arc_reactor()
        
        # Update visualizer
        self.update_visualizer(np.random.random() * 0.3)
        
        # Update time
        self.time_label.config(text=time.strftime("%H:%M:%S"))
        
        # Check command queue
        with self.queue_lock:
            while self.command_queue:
                cmd_type, data = self.command_queue.pop(0)
                if cmd_type == "voice":
                    self.log_command(f"[VOICE] {data['text']} → {data['intent']}")
                    self.update_command_display(data['text'], f"→ {data['intent']}")
                    self.update_visualizer(0.8)  # Spike for voice
                    
        self.root.after(50, self.update_gui)
        
    def test_microphone(self):
        """Test microphone functionality"""
        self.mic_test_btn.config(text="🔴 TESTING... SPEAK NOW", bg=GUI_CONFIG['colors']['red_iron'])
        self.update_energy_display(150, "Testing...")
        self.log_command("[MIC TEST] Speak now for 3 seconds...")
        
        def run_test():
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                recognizer.energy_threshold = 300       # FIX: was 150
                recognizer.dynamic_energy_threshold = True  # FIX: adapt in real-time
                
                mics = sr.Microphone.list_microphone_names()
                source = None
                
                # Try to find working mic
                for idx in list(range(5)) + [None]:
                    try:
                        temp = sr.Microphone(device_index=idx)
                        with temp: pass
                        source = temp
                        break
                    except: continue
                
                if not source:
                    self.root.after(0, lambda: self.log_command("[MIC TEST] ✗ No mic found!"))
                    self.root.after(0, lambda: self.mic_test_btn.config(
                        text="🎤 TEST MICROPHONE", bg=GUI_CONFIG['colors']['gold']))
                    return
                
                with source as s:
                    recognizer.adjust_for_ambient_noise(s, duration=2)  # FIX: was 1
                    self.root.after(0, lambda: self.update_energy_display(
                        int(recognizer.energy_threshold), "Listening..."))
                    
                    self.root.after(0, lambda: self.log_command("[MIC TEST] Listening..."))
                    audio = recognizer.listen(s, timeout=5, phrase_time_limit=5)  # FIX: was 3
                    
                    # Try to recognize — Urdu first, then English fallback
                    try:
                        try:
                            text = recognizer.recognize_google(audio, language="ur-PK").lower()
                        except sr.UnknownValueError:
                            text = recognizer.recognize_google(audio, language="en-US").lower()
                        self.root.after(0, lambda: self.log_command(f"[MIC TEST] ✓ Heard: '{text}'"))
                        self.root.after(0, lambda: speak(f"I heard you say: {text}"))
                    except sr.UnknownValueError:
                        self.root.after(0, lambda: self.log_command("[MIC TEST] ✗ Could not understand speech"))
                        self.root.after(0, lambda: speak("I couldn't understand that. Please speak more clearly."))
                    
            except Exception as e:
                self.root.after(0, lambda: self.log_command(f"[MIC TEST] ✗ Error: {e}"))
            finally:
                self.root.after(0, lambda: self.mic_test_btn.config(
                    text="🎤 TEST MICROPHONE", bg=GUI_CONFIG['colors']['gold']))
                self.root.after(0, lambda: self.update_energy_display(0, "Ready"))
        
        threading.Thread(target=run_test, daemon=True).start()
        
    def update_energy_display(self, energy, status):
        """Update microphone energy level display"""
        if hasattr(self, 'energy_display'):
            self.energy_display.config(text=f"{status} ({energy})")
            # Color based on energy level
            if energy > 300:
                self.energy_display.config(fg=GUI_CONFIG['colors']['red_glow'])
            elif energy > 150:
                self.energy_display.config(fg=GUI_CONFIG['colors']['gold'])
            else:
                self.energy_display.config(fg=GUI_CONFIG['colors']['arc_blue'])
            
    def queue_voice_command(self, text, intent):
        """Thread-safe method to queue voice commands"""
        with self.queue_lock:
            self.command_queue.append(("voice", {"text": text, "intent": intent}))
            
    def run(self):
        """Start the GUI"""
        self.root.mainloop()

# Create global GUI instance
gui = None

def text_input_loop():
    """Placeholder - now handled by GUI"""
    pass

def cleanup_and_exit(sig, frame):
    print("\n[J.A.R.V.I.S. SHUTTING DOWN]")
    try:
        if os.path.exists(COMMAND_FILE): os.remove(COMMAND_FILE)
        if os.path.exists(HEARTBEAT_FILE): os.remove(HEARTBEAT_FILE)
    except: pass
    sys.exit(0)

# Windows doesn't support all signals, so we wrap them
if hasattr(signal, 'SIGINT'): signal.signal(signal.SIGINT, cleanup_and_exit)
if hasattr(signal, 'SIGTERM'): signal.signal(signal.SIGTERM, cleanup_and_exit)

threading.Thread(target=heartbeat_loop, daemon=True).start()
threading.Thread(target=text_input_loop, daemon=True).start()

def safe_gui_update(func):
    """Safely update GUI from any thread"""
    global gui
    try:
        if gui and gui.root and gui.root.winfo_exists():
            gui.root.after(0, func)
    except:
        pass

def get_intent(text):
    text = text.lower().strip()
    if not text: return None
    
    words = text.split()
    
    # Priority 0: Direct Phonetic Corrections (fixes common speech recognition errors)
    for word in words:
        if word in PHONETIC_CORRECTIONS:
            corrected = PHONETIC_CORRECTIONS[word]
            safe_gui_update(lambda w=word, c=corrected: gui.log_command(f"[PHONETIC FIX] '{w}' → '{c}'"))
            return corrected
    
    # Priority 0.5: Multi-word phrase matching (check full phrases first)
    for intent, keywords in KEYWORD_MAP.items():
        for keyword in keywords:
            if len(keyword.split()) > 1 and keyword in text:
                # Multi-word match found
                safe_gui_update(lambda k=keyword, i=intent: gui.log_command(f"[PHRASE MATCH] '{k}' → {i}"))
                return intent
    
    # Priority 1: Direct Keyword Match (exact matches)
    for intent, keywords in KEYWORD_MAP.items():
        for word in words:
            if word in keywords:
                safe_gui_update(lambda w=word, i=intent: gui.log_command(f"[EXACT MATCH] '{w}' → {i}"))
                return intent
    
    # Priority 2: Fuzzy Match with phonetic similarity (75% threshold for better recall)
    best_match = None
    best_score = 0
    best_intent = None
    
    for intent, keywords in KEYWORD_MAP.items():
        for word in words:
            # Get fuzzy matches
            matches = difflib.get_close_matches(word, keywords, n=1, cutoff=0.75)
            if matches:
                # Calculate similarity score
                score = difflib.SequenceMatcher(None, word, matches[0]).ratio()
                if score > best_score:
                    best_score = score
                    best_match = matches[0]
                    best_intent = intent
    
    if best_intent and best_score >= 0.75:
        safe_gui_update(lambda w=words[0], m=best_match, s=f"{best_score:.2f}", i=best_intent: 
                      gui.log_command(f"[FUZZY MATCH] '{w}' ~ '{m}' ({s}) → {i}"))
        return best_intent
    
    # Priority 3: Phonetic Sound-Alike Matching (for words that sound similar)
    for word in words:
        for intent, keywords in KEYWORD_MAP.items():
            for keyword in keywords:
                # Check if first 3 characters match (prefix similarity)
                if len(word) >= 3 and len(keyword) >= 3:
                    if word[:3] == keyword[:3]:
                        # Check overall similarity
                        if difflib.SequenceMatcher(None, word, keyword).ratio() > 0.65:
                            safe_gui_update(lambda w=word, k=keyword, i=intent: 
                                          gui.log_command(f"[SOUND MATCH] '{w}' ≈ '{k}' → {i}"))
                            return intent
    
    # Priority 4: ML Classifier (Only if all else fails)
    if len(words) > 1:
        try:
            vec = vectorizer.transform([text])
            ml_result = clf.predict(vec)[0]
            safe_gui_update(lambda r=ml_result: gui.log_command(f"[ML CLASSIFIER] → {r}"))
            return ml_result
        except:
            pass
    
    # No match found
    return None

def jarvis_main():
    global gui
    
    # Initialize TTS engine
    print("="*50)
    print("[INIT] Initializing J.A.R.V.I.S....")
    print("="*50)
    init_tts()
    
    # Test TTS immediately
    print("[INIT] Testing voice output...")
    speak("Voice test. Jarvis is online.")
    time.sleep(2)  # Wait for speech to complete
    
    # Start GUI in separate thread
    def run_gui():
        global gui
        gui = JarvisGUI()
        gui.run()
    
    gui_thread = threading.Thread(target=run_gui, daemon=True)
    gui_thread.start()
    
    # Give GUI time to initialize
    time.sleep(1)
    
    # JARVIS greeting
    speak("Ready for your commands sir.")
    
    recognizer = sr.Recognizer()
    
    # List all available microphones and try each one
    mics = sr.Microphone.list_microphone_names()
    if gui:
        safe_gui_update(lambda: gui.log_command(f"[INFO] Available microphones: {len(mics)}"))
        for i, mic in enumerate(mics):
            safe_gui_update(lambda m=mic, idx=i: gui.log_command(f"  [{idx}] {m}"))
    
    source = None
    # Try microphone indices 0-10 and None (default)
    for idx in list(range(10)) + [None]:
        try:
            temp_source = sr.Microphone(device_index=idx)
            with temp_source as s: 
                pass
            source = temp_source
            if gui:
                safe_gui_update(lambda i=idx: gui.log_command(f"[✓] Connected to Microphone Index: {i}"))
                if idx is not None and idx < len(mics):
                    safe_gui_update(lambda m=mics[idx]: gui.log_command(f"    Name: {m}"))
            break
        except Exception as e:
            if gui:
                safe_gui_update(lambda i=idx, err=str(e): gui.log_command(f"[✗] Mic {i}: {err[:50]}"))
            continue

    if not source:
        error_msg = "No microphone found! Please check your audio settings."
        if gui:
            safe_gui_update(lambda: gui.log_command(f"[✗] {error_msg}"))
            safe_gui_update(lambda: gui.update_mic_status(False))
        speak(error_msg)
        return

    # OPTIMIZED SETTINGS FOR BETTER SPEECH RECOGNITION (Urdu/Hindi/English)
    recognizer.pause_threshold = 1.2    # FIX: was 0.8 — extra time between Urdu words
    recognizer.phrase_threshold = 0.1   # Very low threshold to catch quiet speech
    recognizer.non_speaking_duration = 0.8  # FIX: was 0.5 — more forgiving end-of-speech
    
    # Start with a reasonable energy threshold — let calibration tune it
    recognizer.energy_threshold = 300   # FIX: was 150 — sensible starting point
    recognizer.dynamic_energy_threshold = True   # FIX: was False — adapt in real-time to noise
    
    if gui:
        safe_gui_update(lambda: gui.log_command("[J.A.R.V.I.S. ONLINE - MULTI-LANG (Urdu/Hindi/English)]"))
        safe_gui_update(lambda: gui.log_command("[Voice and Text commands active]"))
        safe_gui_update(lambda: gui.log_command(f"[Initial Energy Threshold: {recognizer.energy_threshold}]"))
    
    try:
        with source as s:
            if gui:
                safe_gui_update(lambda: gui.log_command("[Calibrating for 5 seconds - PLEASE BE SILENT...]"))
                safe_gui_update(lambda: gui.update_mic_status(True))
            
            # FIX: Longer calibration (5s) for noisy environments
            recognizer.adjust_for_ambient_noise(s, duration=5.0)
            
            # FIX: Removed forced ceiling — let calibration decide.
            # Only clamp extreme outliers so recognition still works in very noisy rooms.
            if recognizer.energy_threshold > 600:
                recognizer.energy_threshold = 500
                if gui:
                    safe_gui_update(lambda: gui.log_command("[Very noisy environment — capping threshold at 500]"))
            elif recognizer.energy_threshold < 80:
                recognizer.energy_threshold = 120
                if gui:
                    safe_gui_update(lambda: gui.log_command("[Very quiet environment — raising threshold to 120]"))
            
            if gui:
                safe_gui_update(lambda: gui.log_command(f"[Calibration Complete. Energy: {recognizer.energy_threshold:.0f}]"))
                safe_gui_update(lambda: gui.log_command("[TIPS: Speak clearly, 6 inches from mic, moderate volume]"))
                safe_gui_update(lambda: gui.update_mic_status(False))
            
            speak("Calibration complete. I'm listening. Speak clearly.")
            
            while True:
                try:
                    if gui:
                        safe_gui_update(lambda: gui.update_mic_status(True))
                    
                    # Listen with shorter timeout for responsiveness
                    safe_gui_update(lambda: gui.log_command("[Listening...]"))
                    
                    audio = recognizer.listen(s, timeout=None, phrase_time_limit=10)  # FIX: was 6 — longer for Urdu sentences
                    
                    if gui:
                        safe_gui_update(lambda: gui.update_mic_status(False))
                        safe_gui_update(lambda: gui.log_command("[Processing speech...]"))
                    
                    # FIX: Try Urdu (Pakistan) first, fall back to English
                    # This dramatically improves recognition of Urdu/Hindi words
                    try:
                        user_text = recognizer.recognize_google(audio, language="ur-PK").lower()
                    except sr.UnknownValueError:
                        try:
                            user_text = recognizer.recognize_google(audio, language="en-US").lower()
                        except sr.UnknownValueError:
                            raise sr.UnknownValueError()
                    intent = get_intent(user_text)
                    
                    if intent:
                        # Send to GUI for display
                        if gui:
                            gui.queue_voice_command(user_text, intent)
                        
                        # Handle special non-tool commands
                        if intent in ["GREETING", "STATUS"]:
                            # These don't control Blender, just respond verbally
                            response = get_jarvis_response(intent, user_text)
                            speak(response)
                        else:
                            # Send tool command to Blender
                            with open(COMMAND_FILE, "w") as f:
                                f.write(intent)
                            
                            # Voice response with confirmation
                            response = get_jarvis_response(intent, user_text)
                            speak(response)
                    else:
                        if gui:
                            safe_gui_update(lambda: gui.log_command(f"[?] Unrecognized: '{user_text}'"))
                            safe_gui_update(lambda: gui.log_command("[TIP] Try: hammer, wrench, sword, break, repair, or say 'hi jarvis'"))
                            
                except sr.UnknownValueError:
                    # Speech was unintelligible - this is normal when no speech
                    if gui:
                        safe_gui_update(lambda: gui.update_mic_status(False))
                    pass
                except sr.WaitTimeoutError:
                    # Timeout - no speech detected
                    safe_gui_update(lambda: gui.update_mic_status(False))
                    pass
                except sr.RequestError as e:
                    if gui:
                        safe_gui_update(lambda: gui.log_command(f"[!] Google Speech API error: {e}"))
                    speak("I'm having trouble connecting to the speech recognition service.")
                except Exception as e:
                    if gui:
                        safe_gui_update(lambda: gui.log_command(f"[ERROR] {e}"))
                        safe_gui_update(lambda: gui.update_mic_status(False))
    except Exception as e:
        error_msg = f"Fatal error: {e}"
        if gui:
            safe_gui_update(lambda: gui.log_command(f"[ERROR] {error_msg}"))
        speak("I've encountered a critical error and need to shut down.")

def get_jarvis_response(intent, command_text=""):
    """Get JARVIS voice response for a command with personality"""
    import random
    
    # Greeting responses - varied and personable
    if intent == "GREETING":
        greetings = [
            "Hello sir. Jarvis at your service.",
            "Good day sir. I am online and ready.",
            "Hello! Always a pleasure. How may I assist you?",
            "Hi there! Jarvis is listening and ready for commands.",
            "Greetings sir. The suit is powered and ready.",
            "Hello! I am Jarvis, your AI assistant. What would you like me to do?",
            "Salam sir. I am operational and awaiting your commands.",
            "Namaste! Jarvis is online and ready to help."
        ]
        return random.choice(greetings)
    
    # Status check responses
    if intent == "STATUS":
        status_responses = [
            "All systems are functioning at optimal capacity sir. Ready for your commands.",
            "Systems nominal. Microphone active. Speech recognition online. Ready to serve.",
            "I am fully operational sir. All systems green. Awaiting your instructions.",
            "Jarvis online and operational. Speech engine active. Nanotech systems standing by.",
            "All diagnostics complete. I am ready sir. Please issue a command."
        ]
        return random.choice(status_responses)
    
    # Standard command responses with "Command accepted" confirmation
    responses = {
        "HAMMER": "Command accepted. Deploying hammer interface. Smash mode activated.",
        "WRENCH": "Command accepted. Wrench configuration loaded. Repair protocols engaged.",
        "SWORD": "Command accepted. Sword mode active. Combat systems online.",
        "SCREWDRIVER": "Command accepted. Screwdriver tool selected. Precision mode engaged.",
        "IDLE": "Command accepted. Returning to base configuration. Systems standing by.",
        "BIGGER": "Command accepted. Increasing scale. Size augmentation in progress.",
        "SMALLER": "Command accepted. Decreasing scale. Miniaturization engaged.",
        "BREAK": "Command accepted. Warning. Initiating controlled demolition sequence.",
        "REPAIR": "Command accepted. Repair sequence initiated. Restoring functionality.",
        "REGENERATE": "Command accepted. Initiating full system regeneration. All systems restoring to optimal performance."
    }
    
    return responses.get(intent, f"Command accepted. {intent} acknowledged.")

def get_confirmation_message():
    """Get a random command acceptance confirmation"""
    import random
    confirmations = [
        "Command accepted.",
        "Acknowledged sir.",
        "As you wish sir.",
        "At once sir.",
        "Very good sir.",
        "Affirmative.",
        "Executing now.",
        "Right away sir."
    ]
    return random.choice(confirmations)

if __name__ == "__main__":
    jarvis_main()