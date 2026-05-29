#include <esp_now.h>
#include <WiFi.h>

// =======================================================
// ADRESY MAC AUTEK
// =======================================================
uint8_t mac_autko1[] = {0xD4, 0xE9, 0xF4, 0x77, 0xFC, 0xF8}; 
uint8_t mac_autko2[] = {0xD4, 0xE9, 0xF4, 0x77, 0xB0, 0x18}; 

// =======================================================
// KONFIGURACJA PINÓW
// =======================================================
const int ESTOP_PIN = 17;
const int BLUE_BTN_PIN = 16;

// =======================================================
// ZMIENNE STANU (SOFTWARE LATCH)
// =======================================================
bool isArmed = false;         
bool isEStopLocked = false;   // Software Latch dla E-STOP'a
bool lastBlueBtnState = HIGH; 

typedef struct struct_message {
    int x;
    int y;
} struct_message;

struct_message joy1_data;
struct_message joy2_data;

// Funkcja pomocnicza do wysyłania 0,0 do autek
void sendStopCommand() {
  joy1_data.x = 0; joy1_data.y = 0;
  joy2_data.x = 0; joy2_data.y = 0;
  esp_now_send(mac_autko1, (uint8_t *) &joy1_data, sizeof(joy1_data));
  esp_now_send(mac_autko2, (uint8_t *) &joy2_data, sizeof(joy2_data));
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(2); 

  pinMode(ESTOP_PIN, INPUT_PULLUP);
  pinMode(BLUE_BTN_PIN, INPUT_PULLUP);

  WiFi.mode(WIFI_STA);

  if (esp_now_init() != ESP_OK) {
    Serial.println("Blad inicjalizacji ESP-NOW");
    return;
  }

  esp_now_peer_info_t peerInfo1 = {}; 
  memcpy(peerInfo1.peer_addr, mac_autko1, 6);
  peerInfo1.channel = 0;  
  peerInfo1.encrypt = false;
  peerInfo1.ifidx = WIFI_IF_STA;
  esp_now_add_peer(&peerInfo1);

  esp_now_peer_info_t peerInfo2 = {}; 
  memcpy(peerInfo2.peer_addr, mac_autko2, 6);
  peerInfo2.channel = 0;  
  peerInfo2.encrypt = false;
  peerInfo2.ifidx = WIFI_IF_STA;
  esp_now_add_peer(&peerInfo2);
  
  neopixelWrite(RGB_BUILTIN, 0, 0, 0);
  delay(2000); 
  Serial.println("\n--- SYSTEM HOST S3 URUCHOMIONY ---");
}

void loop() {
  // 1. ODCZYT STANÓW FIZYCZNYCH Z PINÓW
  // Jeśli grzyb jest wciśnięty, pin jest zwierany do masy (LOW)
  bool isEStopPressed = (digitalRead(ESTOP_PIN) == HIGH);
  bool currentBlueBtnState = digitalRead(BLUE_BTN_PIN);

  // 2. ZATRZASK E-STOP (SOFTWARE LATCH)
  // Nawet jeśli E-STOP zaraz odskoczy, system zatrzaśnie błąd
  if (isEStopPressed && !isEStopLocked) {
    isEStopLocked = true;
    isArmed = false; // Rozbrój automatycznie
    sendStopCommand(); // Wyślij natychmiastowe zatrzymanie do autek
    Serial.println(">>> E-STOP WCIŚNIĘTY! ZATRZYMANIE AWARYJNE! <<<");
  }

  // 3. LOGIKA NIEBIESKIEGO PRZYCISKU
  if (currentBlueBtnState == LOW && lastBlueBtnState == HIGH) {
    delay(50); // Debouncing (eliminacja drgań styków)
    if (digitalRead(BLUE_BTN_PIN) == LOW) {
      
      if (isEStopLocked) {
        // A. KASOWANIE BŁĘDU E-STOP
        // Jeśli E-STOP fizycznie odskoczył, pozwól na jego odblokowanie
        if (!isEStopPressed) {
          isEStopLocked = false;
          Serial.println("Błąd awaryjny skasowany. System ROZBROJONY (czuwa).");
        } else {
          Serial.println("Nie można skasować! Prawdopodobnie trzymasz wciśnięty E-STOP!");
        }
      } else {
        // B. NORMALNE PRZEŁĄCZANIE: Rozbrojony <-> Uzbrojony
        isArmed = !isArmed;
        Serial.printf("Zmieniono tryb. System: %s\n", isArmed ? "UZBROJONY (WALKA)" : "ROZBROJONY");
      }
    }
  }
  lastBlueBtnState = currentBlueBtnState;

  // 4. OBSŁUGA NEOPIXELA ZALEŻNIE OD STANU MASZYNY
  if (isEStopLocked) {
    // E-STOP Zatrzaśnięty: Miga szybko na czerwono
    if ((millis() / 150) % 2 == 0) {
      neopixelWrite(RGB_BUILTIN, 255, 0, 0); 
    } else {
      neopixelWrite(RGB_BUILTIN, 0, 0, 0);   
    }
  } else if (!isArmed) {
    // System bezpieczny, rozbrojony: Stały ŻÓŁTY
    neopixelWrite(RGB_BUILTIN, 128, 64, 0); 
  } else {
    // System uzbrojony, walka: Stały ZIELONY
    neopixelWrite(RGB_BUILTIN, 0, 255, 0);  
  }

  // 5. PRZESYŁANIE DANYCH DO AUTEK (Tylko najświeższy pakiet)
  String lastPacket = "";
  while (Serial.available() > 0) {
    lastPacket = Serial.readStringUntil('\n'); 
  }
  
  if (lastPacket.length() > 0) {
    int t_x1, t_y1, t_x2, t_y2;
    int parsed = sscanf(lastPacket.c_str(), "%d,%d,%d,%d", &t_x1, &t_y1, &t_x2, &t_y2);
    
    if (parsed == 4) {
      // Zabezpieczenie: wysyłamy ruch TYLKO, gdy system jest UZBROJONY i NIE jest zablokowany
      if (isEStopLocked || !isArmed) {
        joy1_data.x = 0; joy1_data.y = 0;
        joy2_data.x = 0; joy2_data.y = 0;
      } else {
        joy1_data.x = t_x1; joy1_data.y = t_y1;
        joy2_data.x = t_x2; joy2_data.y = t_y2;
      }
      esp_now_send(mac_autko1, (uint8_t *) &joy1_data, sizeof(joy1_data));
      esp_now_send(mac_autko2, (uint8_t *) &joy2_data, sizeof(joy2_data));
    }
  }
}
