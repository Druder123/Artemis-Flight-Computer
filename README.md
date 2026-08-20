# 🚀 Cohete Artemis - Sistema de Aviónica y Telemetría
**Equipo de Cohetería Hidropropulsada - Instituto Politécnico Nacional (IPN)**

Repositorio oficial de la computadora de vuelo para el vehículo aeroespacial **Artemis**. Diseñado para adquirir datos ambientales, inerciales y de posición, gestionar una máquina de estados finitos (FSM) y transmitir telemetría de largo alcance mediante LoRa.

---

## 🛠️ Especificaciones Técnicas del Sistema
* **Microcontrolador:** ESP32 Heltec LoRa V4 (SX1262 a 915 MHz).
* **Sensores:** 
  * Barómetro BME280 (Presión, Temperatura y Altitud).
  * Acelerómetro/Giroscopio MPU-6050 (6 Ejes).
  * GPS integrado (Transmisión de tramas NMEA en crudo).
* **Actuadores:** Servomotor SG90 para despliegue de carga útil (Autogiro).
* **Alimentación:** Batería LiPo 2S (7.4V) regulada con módulo MP1584.

---

## 📂 Contenido del Repositorio
1. **[`src/Artemis_Flight_Computer.cpp`](src/Artemis_Flight_Computer.ino):** Código fuente principal optimizado, no bloqueante y documentado para la evaluación de los jueces.
2. **[`docs/Diagrama_Conexiones.md`](docs/Diagrama_Conexiones.md):** Mapa detallado de conexiones eléctricas y aislamiento de potencia.
3. **[`docs/Tabla_Consumo_Bateria.md`](docs/Tabla_Consumo_Bateria.md):** Registro de rendimiento energético y autonomía de la LiPo.
4. **[`bom/Bill_Of_Materials.md`](bom/Bill_Of_Materials.md):** Lista completa de materiales y costos del proyecto.
