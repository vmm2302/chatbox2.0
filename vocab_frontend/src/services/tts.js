/**
 * Text-to-Speech (TTS) Service using Local Kokoro-ONNX Backend.
 * Completely offline, zero cloud API dependencies, zero external network calls.
 * Plays 24kHz 16-bit PCM WAV audio synthesized locally on the machine.
 */

import { getAuthHeaders, notifyUnauthorized } from './api';

const API_BASE = '/api';

class LocalTTSService {
  constructor() {
    this.currentAudio = null;
    this.isPlaying = false;
    this.audioCache = new Map(); // cacheKey -> ObjectURL
  }

  /**
   * Cancel and immediately stop any active audio playback.
   * Ensures repeated button clicks never overlap audio.
   */
  cancel() {
    if (this.currentAudio) {
      try {
        this.currentAudio.pause();
        this.currentAudio.currentTime = 0;
      } catch (e) {
        console.debug('Error stopping audio:', e);
      }
      this.currentAudio = null;
    }
    this.isPlaying = false;
  }

  /**
   * Synthesize and play speech for an English word or phrase using local Kokoro-ONNX.
   *
   * @param {string} text - English word or sentence to pronounce.
   * @param {Object} options - Configuration options.
   * @param {string} [options.voice='af_heart'] - Kokoro voice (default: af_heart US Female).
   * @param {number} [options.speed=1.0] - Speech speed multiplier.
   * @param {Function} [options.onStart] - Callback when playback starts.
   * @param {Function} [options.onEnd] - Callback when playback ends or resets.
   * @param {Function} [options.onError] - Callback when synthesis fails.
   */
  async speak(text, { voice = 'af_heart', speed = 1.0, onStart, onEnd, onError } = {}) {
    // 1. Immediately cancel any currently playing audio so clicks never overlap
    this.cancel();

    if (!text || typeof text !== 'string') {
      if (onEnd) onEnd();
      return;
    }

    const cleanText = text.replace(/[/\\()[\]*~_"'`“”‘’]/g, ' ').replace(/\s+/g, ' ').trim();
    if (!cleanText) {
      if (onEnd) onEnd();
      return;
    }

    this.isPlaying = true;
    if (onStart) onStart();

    const cacheKey = `${cleanText.toLowerCase()}__${voice}__${speed}`;

    try {
      let audioUrl = this.audioCache.get(cacheKey);

      if (!audioUrl) {
        const response = await fetch(`${API_BASE}/tts/synthesize`, {
          method: 'POST',
          headers: getAuthHeaders({
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({
            text: cleanText,
            voice: voice || 'af_heart',
            speed: speed || 1.0,
          }),
        });

        if (response.status === 401) {
          notifyUnauthorized();
          throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
        }

        if (!response.ok) {
          let errorMessage = 'Không thể phát âm: Mô hình TTS cục bộ chưa sẵn sàng.';
          try {
            const errData = await response.json();
            if (errData.detail) {
              errorMessage = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
            }
          } catch {
            errorMessage = `Dịch vụ phát âm trả về mã lỗi ${response.status}.`;
          }
          throw new Error(errorMessage);
        }

        const blob = await response.blob();
        audioUrl = URL.createObjectURL(blob);
        this.audioCache.set(cacheKey, audioUrl);
      }

      const audio = new Audio(audioUrl);
      this.currentAudio = audio;

      audio.onended = () => {
        this.isPlaying = false;
        this.currentAudio = null;
        if (onEnd) onEnd();
      };

      audio.onerror = (evt) => {
        this.isPlaying = false;
        this.currentAudio = null;
        const msg = 'Lỗi khi phát tệp âm thanh từ vựng.';
        console.error('Audio playback error:', evt);
        if (onError) onError(msg);
        if (onEnd) onEnd();
      };

      await audio.play();
    } catch (err) {
      this.isPlaying = false;
      this.currentAudio = null;
      console.error('Local TTS synthesis error:', err);
      if (onError) {
        onError(err.message || 'Lỗi kết nối dịch vụ phát âm cục bộ.');
      }
      if (onEnd) onEnd();
    }
  }

  speakSlow(text, callbacks = {}) {
    this.speak(text, { ...callbacks, speed: 0.85 });
  }
}

export const tts = new LocalTTSService();
