# 🔋 Tabla de Consumo Energético y Batería

El sistema es alimentado por una batería LiPo 2S de 7.4V / 2200mAh, regulada a 5V mediante un módulo MP1584 para los periféricos de alto consumo, mientras que el ESP32 gestiona su propia lógica interna de 3.3V.

| Fase de Misión | Componentes Activos | Consumo Promedio (mA) | Voltaje Registrado (V) | Duración Estimada |
| :--- | :--- | :--- | :--- | :--- |
| **Pre-Vuelo (En Plataforma)** | ESP32 (LoRa Standby), BME280, MPU6050, GPS | ~110 mA | 8.2V (Carga completa) / 7.4V | > 15 Horas |
| **Ascenso (Empuje Activo)** | ESP32 (Tx LoRa 27dBm), Sensores, GPS, Cámara FPV, DVR | ~650 mA | 7.3V - 7.1V | ~3.3 Horas |
| **Apogeo y Despliegue** | ESP32, Servomotor SG90 (Pico), LoRa Tx, FPV | ~850 mA (Pico) | 7.0V | ~2.5 Horas |
| **Descenso / Recuperación** | ESP32, Buzzer Activo, LoRa Tx, GPS | ~180 mA | 6.8V | > 10 Horas |

### Conclusión de Autonomía:
Con un consumo medio operativo de ~450 mA durante las fases críticas de vuelo y una capacidad de batería de 2200 mAh, el sistema garantiza un **margen de seguridad de más del 300%** frente al tiempo total estimado de la misión (menor a 10 minutos desde el encendido hasta la recuperación).
