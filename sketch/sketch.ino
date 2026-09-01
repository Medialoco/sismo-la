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
 *
 * Since 2026-09-01 the detector runs on a 0.7-12 Hz band-passed signal rather
 * than on the raw vector magnitude, and `pga_g` is the band-passed peak. See
 * "The seismic band-pass" below for why. Measured afterwards, on the two floors
 * this sketch reports over the same ten seconds: the filter removes 1.43x of
 * the at-rest floor (0.00036 g in band against 0.00052 g wideband), worth
 * 0.18 Mw. Real, and far short of turning this into an instrument that feels
 * distant earthquakes.
 */

#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>

ModulinoMovement imu;

// Types first, before any function: the Arduino preprocessor injects generated
// prototypes just above the first function definition, and a prototype naming a
// type declared further down does not compile.

// State of one axis' band-pass cascade: two one-pole high-pass sections then
// two one-pole low-pass sections.
struct BandPass {
  float h1x, h1y, h2x, h2y, lp1, lp2;
  bool primed;
};

// One IMU reading, in both representations.
struct Reading {
  float band;  // 0.7-12 Hz, unity gain in band, in g  -> drives everything
  float wide;  // raw dynamic magnitude, in g          -> diagnostic only
};

// --- Sampling parameters ---
// Nominal only: this is a poll loop over I2C, and the real rate is measured at
// boot and again at every heartbeat. Every coefficient below is derived from
// the MEASURED rate, never from this constant.
const float SAMPLE_HZ = 100.0f;
const unsigned long SAMPLE_PERIOD_US = (unsigned long)(1000000.0f / SAMPLE_HZ);

// --- The seismic band-pass ---
//
// Until 2026-09-01 the trigger ran on the raw dynamic magnitude, i.e. on
// everything from 0.08 Hz (where the gravity EMA stops removing DC) to the
// sensor's anti-alias corner. STA/LTA is a *ratio*, so any noise the detector
// looks at outside the band an earthquake actually occupies costs sensitivity
// and buys nothing.
//
// The band is argued from the station's own journal, not from a textbook. Over
// the 255 shakes recorded at this location, the dominant ground-motion
// frequency (dom_hz/2, the rectification factor) runs p5 = 1.0 Hz, median
// 4.4 Hz, p95 = 7.8 Hz. 0.7 Hz sits below the 5th percentile and 12 Hz above
// the 95th, so the band was chosen to keep essentially all of the motion this
// site really produces; a local M4-M4.5 at 20-50 km radiates in the same
// 1-10 Hz window, so the same band fits the signal we are waiting for.
//
// NOTE, and it is the uncomfortable one: that same journal says 96.5% of the
// FALSE positives already sit inside 0.7-12 Hz. The band-pass is therefore not
// a false-positive filter — the earlier belief that footsteps and doors were
// "high frequency" came from reading dom_hz as a physical frequency when it
// runs at twice the ground motion. What the filter can still do is remove
// out-of-band NOISE POWER from the LTA, which lowers the amplitude at which a
// real earthquake reaches TRIGGER_ON. How much depends entirely on where the
// noise floor's energy actually lives, which is the open question this build
// is instrumented to answer (see the heartbeat below).
//
// Structure: two one-pole high-pass sections plus two one-pole low-pass
// sections, per axis, on the RAW acceleration (the high-pass removes gravity
// itself, so this path does not use the gravity EMA at all). A cascade of
// first-order sections rather than a biquad is deliberate: at 0.7 Hz over
// 100 Hz a biquad's pole pair sits within 0.04 of the unit circle, where
// float32 coefficient rounding starts to matter, while a one-pole section
// stores a = 0.957 and is numerically unremarkable. Cost is four first-order
// sections per axis, about 3600 flops/s at 100 Hz.
const float BP_HP_HZ = 0.7f;
const float BP_LP_HZ = 12.0f;

