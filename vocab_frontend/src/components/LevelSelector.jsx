import React, { useState, useEffect } from 'react';
import { CEFR_LEVELS, getLevelConfig } from '../utils/cefr';
import { getAvailableLevels } from '../services/api';

export default function LevelSelector({ selectedLevel, onSelectLevel }) {
  const [availableLevels, setAvailableLevels] = useState(['A1', 'A2']);

  useEffect(() => {
    let isMounted = true;
    getAvailableLevels()
      .then((data) => {
        if (isMounted && data && Array.isArray(data.levels) && data.levels.length > 0) {
          setAvailableLevels(data.levels);
        }
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  const levelItems = [
    CEFR_LEVELS.ALL,
    ...availableLevels.map((lvl) => getLevelConfig(lvl)),
  ];

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider flex items-center space-x-1">
          <span>Ưu tiên cấp độ CEFR</span>
        </label>
        <span className="text-xs text-slate-400 dark:text-zinc-500">
          {selectedLevel === 'Tất cả' ? 'Mọi cấp độ' : `Đang lọc từ vựng cấp độ ${selectedLevel}`}
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-1.5 sm:gap-2">
        {levelItems.map((lvl) => {
          const isSelected = selectedLevel === lvl.id;
          return (
            <button
              key={lvl.id}
              onClick={() => onSelectLevel(lvl.id)}
              className={`relative flex items-center justify-center space-x-1.5 py-2 px-3 rounded-2xl border text-xs sm:text-sm font-extrabold transition-all duration-200 cursor-pointer ${
                isSelected
                  ? `bg-gradient-to-r ${lvl.gradient} text-white shadow-md border-transparent scale-[1.02]`
                  : 'bg-white hover:bg-slate-50 dark:bg-[#212121] dark:hover:bg-[#262626] text-slate-700 dark:text-zinc-200 border-slate-200/80 dark:border-white/10 shadow-2xs'
              }`}
            >
              <span>{lvl.badge}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
