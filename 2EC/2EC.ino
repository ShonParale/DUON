// ESP32 #2 - B2 RIGHT SIDE - POLARITY CORRECTED IN SOFTWARE
#include <WiFi.h>

const char* ssid     = "Airtel_ShonPraleWiFi";
const char* password = "1#Gswifi05s";
const int   PORT     = 8080;

const int B2_RPWM = 18;
const int B2_LPWM = 19;
const int PWM_FREQ = 5000, PWM_RES = 8, SPEED = 255;

WiFiServer server(PORT);
WiFiClient client;

void setup() {
  Serial.begin(115200);
  Serial.println("\n[BOOT] ESP32 #2 - B2 RIGHT SIDE");

  ledcAttach(B2_RPWM, PWM_FREQ, PWM_RES);
  ledcAttach(B2_LPWM, PWM_FREQ, PWM_RES);
  stopMotors();

  WiFi.begin(ssid, password);
  Serial.print("[WIFI] Connecting");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\n[WIFI] Connected!");
  Serial.print("[WIFI] ESP32 #2 IP: ");
  Serial.println(WiFi.localIP());

  server.begin();
  server.setNoDelay(true);
  Serial.println("[READY] Waiting for Python...");
}

void loop() {
  if (!client || !client.connected()) {
    if (client) {
      client.stop();
      stopMotors();
      Serial.println("[CLIENT] Disconnected - waiting...");
    }
    client = server.accept();
    if (client) {
      Serial.println("[CLIENT] Python connected!");
      client.println("[ESP2] B2 Right side ready");
    }
  }

  if (client && client.connected() && client.available()) {
    char cmd = client.read();
    switch (cmd) {
      case 'W': case 'w':
        // B2 motors reversed - swap RPWM/LPWM
        ledcWrite(B2_RPWM, 0); ledcWrite(B2_LPWM, SPEED);
        Serial.println("[CMD] FORWARD"); client.println("[ESP2] FORWARD");
        break;
      case 'S': case 's':
        ledcWrite(B2_RPWM, SPEED); ledcWrite(B2_LPWM, 0);
        Serial.println("[CMD] BACKWARD"); client.println("[ESP2] BACKWARD");
        break;
      case 'A': case 'a':
        // Left turn: right side forward
        ledcWrite(B2_RPWM, 0); ledcWrite(B2_LPWM, SPEED);
        Serial.println("[CMD] TURN LEFT"); client.println("[ESP2] TURN LEFT");
        break;
      case 'D': case 'd':
        // Right turn: right side backward
        ledcWrite(B2_RPWM, SPEED); ledcWrite(B2_LPWM, 0);
        Serial.println("[CMD] TURN RIGHT"); client.println("[ESP2] TURN RIGHT");
        break;
      case 'X': case 'x': case ' ':
        stopMotors();
        Serial.println("[CMD] STOP"); client.println("[ESP2] STOP");
        break;
      case '\n': case '\r': break;
      default:
        Serial.print("[WARN] Unknown: "); Serial.println(cmd);
    }
  }
}

void stopMotors() {
  ledcWrite(B2_RPWM, 0);
  ledcWrite(B2_LPWM, 0);
}