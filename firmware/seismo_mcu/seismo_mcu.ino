/*
 * Sismo-LA - Firmware MCU (STM32U585 sur Arduino UNO Q)
 *
 * Role : echantillonner l'IMU en continu, detecter une secousse par algorithme
 * STA/LTA, caracteriser l'evenement (PGA, duree, frequence dominante approx) et
 * l'emettre.
 *
 * Transport : pour le prototype, on emet une ligne JSON sur le port serie. En
 * production App Lab, remplacer emitEvent() par un appel Bridge (RPC) vers
 * l'application Python cote Linux.
 *
 * Capteur : Modulino Movement (LSM6DSOX) via Qwiic. Adapter si autre IMU.
 */

#include <Modulino.h>

ModulinoMovement imu;

// --- Parametres d'echantillonnage ---
const float SAMPLE_HZ = 100.0f;
const unsigned long SAMPLE_PERIOD_US = (unsigned long)(1000000.0f / SAMPLE_HZ);

// --- Parametres STA/LTA ---
const float STA_SEC = 0.5f;
const float LTA_SEC = 10.0f;
const float TRIGGER_ON = 4.0f;   // ratio STA/LTA de declenchement
const float TRIGGER_OFF = 1.5f;  // ratio de fin d'evenement
const float GRAVITY_ALPHA = 0.995f; // suivi lent de la composante gravite

const int STA_N = (int)(STA_SEC * SAMPLE_HZ);
const int LTA_N = (int)(LTA_SEC * SAMPLE_HZ);

// Moyennes glissantes exponentielles (evite de stocker de longs buffers).
float sta = 0.0f;
float lta = 1e-6f; // evite division par zero au demarrage
const float STA_W = 2.0f / (STA_N + 1);
const float LTA_W = 2.0f / (LTA_N + 1);

// Estimation de la gravite par axe (filtre passe-bas).
float gx = 0, gy = 0, gz = 1.0f;

// Etat de l'evenement courant.
bool inEvent = false;
float eventPeakG = 0.0f;
unsigned long eventStartMs = 0;
unsigned long lastSampleUs = 0;
long zeroCrossings = 0;
float prevDyn = 0.0f;

void setup() {
  Serial.begin(115200);
  Modulino.begin();
  imu.begin();
  // Amorcage du LTA pendant ~1 s pour stabiliser le bruit de fond.
  unsigned long t0 = millis();
  while (millis() - t0 < 1000) {
    float d = readDynamicMagnitude();
    lta = lta + LTA_W * (d - lta);
    sta = sta + STA_W * (d - sta);
    delayMicroseconds(SAMPLE_PERIOD_US);
  }
}

// Norme de l'acceleration dynamique (gravite retiree), en g.
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

  // Mise a jour des moyennes (le LTA est gele pendant un evenement pour ne pas
  // s'auto-contaminer par le signal sismique).
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
    if ((prevDyn < 0) != (dyn < 0)) zeroCrossings++; // approx freq dominante
    if (ratio < TRIGGER_OFF) {
      unsigned long durMs = millis() - eventStartMs;
      float domHz = (durMs > 0) ? (zeroCrossings * 1000.0f) / (2.0f * durMs) : 0;
      emitEvent(eventStartMs, eventPeakG, durMs, domHz);
      inEvent = false;
    }
  }
  prevDyn = dyn - sta; // signal centre pour le comptage de passages a zero
}

// Prototype : JSON sur le port serie. En production App Lab -> Bridge RPC.
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
