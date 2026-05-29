#include <esp_now.h>
#include <WiFi.h>
#include "telemetry.h"
// Definicja pinów mostka H (IN1-IN4)
const int IN1 = 15; // Lewy silnik w przód
const int IN2 = 2;  // Lewy silnik w tył
const int IN3 = 4;  // Prawy silnik w przód
const int IN4 = 16; // Prawy silnik w tył

// Struktura do odbierania danych
typedef struct struct_message {
    int x;
    int y;
} struct_message;

struct_message incomingJoy;

// ===================================================================
// ZMIANA SYGNATURY DLA ESP32 CORE 3.x:
// Pierwszym parametrem musi być wskaźnik na strukturę 'esp_now_recv_info'
// ===================================================================
void OnDataRecv(const uint8_t *mac, const uint8_t *incomingData, int len) {
  memcpy(&incomingJoy, incomingData, sizeof(incomingJoy));
  // ===================================================================
  // DOPASOWANIE POZIOMEGO JOY-CONA:
  // Ponieważ Joy-Con trzymany jest poziomo, osie X i Y są obrócone.
  // Poniższe mapowanie zakłada, że trzymasz Joy-Con poziomo (drążek po lewej lub prawej).
  // Jeśli autko skręca zamiast jechać prosto, zamień wartości przypisane do 'forward' i 'turn'
  // lub dodaj/usuń minusy, aby zmienić kierunki.
  // ===================================================================
  int forward = -incomingJoy.y;  // Ruch przód / tył
  int turn = incomingJoy.x;     // Skręt lewo / prawo
  
  // Przeliczenie wartości (-100 do 100) na sygnał PWM (-255 do 255)
  int speed = forward * 2.55;
  int steer = turn * 2.55;

  // Miksowanie napędu (Arcade Drive) dla dwóch silników
  int leftSpeed = speed + steer;
  int rightSpeed = speed - steer;

  // Ograniczenie wartości do dopuszczalnego zakresu PWM
  leftSpeed = constrain(leftSpeed, -255, 255);
  rightSpeed = constrain(rightSpeed, -255, 255);

  // Sterowanie silnikami
  controlMotors(leftSpeed, rightSpeed);
}

void setup() {
  Serial.begin(115200);

  // Konfiguracja pinów jako wyjścia
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  // Zatrzymanie silników na starcie
  controlMotors(0, 0);

  // Uruchomienie Wi-Fi w trybie Station
  WiFi.mode(WIFI_STA);

  // Inicjalizacja ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Blad inicjalizacji ESP-NOW");
    return;
  }

  // Rejestracja funkcji odbiorczej (teraz przejdzie kompilację pomyślnie)
  esp_now_register_recv_cb(OnDataRecv);
  setupTelemetryAndBatteryMonitoring();
  Serial.println("Odbiornik ESP-NOW gotowy...");
}

void loop() {
  delay(100);
}

// Funkcja pomocnicza do bezpośredniego sterowania mostkiem H (IN1-IN4)
void controlMotors(int left, int right) {
  if (stopMotors) {
    left = 0;
    right = 0;
  }
  // LEWY SILNIK
  if (left >= 0) {
    analogWrite(IN1, left);
    analogWrite(IN2, 0);
  } else {
    analogWrite(IN1, 0);
    analogWrite(IN2, -left); // Podanie wartości dodatniej dla biegu wstecznego
  }

  // PRAWY SILNIK
  if (right >= 0) {
    analogWrite(IN3, right);
    analogWrite(IN4, 0);
  } else {
    analogWrite(IN3, 0);
    analogWrite(IN4, -right);
  }
}
