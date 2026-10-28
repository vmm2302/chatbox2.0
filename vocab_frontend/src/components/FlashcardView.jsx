import React, { useState, useEffect } from 'react';
import confetti from 'canvas-confetti';
import { Volume2, RotateCcw, CheckCircle2, XCircle, ArrowLeft, ArrowRight, Trash2, BookOpen, Sparkles, Filter, Layers } from 'lucide-react';
import { getNotebookWords, deleteNotebookWord, updateNotebookStatus } from '../services/api';
import { tts } from '../services/tts';
import { getLevelConfig } from '../utils/cefr';

export default function FlashcardView({ onSwitchToChat, onStatsUpdate, currentUser }) {
  const [words, setWords] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [filterLevel, setFilterLevel] = useState('Tất cả');
  const [filterStatus, setFilterStatus] = useState('all');
  const [viewMode, setViewMode] = useState('flashcard'); // 'flashcard' or 'list'
  const [isLoading, setIsLoading] = useState(true);

  const userId = currentUser?.id || 'default_user';

  const fetchWords = async () => {
    setIsLoading(true);
    try {
      const res = await getNotebookWords(filterLevel, filterStatus, userId);
      setWords(res.saved_words || []);
      setCurrentIndex(0);
      setIsFlipped(false);
    } catch (err) {
      console.error('Fetch notebook error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWords();
  }, [filterLevel, filterStatus]);

  // Keyboard navigation for flashcards
  useEffect(() => {
    if (viewMode !== 'flashcard' || words.length === 0) return;

    const handleKeyDown = (e) => {
      if (e.code === 'Space') {
        e.preventDefault();
        setIsFlipped((prev) => !prev);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handlePrev();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [viewMode, words, currentIndex]);

  const currentWord = words[currentIndex] || null;

  const handleFlip = () => {
    setIsFlipped(!isFlipped);
  };

  const handleNext = () => {
    setIsFlipped(false);
    setCurrentIndex((prev) => (prev < words.length - 1 ? prev + 1 : 0));
  };

  const handlePrev = () => {
    setIsFlipped(false);
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : words.length - 1));
  };

  const handleMarkMastered = async () => {
    if (!currentWord) return;
    try {
      // Fire festive celebration confetti!
      confetti({
        particleCount: 80,
        spread: 60,
        origin: { y: 0.65 },
        colors: ['#10b981', '#14b8a6', '#06b6d4', '#f59e0b'],
      });

      await updateNotebookStatus(currentWord.word, 'mastered', true, userId);
      // Update local state
      setWords((prev) =>
        prev.map((w, idx) => (idx === currentIndex ? { ...w, status: 'mastered' } : w))
      );
      if (onStatsUpdate) onStatsUpdate();

      // Automatically advance to next card after a brief moment
      setTimeout(() => {
        handleNext();
      }, 500);
    } catch (err) {
      console.error('Update status error:', err);
    }
  };

  const handleMarkReview = async () => {
    if (!currentWord) return;
    try {
      await updateNotebookStatus(currentWord.word, 'learning', true, userId);
      setWords((prev) =>
        prev.map((w, idx) => (idx === currentIndex ? { ...w, status: 'learning' } : w))
      );
      if (onStatsUpdate) onStatsUpdate();
      handleNext();
    } catch (err) {
      console.error('Update review error:', err);
    }
  };

  const handleDelete = async (wordToDelete) => {
    if (!confirm(`Bạn có chắc muốn xóa từ '${wordToDelete}' khỏi sổ tay?`)) return;
    try {
      await deleteNotebookWord(wordToDelete, userId);
      setWords((prev) => prev.filter((w) => w.word !== wordToDelete));
      if (currentIndex >= words.length - 1) {
        setCurrentIndex(Math.max(0, words.length - 2));
      }
      if (onStatsUpdate) onStatsUpdate();
    } catch (err) {
      console.error('Delete word error:', err);
    }
  };

  const handlePlayAudio = (e, wordText) => {
    e.stopPropagation();
    tts.speak(wordText, { lang: 'en-US' });
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      
      {/* Top Controls Header */}
      <div className="bg-white rounded-3xl p-5 border border-slate-200 shadow-sm mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
              <span>🗂️ Sổ Tay Từ Vựng & Flashcards</span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 font-medium mt-1">
              Ôn tập phản xạ từ vựng CEFR A1–B2 qua thẻ lật tương tác 3D
            </p>
          </div>

          {/* Mode Switcher */}
          <div className="flex items-center space-x-2 bg-slate-100 p-1 rounded-2xl border border-slate-200">
            <button
              onClick={() => setViewMode('flashcard')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                viewMode === 'flashcard'
                  ? 'bg-white text-emerald-700 shadow-sm font-extrabold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              🎴 Thẻ lật 3D
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                viewMode === 'list'
                  ? 'bg-white text-emerald-700 shadow-sm font-extrabold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              📋 Danh sách từ
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-slate-100">
          <span className="text-xs font-bold text-slate-400 flex items-center space-x-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Lọc cấp độ:</span>
          </span>

          {['Tất cả', 'A1', 'A2', 'B1', 'B2'].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setFilterLevel(lvl)}
              className={`px-2.5 py-1 rounded-xl text-xs font-bold border transition-all ${
                filterLevel === lvl
                  ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              {lvl}
            </button>
          ))}

          <span className="text-xs font-bold text-slate-400 ml-2">Trạng thái:</span>
          {['all', 'learning', 'mastered'].map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-2.5 py-1 rounded-xl text-xs font-bold border transition-all ${
                filterStatus === st
                  ? 'bg-slate-900 text-white border-slate-900 shadow-xs'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              {st === 'all' ? 'Tất cả' : st === 'learning' ? 'Đang học' : 'Đã thuộc'}
            </button>
          ))}
        </div>
      </div>

      {/* Main Flashcard or List view */}
      {isLoading ? (
        <div className="text-center py-16 text-slate-400 font-medium">
          Đang tải sổ tay từ vựng...
        </div>
      ) : words.length === 0 ? (
        /* Empty Notebook State */
        <div className="bg-white rounded-3xl p-10 border border-slate-200 shadow-sm text-center max-w-lg mx-auto">
          <div className="w-16 h-16 rounded-3xl bg-amber-100 text-amber-600 flex items-center justify-center text-3xl mx-auto mb-4">
            ⭐
          </div>
          <h2 className="text-xl font-black text-slate-800">Sổ tay chưa có từ vựng nào!</h2>
          <p className="text-sm text-slate-500 mt-2 leading-relaxed">
            Khi tra cứu từ vựng trên chatbot, hãy nhấn nút <b>⭐ Lưu sổ tay</b> để gom lại các từ bạn muốn ghi nhớ và ôn tập tại đây.
          </p>
          <button
            onClick={onSwitchToChat}
            className="mt-6 px-5 py-2.5 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-black text-sm shadow-md shadow-emerald-500/20 hover:from-emerald-600 hover:to-teal-700 transition-all cursor-pointer"
          >
            Quay lại tra cứu ngay ↗
          </button>
        </div>
      ) : viewMode === 'flashcard' && currentWord ? (
        /* 3D INTERACTIVE FLASHCARD MODE */
        <div className="space-y-6">
          {/* Progress bar and counter */}
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 px-2">
            <span>
              Thẻ <b>{currentIndex + 1}</b> / {words.length}
            </span>
            <span>
              Trạng thái:{' '}
              <b className={currentWord.status === 'mastered' ? 'text-emerald-600' : 'text-amber-600'}>
                {currentWord.status === 'mastered' ? '✅ Đã thuộc' : '⏳ Đang học'}
              </b>
            </span>
          </div>

          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
            <div
              className="bg-gradient-to-r from-emerald-500 to-teal-600 h-full transition-all duration-300 rounded-full"
              style={{ width: `${((currentIndex + 1) / words.length) * 100}%` }}
            />
          </div>

          {/* 3D Flip Card Container */}
          <div className="perspective-1000 w-full min-h-[360px] sm:min-h-[400px] cursor-pointer" onClick={handleFlip}>
            <div
              className={`relative w-full h-full min-h-[360px] sm:min-h-[400px] rounded-3xl transition-transform duration-500 transform-style-3d shadow-xl border-2 ${
                isFlipped ? 'rotate-y-180 border-teal-300' : 'border-emerald-200'
              }`}
            >
              {/* FRONT SIDE */}
              <div className="absolute inset-0 w-full h-full backface-hidden bg-gradient-to-br from-white via-emerald-50/40 to-teal-50/60 rounded-3xl p-8 flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-emerald-100 text-emerald-800 border border-emerald-200">
                    {getLevelConfig(currentWord.level).badge}
                  </span>
                  <button
                    onClick={(e) => handlePlayAudio(e, currentWord.word)}
                    className="p-2.5 rounded-2xl bg-white shadow-sm border border-slate-200 text-emerald-600 hover:bg-emerald-50 transition-all cursor-pointer"
                  >
                    <Volume2 className="w-5 h-5" />
                  </button>
                </div>

                <div className="text-center my-auto py-6">
                  <h2 className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight">
                    {currentWord.word}
                  </h2>
                  {currentWord.ipa && (
                    <p className="text-lg font-mono font-bold text-slate-500 mt-2 bg-white/80 inline-block px-3 py-1 rounded-xl border border-slate-200/60">
                      {currentWord.ipa}
                    </p>
                  )}
                  {currentWord.part_of_speech && (
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mt-3">
                      {currentWord.part_of_speech}
                    </p>
                  )}
                </div>

                <div className="text-center text-xs font-bold text-slate-400 flex items-center justify-center space-x-1.5">
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Chạm hoặc nhấn Phím Cách (Space) để lật xem nghĩa</span>
                </div>
              </div>

              {/* BACK SIDE */}
              <div className="absolute inset-0 w-full h-full backface-hidden rotate-y-180 bg-gradient-to-br from-white via-teal-50/50 to-cyan-50/60 rounded-3xl p-8 flex flex-col justify-between overflow-y-auto">
                <div className="flex items-center justify-between">
                  <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-teal-100 text-teal-800 border border-teal-200">
                    Nghĩa & Ví dụ
                  </span>
                  <span className="text-sm font-bold text-slate-400">{currentWord.word}</span>
                </div>

                <div className="my-auto py-4 space-y-4">
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Nghĩa tiếng Việt:</span>
                    <p className="text-xl sm:text-2xl font-black text-slate-900 mt-1 leading-snug">
                      {currentWord.meaning || 'Chưa cập nhật nghĩa chi tiết'}
                    </p>
                  </div>

                  {currentWord.example && (
                    <div className="bg-white/90 p-4 rounded-2xl border border-slate-200/80 shadow-2xs">
                      <span className="text-xs font-bold uppercase tracking-wider text-teal-700">Ví dụ câu:</span>
                      <p className="text-sm sm:text-base font-semibold text-slate-800 mt-1">
                        • {currentWord.example}
                      </p>
                    </div>
                  )}
                </div>

                <div className="text-center text-xs font-bold text-slate-400">
                  Chạm để lật lại mặt trước
                </div>
              </div>
            </div>
          </div>

          {/* Action buttons (Cần ôn lại vs Đã nhớ) */}
          <div className="flex items-center justify-center space-x-3 sm:space-x-4 pt-2">
            <button
              onClick={handlePrev}
              title="Thẻ trước (←)"
              className="p-3.5 rounded-2xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm cursor-pointer"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>

            <button
              onClick={handleMarkReview}
              className="flex-1 max-w-xs flex items-center justify-center space-x-2 py-3.5 px-4 rounded-2xl bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 font-extrabold text-sm shadow-sm transition-all cursor-pointer"
            >
              <XCircle className="w-4 h-4 text-amber-600" />
              <span>Cần ôn lại</span>
            </button>

            <button
              onClick={handleMarkMastered}
              className="flex-1 max-w-xs flex items-center justify-center space-x-2 py-3.5 px-4 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-extrabold text-sm shadow-md shadow-emerald-500/25 transition-all cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Đã thuộc từ này!</span>
            </button>

            <button
              onClick={handleNext}
              title="Thẻ tiếp (→)"
              className="p-3.5 rounded-2xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm cursor-pointer"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      ) : (
        /* TABLE / LIST MODE */
        <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden divide-y divide-slate-100">
          {words.map((item) => (
            <div key={item.word} className="p-4 sm:p-5 flex items-center justify-between hover:bg-slate-50/80 transition-colors">
              <div className="space-y-1">
                <div className="flex items-center space-x-3">
                  <span className="text-lg font-black text-slate-900">{item.word}</span>
                  {item.ipa && <span className="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">{item.ipa}</span>}
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-extrabold ${getLevelConfig(item.level).bgLight} ${getLevelConfig(item.level).text}`}>
                    {item.level}
                  </span>
                </div>
                <p className="text-sm font-semibold text-slate-700">{item.meaning}</p>
                {item.example && <p className="text-xs text-slate-500 truncate max-w-lg">• {item.example}</p>}
              </div>

              <div className="flex items-center space-x-2 shrink-0">
                <button
                  onClick={(e) => handlePlayAudio(e, item.word)}
                  className="p-2 rounded-xl text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 border border-slate-200 transition-colors cursor-pointer"
                >
                  <Volume2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(item.word)}
                  className="p-2 rounded-xl text-slate-400 hover:text-red-600 hover:bg-red-50 border border-slate-200 transition-colors cursor-pointer"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

    </div>
  );
}
