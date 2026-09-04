#include <Servo.h>

// --- PIN DEFINITIONS ---
// L298N Motor Driver
const int IN1 = 2;
const int IN2 = 3;
const int IN3 = 4;
const int IN4 = 5;

// HC-SR04 Ultrasonic Sensor
const int TRIG_PIN = 6;
const int ECHO_PIN = 7;

// SG90 Servo
const int SERVO_PIN = 11;

// MQ Gas Sensors (Analog Inputs)
const int MQ_PIN_1 = A0;
const int MQ_PIN_2 = A1;
const int MQ_PIN_3 = A2;

// --- VARIABLES & OBJECTS ---
Servo radarServo;
bool autonomousMode = true; // Starts in Auto mode by default
unsigned long lastTelemetryTime = 0;
const unsigned long telemetryInterval = 200; // Send data every 200ms

void setup() {
  Serial.begin(115200); // High baud rate for fast Pi communication
 
  // Initialize Motor Pins
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
 
  // Initialize Ultrasonic Pins
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
 
  // Initialize Servo
  radarServo.attach(SERVO_PIN);
  radarServo.write(90); // Look straight ahead
 
  stopMotors();
}

void loop() {
  // 1. Check for incoming commands from Raspberry Pi
  checkSerialCommands();

  // 2. Handle Movement Logic Based on Mode
  if (autonomousMode) {
    runObstacleAvoidance();
  }

  // 3. Send Sensor Data to Pi at regular intervals
  if (millis() - lastTelemetryTime >= telemetryInterval) {
    sendTelemetry();
    lastTelemetryTime = millis();
  }
}

// --- NAVIGATION & SENSORS ---
long getDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout
  long distance = duration * 0.034 / 2;
  return (distance == 0) ? 999 : distance; // Return 999 if timeout out (clear path)
}

void runObstacleAvoidance() {
  long distanceAhead = getDistance();
 
  if (distanceAhead > 30) {
    moveForward();
  } else {
    stopMotors();
    delay(200);
   
    // Look Left
    radarServo.write(150);
    delay(400);
    long leftDist = getDistance();
   
    // Look Right
    radarServo.write(30);
    delay(400);
    long rightDist = getDistance();
   
    // Return to Center
    radarServo.write(90);
    delay(200);
   
    // Make Decision
    if (leftDist > rightDist && leftDist > 30) {
      turnLeft();
      delay(500); // Turn for half a second
    } else if (rightDist > leftDist && rightDist > 30) {
      turnRight();
      delay(500);
    } else {
      moveBackward();
      delay(600);
      turnLeft();
      delay(500);
    }
    stopMotors();
  }
}

// --- MOTOR ACTUATION ---
void moveForward() {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
}
void moveBackward() {
  digitalWrite(IN1, LOW);  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);  digitalWrite(IN4, HIGH);
}
void turnLeft() {
  digitalWrite(IN1, LOW);  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
}
void turnRight() {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);  digitalWrite(IN4, HIGH);
}
void stopMotors() {
  digitalWrite(IN1, LOW);  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);  digitalWrite(IN4, LOW);
}

// --- SERIAL COMMUNICATION ---
void sendTelemetry() {
  int gas1 = analogRead(MQ_PIN_1);
  int gas2 = analogRead(MQ_PIN_2);
  int gas3 = analogRead(MQ_PIN_3);
  long dist = getDistance();
 
  // Format: GAS1:val,GAS2:val,GAS3:val,DIST:val,MODE:A/M
  Serial.print("GAS1:"); Serial.print(gas1);
  Serial.print(",GAS2:"); Serial.print(gas2);
  Serial.print(",GAS3:"); Serial.print(gas3);
  Serial.print(",DIST:"); Serial.print(dist);
  Serial.print(",MODE:"); Serial.println(autonomousMode ? "A" : "M");
}

void checkSerialCommands() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
   
    // Handle Mode Changes
    if (command == "MODE:A") {
      autonomousMode = true;
    }
    else if (command == "MODE:M") {
      autonomousMode = false;
      stopMotors(); // Instantly stop when switching to manual
    }
   
    // Handle Manual Steering Commands (Only executed if in Manual Mode)
    if (!autonomousMode) {
      if (command == "CMD:F") moveForward();
      else if (command == "CMD:B") moveBackward();
      else if (command == "CMD:L") turnLeft();
      else if (command == "CMD:R") turnRight();
      else if (command == "CMD:S") stopMotors();
    }
  }
}
