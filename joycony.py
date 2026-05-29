import sys
import time
from pathlib import Path

# Automatyczne wsparcie dla wirtualnego środowiska (.venv) na macOS oraz Windows
_PROJECT_ROOT = Path(__file__).resolve().parent
_VENV_SITE_PACKAGES_WIN = _PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
_VENV_SITE_PACKAGES_MAC = (
    _PROJECT_ROOT
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)

if _VENV_SITE_PACKAGES_WIN.exists():
    sys.path.insert(0, str(_VENV_SITE_PACKAGES_WIN))
elif _VENV_SITE_PACKAGES_MAC.exists():
    sys.path.insert(0, str(_VENV_SITE_PACKAGES_MAC))

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
    lines.append(" Odbierana Telemetria z Autek:")
    lines.append(" MAC                | batVol | batPct | temp")
    lines.append(" -------------------+--------+--------+------")

    if telemetry_by_mac:
        for mac, data in telemetry_by_mac.items():
            bat_vol = data.get("batVol", "-")
            bat_pct = data.get("batPct", "-")
            temp = data.get("temp", "-")

            # Kolorowanie krytycznego stanu baterii
            lvc_warning = ""
            if isinstance(bat_vol, (int, float)) and bat_vol <= 7.0:
                lvc_warning = " [!!! LVC !!!]"

            lines.append(
                f" {mac:17} | {bat_vol:6.2f}V| {bat_pct:5.1f}% | {temp:3}°C{lvc_warning}"
                if isinstance(bat_vol, (int, float))
                and isinstance(bat_pct, (int, float))
                else f" {mac:17} | {bat_vol!s:6} | {bat_pct!s:6} | {temp!s:4}"
            )
    else:
        lines.append(" Oczekiwanie na telemetrie przez ESP-NOW...")

    if recent_invalid_lines:
        lines.append("")
        lines.append(" Nieczytelne pakiety z portu:")
        for entry in recent_invalid_lines[-2:]:
            lines.append(f" - {entry[:70]}")

    return lines


def render_dashboard(
    serial_port,
    joystick_count,
    payload,
    axes_debug_str,
    telemetry_by_mac,
    recent_invalid_lines,
    mode_name,
):
    clear_terminal()
    ser_status = "CONNECTED" if serial_port and serial_port.is_open else "DEMO MODE"
    lines = [
        "==========================================================================",
        "                S3 BROADCASTER CONTROL CENTER - DUAL ROBOTS               ",
        "==========================================================================",
        f" Broadcaster Port: {SERIAL_PORT:<22} | Status: {ser_status}",
        f" Wspolny Tryb Jazdy: {mode_name:<20} | Pady:   {joystick_count}",
        f" Ostatnia ramka USB: {payload.strip()}",
    ]
    if axes_debug_str:
        lines.append(f" Stan osi fizycznych:{axes_debug_str}")
    lines.append(
        "--------------------------------------------------------------------------"
    )
    lines.extend(format_telemetry_block(telemetry_by_mac, recent_invalid_lines))
    lines.append(
        "=========================================================================="
    )
    lines.append(
        " Zmiana trybu: Klikaj boczne triggery (L/R/ZL/ZR) | Wyjscie: [Ctrl + C]"
    )
    lines.append(
        "=========================================================================="
    )
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


# ==========================================
# KONFIGURACJA PORTU SZEREGOWEGO (macOS)
# ==========================================
SERIAL_PORT = "/dev/cu.usbmodem101"
BAUD_RATE = 115200

ser = None
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.001, write_timeout=0.01)
    print(f"Połączono z ESP32 na porcie {SERIAL_PORT}")
except Exception as e:
    print(f"Nie udało się otworzyć portu szeregowego: {e}")
    print("Uruchamiam w trybie demonstracyjnym (bez wysyłania do ESP32).")

# Inicjalizacja Pygame (Headless)
pygame.init()
pygame.joystick.init()
clock = pygame.time.Clock()

steering_modes = ["ARCADE", "TANK", "SMOOTH"]
current_mode_idx = 0
last_button_states = {}

