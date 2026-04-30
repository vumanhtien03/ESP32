const int NUM_LOCKERS = 4;

// Chân LED cho 4 ngăn
int ledPins[NUM_LOCKERS] = {4, 18, 19, 21};

// Trạng thái tủ
bool lockerIsOpen[NUM_LOCKERS] = {false, false, false, false};

void ledOn(int lockerIndex) {
  digitalWrite(ledPins[lockerIndex], HIGH);
}

void ledOff(int lockerIndex) {
  digitalWrite(ledPins[lockerIndex], LOW);
}

void openLocker(int lockerIndex) {
  ledOn(lockerIndex);
  lockerIsOpen[lockerIndex] = true;

  Serial.print("LOCKER_");
  Serial.print(lockerIndex + 1);
  Serial.println("_OPENED");
}

void closeLocker(int lockerIndex) {
  ledOff(lockerIndex);
  lockerIsOpen[lockerIndex] = false;

  Serial.print("LOCKER_");
  Serial.print(lockerIndex + 1);
  Serial.println("_CLOSED");
}

void openLockerTemporary(int lockerIndex, unsigned long holdMs = 3000) {
  openLocker(lockerIndex);
  delay(holdMs);
  closeLocker(lockerIndex);
}

void printStatusAll() {
  for (int i = 0; i < NUM_LOCKERS; i++) {
    Serial.print("LOCKER_");
    Serial.print(i + 1);
    Serial.print("_STATE:");
    Serial.println(lockerIsOpen[i] ? "OPEN" : "CLOSED");
  }
}

void handleCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "OPEN_LOCKER_1") {
    openLockerTemporary(0);
  }
  else if (cmd == "OPEN_LOCKER_2") {
    openLockerTemporary(1);
  }
  else if (cmd == "OPEN_LOCKER_3") {
    openLockerTemporary(2);
  }
  else if (cmd == "OPEN_LOCKER_4") {
    openLockerTemporary(3);
  }
  else if (cmd == "OPEN_ONLY_1") {
    openLocker(0);
  }
  else if (cmd == "OPEN_ONLY_2") {
    openLocker(1);
  }
  else if (cmd == "OPEN_ONLY_3") {
    openLocker(2);
  }
  else if (cmd == "OPEN_ONLY_4") {
    openLocker(3);
  }
  else if (cmd == "CLOSE_ONLY_1") {
    closeLocker(0);
  }
  else if (cmd == "CLOSE_ONLY_2") {
    closeLocker(1);
  }
  else if (cmd == "CLOSE_ONLY_3") {
    closeLocker(2);
  }
  else if (cmd == "CLOSE_ONLY_4") {
    closeLocker(3);
  }
  else if (cmd == "STATUS_ALL") {
    printStatusAll();
  }
  else {
    Serial.print("UNKNOWN_COMMAND:");
    Serial.println(cmd);
  }
}

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < NUM_LOCKERS; i++) {
    pinMode(ledPins[i], OUTPUT);
    digitalWrite(ledPins[i], LOW);
  }

  Serial.println("ESP32_SMART_LOCKER_LED_READY");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    handleCommand(cmd);
  }

  delay(20);
}
