/**
 * @file Artemis_Ground_Station_Receiver.cpp
 * @brief Estación Terrena (Receptor) - Vehículo Artemis (IPN)
 * @details Código para ESP32 Heltec LoRa V4 con Pantalla OLED (SX1262 a 915 MHz).
 */

#include <Wire.h>
#include <RadioLib.h>
#include <HT_SSD1306Wire.h> // Librería oficial de Heltec para OLED integrado

// ====================================================================
// 1. MAPA DE PINES HELTEC V4 (SX1262, OLED y VEXT)
// ====================================================================
#define LORA_NSS    8
#define LORA_DIO1   14
#define LORA_NRST   12
#define LORA_BUSY   13

#define OLED_SDA    17
#define OLED_SCL    18
#define OLED_RST    21
#define VEXT_PIN    36 // Control de alimentación para OLED y LoRa en Heltec

// ====================================================================
// 2. OBJETOS GLOBALES Y VARIABLES
// ====================================================================
SX1262 radio = new Module(LORA_NSS, LORA_DIO1, LORA_NRST, LORA_BUSY);
SSD1306Wire display(0x3c, 500000, OLED_SDA, OLED_SCL, GEOMETRY_128_64, OLED_RST);

volatile bool receivedFlag = false;
unsigned long paquetesRecibidos = 0;
float ultimoRSSI = 0.0;
String ultimaAltitudStr = "0.0";

// Rutina de interrupción al recibir paquete por LoRa
void IRAM_ATTR setRxFlag() {
  receivedFlag = true;
}

// ====================================================================
// 3. CONFIGURACIÓN INICIAL (SETUP)
// ====================================================================
void setup() {
  Serial.begin(115200); // Conexión Serial de alta velocidad hacia Python
  Serial.setTimeout(10); // Evitar bloqueos al leer comandos desde el Serial

  // Activar la línea de alimentación Vext en placas Heltec
  pinMode(VEXT_PIN, OUTPUT);
  digitalWrite(VEXT_PIN, LOW); // LOW = Alimentación activa
  delay(100);

  // Inicialización de la pantalla OLED
  display.init();
  display.clear();
  display.setFont(ArialMT_Plain_10);
  display.drawString(0, 0, "ARTEMIS GS - IPN");
  display.drawString(0, 16, "Iniciando LoRa 915MHz...");
  display.display();

  // CORRECCIÓN: Ajuste de SF a 7 para sincronización exacta con el emisor
  if (radio.begin(915.0, 125.0, 7, 7, 18, 10, 8, 1.6) == RADIOLIB_ERR_NONE) {
    display.drawString(0, 32, "LoRa Listo. Esperando...");
    display.display();
    
    radio.setDio1Action(setRxFlag);
    radio.startReceive();
  } else {
    display.drawString(0, 32, "ERROR CRITICO LORA");
    display.display();
  }
}

// ====================================================================
// 4. FUNCIONES AUXILIARES DE PANTALLA
// ====================================================================
void actualizarOLED() {
  display.clear();
  display.setFont(ArialMT_Plain_10);
  display.drawString(0, 0, "ARTEMIS - ESTACION TERRENA");
  display.drawLine(0, 12, 128, 12);
  
  display.drawString(0, 18, "Altitud: " + ultimaAltitudStr + " m");
  display.drawString(0, 32, "RSSI: " + String(ultimoRSSI, 1) + " dBm");
  display.drawString(0, 46, "Pkts Recibidos: " + String(paquetesRecibidos));
  
  display.display();
}

// Extrae la altitud del CSV de 10 variables:
// [Presion, Temp, Hum, Lat, Lon, AccX, AccY, AccZ, RPM, Altura]
void parsearParaOLED(String paquete) {
  int ultimaComa = paquete.lastIndexOf(',');
  if (ultimaComa != -1) {
    ultimaAltitudStr = paquete.substring(ultimaComa + 1);
    ultimaAltitudStr.trim();
  }
}

// ====================================================================
// 5. BUCLE PRINCIPAL (BRIDGE NON-BLOCKING)
// ====================================================================
void loop() {
  // ------------------------------------------------------------------
  // A. DOWNLINK (Interrupción LoRa -> Envío limpio a Python)
  // ------------------------------------------------------------------
  if (receivedFlag) {
    receivedFlag = false;
    String cadenaRecibida;
    int state = radio.readData(cadenaRecibida);

    if (state == RADIOLIB_ERR_NONE) {
      paquetesRecibidos++;
      ultimoRSSI = radio.getRSSI();

      // ENVÍO A PYTHON:
      // Se transmite únicamente el CSV limpio para que Python lo divida sin fallos
      Serial.println(cadenaRecibida);

      parsearParaOLED(cadenaRecibida);
      actualizarOLED();
    }
    
    // Volver a activar el modo escucha no bloqueante
    radio.startReceive();
  }

  // ------------------------------------------------------------------
  // B. UPLINK (Comandos de Python por Serial -> Transmisión LoRa)
  // ------------------------------------------------------------------
  if (Serial.available() > 0) {
    String comandoPython = Serial.readStringUntil('\n');
    comandoPython.trim();

    if (comandoPython.length() > 0) {
      // Pausar escucha temporalmente para transmitir el comando
      radio.finishTransmit();
      radio.transmit(comandoPython);
      
      // Reanudar escucha inmediatamente
      radio.startReceive();
    }
  }
}