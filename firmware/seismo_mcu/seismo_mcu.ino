/*
 * Sismo-LA - MCU firmware (STM32U585 on the Arduino UNO Q)
 *
 * Role: continuously sample the IMU, detect a shake with the STA/LTA algorithm,
 * characterize the event (PGA, duration, approximate dominant frequency) and
 * emit it.
 *
 * Transport: for the prototype we emit a JSON line over the serial port. In an
 * App Lab production build, replace emitEvent() with a Bridge (RPC) call to the
 * Python application on the Linux side.
 *
 * Sensor: Modulino Movement (LSM6DSOX) over Qwiic. Adapt for a different IMU.
 */

#include <Modulino.h>

ModulinoMovement imu;

// --- Sampling parameters ---
const float SAMPLE_HZ = 100.0f;
const unsigned long SAMPLE_PERIOD_US = (unsigned long)(1000000.0f / SAMPLE_HZ);

// --- STA/LTA parameters ---
const float STA_SEC = 0.5f;
const float LTA_SEC = 10.0f;
const float TRIGGER_ON = 4.0f;   // STA/LTA trigger ratio
const float TRIGGER_OFF = 1.5f;  // end-of-event ratio
const float GRAVITY_ALPHA = 0.995f; // slow tracking of the gravity component

const int STA_N = (int)(STA_SEC * SAMPLE_HZ);
const int LTA_N = (int)(LTA_SEC * SAMPLE_HZ);

// Exponential moving averages (avoids storing long buffers).
float sta = 0.0f;
float lta = 1e-6f; // avoids division by zero at startup
const float STA_W = 2.0f / (STA_N + 1);
const float LTA_W = 2.0f / (LTA_N + 1);

// Per-axis gravity estimate (low-pass filter).
float gx = 0, gy = 0, gz = 1.0f;

// Current event state.
bool inEvent = false;
float eventPeakG = 0.0f;
unsigned long eventStartMs = 0;
unsigned long lastSampleUs = 0;
long zeroCrossings = 0;
float prevDyn = 0.0f;

void setup() {
  Serial.begin(115200);
  // On the UNO Q the Qwiic connector is on the I2C bus Wire1 (not Wire).
  // If Modulino.begin() does not find the node, pass the bus explicitly:
  //   Modulino.begin(Wire1);
  Modulino.begin();
  imu.begin();
  // Warm up the LTA for ~1 s to stabilize the background noise estimate.
  unsigned long t0 = millis();
  while (millis() - t0 < 1000) {
    float d = readDynamicMagnitude();
    lta = lta + LTA_W * (d - lta);
    sta = sta + STA_W * (d - sta);
    delayMicroseconds(SAMPLE_PERIOD_US);
  }
}

// Magnitude of the dynamic acceleration (gravity removed), in g.
float readDynamicMagnitude() {
  imu.update();
  float ax = imu.getX();
  float ay = imu.getY();
  float az = imu.getZ();

  gx = GRAVITY_ALPHA * gx + (1 - GRAVITY_ALPHA) * ax;
  gy = GRAVITY_ALPHA * gy + (1 - GRAVITY_ALPHA) * ay;
  gz = GRAVITY_ALPHA * gz + (1 - GRAVITY_ALPHA) * az;

  float dx = ax - gx, dy = ay - gy, dz = az - gz;
  return sqrtf(dx * dx + dy * dy + dz * dz);
}

void loop() {
  unsigned long now = micros();
  if (now - lastSampleUs < SAMPLE_PERIOD_US) return;
  lastSampleUs = now;

  float dyn = readDynamicMagnitude();

  // Update the averages (the LTA is frozen during an event so it does not get
  // self-contaminated by the seismic signal).
  sta = sta + STA_W * (dyn - sta);
  if (!inEvent) {
    lta = lta + LTA_W * (dyn - lta);
  }

  float ratio = sta / lta;

  if (!inEvent && ratio > TRIGGER_ON) {
    inEvent = true;
    eventPeakG = dyn;
    eventStartMs = millis();
    zeroCrossings = 0;
  } else if (inEvent) {
    if (dyn > eventPeakG) eventPeakG = dyn;
    if ((prevDyn < 0) != (dyn < 0)) zeroCrossings++; // dominant freq approx.
    if (ratio < TRIGGER_OFF) {
      unsigned long durMs = millis() - eventStartMs;
      float domHz = (durMs > 0) ? (zeroCrossings * 1000.0f) / (2.0f * durMs) : 0;
      emitEvent(eventStartMs, eventPeakG, durMs, domHz);
      inEvent = false;
    }
  }
  prevDyn = dyn - sta; // centered signal for zero-crossing counting
}

// Prototype: JSON over the serial port. In App Lab production -> Bridge RPC.
void emitEvent(unsigned long tMs, float pgaG, unsigned long durMs, float domHz) {
  Serial.print("{\"t_ms\":");
  Serial.print(tMs);
  Serial.print(",\"pga_g\":");
  Serial.print(pgaG, 5);
  Serial.print(",\"dur_ms\":");
  Serial.print(durMs);
  Serial.print(",\"dom_hz\":");
  Serial.print(domHz, 2);
  Serial.println("}");
}
