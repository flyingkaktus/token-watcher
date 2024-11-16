import tkinter as tk
from tkinter import ttk
import requests
import time
from time import sleep
from datetime import datetime
import threading
import webbrowser
from solders.pubkey import Pubkey
import solders.rpc.responses as responses
from solana.rpc.api import Client
from typing import Dict, Optional
import logging
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TokenMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Token Monitor")
        self.root.geometry("1000x800")
        
        # Definiere Pfade für Einstellungen und Cache
        self.settings_file = Path("token_monitor_settings.json")
        self.cache_file = Path("token_monitor_cache.json")
        
        # Parameter
        self.min_liquidity = tk.DoubleVar(value=0)
        self.max_liquidity = tk.DoubleVar(value=10000)
        self.min_volume = tk.DoubleVar(value=0)
        self.update_interval = tk.IntVar(value=120)
        self.max_display = tk.IntVar(value=3)
        self.max_token_age = tk.IntVar(value=24)
        self.tokens_found_var = tk.StringVar(value="Gefundene Token: 0")
        self.filtered_tokens_var = tk.StringVar(value="Nach Filter: 0")
        
        # Lade gespeicherte Einstellungen
        self.load_settings()
        
        # Solana Client mit Konfiguration initialisieren
        self.solana_client = Client(
            "https://api.mainnet-beta.solana.com",
            commitment="confirmed"
        )

        # Token Storage
        self.tokens = []
        self.running = False
        
        # Cache für Token-Erstellungsdaten
        self.creation_date_cache: Dict[str, Optional[datetime]] = {}
        
        # Lade gespeicherten Cache
        self.load_cache()
        
        self.setup_ui()
        
    def save_settings(self):
        """Speichere aktuelle Einstellungen"""
        settings = {
            'min_liquidity': self.min_liquidity.get(),
            'max_liquidity': self.max_liquidity.get(),
            'min_volume': self.min_volume.get(),
            'update_interval': self.update_interval.get(),
            'max_display': self.max_display.get(),
            'max_token_age': self.max_token_age.get()  # Neue Zeile
        }
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
            logging.info("Einstellungen gespeichert")
        except Exception as e:
            logging.error(f"Fehler beim Speichern der Einstellungen: {e}")

    def load_settings(self):
        """Lade gespeicherte Einstellungen"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    
                self.min_liquidity.set(settings.get('min_liquidity', 0))
                self.max_liquidity.set(settings.get('max_liquidity', 10000))
                self.min_volume.set(settings.get('min_volume', 0))
                self.update_interval.set(settings.get('update_interval', 120))
                self.max_display.set(settings.get('max_display', 3))
                self.max_token_age.set(settings.get('max_token_age', 24)) 
                
                logging.info("Einstellungen geladen")
            except Exception as e:
                logging.error(f"Fehler beim Laden der Einstellungen: {e}")

    def save_cache(self):
        """Speichere den Token-Erstellungsdaten-Cache"""
        try:
            # Konvertiere datetime Objekte zu Strings
            cache_to_save = {
                k: v.isoformat() if v else None 
                for k, v in self.creation_date_cache.items()
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_to_save, f, indent=2)  # indent=2 für bessere Lesbarkeit
            logging.info(f"Cache gespeichert mit {len(cache_to_save)} Einträgen")
        except Exception as e:
            logging.error(f"Fehler beim Speichern des Cache: {e}")

    def load_cache(self):
        """Lade den gespeicherten Cache"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    cached_data = json.load(f)
                    
                # Konvertiere Strings zurück zu datetime Objekten
                self.creation_date_cache = {
                    k: datetime.fromisoformat(v) if v else None 
                    for k, v in cached_data.items()
                }
                
                logging.info("Cache geladen")
            except Exception as e:
                logging.error(f"Fehler beim Laden des Cache: {e}")
        
    def setup_ui(self):
        # Parameter Frame (für Monitoring)
        param_frame = ttk.LabelFrame(self.root, text="Monitoring Parameter", padding=10)
        param_frame.pack(fill="x", padx=5, pady=5)
        
        # Liquidität Parameter
        liquidity_frame = ttk.LabelFrame(param_frame, text="Liquidität Filter", padding=5)
        liquidity_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(liquidity_frame, text="Min Liquidität ($):").grid(row=0, column=0, padx=5)
        ttk.Entry(liquidity_frame, textvariable=self.min_liquidity).grid(row=0, column=1, padx=5)
        
        ttk.Label(liquidity_frame, text="Max Liquidität ($):").grid(row=0, column=2, padx=5)
        ttk.Entry(liquidity_frame, textvariable=self.max_liquidity).grid(row=0, column=3, padx=5)
        
        # Volumen und Intervall Parameter
        other_frame = ttk.LabelFrame(param_frame, text="Weitere Monitoring Filter", padding=5)
        other_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(other_frame, text="Min 24h Volumen ($):").grid(row=0, column=0, padx=5)
        ttk.Entry(other_frame, textvariable=self.min_volume).grid(row=0, column=1, padx=5)
        
        ttk.Label(other_frame, text="Update Interval (s):").grid(row=0, column=2, padx=5)
        ttk.Entry(other_frame, textvariable=self.update_interval).grid(row=0, column=3, padx=5)
        
        ttk.Label(other_frame, text="Max. Anzahl Token:").grid(row=0, column=4, padx=5)
        ttk.Entry(other_frame, textvariable=self.max_display).grid(row=0, column=5, padx=5)
        
        # Control Buttons
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=5, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop Monitoring", command=self.stop_monitoring)
        self.stop_button.pack(side="left", padx=5)
        self.stop_button["state"] = "disabled"
        
        # Clear Cache Button
        self.clear_cache_button = ttk.Button(control_frame, text="Cache leeren", command=self.clear_cache)
        self.clear_cache_button.pack(side="left", padx=5)
        
        # Display Filter Frame (für bereits gefundene Token)
        display_filter_frame = ttk.LabelFrame(self.root, text="Anzeige Filter", padding=10)
        display_filter_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(display_filter_frame, text="Max. Token Alter (h):").pack(side="left", padx=5)
        ttk.Entry(display_filter_frame, textvariable=self.max_token_age, width=10).pack(side="left", padx=5)
        
        # Filter anwenden Button
        self.apply_filter_button = ttk.Button(display_filter_frame, text="Filter anwenden", 
                                            command=lambda: self.update_ui())
        self.apply_filter_button.pack(side="left", padx=5)
        
        # Stats Frame
        stats_frame = ttk.LabelFrame(self.root, text="Statistiken", padding=10)
        stats_frame.pack(fill="x", padx=5, pady=5)
        
        # Frame für die Statistiken
        stats_container = ttk.Frame(stats_frame)
        stats_container.pack()
        
        ttk.Label(stats_container, textvariable=self.tokens_found_var).grid(row=0, column=0, padx=5)
        ttk.Label(stats_container, textvariable=self.filtered_tokens_var).grid(row=0, column=1, padx=5)
        
        # Token List
        list_frame = ttk.LabelFrame(self.root, text="Token Liste", padding=10)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        columns = ("Name", "Liquidität", "24h Volumen", "Preis", "Erstellungsdatum", "Pump Warnung")
        self.token_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        column_widths = {
            "Name": 150,
            "Liquidität": 100,
            "24h Volumen": 100,
            "Preis": 100,
            "Erstellungsdatum": 150,
            "Pump Warnung": 150
        }
        
        for col, width in column_widths.items():
            self.token_tree.heading(col, text=col)
            self.token_tree.column(col, width=width)
                
        self.token_tree.pack(fill="both", expand=True)
        self.token_tree.bind("<Double-1>", self.show_token_details)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.token_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.token_tree.configure(yscrollcommand=scrollbar.set)
        
    def clear_cache(self):
        """Cache für Token-Erstellungsdaten leeren"""
        self.creation_date_cache.clear()
        if self.cache_file.exists():
            try:
                os.remove(self.cache_file)
            except Exception as e:
                logging.error(f"Fehler beim Löschen der Cache-Datei: {e}")
        logging.info("Cache wurde geleert")

    def get_token_creation_date(self, token_address: str) -> Optional[datetime]:
        """Hole das Erstellungsdatum eines Tokens von GeckoTerminal"""
        if token_address in self.creation_date_cache:
            return self.creation_date_cache[token_address]
        
        try:
            url = f"https://www.geckoterminal.com/solana/pools/{token_address}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            print(f"Requesting URL: {url}")
            response = requests.get(url, headers=headers)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Finde alle Span-Elemente und ihre Texte
                spans = soup.find_all('span')
                for i in range(len(spans) - 1):  # -1 weil wir immer das nächste Element auch prüfen
                    current_text = spans[i].text.strip()
                    next_text = spans[i + 1].text.strip()
                    
                    print(f"Checking: Current '{current_text}' - Next '{next_text}'")  # Debug
                    
                    if current_text == "Age":
                        print(f"Found Age, next value is: {next_text}")  # Debug
                        if 'months' in next_text or 'days' in next_text:
                            current_time = datetime.now()
                            if 'months' in next_text:
                                months = int(next_text.split()[0])
                                creation_date = current_time - timedelta(days=months*30)  # Approximation
                            else:
                                days = int(next_text.split()[0])
                                creation_date = current_time - timedelta(days=days)
                                
                            print(f"Calculated creation date: {creation_date}")  # Debug
                            self.creation_date_cache[token_address] = creation_date
                            self.save_cache()
                            return creation_date
            
            print("No age information found")
            return None
                
        except Exception as e:
            print(f"Full error: {str(e)}")
            logging.error(f"Fehler beim Abrufen des Creation Date von GeckoTerminal für {token_address}: {e}")
            return None
        
    def check_pump_warning(self, token: dict) -> str:
        """Prüfe auf Pump-Warnungen"""
        warnings = []
        
        if "pump" in token['base_token'].lower() or "pump" in token['quote_token'].lower():
            warnings.append("Pump in Adresse")
        
        if token['liquidity'] > 0 and token['volume24h'] / token['liquidity'] > 100:
            warnings.append("Hohes V/L Verhältnis")
            
        return ", ".join(warnings) if warnings else "Keine"
        
    def show_token_details(self, event):
        """Zeige detaillierte Token-Informationen"""
        selected_items = self.token_tree.selection()
        if not selected_items:
            return
            
        selected_item = selected_items[0]
        token = next((t for t in self.tokens if t["name"] == self.token_tree.item(selected_item)["values"][0]), None)
        
        if token:
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Token Details: {token['name']}")
            details_window.geometry("600x500")
            
            text = tk.Text(details_window, wrap=tk.WORD, padx=10, pady=10)
            text.pack(fill="both", expand=True)
            
            creation_date_str = token['creation_date'].strftime("%Y-%m-%d %H:%M") if token['creation_date'] else "Unbekannt"
            volume_liquidity_ratio = token['volume24h'] / token['liquidity'] if token['liquidity'] > 0 else 0
            
            details = f"""
Token Name: {token['name']}
Erstellungsdatum: {creation_date_str}
Liquidität: ${token['liquidity']:,.2f}
24h Volumen: ${token['volume24h']:,.2f}
Aktueller Preis: ${token['price']:,.6f}

Zusätzliche Metriken:
- Volumen/Liquidität Verhältnis: {volume_liquidity_ratio:.2f}
- Pump Warnung: {self.check_pump_warning(token)}

Token Adressen:
- Base Token: {token['base_token']}
- Quote Token: {token['quote_token']}

Raydium Pool Link:
https://raydium.io/swap/?inputCurrency={token['base_token']}&outputCurrency={token['quote_token']}
            """
            text.insert("1.0", details)
            text.config(state="disabled")
            
            def open_raydium():
                url = f"https://raydium.io/swap/?inputCurrency={token['base_token']}&outputCurrency={token['quote_token']}"
                webbrowser.open(url)
            
            ttk.Button(details_window, text="Auf Raydium öffnen", command=open_raydium).pack(pady=10)
    
    def get_new_tokens(self):
        """Hole neue Token-Daten von der Raydium API"""
        api_url = "https://api.raydium.io/v2/main/pairs"
        
        try:
            response = requests.get(api_url)
            pairs = response.json()
            
            filtered_pairs = [
                pair for pair in pairs 
                if (self.min_liquidity.get() <= pair['liquidity'] <= self.max_liquidity.get() and 
                    pair['volume24h'] > self.min_volume.get())
            ]
            
            interesting_tokens = []
            
            # Nur die ersten n Token entsprechend max_display verarbeiten
            for pair in filtered_pairs[:self.max_display.get()]:
                try:
                    # Füge Verzögerung zwischen Token-Abfragen hinzu
                    sleep(1)
                    creation_date = self.get_token_creation_date(pair['baseMint'])
                    
                    interesting_tokens.append({
                        'name': pair['name'],
                        'liquidity': round(pair['liquidity'], 2),
                        'volume24h': round(pair['volume24h'], 2),
                        'price': round(pair['price'], 6),
                        'base_token': pair['baseMint'],
                        'quote_token': pair['quoteMint'],
                        'creation_date': creation_date
                    })
                    
                    logging.info(f"Token {pair['name']} erfolgreich verarbeitet und im Cache gespeichert")
                    
                except Exception as e:
                    logging.error(f"Fehler bei der Verarbeitung von Token {pair['name']}: {e}")
                    continue
            
            return interesting_tokens
            
        except Exception as e:
            logging.error(f"Fehler beim Abrufen der Token: {e}")
            return None
    
    def update_ui(self):
        """Aktualisiere die UI mit den neuesten Token-Daten"""
        # Aktuelle Zeit für Altersvergleich
        current_time = datetime.now()
        max_age = timedelta(hours=self.max_token_age.get())
        
        # Filtere Token nach Alter
        filtered_tokens = [
            token for token in self.tokens 
            if token['creation_date'] and (current_time - token['creation_date']) <= max_age
        ]
        
        # Update Statistiken
        total_tokens = len(self.tokens)
        filtered_count = len(filtered_tokens)
        self.tokens_found_var.set(f"Gefundene Token: {total_tokens}")
        self.filtered_tokens_var.set(f"Nach Filter: {filtered_count}")
        
        # Clear tree
        for item in self.token_tree.get_children():
            self.token_tree.delete(item)
            
        # Update tree mit gefilterten Tokens
        for token in filtered_tokens:
            creation_date_str = token['creation_date'].strftime("%Y-%m-%d %H:%M") if token['creation_date'] else "Unbekannt"
            pump_warning = self.check_pump_warning(token)
            
            self.token_tree.insert("", "end", values=(
                token['name'],
                f"${token['liquidity']:,.2f}",
                f"${token['volume24h']:,.2f}",
                f"${token['price']:,.6f}",
                creation_date_str,
                pump_warning
            ))
    
    def monitoring_loop(self):
        """Hauptschleife für das Token-Monitoring"""
        while self.running:
            try:
                tokens = self.get_new_tokens()
                if tokens:
                    self.tokens = tokens
                    self.root.after(0, self.update_ui)
            except Exception as e:
                logging.error(f"Fehler in der Monitoring-Schleife: {e}")
            time.sleep(self.update_interval.get())
    
    def start_monitoring(self):
        """Starte das Token-Monitoring"""
        self.save_settings()  # Speichere aktuelle Einstellungen
        self.running = True
        self.start_button["state"] = "disabled"
        self.stop_button["state"] = "normal"
        threading.Thread(target=self.monitoring_loop, daemon=True).start()
        logging.info("Monitoring gestartet")
    
    def stop_monitoring(self):
        """Stoppe das Token-Monitoring"""
        self.running = False
        self.save_cache()  # Speichere Cache beim Beenden
        self.start_button["state"] = "normal"
        self.stop_button["state"] = "disabled"
        logging.info("Monitoring gestoppt")

if __name__ == "__main__":
    root = tk.Tk()
    app = TokenMonitor(root)
    root.mainloop()