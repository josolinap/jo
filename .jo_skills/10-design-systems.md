# DESIGN.md - Design System Knowledge Base

This skill provides Jo with design system knowledge for generating consistent UI.

## How to Use

When asked to generate UI, use the appropriate design system below:

### OpenCode AI Style (Terminal-Native)
- Background: `#201d1d` (warm near-black)
- Text: `#fdfcfc` (warm off-white)
- Font: Berkeley Mono (monospace everywhere)
- Border radius: 4px
- Accent: `#007aff` (Apple blue)

### Claude Style (Warm Editorial)
- Background: `#0c0c0c` (dark)
- Accent: `#d4a574` (terracotta)
- Font: System UI fonts

### Cursor Style (Dark IDE)
- Background: `#1e1e1e`
- Accent: `#3b82f6` (gradient blue)
- Font: Inter/SF Pro

### Vercel Style (Precision)
- Background: `#000000`
- Text: `#ffffff`
- Font: Geist (sans-serif)

### Linear Style (Minimal)
- Background: `#0d0d0d`
- Accent: `#5e6ad2` (purple)
- Border radius: 6px

### Supabase Style (Emerald)
- Background: `#1a1a1a`
- Accent: `#24b47e` (green)
- Font: Inter

## Quick Reference

For any UI task, use this format:

```
Design: [name]
Colors: [comma-separated hex codes]
Typography: [font stack]
Spacing: 8px base unit
Radius: 4-6px
```

When generating code, always include:
1. Color variables in CSS custom properties
2. Consistent spacing using 4/8px scale
3. Font stack with system fallbacks
4. Hover/focus states for interactive elements
