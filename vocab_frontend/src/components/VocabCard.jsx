import React, { useState } from 'react';
import { Volume2, ArrowUpRight, BookOpen, Sparkles, ShieldCheck } from 'lucide-react';
import { tts } from '../services/tts';
import { getLevelConfig } from '../utils/cefr';

function getPosIcon(pos = '') {
  const p = (pos || '').toLowerCase();
  if (p.includes('danh') || p.includes('noun')) return '🏷️';
  if (p.includes('động') || p.includes('verb')) return '⚡';
  if (p.includes('tính') || p.includes('adj')) return '✨';
  if (p.includes('trạng') || p.includes('adv')) return '🌀';
  if (p.includes('giới') || p.includes('prep')) return '🔗';
  if (p.includes('liên') || p.includes('conj')) return '🤝';
  return '📌';
}

export default function VocabCard({ cardData, meta }) {
  const [playingText, setPlayingText] = useState(null);
  const [ttsError, setTtsError] = useState(null);

  if (!cardData) return null;

  const {
    word = '',
    level = 'A1',
    ipa = '',
    primary_pos = '',
    primary_meaning = '',
    primary_example = '',
    blocks = [],
  } = cardData;

  const lvlConf = getLevelConfig(level);
  const metadata = meta || cardData.meta || {};
  const sourceName = metadata.source || cardData.source || 'Cambridge Dictionary';
  const isUrl = typeof sourceName === 'string' && (sourceName.startsWith('http://') || sourceName.startsWith('https://'));
  const intent = metadata.intent || 'DEFINE_VOCAB';

  const handlePlayAudio = (textToPlay = word) => {
    if (!textToPlay) return;
    if (playingText === textToPlay) {
      tts.cancel();
      setPlayingText(null);
      return;
    }
    tts.cancel();
    setTtsError(null);
    setPlayingText(textToPlay);
    tts.speak(textToPlay, {
      voice: 'af_heart',
      speed: 1.0,
      onStart: () => setPlayingText(textToPlay),
      onEnd: () => setPlayingText(null),
      onError: (err) => {
        setPlayingText(null);
        setTtsError(err);
      },
    });
  };

  const isWordPlaying = playingText === word;

  return (
    <div className={`relative bg-gradient-to-br ${lvlConf.bgCard} dark:from-[#232323] dark:via-[#232323] dark:to-[#232323] rounded-3xl border-2 ${lvlConf.border} dark:border-white/10 shadow-lg shadow-slate-900/5 dark:shadow-2xl dark:shadow-black/50 p-5 sm:p-7 transition-all duration-300 overflow-hidden`}>
      
      {/* Decorative background blur ring */}
      <div className={`absolute -top-12 -right-12 w-48 h-48 rounded-full bg-gradient-to-br ${lvlConf.gradient} opacity-10 blur-2xl pointer-events-none`} />

      {/* TOP HEADER: CEFR BADGE, INTENT CONTEXT & US PRONUNCIATION */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5 pb-3.5 border-b border-slate-200/70 dark:border-white/10">
        <div className="flex flex-wrap items-center gap-2">
          {/* CEFR Level Badge */}
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wide ${lvlConf.bgLight} ${lvlConf.text} border ${lvlConf.border} dark:bg-white/[0.08] dark:border-white/15 shadow-2xs`}>
            {lvlConf.badge}
          </span>
        </div>
      </div>

      {/* MAIN HEADWORD & IPA HERO */}
      <div className="flex flex-wrap items-baseline justify-between gap-3 mb-5">
        <div className="flex flex-wrap items-baseline gap-3">
          <h2 className="text-3xl sm:text-4xl font-black text-slate-900 dark:text-white tracking-tight">
            {word}
          </h2>
          {ipa && (
            <button
              type="button"
              onClick={() => handlePlayAudio(word)}
              title="Nhấp để nghe phát âm"
              className="group inline-flex items-center space-x-1.5 text-sm sm:text-base font-mono font-bold text-slate-700 dark:text-zinc-200 bg-white/90 dark:bg-white/[0.08] hover:bg-emerald-50 dark:hover:bg-emerald-950/40 hover:text-emerald-700 dark:hover:text-emerald-300 px-3 py-1 rounded-xl border border-slate-200/80 dark:border-white/10 hover:border-emerald-300 dark:hover:border-emerald-500/40 shadow-2xs transition-all cursor-pointer"
            >
              <span>{ipa}</span>
              <Volume2 className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors" />
            </button>
          )}
        </div>
      </div>

      {ttsError && (
        <div className="mb-4 p-3 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs font-semibold text-rose-700 dark:text-rose-300 flex items-center justify-between">
          <span>⚠️ {ttsError}</span>
          <button
            type="button"
            onClick={() => setTtsError(null)}
            className="text-rose-500 hover:text-rose-700 font-bold ml-2 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* DEFINITION & EXAMPLES CONTENT */}
      <div className="space-y-4">
        {blocks && blocks.length > 0 ? (
          blocks
            .filter((b) => !(b.pos && b.pos.toLowerCase().includes('định nghĩa chung') && !b.meanings?.some((m) => m.definition && m.definition.trim())))
            .map((block, bIdx) => (
            <div key={bIdx} className="bg-white/90 dark:bg-[#1a1a1a] rounded-2xl p-4 sm:p-5 border border-slate-200/80 dark:border-white/10 shadow-2xs">
              {/* Part of Speech Header */}
              {block.pos && (
                <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-xl bg-slate-100/90 dark:bg-white/10 text-slate-800 dark:text-zinc-200 text-xs font-black uppercase tracking-wider mb-3.5 border border-slate-200/60 dark:border-white/10 shadow-2xs">
                  <span>{getPosIcon(block.pos)}</span>
                  <span>{block.pos}</span>
                </div>
              )}

              {/* Meanings & Examples */}
              <div className="space-y-4">
                {block.meanings && block.meanings.map((m, mIdx) => {
                  const cleanDef = (m.definition || '').replace(/\*\*/g, '').replace(/^\*\s*/, '').trim();
                  return (
                    <div key={mIdx} className="border-l-3 border-emerald-500/80 pl-3.5 py-0.5">
                      {cleanDef && (
                        <div className="flex items-start space-x-2.5">
                          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 text-xs font-black shrink-0 mt-0.5 border border-emerald-300/60 dark:border-emerald-600/40">
                            {mIdx + 1}
                          </span>
                          <p className="text-sm sm:text-base font-extrabold text-slate-800 dark:text-zinc-100 leading-snug">
                            {cleanDef}
                          </p>
                        </div>
                      )}

                      {/* Example Sentences */}
                      {m.examples && m.examples.length > 0 && (
                        <div className="mt-2.5 space-y-2">
                          {m.examples.map((ex, exIdx) => {
                            const cleanEx = (ex || '').replace(/\*\*/g, '').trim();
                            const isThisExPlaying = playingText === cleanEx;
                            return (
                              <div
                                key={exIdx}
                                className="group relative flex items-start justify-between gap-2.5 text-xs sm:text-sm text-slate-700 dark:text-zinc-300 bg-slate-50/90 dark:bg-black/40 hover:bg-slate-100/90 dark:hover:bg-white/[0.04] rounded-2xl p-3 sm:p-3.5 border border-slate-200/70 dark:border-white/10 shadow-2xs transition-all"
                              >
                                <div className="flex items-start space-x-2 flex-1 min-w-0">
                                  <span className="text-emerald-500 font-bold shrink-0 mt-0.5">•</span>
                                  <span className="font-semibold text-slate-800 dark:text-zinc-200 leading-relaxed">
                                    {highlightWord(cleanEx, word)}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => handlePlayAudio(cleanEx)}
                                  title={isThisExPlaying ? "Dừng đọc ví dụ" : "Nghe câu ví dụ bằng giọng Kokoro"}
                                  className={`shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-white dark:hover:bg-white/10 border border-transparent hover:border-slate-200 dark:hover:border-white/10 transition-all cursor-pointer ${
                                    isThisExPlaying ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 ring-1 ring-emerald-400' : 'opacity-70 group-hover:opacity-100'
                                  }`}
                                >
                                  <Volume2 className={`w-3.5 h-3.5 ${isThisExPlaying ? 'animate-bounce' : ''}`} />
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        ) : (
          <div className="bg-white/90 dark:bg-[#1a1a1a] rounded-2xl p-4 sm:p-5 border border-slate-200/80 dark:border-white/10 shadow-2xs">
            {primary_pos && (
              <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-xl bg-slate-100 dark:bg-white/10 text-slate-800 dark:text-zinc-200 text-xs font-black mb-3 border border-slate-200/60 dark:border-white/10">
                <span>{getPosIcon(primary_pos)}</span>
                <span>{primary_pos}</span>
              </span>
            )}
            <p className="text-base font-bold text-slate-800 dark:text-zinc-100">{primary_meaning}</p>
            {primary_example && (
              <div className="group relative flex items-start justify-between gap-2.5 text-xs sm:text-sm text-slate-700 dark:text-zinc-300 bg-slate-50/90 dark:bg-black/40 rounded-2xl p-3 sm:p-3.5 border border-slate-200/70 dark:border-white/10 mt-3">
                <div className="flex items-start space-x-2 flex-1 min-w-0">
                  <span className="text-emerald-500 font-bold shrink-0 mt-0.5">•</span>
                  <span className="font-semibold text-slate-800 dark:text-zinc-200">
                    {highlightWord(primary_example, word)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handlePlayAudio(primary_example)}
                  title={playingText === primary_example ? "Dừng đọc ví dụ" : "Nghe câu ví dụ bằng giọng Kokoro"}
                  className={`shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-white dark:hover:bg-white/10 border border-transparent hover:border-slate-200 dark:hover:border-white/10 transition-all cursor-pointer ${
                    playingText === primary_example ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 ring-1 ring-emerald-400' : 'opacity-70 group-hover:opacity-100'
                  }`}
                >
                  <Volume2 className={`w-3.5 h-3.5 ${playingText === primary_example ? 'animate-bounce' : ''}`} />
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* PROVENANCE DISCLOSURE & SECURITY GUARANTEE */}
      <div className="mt-5 pt-4 border-t border-slate-200/60 dark:border-white/10 flex flex-wrap items-center justify-between gap-2.5 text-xs text-slate-500 dark:text-zinc-400">
        <div className="inline-flex items-center space-x-1.5 bg-white/80 dark:bg-white/[0.05] px-2.5 py-1 rounded-xl border border-slate-200/60 dark:border-white/10 shadow-2xs">
          <BookOpen className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="font-semibold text-slate-700 dark:text-zinc-300">Nguồn dữ liệu:</span>
          {isUrl ? (
            <a
              href={sourceName}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 underline truncate max-w-[200px] sm:max-w-xs inline-flex items-center gap-1 cursor-pointer transition-colors"
              title={`Mở nguồn từ điển gốc: ${sourceName}`}
            >
              <span>{sourceName.includes('cambridge.org') ? 'Cambridge Dictionary' : (sourceName.includes('oxford') ? 'Oxford Dictionary' : sourceName)}</span>
              <ArrowUpRight className="w-3 h-3 flex-shrink-0" />
            </a>
          ) : (
            <span className="font-medium text-slate-600 dark:text-zinc-400 truncate max-w-[200px] sm:max-w-xs">{sourceName}</span>
          )}
        </div>
      </div>

    </div>
  );
}

/**
 * Helper to highlight the vocabulary headword inside example sentences
 */
function highlightWord(text, word) {
  if (!text || !word) return text;
  const regex = new RegExp(`(\\b${word}[a-z]*\\b)`, 'gi');
  const parts = text.split(regex);
  return parts.map((part, index) => {
    if (part.toLowerCase().startsWith(word.toLowerCase())) {
      return (
        <span key={index} className="text-emerald-700 dark:text-emerald-400 font-black underline decoration-emerald-400 decoration-1">
          {part}
        </span>
      );
    }
    return part;
  });
}