// --- STA/LTA parameters ---
const float STA_SEC = 0.5f;
const float LTA_SEC = 10.0f;
// STA/LTA trigger ratio. Lowered from 4.0 to 2.5 on measured evidence, not
// taste:
//   - the sensor's own noise produces ZERO triggers per hour at any ratio down
//     to 1.8 over six simulated hours, so what a lower ratio actually catches
//     is more building vibration, not more electrical noise;
//   - the ~780 triggers/day recorded on a desk were all mechanical, and their
//     measured amplitude distribution says this change adds only 5-55% of them;
//   - at 4.0 the detector was blind to a long slow wavelet (2 Hz, 12 s,
//     0.02 g) — the very shape a distant moderate earthquake arrives with,
//     because a slow envelope lets the 10 s LTA creep up with the signal. At
//     2.5 the same wavelet is caught.
// 2.5 rather than 2.0 keeps a 1.67x margin over TRIGGER_OFF: the simulations
// use white noise, while real MEMS noise has a 1/f component and the board
// drifts thermally, and none of that can be re-tested remotely.
// Deliberately UNCHANGED when the band-pass went in, so the before/after
// comparison measures the filter and nothing else.
const float TRIGGER_ON = 2.5f;   // STA/LTA trigger ratio
const float TRIGGER_OFF = 1.5f;  // end-of-event ratio
const float GRAVITY_ALPHA = 0.995f; // slow tracking of the gravity component

// --- Rate-dependent coefficients, all recomputed from the MEASURED rate ---
float fsHz = SAMPLE_HZ;
float STA_W = 2.0f / (STA_SEC * SAMPLE_HZ + 1.0f);
float LTA_W = 2.0f / (LTA_SEC * SAMPLE_HZ + 1.0f);
float bpA = 0.0f;      // one-pole high-pass coefficient
float bpB = 0.0f;      // one-pole low-pass coefficient
float bpNorm = 1.0f;   // scales the cascade to unity gain in the passband

// exp(-u), u >= 0, without libm.
//
// `expf` cannot be called from this sketch: newlib's version sets errno, this
// Zephyr link provides no `__errno`, and the build dies at the link stage with
// "undefined reference to `__errno'" — long after every compilation unit has
// succeeded, which makes it look like a platform fault rather than a call site.
// Range-reduce by halving until u <= 0.5, sum seven Taylor terms (error under
// 1e-7 there), then square back. The arguments here are 2*pi*fc/fs, i.e. 0.04
// and 0.75 at the nominal rate, so this is comfortably inside its accurate
// range.
static float expNeg(float u) {
  if (!(u > 0.0f)) return 1.0f;
  int halvings = 0;
  while (u > 0.5f && halvings < 12) { u *= 0.5f; halvings++; }
  float term = 1.0f, sum = 1.0f;
  for (int k = 1; k <= 7; k++) {
    term *= -u / (float)k;
    sum += term;
  }
  while (halvings-- > 0) sum *= sum;
  return sum;
}

// Recompute every coefficient for a measured sample rate.
//
// The passband gain of the cascade is not 1 (it peaks at 0.857 for 0.7/12 Hz
// at 100 Hz), and `pga_g` is now read off this signal and fed to the amplitude
// model, so it has to come out in real g. Normalising by the peak keeps it
// comparable with a ground-motion prediction equation. The peak of a
// (1-pole HP)^2 (1-pole LP)^2 cascade sits at the geometric mean of the two
// corners, f0 = sqrt(0.7 * 12) = 2.90 Hz; evaluating the exact digital
// magnitude there matches a numerical sweep of the true peak to 0.01%.
void setRates(float fs) {
  if (!(fs > 20.0f && fs < 400.0f)) return;  // refuse a nonsensical measurement
  fsHz = fs;
  STA_W = 2.0f / (STA_SEC * fs + 1.0f);
  LTA_W = 2.0f / (LTA_SEC * fs + 1.0f);

  bpA = expNeg(2.0f * PI * BP_HP_HZ / fs);
  bpB = 1.0f - expNeg(2.0f * PI * BP_LP_HZ / fs);

  const float theta = 2.0f * PI * sqrtf(BP_HP_HZ * BP_LP_HZ) / fs;
  const float c = cosf(theta);
  const float mHp = bpA * 2.0f * sinf(theta * 0.5f)
                    / sqrtf(1.0f - 2.0f * bpA * c + bpA * bpA);
  const float p = 1.0f - bpB;
  const float mLp = bpB / sqrtf(1.0f - 2.0f * p * c + p * p);
  const float peak = mHp * mHp * mLp * mLp;
  bpNorm = (peak > 1e-6f) ? (1.0f / peak) : 1.0f;
}

