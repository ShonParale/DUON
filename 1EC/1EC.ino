// ============================================================
//  ESP32 #1 - B1 LEFT SIDE (M1+M3) + ALL 3 SONARS
//  MANUAL DRIVE: UNCHANGED (W/A/S/D/X/SPACE)
//  NEW: Non-blocking sonar reads, streamed as [SONAR]L:xx,F:xx,R:xx
// ============================================================
#include <WiFi.h>

const char* ssid     = "Airtel_ShonPraleWiFi";
const char* password = "1#Gswifi05s";
const int   PORT     = 8080;

// --- BTS7960 #1 pins (UNCHANGED) ---
const int B1_RPWM = 25;
const int B1_LPWM = 27;
const int PWM_FREQ = 5000, PWM_RES = 8, SPEED = 255;

// --- Sonar pins ---
const int S1_TRIG = 32, S1_ECHO = 33;  // Left  (45 deg diagonal)
const int S2_TRIG = 14, S2_ECHO = 16;  // Front (straight)
const int S3_TRIG = 13, S3_ECHO = 17;  // Right (45 deg diagonal)

WiFiServer server(PORT);
WiFiClient client;

// --- Non-blocking sonar state machine ---
const int TRIG_PINS[3] = {S1_TRIG, S2_TRIG, S3_TRIG};
const int ECHO_PINS[3] = {S1_ECHO, S2_ECHO, S3_ECHO};

int     sonarIdx       = 0;
bool    trigSent       = false;
unsigned long trigTime = 0;
float   dist_cm[3]     = {0, 0, 0};  // L, F, R

unsigned long lastSonarReport = 0;
const unsigned long SONAR_INTERVAL = 100; // ms between reports to Python

void triggerSonar(int idx) {
  digitalWrite(TRIG_PINS[idx], LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PINS[idx], HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PINS[idx], LOW);
  trigTime = micros();
  trigSent = true;
}

float readEcho(int idx) {
  unsigned long elapsed = micros() - trigTime;
  int pin = ECHO_PINS[idx];
  if (digitalRead(pin) == LOW) {
    if (elapsed > 25000) return -1; // timeout = no object in range
    return 0;                       // still waiting for echo
  }
  unsigned long pulseStart = micros();
  while (digitalRead(pin) == HIGH) {
    if (micros() - pulseStart > 25000) break;
  }
  unsigned long pulseEnd = micros();
  float cm = (pulseEnd - pulseStart) / 58.0;
  return (cm > 400) ? 400 : cm;
}

void stopMotors() {
  ledcWrite(B1_RPWM, 0);
  ledcWrite(B1_LPWM, 0);
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n[BOOT] ESP32 #1 - B1 LEFT SIDE + SONARS");

  // Motor PWM (UNCHANGED)
  ledcAttach(B1_RPWM, PWM_FREQ, PWM_RES);
  ledcAttach(B1_LPWM, PWM_FREQ, PWM_RES);
  stopMotors();

  // Sonar pin setup
  for (int i = 0; i < 3; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    pinMode(ECHO_PINS[i], INPUT);
    digitalWrite(TRIG_PINS[i], LOW);
  }

  WiFi.begin(ssid, password);
  Serial.print("[WIFI] Connecting");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\n[WIFI] Connected!");
  Serial.print("[WIFI] ESP32 #1 IP: ");
  Serial.println(WiFi.localIP());

  server.begin();
  Serial.println("[READY] Waiting for Python...");
}

void loop() {

  // 1. Handle client connection (UNCHANGED)
  if (!client || !client.connected()) {
    client = server.accept();
    if (client) {
      Serial.println("[CLIENT] Python connected!");
      client.println("[ESP1] B1 Left side ready");
    }
  }

  // 2. Manual drive command handler (COMPLETELY UNCHANGED)
  if (client && client.connected() && client.available()) {
    char cmd = client.read();
    switch (cmd) {
      case 'W': case 'w':
        ledcWrite(B1_RPWM, SPEED); ledcWrite(B1_LPWM, 0);
        Serial.println("[CMD] FORWARD"); client.println("[ESP1] FORWARD");
        break;
      case 'S': case 's':
        ledcWrite(B1_RPWM, 0); ledcWrite(B1_LPWM, SPEED);
        Serial.println("[CMD] BACKWARD"); client.println("[ESP1] BACKWARD");
        break;
      case 'A': case 'a':
        ledcWrite(B1_RPWM, 0); ledcWrite(B1_LPWM, SPEED);
        Serial.println("[CMD] TURN LEFT - B1 reverse"); client.println("[ESP1] TURN LEFT");
        break;
      case 'D': case 'd':
        ledcWrite(B1_RPWM, SPEED); ledcWrite(B1_LPWM, 0);
        Serial.println("[CMD] TURN RIGHT - B1 forward"); client.println("[ESP1] TURN RIGHT");
        break;
      case 'X': case 'x': case ' ':
        stopMotors();
        Serial.println("[CMD] STOP"); client.println("[ESP1] STOP");
        break;
      case '\n': case '\r': break;
      default:
        Serial.print("[WARN] Unknown: "); Serial.println(cmd);
    }
  }

  // 3. Non-blocking sonar cycling
  if (!trigSent) {
    triggerSonar(sonarIdx);
  } else {
    float result = readEcho(sonarIdx);
    if (result > 0 || result == -1) {
      dist_cm[sonarIdx] = (result == -1) ? 400 : result;
      trigSent = false;
      sonarIdx = (sonarIdx + 1) % 3;
    }
    // result == 0 means echo not arrived yet, loop continues
  }

  // 4. Stream sonar data to Python every 100ms
  if (client && client.connected()) {
    unsigned long now = millis();
    if (now - lastSonarReport >= SONAR_INTERVAL) {
      lastSonarReport = now;
      char buf[48];
      snprintf(buf, sizeof(buf), "[SONAR]L:%.1f,F:%.1f,R:%.1f",
               dist_cm[0], dist_cm[1], dist_cm[2]);
      client.println(buf);
    }
  }
}