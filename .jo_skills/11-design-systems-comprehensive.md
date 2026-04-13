# DESIGN.md - Comprehensive Design System Reference

AI-generated design system reference for consistent UI creation.

## Table of Contents
1. [Color Palettes](#color-palettes)
2. [Typography](#typography)
3. [Components](#components)
4. [Layout](#layout)
5. [Agent Prompts](#agent-prompts)

---

## Color Palettes

### OpenCode AI (Terminal-Native)
| Role | Color | Hex |
|------|-------|-----|
| Background | Warm near-black | `#201d1d` |
| Surface | Dark surface | `#302c2c` |
| Text Primary | Warm off-white | `#fdfcfc` |
| Text Secondary | Mid gray | `#9a9898` |
| Text Muted | Muted gray | `#6e6e73` |
| Border | Warm transparent | `rgba(15, 0, 0, 0.12)` |
| Accent | Apple blue | `#007aff` |
| Success | Apple green | `#30d158` |
| Warning | Apple orange | `#ff9f0a` |
| Danger | Apple red | `#ff3b30` |

### Claude (Warm Editorial)
| Role | Color | Hex |
|------|-------|-----|
| Background | Dark | `#0c0c0c` |
| Text | Off-white | `#e8e6e3` |
| Accent | Terracotta | `#d4a574` |
| Border | Subtle | `#2a2a2a` |

### Cursor (Dark IDE)
| Role | Color | Hex |
|------|-------|-----|
| Background | VS Code dark | `#1e1e1e` |
| Surface | Elevated | `#252526` |
| Accent | Gradient blue | `#3b82f6` |
| Accent Hover | Lighter blue | `#60a5fa` |

### Linear (Ultra-Minimal)
| Role | Color | Hex |
|------|-------|-----|
| Background | Near black | `#0d0d0d` |
| Surface | Dark | `#141414` |
| Accent | Purple | `#5e6ad2` |
| Border | Subtle | `#2e2e2e` |

### Vercel (Precision)
| Role | Color | Hex |
|------|-------|-----|
| Background | Black | `#000000` |
| Text | White | `#ffffff` |
| Text Secondary | Gray | `#888888` |
| Accent | Vercel blue | `#3291ff` |

### Supabase (Emerald)
| Role | Color | Hex |
|------|-------|-----|
| Background | Dark | `#1a1a1a` |
| Surface | Elevated | `#222222` |
| Accent | Emerald | `#24b47e` |
| Border | Subtle | `#38383a` |

### Notion (Warm Minimal)
| Role | Color | Hex |
|------|-------|-----|
| Background | Warm white | `#ffffff` |
| Surface | Light gray | `#f7f7f5` |
| Text Primary | Near black | `#37352f` |
| Text Secondary | Gray | `#9b9b9b` |
| Accent | Notion red | `#eb5757` |

### GitHub (Developer)
| Role | Color | Hex |
|------|-------|-----|
| Background | White | `#ffffff` |
| Surface | Light | `#f6f8fa` |
| Text Primary | Dark gray | `#24292f` |
| Text Secondary | Gray | `#57606a` |
| Accent | GitHub blue | `#0969da` |
| Border | Subtle | `#d0d7de` |

---

## Typography

### Font Stacks

**Monospace (Terminal)**
```
Berkeley Mono, IBM Plex Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace
```

**Sans-Serif (System)**
```
Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif
```

**Sans-Serif (Premium)**
```
Geist, Geist Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif
```

### Type Scale

| Style | Size | Weight | Line Height |
|-------|------|--------|-------------|
| H1 | 38px | 700 | 1.50 |
| H2 | 24px | 600 | 1.30 |
| H3 | 20px | 600 | 1.40 |
| Body | 16px | 400 | 1.50 |
| Small | 14px | 400 | 1.50 |
| Caption | 12px | 400 | 1.40 |

---

## Components

### Buttons

**Primary**
```css
background: #201d1d;
color: #fdfcfc;
padding: 8px 16px;
border-radius: 4px;
font-weight: 500;
border: none;
```

**Secondary**
```css
background: transparent;
color: #201d1d;
border: 1px solid rgba(15, 0, 0, 0.12);
border-radius: 4px;
```

**Danger**
```css
background: #ff3b30;
color: #ffffff;
```

### Inputs
```css
background: #f8f7f7;
border: 1px solid rgba(15, 0, 0, 0.12);
border-radius: 6px;
padding: 12px 16px;
font-size: 16px;
```

### Cards
```css
background: #ffffff;
border: 1px solid #e5e5e5;
border-radius: 8px;
padding: 24px;
box-shadow: none;
```

---

## Layout

### Spacing Scale (8px base)
| Name | Value |
|------|-------|
| xs | 4px |
| sm | 8px |
| md | 16px |
| lg | 24px |
| xl | 32px |
| 2xl | 48px |
| 3xl | 64px |

### Container Widths
| Type | Max Width |
|------|-----------|
| Narrow | 640px |
| Default | 800px |
| Wide | 1024px |
| Full | 100% |

### Grid
- 12-column grid system
- 24px gutter
- 48px margin (desktop)

---

## Agent Prompts

### Hero Section
```
Create a hero section with:
- Background: #201d1d
- Heading: 38px Berkeley Mono, weight 700, #fdfcfc
- Subtitle: 16px, weight 400, #9a9898
- CTA button: dark bg, light text, 4px radius
```

### Feature List
```
Single-column feature list:
- Background: #201d1d
- Feature name: 16px weight 700, #fdfcfc
- Description: 16px weight 400, #9a9898
- 16px gap between items
- No cards, no borders
```

### Form
```
Email capture form:
- Input: #f8f7f7 bg, 6px radius, 20px padding
- Button: #201d1d bg, #fdfcfc text, 4px radius
- Berkeley Mono throughout
```

### Navigation
```
Sticky nav:
- Background: #201d1d
- Links: 16px weight 500, #fdfcfc, underline
- Brand: left-aligned monospace
- No blur, solid surface
```

---

## Usage

When generating UI:
1. Choose a design system from above
2. Use the color palette consistently
3. Apply typography rules
4. Follow component patterns
5. Use spacing scale

To get pixel-perfect results:
1. Include DESIGN.md in your prompt
2. Reference specific colors by hex
3. Use exact spacing values
4. Test on multiple breakpoints