BandPass bpX, bpY, bpZ;

// One sample through the cascade. Priming on the first sample (rather than
// from zero) matters: the axis carrying gravity starts at ~1 g, and a
// high-pass fed a 1 g step rings for seconds. Seeding x[-1] with the first
// sample makes the step disappear instead of being filtered.
float bpStep(BandPass &s, float x) {
  if (!s.primed) {
    s.h1x = x; s.h1y = 0.0f;
    s.h2x = 0.0f; s.h2y = 0.0f;
    s.lp1 = 0.0f; s.lp2 = 0.0f;
    s.primed = true;
    return 0.0f;
  }
  const float y1 = bpA * (s.h1y + x - s.h1x);
  s.h1x = x; s.h1y = y1;
  const float y2 = bpA * (s.h2y + y1 - s.h2x);
  s.h2x = y1; s.h2y = y2;
  s.lp1 += bpB * (y2 - s.lp1);
  s.lp2 += bpB * (s.lp1 - s.lp2);
  return s.lp2;
}

void resetBandPass() {
  bpX.primed = false;
  bpY.primed = false;
  bpZ.primed = false;
}

// Exponential moving averages (avoids storing long buffers). `band` drives the
// trigger; `wide` is carried only so the heartbeat can report how much of the
// noise floor lies outside the band — that ratio is the whole experiment.
float staBand = 0.0f, ltaBand = 1e-6f;
float ltaWide = 1e-6f;

// Per-axis gravity estimate (low-pass filter), used by the wideband diagnostic
// path only.
float gx = 0, gy = 0, gz = 1.0f;

// Current event state.
bool inEvent = false;
float eventPeakBand = 0.0f;
float eventPeakWide = 0.0f;
unsigned long eventStartMs = 0;
unsigned long lastSampleUs = 0;
long zeroCrossings = 0;
// Previous sample of the MEAN-CENTERED signal. Both sides of the sign test
// must be centered: the band-passed magnitude is still a vector magnitude and
// is never negative, so testing its raw sign would always yield the same
// answer.
float prevCentered = 0.0f;

// Heartbeat: proves the MCU->Linux link is alive even with no shakes.
const unsigned long HEARTBEAT_MS = 10000;
unsigned long lastHeartbeatMs = 0;
unsigned long sampleCount = 0;

