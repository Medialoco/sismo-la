/*
 * Sismo-LA - MCU firmware (STM32U585 on the Arduino UNO Q)
 *
 * Role: continuously sample the IMU, detect a shake with the STA/LTA algorithm,
 * characterize the event (PGA, duration, approximate dominant frequency) and
 * emit it.
 *
 * Transport: `Bridge.notify("seismic_event", ...)`, an RPC notification the
 * Python half receives through `Bridge.provide`. On the UNO Q the MCU's
 * `Serial` goes to the D0/D1 UART pins (NOT USB): the USB-C port belongs to the
 * Linux MPU. Each event is also echoed as a JSON line on `Monitor` for
 * debugging with `arduino-app-cli monitor`.
 *
 * Sensor: Modulino Movement (LSM6DSOX) over Qwiic (bus Wire1). Adapt for a
 * different IMU.
 */

#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>

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
// Previous sample of the MEAN-CENTERED signal. Both sides of the sign test
// must be centered: `dyn` is a vector magnitude and is never negative, so
// testing its raw sign would always yield the same answer.
float prevCentered = 0.0f;

// Heartbeat: proves the MCU->Linux link is alive even with no shakes.
const unsigned long HEARTBEAT_MS = 10000;
unsigned long lastHeartbeatMs = 0;

bool sensorOk = false;

// Status goes out on both transports for the same reason events do: the Bridge
// reaches the app (and its log) from inside the container, the Monitor line is
// there for a human watching `arduino-app-cli monitor`.
void report(const char *message) {
  Bridge.notify("mcu_status", message);
  Monitor.print("{\"status\":\"");
  Monitor.print(message);
  Monitor.println("\"}");
}

void setup() {
  Bridge.begin();
  Monitor.begin(115200);
  // On the UNO Q the Qwiic connector is on the I2C bus Wire1 (not Wire),
  // so we pass the bus explicitly (known gotcha on this board).
  Modulino.begin(Wire1);
  sensorOk = imu.begin();
  report(sensorOk ? "imu ok" : "imu not found");

  // Without an IMU there is nothing to sample, and silently running the
  // detector on a dead bus would look identical to "no earthquakes". Say so,
  // repeatedly, instead of pretending to monitor.
  while (!sensorOk) {
    report("imu not found - check the Modulino on the Qwiic port (Wire1)");
    delay(5000);
    sensorOk = imu.begin();
    if (sensorOk) report("imu ok");
  }

  // Seed both averages with the first reading instead of letting the LTA climb
  // from ~0: a 10 s EMA started at zero stays far from the true noise floor for
  // tens of seconds, and every ratio computed meanwhile is spuriously large.
  // Seeding, then warming up for one full LTA window, avoids a burst of false
  // triggers at boot.
  float seed = readDynamicMagnitude();
  sta = seed;
  lta = (seed > 0.0f) ? seed : 1e-6f;

  unsigned long t0 = millis();
  while (millis() - t0 < (unsigned long)(LTA_SEC * 1000.0f)) {
    float d = readDynamicMagnitude();
    lta = lta + LTA_W * (d - lta);
    sta = sta + STA_W * (d - sta);
    delayMicroseconds(SAMPLE_PERIOD_US);
  }
  report("noise floor ready");
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

  // Centered about the short-term mean so the signal actually crosses zero.
  float centered = dyn - sta;

  if (!inEvent && ratio > TRIGGER_ON) {
    inEvent = true;
    eventPeakG = dyn;
    eventStartMs = millis();
    zeroCrossings = 0;
  } else if (inEvent) {
    if (dyn > eventPeakG) eventPeakG = dyn;
    if ((prevCentered < 0.0f) != (centered < 0.0f)) zeroCrossings++;
    if (ratio < TRIGGER_OFF) {
      unsigned long durMs = millis() - eventStartMs;
      // Rectification note: `dyn` is a vector magnitude, so this rate runs
      // about 2x the true ground-motion frequency. Both downstream consumers
      // absorb a constant factor (log-linear distance fit, standardized
      // classifier feature), so it is a usable proxy, not a calibrated
      // spectral estimate.
      float domHz = (durMs > 0) ? (zeroCrossings * 1000.0f) / (2.0f * durMs) : 0;
      emitEvent(eventStartMs, eventPeakG, durMs, domHz);
      inEvent = false;
    }
  }
  prevCentered = centered;

  unsigned long ms = millis();
  if (ms - lastHeartbeatMs >= HEARTBEAT_MS) {
    lastHeartbeatMs = ms;
    Bridge.notify("mcu_heartbeat", ms, ratio, dyn);
    Monitor.print("{\"status\":\"alive\",\"t_ms\":");
    Monitor.print(ms);
    Monitor.print(",\"sta_lta\":");
    Monitor.print(ratio, 3);
    Monitor.println("}");
  }
}

// Two transports on purpose. `Bridge.notify` is the one the app consumes: it
// reaches the Python half through the router socket, which is the only path
// available now that App Lab runs that half inside a container. The Monitor
// line is kept as a human-readable trace for `arduino-app-cli monitor`.
void emitEvent(unsigned long tMs, float pgaG, unsigned long durMs, float domHz) {
  Bridge.notify("seismic_event", tMs, pgaG, durMs, domHz);

  Monitor.print("{\"t_ms\":");
  Monitor.print(tMs);
  Monitor.print(",\"pga_g\":");
  Monitor.print(pgaG, 5);
  Monitor.print(",\"dur_ms\":");
  Monitor.print(durMs);
  Monitor.print(",\"dom_hz\":");
  Monitor.print(domHz, 2);
  Monitor.println("}");
}
