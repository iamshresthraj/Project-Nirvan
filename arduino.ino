/*
  Project Nirvan — Arduino Firmware
  - HC-SR04 ultrasonic on SG90 servo (scans center/left/right)
  - L298N driving 2 motor banks (skid-steer)
  - MQ-135, MQ-136, MQ-2 gas sensors
  - Buzzer: warning/danger audible alert (thresholds from repo README)
  - Serial link to Raspberry Pi (115200 baud): sends telemetry,
    receives MODE:A / MODE:M / CMD:F/B/L/R/S
  Library required: NewPing
*/

#include <Servo.h>
#include <NewPing.h>

// ---------- L298N control pins ----------
const int LeftMotorForward   = 7;
const int LeftMotorBackward  = 6;
const int RightMotorForward  = 5;
const int RightMotorBackward = 4;

// ---------- Ultrasonic sensor pins ----------
#define TRIG_PIN A1
#define ECHO_PIN A2
#define MAX_DISTANCE 200   // cm

// ---------- Servo ----------
#define SERVO_PIN 10
const int SERVO_CENTER = 90;
const int SERVO_RIGHT  = 30;
const int SERVO_LEFT   = 150;

// ---------- Gas sensor pins ----------
#define MQ135_PIN A0   // air quality: CO2, NH3, benzene, smoke
#define MQ136_PIN A3   // H2S, SO2
#define MQ2_PIN   A4   // LPG, methane, smoke, CO

const int MQ135_THRESHOLD = 400;
const int MQ136_THRESHOLD = 400;
const int MQ2_THRESHOLD   = 400;

// ---------- Buzzer ----------
#define BUZZER_PIN 8
const int GAS_WARNING_THRESHOLD = 350;   // from repo README safety banner
const int GAS_DANGER_THRESHOLD  = 650;   // from repo README safety banner
unsigned long lastBuzzerToggle = 0;
bool buzzerState = false;
const unsigned long BUZZER_WARNING_INTERVAL = 500;  // slow beep
const unsigned long BUZZER_DANGER_INTERVAL  = 150;  // fast beep

// ---------- Behavior tuning ----------
const int STOP_DISTANCE = 30;   // cm, matches README's documented 30cm logic

NewPing sonar(TRIG_PIN, ECHO_PIN, MAX_DISTANCE);
Servo scanServo;

boolean movingForward = false;
bool autonomousMode = true;     // starts in Auto, same as before
int distance = 100;

int mq135Value = 0;
int mq136Value = 0;
int mq2Value   = 0;

unsigned long lastTelemetryTime = 0;
const unsigned long telemetryInterval = 200; // ms, unchanged from before

void setup() {
  Serial.begin(115200);   // matches app.py's BAUD_RATE

  pinMode(LeftMotorForward, OUTPUT);
  pinMode(LeftMotorBackward, OUTPUT);
  pinMode(RightMotorForward, OUTPUT);
  pinMode(RightMotorBackward, OUTPUT);

  pinMode(MQ135_PIN, INPUT);
  pinMode(MQ136_PIN, INPUT);
  pinMode(MQ2_PIN, INPUT);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  scanServo.attach(SERVO_PIN);
  scanServo.write(SERVO_CENTER);
  delay(2000);

  for (int i = 0; i < 4; i++) {
    distance = readPing();
    delay(100);
  }

  moveStop();
}

void loop() {
  // 1. Check for incoming commands from Raspberry Pi
  checkSerialCommands();

  // 2. Read gas sensors (updates globals + returns alert flag)
  bool gasAlert = checkGasSensors();

  // 3. Update buzzer based on repo's warning/danger thresholds
  updateBuzzer();

  // 4. Movement logic
  if (gasAlert) {
    // Gas threshold breached: stop regardless of mode, for safety
    moveStop();
    if (autonomousMode) distance = readPing();
  }
  else if (autonomousMode) {
    runObstacleAvoidance();
    distance = readPing();
  }
  // else: manual mode, no gas alert -> motors stay as last set by checkSerialCommands()

  // 5. Send telemetry to Pi at regular intervals
  if (millis() - lastTelemetryTime >= telemetryInterval) {
    sendTelemetry();
    lastTelemetryTime = millis();
  }
}

// ---------- Obstacle avoidance ----------
void runObstacleAvoidance() {
  if (distance <= STOP_DISTANCE) {
    moveStop();
    delay(300);
    moveBackward();
    delay(400);
    moveStop();
    delay(300);

    int distanceRight = lookRight();
    delay(300);
    int distanceLeft = lookLeft();
    delay(300);

    if (distanceRight >= distanceLeft) {
      turnRight();
    } else {
      turnLeft();
    }
    moveStop();
  } else {
    moveForward();
  }
}