// --- Continuous envelope ---
//
// The STA/LTA trigger above has to decide, unaided, tens of thousands of times
// a day, whether the last half second was an earthquake. That is what forces it
// to demand a large signal-to-noise ratio: every window it examines is another
// chance to be wrong, so the threshold has to sit far out in the tail of the
// noise. Measured on this station the amplitude it needs is ~2 mg for an
// earthquake-shaped wavetrain, which is M3.9 at 30 km.
//
// The catalog, however, publishes the origin time of every earthquake. Looking
// at a KNOWN instant is a completely different statistical problem: a handful
// of windows per earthquake instead of ~170000 a day, so the same false-alarm
// budget is met at a far lower threshold, and the test can average over the
// whole wavetrain instead of reacting inside half a second. Measured gain on
// this station's own noise: x7.7 in amplitude, i.e. 1.0 magnitude unit.
//
// All that costs is keeping a record of how much the ground moved, second by
// second, so there is something to go back and look at. That is this block: per
// second, the peak and the rms of the same 0.7-12 Hz signal the trigger uses,
// batched to keep the Bridge quiet. 2 numbers a second, ~1.6 MB a day on the
// Linux side.
//
// This is NOT a second detector and must never be presented as one. A shake
// found this way was found because the catalog said where to look; the
// distinction is carried all the way to the published snapshot.
const unsigned long ENV_BUCKET_MS = 1000;   // one envelope sample per second
const int ENV_BATCH = 10;                   // one notification per 10 samples
unsigned long envBucketStartMs = 0;
float envPeak = 0.0f;
float envSumSq = 0.0f;
unsigned long envSamples = 0;
unsigned long envPkUg[ENV_BATCH];
unsigned long envRmsUg[ENV_BATCH];
int envFilled = 0;

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

// Narrow the accelerometer's anti-alias filter.
//
// `Arduino_LSM6DSOX::begin()` leaves LPF2 at ODR/4 (~26 Hz). HPCF_XL=001
// selects ODR/10 (~10.4 Hz), which keeps the 1-10 Hz seismic band and removes
// bandwidth that only carries noise. This is the analog-side half of the same
// argument as the digital band-pass above; the digital filter adds the
// high-pass side, which the sensor cannot do at all.
//
// The predicted sqrt(26/10.4) = 1.58x reduction of the floor did NOT show up
// when it was first measured: 81 heartbeats after the change gave a dyn median
// of 0.00074 g against 0.00066-0.00069 g before. Kept anyway: it costs nothing,
// and that measurement was taken in a noisy daytime window against a window
// from another night, so it was never a clean test. The two-channel floors
// reported below were introduced precisely so no such comparison is needed.
static bool narrowAntiAliasFilter() {
  const uint8_t ADDR = 0x6A;      // LSM6DSOX on the Modulino Movement
  const uint8_t CTRL8_XL = 0x17;
  // Keep the bits begin() sets (0x09) and add HPCF_XL=001 in bits 7:5.
  const uint8_t WANTED = 0x29;

  Wire1.beginTransmission(ADDR);
  Wire1.write(CTRL8_XL);
  Wire1.write(WANTED);
  if (Wire1.endTransmission() != 0) return false;

  // Read it back. A write that silently did nothing would show up as "the room
  // got no quieter", which is indistinguishable from a wrong conclusion about
  // where the noise comes from — so verify rather than assume.
  Wire1.beginTransmission(ADDR);
  Wire1.write(CTRL8_XL);
  if (Wire1.endTransmission(false) != 0) return false;
  if (Wire1.requestFrom(ADDR, (uint8_t)1) != 1) return false;
  return Wire1.read() == WANTED;
}

// True when enough time has passed for the next sample. Also the single place
// the sample clock is advanced, so warm-up and steady state are timed
// identically — otherwise the rate measured at boot would not be the rate the
// main loop actually runs at.
bool dueForSample() {
  const unsigned long now = micros();
  if (now - lastSampleUs < SAMPLE_PERIOD_US) return false;
  lastSampleUs = now;
  return true;
}

Reading readSample() {
  imu.update();
  const float ax = imu.getX();
  const float ay = imu.getY();
  const float az = imu.getZ();

  gx = GRAVITY_ALPHA * gx + (1 - GRAVITY_ALPHA) * ax;
  gy = GRAVITY_ALPHA * gy + (1 - GRAVITY_ALPHA) * ay;
  gz = GRAVITY_ALPHA * gz + (1 - GRAVITY_ALPHA) * az;
  const float dx = ax - gx, dy = ay - gy, dz = az - gz;

  const float fx = bpStep(bpX, ax);
  const float fy = bpStep(bpY, ay);
  const float fz = bpStep(bpZ, az);

  Reading r;
  r.wide = sqrtf(dx * dx + dy * dy + dz * dz);
  r.band = bpNorm * sqrtf(fx * fx + fy * fy + fz * fz);
  return r;
}

