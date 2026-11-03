/**
 * CEFR Level Metadata and Styling Configurations (strictly A1–A2).
 */

export const CEFR_LEVELS = {
  ALL: {
    id: 'Tất cả',
    label: 'Tất cả trình độ',
    short: 'Tất cả',
    badge: '🌐 Mọi cấp độ (A1–A2)',
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
};

export function getLevelConfig(level) {
  const clean = (level || 'A1').toUpperCase().trim();
  return CEFR_LEVELS[clean] || CEFR_LEVELS.A1;
}