// ---------- Gas sensors ----------
bool checkGasSensors() {
  mq135Value = analogRead(MQ135_PIN);
  mq136Value = analogRead(MQ136_PIN);
  mq2Value   = analogRead(MQ2_PIN);

  return (mq135Value > MQ135_THRESHOLD) ||
         (mq136Value > MQ136_THRESHOLD) ||
         (mq2Value   > MQ2_THRESHOLD);
}

// ---------- Buzzer ----------
void updateBuzzer() {
  int maxGas = mq135Value;
  if (mq136Value > maxGas) maxGas = mq136Value;
  if (mq2Value   > maxGas) maxGas = mq2Value;

  unsigned long now = millis();

  if (maxGas >= GAS_DANGER_THRESHOLD) {
    // Danger: fast beep
    if (now - lastBuzzerToggle >= BUZZER_DANGER_INTERVAL) {
      buzzerState = !buzzerState;
      digitalWrite(BUZZER_PIN, buzzerState);
      lastBuzzerToggle = now;
    }
  } else if (maxGas >= GAS_WARNING_THRESHOLD) {
    // Warning: slow beep
    if (now - lastBuzzerToggle >= BUZZER_WARNING_INTERVAL) {
      buzzerState = !buzzerState;
      digitalWrite(BUZZER_PIN, buzzerState);
      lastBuzzerToggle = now;
    }
  } else {
    // Normal: silent
    digitalWrite(BUZZER_PIN, LOW);
    buzzerState = false;
  }
}

// ---------- Scanning ----------
int lookRight() {
  scanServo.write(SERVO_RIGHT);
  delay(500);
  int d = readPing();
  delay(100);
  scanServo.write(SERVO_CENTER);
  return d;
}

int lookLeft() {
  scanServo.write(SERVO_LEFT);
  delay(500);
  int d = readPing();
  delay(100);
  scanServo.write(SERVO_CENTER);
  return d;
}

int readPing() {
  delay(70);
  int cm = sonar.ping_cm();
  if (cm == 0) cm = 250;   // no echo = treat as clear
  return cm;
}

// ---------- Motor control ----------
void moveStop() {
  digitalWrite(LeftMotorForward, LOW);
  digitalWrite(RightMotorForward, LOW);
  digitalWrite(LeftMotorBackward, LOW);
  digitalWrite(RightMotorBackward, LOW);
  movingForward = false;
}

void moveForward() {
  if (!movingForward) {
    movingForward = true;
    digitalWrite(LeftMotorForward, HIGH);
    digitalWrite(RightMotorForward, HIGH);
    digitalWrite(LeftMotorBackward, LOW);
    digitalWrite(RightMotorBackward, LOW);
  }
}

void moveBackward() {
  movingForward = false;
  digitalWrite(LeftMotorBackward, HIGH);
  digitalWrite(RightMotorBackward, HIGH);
  digitalWrite(LeftMotorForward, LOW);
  digitalWrite(RightMotorForward, LOW);
}

void turnRight() {
  digitalWrite(LeftMotorForward, HIGH);
  digitalWrite(RightMotorBackward, HIGH);
  digitalWrite(LeftMotorBackward, LOW);
  digitalWrite(RightMotorForward, LOW);
  delay(250);

  digitalWrite(LeftMotorForward, HIGH);
  digitalWrite(RightMotorForward, HIGH);
  digitalWrite(LeftMotorBackward, LOW);
  digitalWrite(RightMotorBackward, LOW);
  movingForward = true;
}

void turnLeft() {
  digitalWrite(LeftMotorBackward, HIGH);
  digitalWrite(RightMotorForward, HIGH);
  digitalWrite(LeftMotorForward, LOW);
  digitalWrite(RightMotorBackward, LOW);
  delay(250);

  digitalWrite(LeftMotorForward, HIGH);
  digitalWrite(RightMotorForward, HIGH);
  digitalWrite(LeftMotorBackward, LOW);
  digitalWrite(RightMotorBackward, LOW);
  movingForward = true;
}

// ---------- Serial communication ----------
void sendTelemetry() {
  // Format: GAS1:val,GAS2:val,GAS3:val,DIST:val,MODE:A/M
  Serial.print("GAS1:"); Serial.print(mq2Value);    // MQ-2  -> GAS1 (matches README mapping)
  Serial.print(",GAS2:"); Serial.print(mq135Value);  // MQ-135 -> GAS2
  Serial.print(",GAS3:"); Serial.print(mq136Value);  // MQ-136 -> GAS3
  Serial.print(",DIST:"); Serial.print(distance);
  Serial.print(",MODE:"); Serial.println(autonomousMode ? "A" : "M");
}

void checkSerialCommands() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "MODE:A") {
      autonomousMode = true;
    }
    else if (command == "MODE:M") {
      autonomousMode = false;
      moveStop();
    }

    if (!autonomousMode) {
      if (command == "CMD:F") moveForward();
      else if (command == "CMD:B") moveBackward();
      else if (command == "CMD:L") turnLeft();
      else if (command == "CMD:R") turnRight();
      else if (command == "CMD:S") moveStop();
    }
  }
}
