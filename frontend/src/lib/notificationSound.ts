/**
 * In-app notification ping (Web Audio API, no asset file).
 * Browsers may block audio until the user interacts; call `primeNotificationAudio()` once
 * after a gesture so `playNotificationSound()` works on later polls.
 */

let sharedCtx: AudioContext | null = null;

function getOrCreateContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  try {
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return null;
    if (!sharedCtx || sharedCtx.state === "closed") {
      sharedCtx = new Ctx();
    }
    return sharedCtx;
  } catch {
    return null;
  }
}

/**
 * Resume/create AudioContext after a user gesture so notification sounds are not blocked.
 */
export function primeNotificationAudio(): void {
  const ctx = getOrCreateContext();
  if (ctx && ctx.state === "suspended") {
    void ctx.resume().catch(() => {});
  }
}

function playTone(
  ctx: AudioContext,
  startTime: number,
  freqStart: number,
  freqEnd: number,
  duration: number,
): void {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.setValueAtTime(freqStart, startTime);
  osc.frequency.exponentialRampToValueAtTime(Math.max(freqEnd, 1), startTime + duration * 0.85);
  gain.gain.setValueAtTime(0.0001, startTime);
  gain.gain.exponentialRampToValueAtTime(0.14, startTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(startTime);
  osc.stop(startTime + duration);
}

function playTwoToneChime(ctx: AudioContext): void {
  const t0 = ctx.currentTime;
  playTone(ctx, t0, 880, 660, 0.14);
  playTone(ctx, t0 + 0.12, 990, 740, 0.16);
}

/**
 * Short two-tone chime when unread inbox count increases.
 */
export function playNotificationSound(): void {
  const ctx = getOrCreateContext();
  if (!ctx) return;
  try {
    if (ctx.state === "suspended") {
      void ctx
        .resume()
        .then(() => {
          if (ctx.state === "running") playTwoToneChime(ctx);
        })
        .catch(() => {});
      return;
    }
    playTwoToneChime(ctx);
  } catch {
    /* autoplay / AudioContext restrictions */
  }
}
