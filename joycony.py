import pygame
import serial
import time
import sys

# ==========================================
# KONFIGURACJA PORTU SZEREGOWEGO
# Zmień poniższą ścieżkę na swój rzeczywisty port ESP32!
# ==========================================
SERIAL_PORT = '/dev/cu.usbmodem101'  
BAUD_RATE = 115200

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"Połączono z ESP32 na porcie {SERIAL_PORT}")
except Exception as e:
    print(f"Nie udało się otworzyć portu szeregowego: {e}")
    print("Uruchamiam w trybie demonstracyjnym (bez wysyłania do ESP32).")
    ser = None

# Inicjalizacja Pygame
pygame.init()
pygame.joystick.init()

print("\nSzukam podłączonych kontrolerów...")
clock = pygame.time.Clock()

try:
    while True:
        pygame.event.pump()
        
        joystick_count = pygame.joystick.get_count()
        
        # Inicjalizacja domyślnych wartości
        x1, y1 = 0, 0
        x2, y2 = 0, 0
        axes_debug_str = ""
        
        if joystick_count == 1:
            # Sytuacja, w której macOS połączył oba Joy-Cony w JEDEN kontroler
            joy = pygame.joystick.Joystick(0)
            if not joy.get_init():
                joy.init()
                
            num_axes = joy.get_numaxes()
            
            # 1. Odczyt lewego Joy-Cona (Oś 0 i Oś 1)
            x1 = int(joy.get_axis(0) * 50)
            y1 = int(joy.get_axis(1) * -30)
            if(y1<22 and y1>-22):
                y1=0
            if(x1<22 and x1>-22):
                x1=0
 
            
            # 2. Odczyt prawego Joy-Cona
            # Zazwyczaj macOS mapuje go na Oś 2 (X) i Oś 3 (Y).
            # Zabezpieczamy kod przed błędem indexu, sprawdzając liczbę osi.
            x2 = int(joy.get_axis(2) * 50) if num_axes > 2 else 0
            y2 = int(joy.get_axis(3) * 30) if num_axes > 3 else 0
            if(y2<22 and y2>-22):
                y2=0
            if(x2<22 and x2>-22):
                x2=0


            # PRZYDATNY DEBUG: Odczytujemy pierwsze 6 osi na żywo w konsoli.
            # Jeśli ruszysz prawym drążkiem i zobaczysz, że zmieniają się np. wartości osi 3 i 4
            # zamiast 2 i 3, zmień numery osi powyżej!
            axes_values = [round(joy.get_axis(i), 2) for i in range(min(num_axes, 6))]
            axes_debug_str = f" | Osie na żywo: {axes_values}"

        elif joystick_count > 1:
            # Sytuacja awaryjna: gdyby z jakiegoś powodu system widział je jako 2 osobne kontrolery
            joy1 = pygame.joystick.Joystick(0)
            joy2 = pygame.joystick.Joystick(1)
            
            if not joy1.get_init(): joy1.init()
            if not joy2.get_init(): joy2.init()
                
            x1 = int(joy1.get_axis(0) * 100)
            y1 = int(joy1.get_axis(1) * 100)
            x2 = int(joy2.get_axis(0) * 100)
            y2 = int(joy2.get_axis(1) * 100)

        # Budujemy ramkę danych dla ESP32: "x1,y1,x2,y2\n"
        payload = f"{x1},{y1},{x2},{y2}\n"
        
        # Wypisujemy w konsoli Maca wysyłany pakiet oraz stan wszystkich osi
        sys.stdout.write(f"\rWysyłam do ESP: {payload.strip()} (Wykryto urządzeń: {joystick_count}){axes_debug_str}      ")
        sys.stdout.flush()
        
        # Wysyłanie przez port szeregowy
        if ser and ser.is_open:
            try:
                ser.write(payload.encode('utf-8'))
            except Exception as e:
                print(f"\nBłąd transmisji: {e}")
                break
                
        # 50 Hz (próbkowanie co 20 ms)
        clock.tick(20)

except KeyboardInterrupt:
    print("\nZakończono działanie programu.")
finally:
    if ser:
        ser.close()
    pygame.quit()
