#include "telemetry.h"


TaskHandle_t mainTelemetryLoopHandle = nullptr;
uint8_t broadcastAddress[6] = {0xAC, 0xA7, 0x04, 0xEE, 0x5E, 0x50};

// 2S LiPo discharge curve (100% -> 0%)
// Approximation for resting voltage
const LiPoPoint lipo2S[] = {
    {8.40, 100},
    {8.39, 99},
    {8.38, 98},
    {8.37, 97},
    {8.36, 96},
    {8.35, 95},
    {8.34, 94},
    {8.33, 93},
    {8.32, 92},
    {8.31, 91},
    {8.30, 90},
    {8.29, 89},
    {8.28, 88},
    {8.27, 87},
    {8.26, 86},
    {8.25, 85},
    {8.24, 84},
    {8.23, 83},
    {8.22, 82},
    {8.21, 81},
    {8.20, 80},
    {8.19, 79},
    {8.18, 78},
    {8.17, 77},
    {8.16, 76},
    {8.15, 75},
    {8.14, 74},
    {8.13, 73},
    {8.12, 72},
    {8.11, 71},
    {8.10, 70},
    {8.09, 69},
    {8.08, 68},
    {8.07, 67},
    {8.06, 66},
    {8.05, 65},
    {8.04, 64},
    {8.03, 63},
    {8.02, 62},
    {8.01, 61},
    {8.00, 60},
    {7.99, 59},
    {7.98, 58},
    {7.97, 57},
    {7.96, 56},
    {7.95, 55},
    {7.94, 54},
    {7.93, 53},
    {7.92, 52},
    {7.91, 51},
    {7.90, 50},
    {7.89, 49},
    {7.88, 48},
    {7.87, 47},
    {7.86, 46},
    {7.85, 45},
    {7.84, 44},
    {7.83, 43},
    {7.82, 42},
    {7.81, 41},
    {7.80, 40},
    {7.79, 39},
    {7.78, 38},
    {7.77, 37},
    {7.76, 36},
    {7.75, 35},
    {7.74, 34},
    {7.73, 33},
    {7.72, 32},
    {7.71, 31},
    {7.70, 30},
    {7.69, 29},
    {7.68, 28},
    {7.67, 27},
    {7.66, 26},
    {7.65, 25},
    {7.64, 24},
    {7.63, 23},
    {7.62, 22},
    {7.61, 21},
    {7.60, 20},
    {7.58, 19},
    {7.56, 18},
    {7.54, 17},
    {7.52, 16},
    {7.50, 15},
    {7.48, 14},
    {7.46, 13},
    {7.44, 12},
    {7.42, 11},
    {7.40, 10},
    {7.36, 9},
    {7.32, 8},
    {7.28, 7},
    {7.24, 6},
    {7.20, 5},
    {7.16, 4},
    {7.12, 3},
    {7.08, 2},
    {7.04, 1},
    {7.00, 0}
};

const int lipo2SSize =
    sizeof(lipo2S) / sizeof(lipo2S[0]);
void setupTelemetryAndBatteryMonitoring(){
    analogReadResolution(12);
    analogSetPinAttenuation(batteryPin, ADC_11db); // 3.3v range
    adcAttachPin(batteryPin);
// Register the peer
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, broadcastAddress, 6);
    peerInfo.ifidx = WIFI_IF_STA;
    peerInfo.channel = 0;  
    peerInfo.encrypt = false;
    
    // Add peer        
    if (esp_now_add_peer(&peerInfo) != ESP_OK){
        Serial.println("Failed to add peer");
        return;
    }
    xTaskCreatePinnedToCore(
  mainTelemetryLoop,          // Task function.
    "telemetry",          // name of task.
      10000,          // Stack size of task
       NULL,          // parameter of the task
          1,          // priority of the task 0 - 3
     &mainTelemetryLoopHandle,          // Task handle to keep track of created task
         1);          // pin task to core X  
}
bool stopMotors = false;
void mainTelemetryLoop(void *pvParameters) {
    while (true) {
        float rawVoltage = analogRead(batteryPin) * (3.675 / 4095.0); 
        float batteryVoltage = rawVoltage * (batteryDeviderR1 + batteryDeviderR2) / batteryDeviderR2;

        float batteryPercent = getBatteryPercent(batteryVoltage);


        uint8_t temp = temperatureRead();
  
        #ifdef telemetryDeguging
        Serial.print("Internal Chip Temperature: ");
        Serial.print(temp);
        Serial.println(" °C");

        Serial.print("Battery Voltage: ");
        Serial.println(batteryVoltage);
        Serial.print("Battery Percent: ");
        Serial.println(batteryPercent);
        Serial.print("raw voltage: ");
        Serial.println(rawVoltage);
        #endif
        //compose message

        String telemMesg = "batVol:" + String(batteryVoltage) + ";";
        telemMesg += "batPct:" + String(batteryPercent) + ";";
        telemMesg += "temp:" + String(temp) + ";";
        Serial.println(telemMesg);
        SendEspNowString(telemMesg);
        if (batteryVoltage <= batteryMinVoltage){
            stopMotors = true;
        }
        vTaskDelay(pdMS_TO_TICKS(telemetryLoopDelay));
    }
}

void SendEspNowString(const String &message) {
    if (message.length() > 250) {
        Serial.println("Message too long to send over ESP-NOW");
        return;
    }
    // Send message
    esp_err_t result = esp_now_send(broadcastAddress, (const uint8_t *)message.c_str(), message.length() + 1);
   
    if (result == ESP_OK) {
        Serial.println("Sent with success");
    }
    else {
        Serial.println("Error sending the data");
    }
}





uint8_t getBatteryPercent(float voltage) {

    float closestDiff = 999.0;
    uint8_t closestPercent = 0;

    for (int i = 0; i < lipo2SSize; i++) {

        float diff = fabs(voltage - lipo2S[i].voltage);

        if (diff < closestDiff) {
            closestDiff = diff;
            closestPercent = lipo2S[i].percent;
        }
    }

    return closestPercent;
}