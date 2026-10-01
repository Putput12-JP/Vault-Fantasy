// window.HK for the NBA app: HK.mount(el, 'View', props) renders a Halaska view into a DOM node,
// synchronously (the page's plain-JS code reads the DOM right after render()).
import React from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { ThemeProvider, AccentContext } from '../../../src/halaska-kit.jsx';
import { views } from './views.jsx';

const roots = new WeakMap();
const ACCENT = '#93c5fd';
window.HK = {
  mount(el, name, props) {
    let r = roots.get(el);
    if (!r) { r = createRoot(el); roots.set(el, r); }
    const V = views[name];
    flushSync(() => r.render(<ThemeProvider theme="dark"><AccentContext.Provider value={ACCENT}><V {...props} /></AccentContext.Provider></ThemeProvider>));
  },
};