void setup() {
  Bridge.begin();
  Monitor.begin(115200);
  // Announce life BEFORE touching the I2C bus. `imu.begin()` can block for a
  // long time on a half-seated Qwiic connector, and until 2026-09-01 the first
  // report() came after it — so "MCU never flashed", "MCU held in reset" and
  // "sensor bus stuck" all produced the same symptom, total silence, and cost
  // an hour to tell apart. This line makes the MCU's own boot observable
  // independently of whether the sensor answers.
  report("booting");

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

  report(narrowAntiAliasFilter()
         ? "anti-alias filter set to ODR/10 (~10 Hz)"
         : "anti-alias filter UNCHANGED - register write refused, floor stays ~26 Hz");

  setRates(SAMPLE_HZ);
  resetBandPass();

  // Phase 1 - measure the sample rate the loop really achieves. The I2C read
  // costs a few ms and ModulinoMovement::update() fetches the gyroscope too,
  // so 100 Hz is an aspiration. Filter corners placed with the wrong rate are
  // wrong by the same proportion, which at 0.7 Hz is exactly where it hurts.
  unsigned long t0 = millis();
  unsigned long n = 0;
  while (millis() - t0 < 5000UL) {
    if (dueForSample()) { readSample(); n++; }
  }
  const unsigned long elapsed = millis() - t0;
  setRates(elapsed > 0 ? (n * 1000.0f) / (float)elapsed : SAMPLE_HZ);
  // Formatted by hand rather than with "%f": newlib-nano on this platform is
  // routinely built without floating-point printf, and a status line that
  // silently prints nothing would hide the one number the filter depends on.
  char line[96];
  const int whole = (int)fsHz;
  const int tenth = (int)((fsHz - whole) * 10.0f + 0.5f);
  snprintf(line, sizeof(line),
           "sample rate %d.%d Hz, band 0.7-12 Hz (2 poles each side)",
           whole, tenth);
  report(line);

  // Phase 2 - the filter states were built with the wrong coefficients, so
  // start them again and let them settle before anything reads them. Two poles
  // at 0.7 Hz settle with tau = 0.23 s; 2 s is ~9 tau.
  resetBandPass();
  t0 = millis();
  while (millis() - t0 < 2000UL) {
    if (dueForSample()) readSample();
  }

  // Seed both averages with a real reading instead of letting the LTA climb
  // from ~0: a 10 s EMA started at zero stays far from the true noise floor for
  // tens of seconds, and every ratio computed meanwhile is spuriously large.
  // Seeding, then warming up for one full LTA window, avoids a burst of false
  // triggers at boot.
  while (!dueForSample()) { /* wait for the next slot */ }
  Reading seed = readSample();
  staBand = seed.band;
  ltaBand = (seed.band > 0.0f) ? seed.band : 1e-6f;
  ltaWide = (seed.wide > 0.0f) ? seed.wide : 1e-6f;

  t0 = millis();
  while (millis() - t0 < (unsigned long)(LTA_SEC * 1000.0f)) {
    if (!dueForSample()) continue;
    Reading r = readSample();
    ltaBand += LTA_W * (r.band - ltaBand);
    staBand += STA_W * (r.band - staBand);
    ltaWide += LTA_W * (r.wide - ltaWide);
  }
  report("noise floor ready");

  lastHeartbeatMs = millis();
  sampleCount = 0;
  envBucketStartMs = lastHeartbeatMs;
}

