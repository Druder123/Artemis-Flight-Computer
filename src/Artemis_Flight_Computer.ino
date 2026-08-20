/**
 * @file Artemis_Flight_Computer.cpp
 * @brief Computadora de Vuelo Optimizada y Corregida - Heltec LoRa V4
 * @details Sistema Cánsat / Vehículo Artemis (IPN)
 * @autor Druder/Abdiel
 */

#include <Wire.h>
#include <RadioLib.h>         
#include <Adafruit_BME280.h>  
#include <Adafruit_MPU6050.h> 
#include <ESP32Servo.h>       
#include <TinyGPS++.h>

// ====================================================================
// 1. MAPA DE PINES (HAL - HELTEC V4)
// ====================================================================
#define LORA_NSS       8
#define LORA_DIO1      14
#define LORA_NRST      12
#define LORA_BUSY      13

// CORRECCIÓN: Pines I2C nativos para Heltec Wi-Fi LoRa 32 V3/V4
#define PIN_SDA        17  
#define PIN_SCL        18
#define VEXT_PIN       36  // Control de alimentación de periferia Heltec

#define PIN_SERVO_CARGA 4  // Servo para liberar autogiro
#define PIN_BUZZER       19  // Buzzer de recuperación
#define PIN_HALL         6   // Sensor Efecto Hall
#define PIN_LIPO         1   // Lectura ADC Batería
#define GPS_RX           38  // ESP32 RX <- GPS TX
#define GPS_TX           39  // ESP32 TX -> GPS RX

// Constante de conversión: m/s² a Fuerzas G
#define SENSORS_GRAVITY_STANDARD 9.80665F

// ====================================================================
// 2. OBJETOS GLOBALES Y VARIABLES
// ====================================================================
SX1262 radio = new Module(LORA_NSS, LORA_DIO1, LORA_NRST, LORA_BUSY);
Adafruit_BME280 bme;
Adafruit_MPU6050 mpu;
Servo servoCarga;
TinyGPSPlus gps;

enum EstadoMision { PRE_VUELO, ASCENSO, APOGEO, DESCENSO };
EstadoMision estadoActual = PRE_VUELO;

float altitudBase = 0.0;
float altitudMaxima = 0.0;

// Interrupción Hardware - Sensor Hall
volatile unsigned long contadorHall = 0;
void IRAM_ATTR ISR_Hall() {
  contadorHall++;
}

// Interrupción Hardware - Recepción LoRa
volatile bool loraCommandReceived = false;
void IRAM_ATTR setRxFlag() {
  loraCommandReceived = true;
}

unsigned long ultimoEnvioLORA = 0;
const unsigned long INTERVALO_TELEMETRIA = 200; // 5 Hz para transmisiones LoRa estables

// ====================================================================
// 3. CONFIGURACIÓN INICIAL (SETUP)
// ====================================================================
void setup() {
  Serial.begin(115200);
  Serial1.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);
  
  // Activar la línea de alimentación Vext en la placa Heltec
  pinMode(VEXT_PIN, OUTPUT);
  digitalWrite(VEXT_PIN, LOW); // Enciende sensores I2C y GPS
  delay(100);

  // Inicializar bus I2C
  Wire.begin(PIN_SDA, PIN_SCL); 

  // CORRECCIÓN: Cambio a SF7 (parámetro 3) para evitar el bloqueo del loop a 5 Hz
  if (radio.begin(915.0, 125.0, 7, 7, 18, 10, 8, 1.6) == RADIOLIB_ERR_NONE) {
    radio.setDio1Action(setRxFlag);
    radio.startReceive();
  } else {
    Serial.println(F("[ERR] Fallo crítico al inicializar LoRa."));
  }

  // Inicializar Sensores I2C
  if (!bme.begin(0x76, &Wire)) {
    Serial.println(F("[ERR] BME280 no detectado."));
  }
  if (!mpu.begin(0x68, &Wire)) {
    Serial.println(F("[ERR] MPU6050 no detectado."));
  }

  // Calibración barométrica inicial (Cero de referencia)
  float sumaAltitud = 0;
  for (int i = 0; i < 10; i++) {
    sumaAltitud += bme.readAltitude(1013.25);
    delay(30);
  }
  altitudBase = sumaAltitud / 10.0;

  // Actuadores
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW); 

  // Configurar Sensor Hall con Interrupción
  pinMode(PIN_HALL, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_HALL), ISR_Hall, FALLING);

  // Configurar Servo Motor
  ESP32PWM::allocateTimer(0);
  servoCarga.setPeriodHertz(50);
  servoCarga.attach(PIN_SERVO_CARGA);
  servoCarga.write(0); // Posición inicial: Carga bloqueada
}

