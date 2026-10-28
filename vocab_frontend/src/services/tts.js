/**
 * Text-to-Speech (TTS) Service using Web Speech API.
 * Completely offline, zero bandwidth, zero cloud dependencies.
 */

class TTSService {
  constructor() {
    this.synth = typeof window !== 'undefined' ? window.speechSynthesis : null;
    this.voices = [];
    if (this.synth) {
      this.loadVoices();
      if (this.synth.onvoiceschanged !== undefined) {
        this.synth.onvoiceschanged = () => this.loadVoices();
      }
    }
  }

  loadVoices() {
    if (!this.synth) return;
    this.voices = this.synth.getVoices();
  }

  getBestVoice(lang = 'en-US') {
    if (!this.voices || this.voices.length === 0) {
      this.loadVoices();
    }
    // Prefer natural / google / english voices
    const targetLang = lang.toLowerCase();
    const matched = this.voices.filter((v) => v.lang.toLowerCase().startsWith(targetLang.slice(0, 2)));
    if (matched.length === 0) return null;

    // Pick US or UK voice specifically if available
    const exact = matched.find((v) => v.lang.toLowerCase() === targetLang);
    if (exact) return exact;

    const naturalVoice = matched.find((v) => v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('David'));
    return naturalVoice || matched[0];
  }

  speak(text, { lang = 'en-US', rate = 1.0, pitch = 1.0, onStart, onEnd } = {}) {
    if (!this.synth) {
      console.warn('SpeechSynthesis is not supported in this browser.');
      return;
    }

    // Cancel any ongoing speech
    this.synth.cancel();

    // Clean word / sentence to speak (remove slashes, brackets)
    const cleanText = text.replace(/[/\\()[\]]/g, '').trim();
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = lang;
    utterance.rate = rate;
    utterance.pitch = pitch;

    const voice = this.getBestVoice(lang);
    if (voice) {
      utterance.voice = voice;
    }

    if (onStart) utterance.onstart = onStart;
    if (onEnd) utterance.onend = onEnd;
    utterance.onerror = (e) => {
      console.debug('TTS playback notice:', e);
      if (onEnd) onEnd();
    };

    this.synth.speak(utterance);
  }

  speakSlow(text, lang = 'en-US', callbacks = {}) {
    this.speak(text, { ...callbacks, lang, rate: 0.72 });
  }

  cancel() {
    if (this.synth) {
      this.synth.cancel();
    }
  }
}

export const tts = new TTSService();
