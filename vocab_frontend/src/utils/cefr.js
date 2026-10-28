/**
 * CEFR Level Metadata and Styling Configurations.
 */

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
    desc: 'Collocations, Phrasal verbs, phân biệt cặp từ và ứng dụng trong công việc.',
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
    desc: 'Sắc thái nghĩa (Formal/Informal), Idioms, Academic words và lỗi sai thường gặp.',
  },
};

export function getLevelConfig(level) {
  const clean = (level || 'A1').toUpperCase().trim();
  return CEFR_LEVELS[clean] || CEFR_LEVELS.A1;
}