// ====================================================================
// 4. RUTINAS DE PROCESAMIENTO
// ====================================================================

void rutearDatosGPS() {
  // Parsea tramas NMEA en segundo plano de manera continua sin bloquear
  while (Serial1.available() > 0) {
    gps.encode(Serial1.read());
  }
}

void procesarComandosTerrena() {
  if (loraCommandReceived) {
    loraCommandReceived = false;
    String comando;
    int state = radio.readData(comando);

    if (state == RADIOLIB_ERR_NONE) {
      comando.trim();
      if (comando == "CMD,CALIBRATE") {
        altitudBase = bme.readAltitude(1013.25);
        altitudMaxima = 0.0;
      } 
      else if (comando == "CMD,FORCE_DEPLOY") {
        servoCarga.write(90); // Desplegar autogiro
        estadoActual = APOGEO;
      } 
      else if (comando == "CMD,BUZZER_ON") {
        digitalWrite(PIN_BUZZER, HIGH);
      }
    }
    radio.startReceive(); // Volver a activar escucha no bloqueante
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
        servoCarga.write(90); // Despliegue automático en apogeo
        estadoActual = APOGEO;
      }
      break;

    case APOGEO:
      estadoActual = DESCENSO;
      break;

    case DESCENSO:
      if (altitudRelativa < 10.0) {
        digitalWrite(PIN_BUZZER, HIGH); // Alarma de rescate cerca de superficie
      }
      break;
  }
}

// ====================================================================
// 5. BUCLE PRINCIPAL (NON-BLOCKING)
// ====================================================================
void loop() {
  unsigned long tiempoActual = millis();

  // Procesar tareas continuas
  rutearDatosGPS();
  procesarComandosTerrena(); 

  // Enviar telemetría según el temporizador (5 Hz)
  if (tiempoActual - ultimoEnvioLORA >= INTERVALO_TELEMETRIA) {
    ultimoEnvioLORA = tiempoActual;

    // Lectura de Barómetro
    float presion = bme.readPressure() / 100.0F; // hPa
    float temp = bme.readTemperature();          // °C
    float hum = bme.readHumidity();              // %
    float altitudRelativa = bme.readAltitude(1013.25) - altitudBase; // Metros

    // Lectura de Acelerómetro (Conversión de m/s² a Fuerzas G)
    sensors_event_t a, g, t;
    mpu.getEvent(&a, &g, &t);
    float accX_g = a.acceleration.x / SENSORS_GRAVITY_STANDARD;
    float accY_g = a.acceleration.y / SENSORS_GRAVITY_STANDARD;
    float accZ_g = a.acceleration.z / SENSORS_GRAVITY_STANDARD;

    // Lectura de GPS parseado por TinyGPS++
    float latitud = gps.location.isValid() ? gps.location.lat() : 0.0;
    float longitud = gps.location.isValid() ? gps.location.lng() : 0.0;

    // Actualizar lógica de la misión
    actualizarMaquinaEstados(altitudRelativa);

    // Construir CSV exacto de 10 parámetros para Estación Terrena y GUI Python:
    // Presion,Temp,Hum,Lat,Lon,AccX,AccY,AccZ,RPM,Altura
    String telemetria = String(presion, 1) + "," +
                        String(temp, 1) + "," +
                        String(hum, 1) + "," +
                        String(latitud, 4) + "," +
                        String(longitud, 4) + "," +
                        String(accX_g, 2) + "," +
                        String(accY_g, 2) + "," +
                        String(accZ_g, 2) + "," +
                        String(contadorHall) + "," +
                        String(altitudRelativa, 2);

    // Enviar por LoRa y reanudar la recepción no bloqueante
    radio.finishTransmit();
    radio.transmit(telemetria); 
    radio.startReceive();
  }
}
