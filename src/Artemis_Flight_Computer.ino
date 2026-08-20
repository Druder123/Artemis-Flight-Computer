/**
 * @file Artemis_Flight_Computer.cpp
 * @brief Computadora de Vuelo - Vehículo Artemis (IPN)
 * @details Sistema multietapa hidropropulsado. 
 * Microcontrolador: ESP32 Heltec LoRa V4 (SX1262 a 915 MHz).
 * 
 * ARQUITECTURA DE SOFTWARE (Para Evaluación de Jueces):
 * 1. Máquina de Estados Finitos (FSM) basada en altitud.
 * 2. Despliegue de carga útil (Autogiro) por detección de apogeo.
 * 3. Transmisión asíncrona de telemetría, sentencias NMEA y Sensor Hall.
 */

#include <Wire.h>
#include <RadioLib.h>         
#include <Adafruit_BME280.h>  
#include <Adafruit_MPU6050.h> 
#include <ESP32Servo.h>       

// ====================================================================
// 1. MAPA DE PINES (HAL)
// ====================================================================
#define LORA_NSS   8
#define LORA_DIO1  14
#define LORA_NRST  12
#define LORA_BUSY  13

#define PIN_SDA           4   // I2C Data para BME280 y MPU6050
#define PIN_SCL           5   // I2C Clock para BME280 y MPU6050

#define PIN_SERVO_CARGA   18  // PWM: Servo para liberar la carga (Autogiro)
#define PIN_BUZZER        19  // Digital: Alarma acústica para recuperación
#define PIN_HALL          6   // Digital: Sensor Efecto Hall
#define PIN_LIPO          3   // ADC: Divisor de tensión para LiPo 2S
#define GPS_RX            16  // UART RX
#define GPS_TX            17  // UART TX

// ====================================================================
// 2. OBJETOS GLOBALES Y VARIABLES
// ====================================================================
SX1262 radio = new Module(LORA_NSS, LORA_DIO1, LORA_NRST, LORA_BUSY);
Adafruit_BME280 bme;
Adafruit_MPU6050 mpu;
Servo servoCarga;

enum EstadoMision { PRE_VUELO, ASCENSO, APOGEO, DESCENSO };
EstadoMision estadoActual = PRE_VUELO;

float altitudBase = 0.0;
float altitudMaxima = 0.0;
float voltajeLiPo = 0.0;

// Variables para el Sensor Hall (Conteo de pulsos / Rotaciones)
volatile unsigned long contadorHall = 0;
unsigned long pulsosHallUltimo = 0;
bool estadoHallAnterior = HIGH;

unsigned long ultimoEnvioLORA = 0;
const unsigned long INTERVALO_TELEMETRIA = 100; // 10Hz
bool transmitirTelemetria = true; 

String nmeaBuffer = ""; 

// ====================================================================
// 3. CONFIGURACIÓN INICIAL (SETUP)
// ====================================================================
void setup() {
  Serial.begin(115200);
  Serial1.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);
  
  // Inicialización explícita del bus I2C
  Wire.begin(PIN_SDA, PIN_SCL); 

  if (radio.begin(915.0, 125.0, 9, 7, 18, 10, 8, 1.6) != RADIOLIB_ERR_NONE) {
    Serial.println("[ERR] Fallo crítico en LoRa.");
  }

  bme.begin(0x76);
  mpu.begin();

  // Calibración barométrica inicial
  float sumaAltitud = 0;
  for(int i=0; i<10; i++) {
    sumaAltitud += bme.readAltitude(1013.25);
    delay(50);
  }
  altitudBase = sumaAltitud / 10.0;

  // Configuración de Periféricos y Actuadores
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW); 

  pinMode(PIN_HALL, INPUT_PULLUP); // Habilitar resistencia pull-up interna para el sensor Hall

  ESP32PWM::allocateTimer(0);
  servoCarga.setPeriodHertz(50);
  servoCarga.attach(PIN_SERVO_CARGA);
  servoCarga.write(0); // Carga asegurada
}

