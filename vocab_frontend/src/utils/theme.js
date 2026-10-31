/**
 * Theme Manager for System, Light, and Dark modes.
 * Defaults to 'system' (prefers-color-scheme) as requested by user.
 */

export const THEME_STORAGE_KEY = 'vocab_theme_mode';

export function getInitialTheme() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'light' || saved === 'dark' || saved === 'system') {
      return saved;
    }
  } catch (e) {
    console.warn('Could not read theme preference from storage:', e);
  }
  return 'system'; // Mặc định tự động theo cấu hình máy tính
}

export function applyTheme(mode) {
  if (typeof document === 'undefined') return;

  const root = document.documentElement;
  const isSystemDark =
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches;

  const shouldBeDark = mode === 'dark' || (mode === 'system' && isSystemDark);

  if (shouldBeDark) {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }
}

export function subscribeSystemTheme(callback) {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return () => {};
  }

  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const handler = (e) => {
    // Re-apply system theme directly to ensure DOM class is in sync immediately
    applyTheme('system');
    callback(e.matches);
  };

  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  } else if (mediaQuery.addListener) {
    mediaQuery.addListener(handler);
    return () => mediaQuery.removeListener(handler);
  }

  return () => {};
}

// Immediately self-initialize theme on module import to prevent any flash of unstyled theme
if (typeof document !== 'undefined') {
  try {
    applyTheme(getInitialTheme());
  } catch (e) {
    console.warn('Initial theme application error:', e);
  }
}
