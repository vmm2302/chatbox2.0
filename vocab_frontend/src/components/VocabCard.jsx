import React, { useState } from 'react';
import { Volume2, Bookmark, BookmarkCheck, Sparkles, Snail, Check, Copy, ArrowUpRight, Database, Cpu, ChevronDown, ChevronUp, Layers, Zap } from 'lucide-react';
import { tts } from '../services/tts';
import { getLevelConfig } from '../utils/cefr';

export default function VocabCard({ cardData, meta, isSaved, onToggleSave, onSelectSuggestion }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isSlowPlaying, setIsSlowPlaying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showInspector, setShowInspector] = useState(false);

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
  const recordId = metadata.record_id || cardData.record_id;
  const sheetName = metadata.sheet || cardData.sheet;
  const isUrl = typeof sourceName === 'string' && (sourceName.startsWith('http://') || sourceName.startsWith('https://'));
  const mode = metadata.mode || 'DIRECT_MATCH';
  const intent = metadata.intent || 'DEFINE_VOCAB';
  const latency = metadata.latency_ms || 0;
  const rrf = metadata.rrf_score || 0;

  const handlePlayAudio = (slow = false) => {
    if (!word) return;
    if (slow) {
      setIsSlowPlaying(true);
      tts.speakSlow(word, 'en-US', {
        onEnd: () => setIsSlowPlaying(false),
      });
    } else {
      setIsPlaying(true);
      tts.speak(word, {
        lang: 'en-US',
        rate: 1.0,
        onEnd: () => setIsPlaying(false),
      });
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(word);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`relative bg-gradient-to-br ${lvlConf.bgCard} dark:from-[#232323] dark:via-[#232323] dark:to-[#232323] rounded-3xl border-2 ${lvlConf.border} dark:border-white/10 shadow-lg shadow-slate-900/5 dark:shadow-2xl dark:shadow-black/50 p-5 sm:p-7 transition-all duration-300 overflow-hidden`}>
      
      {/* Decorative background blur ring */}
      <div className={`absolute -top-12 -right-12 w-48 h-48 rounded-full bg-gradient-to-br ${lvlConf.gradient} opacity-10 blur-2xl pointer-events-none`} />

      {/* TOP HEADER MANDATORY PREFIX REQUIRED BY USER */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-200/60 dark:border-white/10">
        <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-white/90 dark:bg-white/[0.06] border border-slate-200/90 dark:border-white/10 shadow-2xs">
          <span className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider">🎯 Từ bạn tìm kiếm:</span>
          <span className="text-sm sm:text-base font-black text-slate-900 dark:text-white tracking-tight underline decoration-emerald-500 decoration-2 underline-offset-2">
            {word}
          </span>
        </div>

        <div className="flex items-center space-x-2">
          {/* CEFR Level Badge */}
          <span className={`px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wide ${lvlConf.bgLight} ${lvlConf.text} border ${lvlConf.border} dark:bg-white/[0.08] dark:border-white/15 shadow-2xs`}>
            {lvlConf.badge}
          </span>

          {/* Bookmark Button */}
          <button
            onClick={() => onToggleSave && onToggleSave(cardData)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              isSaved
                ? 'bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-700/60 shadow-2xs font-extrabold'
                : 'bg-white dark:bg-white/[0.08] text-slate-600 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.14] border border-slate-200 dark:border-white/10 shadow-2xs'
            }`}
          >
            {isSaved ? (
              <>
                <BookmarkCheck className="w-3.5 h-3.5 text-amber-600 fill-amber-500" />
                <span>Đã lưu sổ tay</span>
              </>
            ) : (
              <>
                <Bookmark className="w-3.5 h-3.5 text-slate-400" />
                <span>Lưu sổ tay</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* MAIN HEADWORD & AUDIO CONTROLS */}
      <div className="flex flex-wrap items-baseline justify-between gap-3 mb-5">
        <div className="flex items-baseline space-x-3">
          <h2 className="text-3xl sm:text-4xl font-black text-slate-900 dark:text-white tracking-tight">
            {word}
          </h2>
          {ipa && (
            <span className="text-sm sm:text-base font-mono font-bold text-slate-600 dark:text-zinc-300 bg-white/80 dark:bg-white/[0.06] px-2.5 py-1 rounded-lg border border-slate-200/60 dark:border-white/10 shadow-2xs">
              {ipa}
            </span>
          )}
        </div>

        {/* Audio buttons */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => handlePlayAudio(false)}
            disabled={isPlaying}
            title="Nghe phát âm chuẩn giọng Mỹ (US)"
            className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-extrabold text-white bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 shadow-md shadow-emerald-500/25 active:scale-95 transition-all cursor-pointer ${
              isPlaying ? 'animate-pulse' : ''
            }`}
          >
            <Volume2 className="w-4 h-4" />
            <span>{isPlaying ? 'Đang đọc...' : 'Phát âm (US)'}</span>
          </button>

          <button
            onClick={() => handlePlayAudio(true)}
            disabled={isSlowPlaying}
            title="Nghe chậm (0.75x) dành cho người mới học"
            className="flex items-center space-x-1 px-3 py-2 rounded-xl text-xs font-bold text-slate-700 dark:text-zinc-200 bg-white dark:bg-white/[0.08] hover:bg-slate-50 dark:hover:bg-white/[0.14] border border-slate-200 dark:border-white/10 shadow-2xs active:scale-95 transition-all cursor-pointer"
          >
            <Snail className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>Nghe chậm</span>
          </button>

          <button
            onClick={handleCopy}
            title="Sao chép từ"
            className="p-2 rounded-xl text-slate-400 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 bg-white dark:bg-white/[0.08] hover:bg-slate-50 dark:hover:bg-white/[0.14] border border-slate-200 dark:border-white/10 shadow-2xs transition-colors cursor-pointer"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* DEFINITION & EXAMPLES CONTENT */}
      <div className="space-y-4">
        {blocks && blocks.length > 0 ? (
          blocks
            .filter((b) => !(b.pos && b.pos.toLowerCase().includes('định nghĩa chung') && !b.meanings?.some((m) => m.definition && m.definition.trim())))
            .map((block, bIdx) => (
            <div key={bIdx} className="bg-white/90 dark:bg-[#1a1a1a] rounded-2xl p-4 sm:p-5 border border-slate-200/80 dark:border-white/10 shadow-2xs">
              {/* Part of Speech Header */}
              {block.pos && (
                <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/10 text-slate-700 dark:text-zinc-200 text-xs font-black uppercase tracking-wider mb-3">
                  <span>🏷️ {block.pos}</span>
                </div>
              )}

              {/* Meanings & Examples */}
              <div className="space-y-3">
                {block.meanings && block.meanings.map((m, mIdx) => {
                  const cleanDef = (m.definition || '').replace(/\*\*/g, '').replace(/^\*\s*/, '').trim();
                  return (
                    <div key={mIdx} className="border-l-3 border-emerald-400 pl-3 py-0.5">
                      {cleanDef && (
                        <p className="text-sm sm:text-base font-extrabold text-slate-800 dark:text-zinc-100 leading-snug">
                          {block.meanings.length > 1 ? `${mIdx + 1}. ` : ''}
                          {cleanDef}
                        </p>
                      )}

                      {/* Example Sentences */}
                      {m.examples && m.examples.length > 0 && (
                        <div className="mt-2 space-y-1.5">
                          {m.examples.map((ex, exIdx) => {
                            const cleanEx = (ex || '').replace(/\*\*/g, '').trim();
                            return (
                              <div key={exIdx} className="text-xs sm:text-sm text-slate-600 dark:text-zinc-300 bg-slate-50/90 dark:bg-black/40 rounded-xl p-2.5 sm:p-3 border border-slate-100 dark:border-white/5">
                                <span className="font-semibold text-slate-800 dark:text-zinc-200">
                                  • {highlightWord(cleanEx, word)}
                                </span>
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
          <div className="bg-white/90 dark:bg-[#1a1a1a] rounded-2xl p-4 border border-slate-200/80 dark:border-white/10">
            {primary_pos && (
              <span className="inline-block px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/10 text-slate-700 dark:text-zinc-200 text-xs font-black mb-2">
                {primary_pos}
              </span>
            )}
            <p className="text-base font-bold text-slate-800 dark:text-zinc-100">{primary_meaning}</p>
            {primary_example && (
              <p className="text-sm text-slate-600 dark:text-zinc-300 mt-2 bg-slate-50 dark:bg-black/40 p-2.5 rounded-xl border border-slate-100 dark:border-white/5">
                • {highlightWord(primary_example, word)}
              </p>
            )}
          </div>
        )}
      </div>

      {/* PROVENANCE DISCLOSURE & TECHNICAL INSPECTOR */}
      <div className="mt-5 pt-4 border-t border-slate-200/60 dark:border-white/10 space-y-2">
        {/* Source citation */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-zinc-400">
          <div className="inline-flex items-center space-x-1.5 bg-white/70 dark:bg-white/[0.05] px-2.5 py-1 rounded-lg border border-slate-200/50 dark:border-white/10">
            <Database className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
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
            {sheetName && (
              <span className="text-[10px] bg-slate-100 dark:bg-white/10 text-slate-600 dark:text-zinc-300 px-1.5 py-0.5 rounded font-mono">
                📑 {sheetName}
              </span>
            )}
            {recordId && (
              <span className="text-[10px] bg-slate-100 dark:bg-white/10 text-slate-500 dark:text-zinc-400 px-1.5 py-0.5 rounded font-mono">
                #{recordId}
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={() => setShowInspector(!showInspector)}
            className="inline-flex items-center space-x-1 text-slate-500 dark:text-zinc-400 hover:text-slate-800 dark:hover:text-white font-semibold px-2 py-1 rounded-lg hover:bg-white/80 dark:hover:bg-white/10 transition-colors cursor-pointer text-[11px]"
          >
            <Cpu className="w-3.5 h-3.5 text-teal-600" />
            <span>Thông số RAG & Pipeline</span>
            {showInspector ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Technical Inspector Drawer */}
        {showInspector && (
          <div className="bg-slate-900/95 dark:bg-[#141414] text-slate-200 dark:text-zinc-300 rounded-2xl p-3.5 sm:p-4 text-xs font-mono border border-slate-800 dark:border-white/10 shadow-inner mt-2 space-y-2.5 animate-in fade-in duration-200">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 dark:border-white/10">
              <span className="font-bold text-emerald-400 flex items-center space-x-1.5">
                <Zap className="w-3.5 h-3.5 text-amber-400" />
                <span>RAG Pipeline Diagnostic Inspector</span>
              </span>
              <span className="text-[10px] text-slate-400 dark:text-zinc-500">Chatbox 2.0 Engine</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
              <div className="bg-slate-800/80 dark:bg-white/[0.06] p-2 rounded-xl">
                <div className="text-slate-400 dark:text-zinc-500 text-[10px] uppercase">Response Mode</div>
                <div className="font-bold text-white truncate">{mode}</div>
              </div>

              <div className="bg-slate-800/80 dark:bg-white/[0.06] p-2 rounded-xl">
                <div className="text-slate-400 dark:text-zinc-500 text-[10px] uppercase">PhoBERT Intent</div>
                <div className="font-bold text-teal-300 truncate">{intent}</div>
              </div>

              <div className="bg-slate-800/80 dark:bg-white/[0.06] p-2 rounded-xl">
                <div className="text-slate-400 dark:text-zinc-500 text-[10px] uppercase">RRF Score</div>
                <div className="font-bold text-amber-300">{Number(rrf).toFixed(3)}</div>
              </div>

              <div className="bg-slate-800/80 dark:bg-white/[0.06] p-2 rounded-xl">
                <div className="text-slate-400 dark:text-zinc-500 text-[10px] uppercase">Latency</div>
                <div className="font-bold text-emerald-300">{latency} ms</div>
              </div>
            </div>

            <div className="text-[10px] text-slate-400 dark:text-zinc-500 pt-1 flex items-center justify-between">
              <span>Kiến trúc: 4-Layer Hybrid Retrieval (ChromaDB + BM25 + Exact RAM Cache)</span>
              <span className="text-emerald-400">● 100% Offline Local</span>
            </div>
          </div>
        )}
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
