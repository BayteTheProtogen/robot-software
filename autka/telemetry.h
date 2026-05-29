#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_err.h>
#include <math.h>

#define batteryPin 35 //gpio
#define bateryMinLevel 3.7 // in volts
#define batteryDeviderR1 5100 // in ohms
#define batteryDeviderR2 2000 // in ohms
#define batteryMinVoltage 7.0 // in volts, for 2S LiPo, 7.0v

//#define telemetryDeguging

#define telemetryLoopDelay 100 // in ms
extern uint8_t broadcastAddress[6];
extern bool stopMotors; 
void setupTelemetryAndBatteryMonitoring();
void mainTelemetryLoop(void *pvParameters);
void SendEspNowString(const String &message);
uint8_t getBatteryPercent(float voltage);

struct LiPoPoint {
    float voltage;
    uint8_t percent;
};


