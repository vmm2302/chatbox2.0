/**
 * CEFR Level Metadata and Dynamic Styling Configurations.
 * Automatically adapts to any level discovered in qa_records.jsonl.
 */

const DYNAMIC_PALETTES = [
  {
    color: 'amber',
    gradient: 'from-amber-500 to-orange-600',
    bgLight: 'bg-amber-50',
    bgCard: 'from-amber-50/70 via-orange-50/30 to-white',
    border: 'border-amber-200',
    borderActive: 'border-amber-500',
    text: 'text-amber-700',
    ring: 'ring-amber-400',
  },
  {
    color: 'purple',
    gradient: 'from-purple-500 to-indigo-600',
    bgLight: 'bg-purple-50',
    bgCard: 'from-purple-50/70 via-indigo-50/30 to-white',
    border: 'border-purple-200',
    borderActive: 'border-purple-500',
    text: 'text-purple-700',
    ring: 'ring-purple-400',
  },
  {
    color: 'rose',
    gradient: 'from-rose-500 to-pink-600',
    bgLight: 'bg-rose-50',
    bgCard: 'from-rose-50/70 via-pink-50/30 to-white',
    border: 'border-rose-200',
    borderActive: 'border-rose-500',
    text: 'text-rose-700',
    ring: 'ring-rose-400',
  },
  {
    color: 'teal',
    gradient: 'from-teal-500 to-cyan-600',
    bgLight: 'bg-teal-50',
    bgCard: 'from-teal-50/70 via-cyan-50/30 to-white',
    border: 'border-teal-200',
    borderActive: 'border-teal-500',
    text: 'text-teal-700',
    ring: 'ring-teal-400',
  },
  {
    color: 'indigo',
    gradient: 'from-indigo-600 to-violet-800',
    bgLight: 'bg-indigo-50',
    bgCard: 'from-indigo-50/70 via-violet-50/30 to-white',
    border: 'border-indigo-200',
    borderActive: 'border-indigo-500',
    text: 'text-indigo-700',
    ring: 'ring-indigo-400',
  },
  {
    color: 'cyan',
    gradient: 'from-cyan-500 to-blue-600',
    bgLight: 'bg-cyan-50',
    bgCard: 'from-cyan-50/70 via-blue-50/30 to-white',
    border: 'border-cyan-200',
    borderActive: 'border-cyan-500',
    text: 'text-cyan-700',
    ring: 'ring-cyan-400',
  },
];

export const CEFR_LEVELS = {
  ALL: {
    id: 'Tất cả',
    label: 'Tất cả trình độ',
    short: 'Tất cả',
    badge: '🌐 Mọi cấp độ',
    color: 'slate',
    gradient: 'from-slate-600 to-slate-800',
    bgLight: 'bg-slate-50',
    border: 'border-slate-200',
    text: 'text-slate-700',
  },
  A1: {
    id: 'A1',
    label: 'A1 · Khởi đầu (Beginner)',
    short: 'A1',
    badge: '🌱 A1 · Khởi đầu',
    color: 'emerald',
    gradient: 'from-emerald-500 to-teal-600',
    bgLight: 'bg-emerald-50',
    bgCard: 'from-emerald-50/70 via-teal-50/30 to-white',
    border: 'border-emerald-200',
    borderActive: 'border-emerald-500',
    text: 'text-emerald-700',
    ring: 'ring-emerald-400',
    desc: 'Từ vựng căn bản thường ngày, danh từ cụ thể, câu ví dụ đơn giản dễ hiểu.',
  },
  A2: {
    id: 'A2',
    label: 'A2 · Nền tảng (Elementary)',
    short: 'A2',
    badge: '🌿 A2 · Nền tảng',
    color: 'sky',
    gradient: 'from-sky-500 to-blue-600',
    bgLight: 'bg-sky-50',
    bgCard: 'from-sky-50/70 via-blue-50/30 to-white',
    border: 'border-sky-200',
    borderActive: 'border-sky-500',
    text: 'text-sky-700',
    ring: 'ring-sky-400',
    desc: 'Các thì cơ bản, từ loại, dạng bất quy tắc và tình huống giao tiếp thông dụng.',
  },
  B1: {
    id: 'B1',
    label: 'B1 · Trung cấp (Intermediate)',
    short: 'B1',
    badge: '🚀 B1 · Trung cấp',
    color: 'amber',
    gradient: 'from-amber-500 to-orange-600',
    bgLight: 'bg-amber-50',
    bgCard: 'from-amber-50/70 via-orange-50/30 to-white',
    border: 'border-amber-200',
    borderActive: 'border-amber-500',
    text: 'text-amber-700',
    ring: 'ring-amber-400',
    desc: 'Giao tiếp hàng ngày trôi chảy, chủ đề công việc, trường học và sở thích.',
  },
  B2: {
    id: 'B2',
    label: 'B2 · Nâng cao (Upper-Intermediate)',
    short: 'B2',
    badge: '🌟 B2 · Nâng cao',
    color: 'purple',
    gradient: 'from-purple-500 to-indigo-600',
    bgLight: 'bg-purple-50',
    bgCard: 'from-purple-50/70 via-indigo-50/30 to-white',
    border: 'border-purple-200',
    borderActive: 'border-purple-500',
    text: 'text-purple-700',
    ring: 'ring-purple-400',
    desc: 'Từ vựng trừu tượng, thảo luận kỹ thuật và diễn đạt tự nhiên.',
  },
  C1: {
    id: 'C1',
    label: 'C1 · Cao cấp (Advanced)',
    short: 'C1',
    badge: '🔥 C1 · Cao cấp',
    color: 'rose',
    gradient: 'from-rose-500 to-pink-600',
    bgLight: 'bg-rose-50',
    bgCard: 'from-rose-50/70 via-pink-50/30 to-white',
    border: 'border-rose-200',
    borderActive: 'border-rose-500',
    text: 'text-rose-700',
    ring: 'ring-rose-400',
    desc: 'Sử dụng ngôn ngữ linh hoạt cho mục đích học thuật và xã hội.',
  },
  C2: {
    id: 'C2',
    label: 'C2 · Thành thạo (Proficiency)',
    short: 'C2',
    badge: '👑 C2 · Thành thạo',
    color: 'indigo',
    gradient: 'from-indigo-600 to-violet-800',
    bgLight: 'bg-indigo-50',
    bgCard: 'from-indigo-50/70 via-violet-50/30 to-white',
    border: 'border-indigo-200',
    borderActive: 'border-indigo-500',
    text: 'text-indigo-700',
    ring: 'ring-indigo-400',
    desc: 'Hiểu và biểu đạt trôi chảy, tinh tế như người bản xứ.',
  },
};

/**
 * Get styling and label config for any level, generating dynamically if not predefined.
 */
export function getLevelConfig(level) {
  if (!level) return CEFR_LEVELS.A1;
  const clean = String(level).toUpperCase().trim();
  if (CEFR_LEVELS[clean]) {
    return CEFR_LEVELS[clean];
  }
  // Generate dynamically for any custom or new level
  const hash = clean.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const palette = DYNAMIC_PALETTES[hash % DYNAMIC_PALETTES.length];
  return {
    id: clean,
    label: `${clean} · Cấp độ ${clean}`,
    short: clean,
    badge: `🏷️ ${clean}`,
    ...palette,
    desc: `Tập hợp từ vựng thuộc trình độ ${clean}.`,
  };
}