try:
    telemetry_by_mac = {}
    recent_invalid_lines = []
    last_render_time = 0.0
    render_interval = 0.2  # Odświeżanie ekranu 5 razy na sekundę

    while True:
        # PUMP - bezpieczna aktualizacja osi bez błędu KeyError: 1
        pygame.event.pump()

        joystick_count = pygame.joystick.get_count()

        # Surowe wartości wejściowe
        x1_a, y1_a = 0, 0
        x1_b, y1_b = 0, 0
        axes_debug_str = ""

        if joystick_count == 1:
            joy = pygame.joystick.Joystick(0)
            if not joy.get_init():
                joy.init()

            num_axes = joy.get_numaxes()
            num_btns = joy.get_numbuttons()

            # Odczyt fizycznych drążków (Twoje sprawdzone mnożniki)
            if num_axes > 1:
                x1_a = int(joy.get_axis(0) * 50)
                y1_a = int(joy.get_axis(1) * -30)
                if -22 < x1_a < 22:
                    x1_a = 0
                if -22 < y1_a < 22:
                    y1_a = 0

            if num_axes > 3:
                x1_b = int(joy.get_axis(2) * 50)
                y1_b = int(joy.get_axis(3) * 30)
                if -22 < x1_b < 22:
                    x1_b = 0
                if -22 < y1_b < 22:
                    y1_b = 0

            # Debug osi na żywo
            axes_values = [round(joy.get_axis(i), 2) for i in range(min(num_axes, 6))]
            axes_debug_str = f" {axes_values}"

            # Przełączanie trybów przyciskami (L/R/ZL/ZR)
            for b_idx in range(num_btns):
                state = joy.get_button(b_idx)
                if state and not last_button_states.get(b_idx, False):
                    if b_idx >= 4:  # Wyzwalacze boczne i przyciski funkcyjne
                        current_mode_idx = (current_mode_idx + 1) % len(steering_modes)
                last_button_states[b_idx] = state

        # --- MATEMATYKA TRYBÓW JAZDY (MIKSOWANIE W PYTHONIE) ---
        x_send_a, y_send_a = x1_a, y1_a
        x_send_b, y_send_b = x1_b, y1_b

        mode_name = steering_modes[current_mode_idx]

        if mode_name == "SMOOTH":
            # Redukcja czułości skrętu przy pełnej prędkości w przód/tył
            # Robot A
            speed_factor_a = abs(y1_a) / 30.0 if y1_a != 0 else 0
            sens_a = 0.6 * (1.0 - (speed_factor_a * 0.5))
            x_send_a = int(x1_a * sens_a)

            # Robot B
            speed_factor_b = abs(y1_b) / 30.0 if y1_b != 0 else 0
            sens_b = 0.6 * (1.0 - (speed_factor_b * 0.5))
            x_send_b = int(x1_b * sens_b)

        elif mode_name == "TANK" and joystick_count == 1:
            # Wirtualny Tank Mode (Używasz lewej gałki jako lewej gąsienicy, a prawej jako prawej)
            # Przeliczamy to na wirtualne osie Arcade dla Autka 1 (Autko 2 stoi w miejscu)
            virtual_forward = (y1_a + y1_b) / 2
            virtual_turn = (y1_a - y1_b) / 2

            x_send_a = int(virtual_turn)
            y_send_a = int(-virtual_forward)

            # Autko 2 nie jedzie w trybie tank
            x_send_b, y_send_b = 0, 0

        # Budujemy ramkę z dokładnie 4 wartościami (x1, y1, x2, y2), czyli tak, jak chce Broadcaster
        payload = f"{x_send_a},{y_send_a},{x_send_b},{y_send_b}\n"

        # Odczyt danych z portu szeregowego (Telemetria)
        if ser and ser.is_open:
            try:
                while ser.in_waiting:
                    incoming_line = (
                        ser.readline().decode("utf-8", errors="ignore").strip()
                    )
                    parsed = parse_telemetry_line(incoming_line)
                    if parsed:
                        telemetry_by_mac[parsed["mac"]] = parsed
                        recent_invalid_lines.clear()
                    elif incoming_line:
                        # Ignoruj systemowe wiadomości ESP32 przy starcie
                        if (
                            "SYSTEM" not in incoming_line
                            and "E-STOP" not in incoming_line
                        ):
                            recent_invalid_lines.append(incoming_line)
                            if len(recent_invalid_lines) > 5:
                                recent_invalid_lines.pop(0)
            except Exception as e:
                recent_invalid_lines.append(f"Serial read error: {e}")
                if len(recent_invalid_lines) > 5:
                    recent_invalid_lines.pop(0)

        # Wysyłanie sterowania przez port szeregowy
        if ser and ser.is_open:
            try:
                ser.write(payload.encode("utf-8"))
            except Exception as e:
                pass

            # Szybkie wyczyszczenie bufora zapisu
            try:
                ser.flush()
            except Exception:
                pass

        # Odświeżanie interfejsu (Dashboard) co 0.2s
        current_time = time.time()
        if current_time - last_render_time >= render_interval:
            render_dashboard(
                ser,
                joystick_count,
                payload,
                axes_debug_str,
                telemetry_by_mac,
                recent_invalid_lines,
                mode_name,
            )
            last_render_time = current_time

        # Pętla 50 Hz (próbkowanie co 20 ms dla najlepszej responsywności robotów)
        clock.tick(50)

except KeyboardInterrupt:
    print("\nZakończono działanie programu.")
finally:
    if ser:
        ser.close()
    pygame.quit()
