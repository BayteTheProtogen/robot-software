from pathlib import Path
import sys
import time

_PROJECT_ROOT = Path(__file__).resolve().parent
_VENV_SITE_PACKAGES = _PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if _VENV_SITE_PACKAGES.exists():
    sys.path.insert(0, str(_VENV_SITE_PACKAGES))

import pygame
import serial


def parse_telemetry_line(line):
    line = line.strip().strip(";")
    if not line:
        return None

    data = {}
    for chunk in line.split(";"):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in ("batVol", "batPct"):
            try:
                data[key] = float(value)
            except ValueError:
                data[key] = value
        elif key == "temp":
            try:
                data[key] = int(float(value))
            except ValueError:
                data[key] = value
        else:
            data[key] = value

    if "mac" not in data:
        return None
    return data


def clear_terminal():
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")


def format_telemetry_block(telemetry_by_mac, recent_invalid_lines):
    lines = []
    lines.append("Incoming telemetry")
    lines.append("MAC                | batVol | batPct | temp")
    lines.append("-------------------+--------+--------+------")

    if telemetry_by_mac:
        for mac, data in telemetry_by_mac.items():
            bat_vol = data.get("batVol", "-")
            bat_pct = data.get("batPct", "-")
            temp = data.get("temp", "-")
            lines.append(
                f"{mac:17} | {bat_vol:6.2f} | {bat_pct:6.2f} | {temp:4}"
                if isinstance(bat_vol, (int, float)) and isinstance(bat_pct, (int, float))
                else f"{mac:17} | {bat_vol!s:6} | {bat_pct!s:6} | {temp!s:4}"
            )
    else:
        lines.append("Waiting for telemetry...")

    if recent_invalid_lines:
        lines.append("")
        lines.append("Unreadable lines")
        for entry in recent_invalid_lines[-3:]:
            lines.append(f"- {entry}")

    return lines


def render_dashboard(serial_port, joystick_count, payload, axes_debug_str, telemetry_by_mac, recent_invalid_lines):
    clear_terminal()
    lines = [
        "Joycony live monitor",
        f"Serial: {'connected on ' + serial_port_label if serial_port and serial_port.is_open else 'demo mode'}",
        f"Controllers: {joystick_count}",
        f"Outgoing: {payload.strip()}",
    ]
    if axes_debug_str:
        lines.append(f"Debug:{axes_debug_str}")
    lines.append("")
    lines.extend(format_telemetry_block(telemetry_by_mac, recent_invalid_lines))
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()

# ==========================================
# KONFIGURACJA PORTU SZEREGOWEGO
# Zmień poniższą ścieżkę na swój rzeczywisty port ESP32!
# ==========================================
SERIAL_PORT = r'\\.\COM10'
BAUD_RATE = 115200

ser = None
serial_port_label = SERIAL_PORT
last_serial_error = None

if not hasattr(serial, "Serial"):
    raise RuntimeError(
        "Loaded the wrong 'serial' package. Install 'pyserial' in the workspace venv or run the script with the venv Python."
    )

for candidate_port in (SERIAL_PORT, 'COM10'):
    try:
        ser = serial.Serial(candidate_port, BAUD_RATE, timeout=0.1)
        serial_port_label = candidate_port
        print(f"Połączono z ESP32 na porcie {candidate_port}")
        break
    except Exception as e:
        last_serial_error = e

if ser is None:
    print(f"Nie udało się otworzyć portu szeregowego: {last_serial_error}")
    print("Uruchamiam w trybie demonstracyjnym (bez wysyłania do ESP32).")

# Inicjalizacja Pygame
pygame.init()
pygame.joystick.init()

print("\nSzukam podłączonych kontrolerów...")
clock = pygame.time.Clock()

try:
    telemetry_by_mac = {}
    recent_invalid_lines = []
    last_render_time = 0.0
    render_interval = 0.2

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

        if ser and ser.is_open:
            try:
                while ser.in_waiting:
                    incoming_line = ser.readline().decode("utf-8", errors="ignore").strip()
                    parsed = parse_telemetry_line(incoming_line)
                    if parsed:
                        telemetry_by_mac[parsed["mac"]] = parsed
                        recent_invalid_lines.clear()
                    elif incoming_line:
                        recent_invalid_lines.append(incoming_line)
                        if len(recent_invalid_lines) > 5:
                            recent_invalid_lines.pop(0)
            except Exception as e:
                recent_invalid_lines.append(f"Serial read error: {e}")
                if len(recent_invalid_lines) > 5:
                    recent_invalid_lines.pop(0)
        
        # Wysyłanie przez port szeregowy
        if ser and ser.is_open:
            try:
                ser.write(payload.encode('utf-8'))
            except Exception as e:
                print(f"\nBłąd transmisji: {e}")
                break

        current_time = time.time()
        if current_time - last_render_time >= render_interval:
            render_dashboard(ser, joystick_count, payload, axes_debug_str, telemetry_by_mac, recent_invalid_lines)
            last_render_time = current_time
                
        # 50 Hz (próbkowanie co 20 ms)
        clock.tick(20)

except KeyboardInterrupt:
    print("\nZakończono działanie programu.")
finally:
    if ser:
        ser.close()
    pygame.quit()
