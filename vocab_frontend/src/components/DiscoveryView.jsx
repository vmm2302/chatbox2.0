import React, { useState, useEffect } from 'react';
import { RefreshCw, Volume2, ArrowRight } from 'lucide-react';
import { getDiscoveryWords } from '../services/api';
import { tts } from '../services/tts';
import { getLevelConfig } from '../utils/cefr';

export default function DiscoveryView({ onSelectWord }) {
  const [level, setLevel] = useState('A1');
  const [words, setWords] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [playingWord, setPlayingWord] = useState(null);
  const [ttsError, setTtsError] = useState(null);

  const fetchDiscovery = async (lvl) => {
    setIsLoading(true);
    try {
      const res = await getDiscoveryWords(lvl, 8);
      setWords(res.words || []);
    } catch (err) {
      console.error('Discovery error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDiscovery(level);
  }, [level]);

  const handlePlayAudio = (e, word) => {
    e.stopPropagation();
    if (playingWord === word) {
      tts.cancel();
      setPlayingWord(null);
      return;
    }
    setTtsError(null);
    tts.speak(word, {
      voice: 'af_heart',
      speed: 1.0,
      onStart: () => setPlayingWord(word),
      onEnd: () => setPlayingWord(null),
      onError: (err) => {
        setPlayingWord(null);
        setTtsError(err);
      },
    });
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      
      {/* Header */}
      <div className="bg-white dark:bg-[#1c1c1c] rounded-3xl p-6 border border-slate-200 dark:border-white/10 shadow-sm mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight flex items-center space-x-2">
              <span>🌟 Khám Phá Từ Vựng Chuẩn CEFR A1 - A2</span>
            </h1>
            <p className="text-sm text-slate-500 dark:text-zinc-400 font-medium mt-1">
              Khám phá vốn từ vựng chuẩn CEFR A1 và A2 kèm ngữ cảnh thực tế
            </p>
          </div>

          <button
            onClick={() => fetchDiscovery(level)}
            disabled={isLoading}
            className="flex items-center space-x-2 px-4 py-2 rounded-2xl bg-slate-100 dark:bg-[#262626] hover:bg-slate-200 dark:hover:bg-white/10 text-slate-700 dark:text-zinc-200 font-bold text-xs transition-colors cursor-pointer border border-transparent dark:border-white/10"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Đổi bộ từ ngẫu nhiên</span>
          </button>
        </div>

        {/* Level Selector */}
        <div className="grid grid-cols-2 gap-2 mt-5">
          {['A1', 'A2'].map((lvl) => {
            const conf = getLevelConfig(lvl);
            const isSelected = level === lvl;
            return (
              <button
                key={lvl}
                onClick={() => setLevel(lvl)}
                className={`p-3 rounded-2xl border text-left transition-all cursor-pointer ${
                  isSelected
                    ? `bg-gradient-to-r ${conf.gradient} text-white shadow-md border-transparent`
                    : 'bg-white dark:bg-[#262626] hover:bg-slate-50 dark:hover:bg-white/10 text-slate-800 dark:text-zinc-100 border-slate-200 dark:border-white/10'
                }`}
              >
                <div className="font-extrabold text-sm">{conf.badge}</div>
                <div className={`text-[11px] mt-0.5 ${isSelected ? 'text-white/80' : 'text-slate-400 dark:text-zinc-500'}`}>
                  {conf.label}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {ttsError && (
        <div className="mb-4 p-3 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs font-semibold text-rose-700 dark:text-rose-300 flex items-center justify-between">
          <span>⚠️ {ttsError}</span>
          <button
            onClick={() => setTtsError(null)}
            className="text-rose-500 hover:text-rose-700 font-bold ml-2 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Grid Cards */}
      {isLoading ? (
        <div className="text-center py-16 text-slate-400 font-medium">
          Đang tải từ vựng mới...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {words.map((card) => {
            return (
              <div
                key={card.word}
                onClick={() => onSelectWord(card.word)}
                className="bg-white dark:bg-[#212121] hover:bg-emerald-50/30 dark:hover:bg-[#262626] rounded-3xl p-5 border border-slate-200 dark:border-white/10 hover:border-emerald-300 dark:hover:border-white/20 shadow-sm hover:shadow-md transition-all duration-200 cursor-pointer flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-baseline space-x-2">
                        <span className="text-2xl font-black text-slate-900 dark:text-white group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition-colors">
                          {card.word}
                        </span>
                        {card.ipa && (
                          <span className="text-xs font-mono text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-white/5 px-2 py-0.5 rounded-md border border-transparent dark:border-white/10">
                            {card.ipa}
                          </span>
                        )}
                      </div>
                      {card.primary_pos && (
                        <span className="inline-block text-[11px] font-black uppercase text-slate-400 dark:text-zinc-500 mt-1">
                          {card.primary_pos}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center space-x-1.5">
                      <button
                        onClick={(e) => handlePlayAudio(e, card.word)}
                        className={`p-2 rounded-xl transition-all cursor-pointer border ${
                          playingWord === card.word
                            ? 'bg-emerald-500 text-white animate-pulse border-emerald-400'
                            : 'bg-slate-100 dark:bg-white/10 hover:bg-emerald-100 dark:hover:bg-white/20 text-slate-600 dark:text-zinc-300 hover:text-emerald-700 dark:hover:text-emerald-300 border-transparent dark:border-white/10'
                        }`}
                        title={playingWord === card.word ? "Dừng phát" : "Nghe phát âm chuẩn Mỹ (Kokoro TTS Cục bộ)"}
                      >
                        <Volume2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <p className="text-sm font-extrabold text-slate-800 dark:text-zinc-100 mt-3 line-clamp-2">
                    {card.primary_meaning || 'Xem chi tiết'}
                  </p>

                  {card.primary_example && (
                    <p className="text-xs text-slate-500 dark:text-zinc-400 mt-2 bg-slate-50 dark:bg-black/40 p-2 rounded-xl border border-slate-100 dark:border-white/5 line-clamp-2">
                      • {card.primary_example}
                    </p>
                  )}
                </div>

                <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-100 dark:border-white/10 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                  <span>Hỏi chatbot về từ này</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
