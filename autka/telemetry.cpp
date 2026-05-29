#include <telemetry.h>


TaskHandle_t mainTelemetryLoopHandle = nullptr;


void setupTelemetryAndBatteryMonitoring(){
    analogReadResolution(12);
    analogSetPinAttenuation(batteryPin, ADC_11db); // 3.3v range
    adcAttachPin(batteryPin);

    xTaskCreatePinnedToCore(
  mainTelemetryLoop,          // Task function.
    "telemetry",          // name of task.
      10000,          // Stack size of task
       NULL,          // parameter of the task
          1,          // priority of the task 0 - 3
     &mainTelemetryLoopHandle,          // Task handle to keep track of created task
         1);          // pin task to core X  
}

void mainTelemetryLoop(void *pvParameters) {
    while (true) {
        float rawVoltage = analogRead(batteryPin) * (3.3 / 4095.0); 
        float batteryVoltage = rawVoltage * (batteryDeviderR1 + batteryDeviderR2) / batteryDeviderR2;

        float batteryPercent = getBatteryPercent(batteryVoltage);


        uint8_t temp = temperatureRead();
  
  
        Serial.print("Internal Chip Temperature: ");
        Serial.print(temp);
        Serial.println(" °C");

        Serial.print("Battery Voltage: ");
        Serial.println(batteryVoltage);
        Serial.print("Battery Percent: ");
        Serial.println(batteryPercent);
        Serial.print("raw voltage: ");
        Serial.println(rawVoltage);

        //compose message

        String telemMesg = "batVol:" + String(batteryVoltage) + ";";
        telemMesg += "batPct:" + String(batteryPercent) + ";";
        telemMesg += "temp:" + String(temp) + ";";

        vTaskDelay(pdMS_TO_TICKS(telemetryLoopDelay));
    }
}

void SendEspNowString(const String &message) {
    if (message.length() > 250) {
        Serial.println("Message too long to send over ESP-NOW");
        return;
    }
    // Send message
    esp_err_t result = esp_now_send(broadcastAddress, (uint8_t *) &message, sizeof(message));
   
    if (result == ESP_OK) {
        Serial.println("Sent with success");
    }
    else {
        Serial.println("Error sending the data");
    }
}



const int lipo2SSize =
    sizeof(lipo2S) / sizeof(lipo2S[0]);

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