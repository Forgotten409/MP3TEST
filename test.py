import os
import subprocess
import customtkinter as ctk
from customtkinter import CTkImage
from tkinter import filedialog, messagebox
import threading
from PIL import Image
import queue
import yt_dlp
import urllib.request
import webbrowser
import sys

# ========== KONFIGURACJA AKTUALIZACJI ==========
CURRENT_VERSION = "1.2" # Zwiększamy wersję po krytycznych poprawkach
VERSION_URL = "https://raw.githubusercontent.com/Forgotten409/MP3TEST/main/version.txt" 
DOWNLOAD_URL = "https://github.com/Forgotten409/MP3TEST/releases"
# ===============================================

TEST_MODE = False

try:
    import win32api, win32file
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False

# ------------------ Funkcje ------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def check_for_updates():
    if "TUTAJ_WKLEJ_LINK" in VERSION_URL: return
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=5) as response:
            latest_version = response.read().decode('utf-8').strip()
        
        if float(latest_version) > float(CURRENT_VERSION):
            if messagebox.askyesno("Dostępna aktualizacja!", f"Dostępna jest nowa wersja programu ({latest_version}).\nTwoja wersja to {CURRENT_VERSION}.\n\nCzy chcesz otworzyć stronę pobierania?"):
                webbrowser.open(DOWNLOAD_URL)
    except Exception as e:
        print(f"Nie udało się sprawdzić aktualizacji: {e}")

def get_downloads_folder():
    return os.path.join(os.path.expanduser("~"), "Downloads")

def find_pendrives():
    if TEST_MODE: return ["F:\\ (Test)", "G:\\ (Test)"]
    if not PYWIN32_AVAILABLE: return []
    drives = [d for d in win32api.GetLogicalDriveStrings().split('\000') if d]
    pendrives = [drive for drive in drives if win32file.GetDriveType(drive) == win32file.DRIVE_REMOVABLE]
    return pendrives

last_download_path = ""

def open_folder_with_file():
    global last_download_path
    if last_download_path and os.path.exists(last_download_path):
        subprocess.run(['explorer', '/select,', os.path.normpath(last_download_path)])
    elif last_download_path and os.path.exists(os.path.dirname(last_download_path)):
        os.startfile(os.path.dirname(last_download_path))

def download_youtube(url, output_path, format_choice, msg_queue):
    global last_download_path
    try:
        def progress_hook(d):
            if d['status'] == 'downloading':
                if total_bytes := d.get('total_bytes') or d.get('total_bytes_estimate'):
                    msg_queue.put(('progress', d.get('downloaded_bytes', 0) / total_bytes))
        
        ydl_opts = {'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'), 'noplaylist': True, 'progress_hooks': [progress_hook]}
        if format_choice == "mp3":
            ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]})
        else:
            ydl_opts.update({'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'})
            
        msg_queue.put(('status', 'Sprawdzam link, proszę czekać...'))
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'nieznany tytuł')
            final_path = ydl.prepare_filename(info)
            last_download_path = os.path.splitext(final_path)[0] + '.mp3' if format_choice == 'mp3' else final_path
            msg_queue.put(('status', f"Pobieram plik, to może potrwać chwilę..."))
            ydl.download([url])
        msg_queue.put(('status', 'Gotowe! Plik został zapisany.'))
        msg_queue.put(('done', f"Pobieranie '{title}' zakończone sukcesem!"))
    except Exception as e:
        msg_queue.put(('error', f"Wystąpił błąd: {e}"))

# ------------------ GUI ------------------
def start_download_thread():
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Błąd", "Najpierw wklej link z YouTube.")
        return
    
    output = folder_path.get() or get_downloads_folder()
    os.makedirs(output, exist_ok=True)
    
    open_folder_button.pack_forget()
    download_button.configure(state="disabled")
    progress_bar.set(0)
    status_label.configure(text="Rozpoczynam pracę...")
    
    threading.Thread(target=download_youtube, args=(url, output, format_var.get(), msg_queue), daemon=True).start()

def on_pendrive_select(choice):
    if choice == "Wybierz folder ręcznie...":
        if folder_selected := filedialog.askdirectory(): folder_path.set(folder_selected)
    elif "Test" in choice or ":" in choice:
        folder_path.set(choice.replace(" (Test)", ""))

def check_queue():
    try:
        while True:
            msg_type, msg_value = msg_queue.get_nowait()
            if msg_type == 'progress': progress_bar.set(msg_value)
            elif msg_type == 'status': status_label.configure(text=msg_value)
            elif msg_type in ['done', 'error']:
                root.bell()
                download_button.configure(state="normal")
                if msg_type == 'done':
                    messagebox.showinfo("Sukces", msg_value)
                    url_entry.delete(0, 'end')
                    open_folder_button.pack(side="left", expand=True, fill="x", padx=(10, 0))
                else:
                    status_label.configure(text="Coś poszło nie tak. Spróbuj ponownie.")
                    messagebox.showerror("Błąd", msg_value)
    except queue.Empty:
        pass
    root.after(100, check_queue)

