(function () {
    'use strict';

    // Mirrors the firmware buzzer: three short beeps, repeated no more than
    // once per minute while the alert stays active.
    const REBEEP_INTERVAL_MS = 60000;
    const BEEP_FREQUENCY = 2200;

    let audioContext = null;
    let beepedOnce = false;
    let lastBeepAt = 0;
    let pendingAlert = false;

    function getAudioContext() {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) {
            return null;
        }
        if (!audioContext) {
            audioContext = new AudioContextClass();
        }
        return audioContext;
    }

    async function unlockAudio() {
        const context = getAudioContext();
        if (!context) {
            return false;
        }
        if (context.state === 'suspended') {
            try {
                await context.resume();
            } catch (error) {
                return false;
            }
        }
        if (pendingAlert && context.state === 'running') {
            pendingAlert = false;
            beepNow();
        }
        return context.state === 'running';
    }

    function beepNow() {
        const context = getAudioContext();
        if (!context || context.state !== 'running') {
            return;
        }

        const startAt = context.currentTime;
        [0, 0.5, 1.0].forEach((offset) => {
            const oscillator = context.createOscillator();
            const gain = context.createGain();

            oscillator.type = 'square';
            oscillator.frequency.setValueAtTime(BEEP_FREQUENCY, startAt + offset);
            gain.gain.setValueAtTime(0.0001, startAt + offset);
            gain.gain.exponentialRampToValueAtTime(0.12, startAt + offset + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.0001, startAt + offset + 0.25);

            oscillator.connect(gain);
            gain.connect(context.destination);
            oscillator.start(startAt + offset);
            oscillator.stop(startAt + offset + 0.3);
        });
    }

    async function playEnvironmentalAlert(alert) {
        if (!alert || !alert.active) {
            return;
        }

        const now = Date.now();
        if (beepedOnce && now - lastBeepAt < REBEEP_INTERVAL_MS) {
            return;
        }
        beepedOnce = true;
        lastBeepAt = now;

        if (await unlockAudio()) {
            beepNow();
        } else {
            // Browsers block sound until the first click/key press. Play the
            // pending alert as soon as the user interacts with the page.
            pendingAlert = true;
        }
    }

    document.addEventListener('pointerdown', unlockAudio);
    document.addEventListener('keydown', unlockAudio);

    window.playEnvironmentalAlert = playEnvironmentalAlert;
})();
