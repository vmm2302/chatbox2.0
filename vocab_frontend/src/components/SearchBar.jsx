import React, { useState, useEffect, useRef } from 'react';
import { Search, X, Sparkles, ArrowRight, CornerDownLeft } from 'lucide-react';
import { searchWords } from '../services/api';
import { getLevelConfig } from '../utils/cefr';

export default function SearchBar({ onSearch, selectedLevel, placeholder = "Nhập từ tiếng Anh (ví dụ: amazing, confident, abandon...)" }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const wrapperRef = useRef(null);

  // Debounced live autocomplete search
  useEffect(() => {
    const clean = query.trim();
    if (clean.length < 1) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await searchWords(clean, selectedLevel === 'Tất cả' ? null : selectedLevel, 8);
        setSuggestions(res.results || []);
        setIsOpen((res.results || []).length > 0);
      } catch (err) {
        console.error('Search error:', err);
      } finally {
        setIsLoading(false);
      }
    }, 180);

    return () => clearTimeout(timer);
  }, [query, selectedLevel]);

  // Click outside listener
  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectWord = (word) => {
    setQuery(word);
    setIsOpen(false);
    onSearch(word);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (selectedIndex >= 0 && suggestions[selectedIndex]) {
      handleSelectWord(suggestions[selectedIndex].word);
    } else if (query.trim()) {
      setIsOpen(false);
      onSearch(query.trim());
    }
  };

  const handleKeyDown = (e) => {
    if (!isOpen || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div ref={wrapperRef} className="relative w-full">
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative flex items-center bg-white rounded-2xl border-2 border-slate-200/90 shadow-sm focus-within:border-emerald-500 focus-within:ring-4 focus-within:ring-emerald-500/15 transition-all duration-200">
          <div className="pl-4 text-slate-400">
            <Search className="w-5 h-5 text-emerald-600" />
          </div>

          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => query.trim() && suggestions.length > 0 && setIsOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="w-full py-3.5 pl-3 pr-24 text-slate-800 placeholder-slate-400 font-medium text-sm sm:text-base focus:outline-hidden bg-transparent"
          />

          <div className="absolute right-2 flex items-center space-x-1.5">
            {query && (
              <button
                type="button"
                onClick={() => {
                  setQuery('');
                  setSuggestions([]);
                  setIsOpen(false);
                }}
                className="p-1.5 rounded-xl text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            <button
              type="submit"
              disabled={!query.trim()}
              className="flex items-center space-x-1 px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-xs sm:text-sm hover:from-emerald-600 hover:to-teal-700 shadow-sm shadow-emerald-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer"
            >
              <span>Tra từ</span>
              <CornerDownLeft className="w-3.5 h-3.5 hidden sm:inline" />
            </button>
          </div>
        </div>
      </form>

      {/* Autocomplete Dropdown */}
      {isOpen && suggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-900/10 z-50 overflow-hidden divide-y divide-slate-100 animate-in fade-in slide-in-from-top-2 duration-150">
          <div className="px-4 py-2 bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span className="flex items-center space-x-1">
              <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
              <span>Gợi ý từ vựng phù hợp</span>
            </span>
            <span>Dùng phím ↑ ↓ để chọn</span>
          </div>

          <div className="max-h-72 overflow-y-auto">
            {suggestions.map((item, index) => {
              const lvlConf = getLevelConfig(item.level);
              const isHighlighted = index === selectedIndex;
              return (
                <div
                  key={item.word}
                  onClick={() => handleSelectWord(item.word)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex items-center justify-between px-4 py-3 cursor-pointer transition-colors ${
                    isHighlighted ? 'bg-emerald-50/80 text-emerald-950' : 'hover:bg-slate-50 text-slate-800'
                  }`}
                >
                  <div className="flex items-center space-x-3 overflow-hidden">
                    <span className="text-base font-extrabold tracking-tight text-slate-900">
                      {item.word}
                    </span>
                    {item.ipa && (
                      <span className="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                        {item.ipa}
                      </span>
                    )}
                    {item.snippet && (
                      <span className="text-xs text-slate-500 truncate max-w-[200px] sm:max-w-xs">
                        {item.snippet}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center space-x-2 shrink-0">
                    <span className={`px-2 py-0.5 rounded-full text-[11px] font-extrabold ${lvlConf.bgLight} ${lvlConf.text} border ${lvlConf.border}`}>
                      {lvlConf.badge}
                    </span>
                    <ArrowRight className="w-4 h-4 text-slate-300" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
