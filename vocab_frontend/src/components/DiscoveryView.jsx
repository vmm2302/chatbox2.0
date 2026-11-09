import React, { useState, useEffect } from 'react';
import { RefreshCw, Volume2, ArrowRight } from 'lucide-react';
import { getDiscoveryWords, getAvailableLevels } from '../services/api';
import { tts } from '../services/tts';
import { getLevelConfig } from '../utils/cefr';

const getGridColsClass = (count) => {
  if (count === 1) return 'grid-cols-1';
  if (count === 2) return 'grid-cols-1 sm:grid-cols-2'; // 50/50 khi có 2 nút
  if (count === 3) return 'grid-cols-1 sm:grid-cols-3';
  if (count === 4) return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4'; // 25% mỗi nút khi có 4 nút
  return 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5';
};

export default function DiscoveryView({ onSelectWord }) {
  const [level, setLevel] = useState('A1');
  const [availableLevels, setAvailableLevels] = useState(['A1', 'A2']);
  const [levelCounts, setLevelCounts] = useState({});
  const [words, setWords] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [playingWord, setPlayingWord] = useState(null);
  const [ttsError, setTtsError] = useState(null);

  // Fetch dynamic levels discovered in qa_records.jsonl on mount
  useEffect(() => {
    let isMounted = true;
    const fetchLevels = async () => {
      try {
        const data = await getAvailableLevels();
        if (isMounted && data && Array.isArray(data.levels) && data.levels.length > 0) {
          setAvailableLevels(data.levels);
          setLevelCounts(data.counts || {});
          if (!data.levels.includes(level)) {
            setLevel(data.levels[0]);
          }
        }
      } catch (err) {
        console.error('Failed to load available levels:', err);
      }
    };
    fetchLevels();
    return () => {
      isMounted = false;
    };
  }, []);

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
    if (level) {
      fetchDiscovery(level);
    }
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
              <span>🌟 Khám Phá Từ Vựng</span>
            </h1>
            <p className="text-sm text-slate-500 dark:text-zinc-400 font-medium mt-1">
              Khám phá các bộ từ vựng kèm ngữ cảnh thực tế
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

        {/* Dynamic Level Selector: wide, slim and elegant */}
        <div className={`grid ${getGridColsClass(availableLevels.length)} gap-3 sm:gap-4 mt-6 w-full`}>
          {availableLevels.map((lvl) => {
            const conf = getLevelConfig(lvl);
            const isSelected = level === lvl;
            const count = levelCounts[lvl];
            return (
              <button
                key={lvl}
                onClick={() => setLevel(lvl)}
                className={`w-full px-5 py-2.5 sm:py-3 rounded-2xl border transition-all duration-200 cursor-pointer flex items-center justify-between gap-3 text-left ${
                  isSelected
                    ? `bg-gradient-to-r ${conf.gradient} text-white shadow-md border-transparent scale-[1.02] ring-2 ring-white/20`
                    : 'bg-white dark:bg-[#262626] hover:bg-slate-50 dark:hover:bg-white/10 text-slate-800 dark:text-zinc-100 border-slate-200 dark:border-white/10 hover:border-slate-300 shadow-xs'
                }`}
              >
                <div className="min-w-0">
                  <div className="font-extrabold text-sm tracking-wide truncate">{conf.badge}</div>
                  <div className={`text-[11px] font-medium truncate ${isSelected ? 'text-white/85' : 'text-slate-400 dark:text-zinc-500'}`}>
                    {conf.label}
                  </div>
                </div>
                {count !== undefined && (
                  <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full shrink-0 whitespace-nowrap ${isSelected ? 'bg-white/20 text-white' : 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400'}`}>
                    {count.toLocaleString()} từ
                  </span>
                )}
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
      ) : words.length === 0 ? (
        <div className="text-center py-16 text-slate-400 font-medium bg-white dark:bg-[#1c1c1c] rounded-3xl border border-slate-200 dark:border-white/10 p-8">
          <p className="text-base font-bold text-slate-700 dark:text-zinc-200">
            Chưa có từ vựng nào thuộc cấp độ {level} trong kho tri thức.
          </p>
          <p className="text-xs text-slate-400 dark:text-zinc-500 mt-2">
            Bạn có thể nạp thêm tài liệu cấp độ {level} từ trang Quản trị để bổ sung dữ liệu tra cứu.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {words.map((card) => {
            return (
              <div
                key={`${card.word}-${card.level || level}`}
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
                        {card.level && (
                          <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-md bg-emerald-100 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/40">
                            {card.level}
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