// Accumulate one sample into the current one-second envelope bucket, and ship a
// batch once ENV_BATCH buckets are closed.
//
// Runs unconditionally, event or no event: the whole point is a continuous
// record, and an earthquake that never reached TRIGGER_ON is exactly the case
// this is for.
void updateEnvelope(float band, unsigned long nowMs) {
  if (band > envPeak) envPeak = band;
  envSumSq += band * band;
  envSamples++;

  if (nowMs - envBucketStartMs < ENV_BUCKET_MS) return;

  const float rms = (envSamples > 0) ? sqrtf(envSumSq / (float)envSamples) : 0.0f;
  if (envFilled < ENV_BATCH) {
    // Micro-g integers: the floor is ~360 ug and the largest shake ever
    // recorded here 1.83 g, so one unit of quantisation is 0.3% of the floor
    // and the range needs seven digits. Integers also keep this off newlib's
    // floating-point printf, which this platform is not built with.
    envPkUg[envFilled] = (unsigned long)(envPeak * 1e6f + 0.5f);
    envRmsUg[envFilled] = (unsigned long)(rms * 1e6f + 0.5f);
    envFilled++;
  }
  envPeak = 0.0f;
  envSumSq = 0.0f;
  envSamples = 0;
  envBucketStartMs = nowMs;

  if (envFilled >= ENV_BATCH) {
    emitEnvelope(nowMs, envFilled);
    envFilled = 0;
  }
}

// One notification per batch, as a compact string.
//
// A string rather than N numeric arguments because the batch length is a tuning
// knob and an RPC signature is not: changing ENV_BATCH must not require a
// matching change in the Python handler's parameter list.
//
// `tEndMs` is the MCU clock at the end of the LAST bucket. The Python half
// re-anchors the batch on its own NTP-synced wall clock and uses these
// millisecond values only for the offsets WITHIN the batch. That is not a
// detail: this MCU's clock runs 1099 ppm slow against Linux (measured over a
// 2.6 h run), so an absolute time derived from millis() drifts by 10 s in three
// hours, which is the width of the arrival window the search uses. Within one
// 10 s batch the same drift is 11 ms.
void emitEnvelope(unsigned long tEndMs, int n) {
  char payload[220];
  int at = 0;
  for (int i = 0; i < n; i++) {
    const int wrote = snprintf(payload + at, sizeof(payload) - at,
                               (i == 0) ? "%lu:%lu" : ",%lu:%lu",
                               envPkUg[i], envRmsUg[i]);
    if (wrote <= 0 || at + wrote >= (int)sizeof(payload)) break;
    at += wrote;
  }
  payload[at] = '\0';
  Bridge.notify("mcu_envelope", tEndMs, (unsigned long)n, ENV_BUCKET_MS, payload);
}

