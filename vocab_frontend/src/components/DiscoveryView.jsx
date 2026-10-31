import React, { useState, useEffect } from 'react';
import { Sparkles, RefreshCw, Volume2, ArrowRight, Bookmark } from 'lucide-react';
import { getDiscoveryWords, saveNotebookWord } from '../services/api';
import { tts } from '../services/tts';
import { getLevelConfig } from '../utils/cefr';

export default function DiscoveryView({ onSelectWord, onStatsUpdate }) {
  const [level, setLevel] = useState('A1');
  const [words, setWords] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [savedWords, setSavedWords] = useState({});

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
    tts.speak(word, { lang: 'en-US' });
  };

  const handleSave = async (e, wordCard) => {
    e.stopPropagation();
    try {
      await saveNotebookWord(wordCard);
      setSavedWords((prev) => ({ ...prev, [wordCard.word]: true }));
      if (onStatsUpdate) onStatsUpdate();
    } catch (err) {
      console.error('Save error:', err);
    }
  };

  const lvlConf = getLevelConfig(level);

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      
      {/* Header */}
      <div className="bg-white dark:bg-[#1c1c1c] rounded-3xl p-6 border border-slate-200 dark:border-white/10 shadow-sm mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-slate-900 dark:text-white tracking-tight flex items-center space-x-2">
              <span>🌟 Khám Phá Từ Vựng Chuẩn CEFR</span>
            </h1>
            <p className="text-sm text-slate-500 dark:text-zinc-400 font-medium mt-1">
              Khám phá vốn từ Oxford 3,000 phân cấp từ A1 đến B2 kèm ngữ cảnh thực tế
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
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-5">
          {['A1', 'A2', 'B1', 'B2'].map((lvl) => {
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

      {/* Grid Cards */}
      {isLoading ? (
        <div className="text-center py-16 text-slate-400 font-medium">
          Đang tải từ vựng mới...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {words.map((card) => {
            const isSaved = savedWords[card.word];
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
                        className="p-2 rounded-xl bg-slate-100 dark:bg-white/10 hover:bg-emerald-100 dark:hover:bg-white/20 text-slate-600 dark:text-zinc-300 hover:text-emerald-700 dark:hover:text-emerald-300 transition-colors cursor-pointer border border-transparent dark:border-white/10"
                        title="Nghe phát âm"
                      >
                        <Volume2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => handleSave(e, card)}
                        className={`p-2 rounded-xl border transition-colors cursor-pointer ${
                          isSaved
                            ? 'bg-amber-100 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700/60'
                            : 'bg-white dark:bg-white/10 hover:bg-slate-100 dark:hover:bg-white/20 text-slate-400 dark:text-zinc-300 border-slate-200 dark:border-white/10'
                        }`}
                        title="Lưu sổ tay"
                      >
                        <Bookmark className="w-4 h-4" />
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
