// window.HK for the NBA app: HK.mount(el, 'View', props) renders a Halaska view into a DOM node,
// synchronously (the page's plain-JS code reads the DOM right after render()). The theme follows the page's data-theme
// (light or dark, chosen with the header switch); HK.setTheme() re-renders every mounted view in the new theme.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { ThemeProvider, AccentContext, tokens } from '../../../src/halaska-kit.jsx';
import { views, setThemeName } from './views.jsx';

// The kit's light palette is tuned for fills, not small text: darken the greys and tones so small numbers clear 4.5:1.
Object.assign(tokens.light, { text: '#262626', textSecondary: '#5c5c5c', textTertiary: '#737373', success: '#15803d', warning: '#b45309', danger: '#c62828', successBg: '#e9f7ee', warningBg: '#fdf3e2', dangerBg: '#fdecec' });
const ACCENT = { dark: '#93c5fd', light: '#1d5fa8' };
const roots = new Map();     // el -> {r, name, props}
const themeNow = () => (document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');
function draw(el) {
  const x = roots.get(el), th = themeNow(), V = views[x.name];
  setThemeName(th);
  flushSync(() => x.r.render(<ThemeProvider theme={th}><AccentContext.Provider value={ACCENT[th]}><V {...x.props} /></AccentContext.Provider></ThemeProvider>));
}
window.HK = {
  mount(el, name, props) {
    let x = roots.get(el);
    if (!x) { x = { r: createRoot(el), name, props }; roots.set(el, x); }
    x.name = name; x.props = props;
    draw(el);
  },
  setTheme() { for (const el of [...roots.keys()]) { if (el.isConnected) draw(el); else roots.delete(el); } },
};
