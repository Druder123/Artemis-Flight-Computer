# 🔌 Diagrama Esquemático y Conexiones Eléctricas

Para proteger la aviónica y evitar reinicios por caídas de tensión, el sistema separa físicamente el bus de potencia (5V) del bus lógico (3.3V).

## 1. Alimentación y Regulación
* **Batería LiPo 2S (7.4V)** $\rightarrow$ Conectada a la entrada `IN+` / `IN-` del **Regulador MP1584**.
* **Salida del Regulador (5V)** $\rightarrow$ Alimenta el pin 5V del ESP32 Heltec V4, el Servomotor SG90, la Cámara FPV AKK A2 y el RunCam DVR.
* **Divisor de Tensión:** Dos resistencias de $10\text{ k}\Omega$ conectadas en serie desde el positivo de la LiPo a GND, con el nodo central hacia el pin **ADC (GPIO 3)** del ESP32 para telemetría de voltaje en tiempo real.

## 2. Bus I2C (Sensores a 3.3V)
* **ESP32 Pin 3.3V** $\rightarrow$ Alimentación para BME280 y MPU-6050.
* **ESP32 Pines I2C** $\rightarrow$ Conectados en paralelo a los pines `SDA` y `SCL` de ambos sensores.

## 3. Actuadores y Periféricos
* **Servomotor SG90:** Señal al **GPIO 18**, VCC a 5V (Regulador) y GND común.
* **Módulo GPS:** Conectado por UART al **RX (GPIO 16)** y **TX (GPIO 17)** del ESP32.