# ---- Ustawienia GUI ----
ctk.set_appearance_mode("dark")
root = ctk.CTk()
root.title(f"Łatwy YouTube Downloader v{CURRENT_VERSION}")
root.geometry("700x750")
root.resizable(False, False)
try:
    # Ikona dla okna i paska zadań
    root.iconbitmap(resource_path("youtube_icon.ico"))
except Exception:
    print("Nie znaleziono pliku youtube_icon.ico.")

font_normal = ("Arial", 16)
font_big_bold = ("Arial", 20, "bold")
msg_queue = queue.Queue()
folder_path = ctk.StringVar(value=get_downloads_folder())
format_var = ctk.StringVar(value="mp3")

# *** KLUCZOWA POPRAWKA UKŁADU INTERFEJSU ***

# 1. Główna ramka, która pozwoli na scrollowanie, jeśli okno będzie za małe
main_frame = ctk.CTkScrollableFrame(root)
main_frame.pack(fill="both", expand=True)

# 2. Ramka z zawartością wewnątrz ramki scrollowanej
content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
content_frame.pack(fill="both", expand=True)

# 3. Dolna ramka na status, PRZYPIĘTA DO GŁÓWNEGO OKNA
status_frame = ctk.CTkFrame(root)
status_frame.pack(side="bottom", fill="x", padx=10, pady=10)
progress_bar = ctk.CTkProgressBar(status_frame)
progress_bar.set(0)
progress_bar.pack(fill="x", padx=10, pady=(5, 5))
status_label = ctk.CTkLabel(status_frame, text="Status: Czekam na zadanie", font=font_normal)
status_label.pack(fill="x", padx=10, pady=(0, 5))

# ---- Elementy GUI (teraz wewnątrz 'content_frame') ----
try:
    youtube_icon_pil = Image.open(resource_path("youtube_icon.png"))
    youtube_icon_ctk = CTkImage(light_image=youtube_icon_pil, dark_image=youtube_icon_pil, size=(80, 80))
    youtube_icon_label = ctk.CTkLabel(content_frame, image=youtube_icon_ctk, text="")
    youtube_icon_label.pack(pady=(15, 10))
except Exception as e:
    print(f"Błąd ładowania ikony w oknie: {e}")

ctk.CTkLabel(content_frame, text="Instrukcja:", font=font_big_bold).pack(pady=(10, 5), padx=25, anchor="w")
ctk.CTkLabel(content_frame, text="1. Wklej link z YouTube.\n2. Wybierz folder lub pendrive.\n3. Wybierz format (MP3 lub MP4).\n4. Naciśnij 'Pobierz Plik'.", font=("Arial", 14), justify="left").pack(pady=5, padx=25, anchor="w")

ctk.CTkLabel(content_frame, text="1. Link z YouTube:", font=font_big_bold).pack(pady=(20, 5), padx=25, anchor="w")
url_entry = ctk.CTkEntry(content_frame, placeholder_text="Tutaj wklej link", font=font_normal)
url_entry.pack(pady=5, padx=25, ipady=10, fill="x")

ctk.CTkLabel(content_frame, text="2. Miejsce zapisu:", font=font_big_bold).pack(pady=(20, 5), padx=25, anchor="w")
pendrive_options = find_pendrives()
options = pendrive_options + ["Wybierz folder ręcznie..."]
pendrive_menu = ctk.CTkOptionMenu(content_frame, values=options, command=on_pendrive_select, font=font_normal, dropdown_font=font_normal)
pendrive_menu.pack(pady=5, padx=25, fill="x")
if not pendrive_options: pendrive_menu.set("Nie wykryto pendrive'a")
else: pendrive_menu.set(f"Wykryto {len(pendrive_options)} pendrive'y - wybierz z listy")
folder_display = ctk.CTkEntry(content_frame, textvariable=folder_path, font=font_normal, state="readonly")
folder_display.pack(pady=5, padx=25, ipady=10, fill="x")

ctk.CTkLabel(content_frame, text="3. Format pliku:", font=font_big_bold).pack(pady=(20, 10), padx=25, anchor="w")
ctk.CTkRadioButton(content_frame, text="Tylko muzyka (MP3)", variable=format_var, value="mp3", font=font_normal).pack(padx=40, anchor="w")
ctk.CTkRadioButton(content_frame, text="Wideo z dźwiękiem (MP4)", variable=format_var, value="mp4", font=font_normal).pack(padx=40, anchor="w", pady=10)

ctk.CTkLabel(content_frame, text="4. Pobieranie:", font=font_big_bold).pack(pady=(20, 10), padx=25, anchor="w")
action_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
action_frame.pack(fill="x", padx=15, pady=10)
download_button = ctk.CTkButton(action_frame, text="Pobierz Plik", command=start_download_thread, height=60, font=font_big_bold, fg_color="#2E8B57", hover_color="#3CB371")
download_button.pack(side="left", expand=True, fill="x", padx=(10, 0))
open_folder_button = ctk.CTkButton(action_frame, text="Otwórz Folder z Plikiem", command=open_folder_with_file, height=60, font=font_big_bold)

# Uruchomienie sprawdzania aktualizacji i pętli GUI
threading.Thread(target=check_for_updates, daemon=True).start()
root.after(100, check_queue)
root.mainloop()