void loop() {
  if (!dueForSample()) return;

  const Reading r = readSample();
  sampleCount++;
  updateEnvelope(r.band, millis());

  // Update the averages (the LTA is frozen during an event so it does not get
  // self-contaminated by the seismic signal).
  staBand += STA_W * (r.band - staBand);
  if (!inEvent) {
    ltaBand += LTA_W * (r.band - ltaBand);
    ltaWide += LTA_W * (r.wide - ltaWide);
  }
  if (ltaBand < 1e-7f) ltaBand = 1e-7f;  // a dead bus must not read as a quake

  const float ratio = staBand / ltaBand;

  // Centered about the short-term mean so the signal actually crosses zero.
  const float centered = r.band - staBand;

  if (!inEvent && ratio > TRIGGER_ON) {
    inEvent = true;
    eventPeakBand = r.band;
    eventPeakWide = r.wide;
    eventStartMs = millis();
    zeroCrossings = 0;
  } else if (inEvent) {
    if (r.band > eventPeakBand) eventPeakBand = r.band;
    if (r.wide > eventPeakWide) eventPeakWide = r.wide;
    if ((prevCentered < 0.0f) != (centered < 0.0f)) zeroCrossings++;
    if (ratio < TRIGGER_OFF) {
      const unsigned long durMs = millis() - eventStartMs;
      // Rectification note: this is a vector magnitude, so the rate runs about
      // 2x the true ground-motion frequency. Both downstream consumers absorb a
      // constant factor (log-linear distance fit, standardized classifier
      // feature), so it is a usable proxy, not a calibrated spectral estimate.
      // Since 2026-09-01 it is measured on the band-passed signal, like
      // everything else the event reports, so it is now bounded by the band:
      // roughly 1.4-24 Hz in these units.
      const float domHz = (durMs > 0)
                          ? (zeroCrossings * 1000.0f) / (2.0f * durMs) : 0;
      emitEvent(eventStartMs, eventPeakBand, durMs, domHz, eventPeakWide);
      inEvent = false;
    }
  }
  prevCentered = centered;

  const unsigned long ms = millis();
  if (ms - lastHeartbeatMs >= HEARTBEAT_MS) {
    const unsigned long window = ms - lastHeartbeatMs;
    const float fsNow = (window > 0) ? (sampleCount * 1000.0f) / (float)window
                                     : fsHz;
    // Re-derive the coefficients if the loop rate has genuinely drifted. The
    // 2% deadband keeps a noisy estimate from re-solving four transcendentals
    // every 10 s for nothing.
    if (fsNow > 20.0f && fsNow < 400.0f && fabsf(fsNow - fsHz) > 0.02f * fsHz) {
      setRates(fsNow);
    }
    lastHeartbeatMs = ms;
    sampleCount = 0;

    // Seven fields, and six of them exist for one measurement: ltaBand against
    // ltaWide, sampled in the SAME ten seconds, is the fraction of the noise
    // floor that lies outside 0.7-12 Hz. Comparing a floor measured today
    // against one measured last night proves nothing (the station's own
    // history is full of that trap); comparing two channels of the same
    // instant proves it outright.
    Bridge.notify("mcu_heartbeat", ms, ratio, r.band, ltaBand,
                  r.wide, ltaWide, fsHz);
    Monitor.print("{\"status\":\"alive\",\"t_ms\":");
    Monitor.print(ms);
    Monitor.print(",\"sta_lta\":");
    Monitor.print(ratio, 3);
    Monitor.print(",\"lta_band\":");
    Monitor.print(ltaBand, 6);
    Monitor.print(",\"lta_wide\":");
    Monitor.print(ltaWide, 6);
    Monitor.print(",\"fs_hz\":");
    Monitor.print(fsHz, 1);
    Monitor.println("}");
  }
}

// Two transports on purpose. `Bridge.notify` is the one the app consumes: it
// reaches the Python half through the router socket, which is the only path
// available now that App Lab runs that half inside a container. The Monitor
// line is kept as a human-readable trace for `arduino-app-cli monitor`.
//
// `pgaG` is the BAND-PASSED peak since 2026-09-01. It is the amplitude that
// actually crossed the trigger, and it is the one the amplitude model should
// learn from when a real earthquake finally arrives; reporting a wideband peak
// while triggering on a filtered one would fit the model to energy the
// detector never used. Records written before the change carry `schema: 1` in
// event_log.jsonl and are NOT comparable. `pgaWbG` keeps the old definition
// alongside, so the two can always be related after the fact.
void emitEvent(unsigned long tMs, float pgaG, unsigned long durMs, float domHz,
               float pgaWbG) {
  Bridge.notify("seismic_event", tMs, pgaG, durMs, domHz, pgaWbG);

  Monitor.print("{\"t_ms\":");
  Monitor.print(tMs);
  Monitor.print(",\"pga_g\":");
  Monitor.print(pgaG, 5);
  Monitor.print(",\"dur_ms\":");
  Monitor.print(durMs);
  Monitor.print(",\"dom_hz\":");
  Monitor.print(domHz, 2);
  Monitor.print(",\"pga_wb_g\":");
  Monitor.print(pgaWbG, 5);
  Monitor.println("}");
}