// ====================================================================
// 4. RUTINAS DE PROCESAMIENTO
// ====================================================================
void procesarComandosTerrena() {
  String comando;
  if (radio.receive(comando) == RADIOLIB_ERR_NONE) {
    
    if (comando == "CMD,CALIBRATE") {
      altitudBase = bme.readAltitude(1013.25);
      altitudMaxima = 0.0;
      radio.transmit("ACK,CALIBRATED");
    } 
    else if (comando == "CMD,START_TLM") {
      transmitirTelemetria = true;
    } 
    else if (comando == "CMD,STOP_TLM") {
      transmitirTelemetria = false;
    } 
    else if (comando == "CMD,PING") {
      radio.transmit("ACK,PING,BATT:" + String(voltajeLiPo, 2) + "V");
    } 
    else if (comando == "CMD,FORCE_DEPLOY") {
      servoCarga.write(90);
      estadoActual = APOGEO;
      radio.transmit("ACK,DEPLOY_FORCED");
    } 
    else if (comando == "CMD,BUZZER_ON") {
      digitalWrite(PIN_BUZZER, HIGH);
      radio.transmit("ACK,BUZZER_ACTIVE");
    }
  }
}

void actualizarMaquinaEstados(float altitudRelativa) {
  if (altitudRelativa > altitudMaxima) altitudMaxima = altitudRelativa;

  switch (estadoActual) {
    case PRE_VUELO:
      if (altitudRelativa > 3.0) estadoActual = ASCENSO;
      break;
    
    case ASCENSO:
      if (altitudRelativa < (altitudMaxima - 2.0)) {
        servoCarga.write(90); // Liberar autogiro
        estadoActual = APOGEO;
      }
      break;

    case APOGEO:
      estadoActual = DESCENSO;
      break;

    case DESCENSO:
      if (altitudRelativa < 10.0) {
        digitalWrite(PIN_BUZZER, HIGH);
      }
      break;
  }
}

void leerSensorHall() {
  // Detección por flanco de bajada (cuando pasa un imán frente al sensor Hall A3144)
  bool estadoHallActual = digitalRead(PIN_HALL);
  if (estadoHallAnterior == HIGH && estadoHallActual == LOW) {
    contadorHall++;
  }
  estadoHallAnterior = estadoHallActual;
}

void rutearDatosGPS() {
  while (Serial1.available() > 0) {
    char c = Serial1.read();
    nmeaBuffer += c;
    if (c == '\n') {
      if ((nmeaBuffer.startsWith("$GNGGA") || nmeaBuffer.startsWith("$GNRMC")) && transmitirTelemetria) {
        radio.transmit("GPS|" + nmeaBuffer);
      }
      nmeaBuffer = ""; 
    }
  }
}

// ====================================================================
// 5. BUCLE PRINCIPAL
// ====================================================================
void loop() {
  unsigned long tiempoActual = millis();
  
  rutearDatosGPS();
  procesarComandosTerrena(); 
  leerSensorHall(); // Monitoreo constante del sensor magnético

  if (tiempoActual - ultimoEnvioLORA >= INTERVALO_TELEMETRIA) {
    ultimoEnvioLORA = tiempoActual;

    float altitudRelativa = bme.readAltitude(1013.25) - altitudBase;
    
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);

    int adcLiPo = analogRead(PIN_LIPO);
    voltajeLiPo = (adcLiPo * 3.3 / 4095.0) * 3.1; 

    actualizarMaquinaEstados(altitudRelativa);

    if (transmitirTelemetria) {
      // CSV ampliado: [Tiempo, Estado, Altitud, AcelZ, Voltaje, PulsosHall]
      String telemetria = String(tiempoActual) + "," +
                          String(estadoActual) + "," +
                          String(altitudRelativa, 2) + "," +
                          String(a.acceleration.z, 2) + "," +
                          String(voltajeLiPo, 2) + "," +
                          String(contadorHall);

      radio.transmit(telemetria); 
    }
  }
}
