# SynchroData · Compra con más contexto

Source: http://127.0.0.1:3000

To create a video from this capture, use the `product-launch-video` skill.

## What's in This Capture

| File | Contents |
|------|----------|
| `screenshots/contact-sheet.jpg` | **View this first.** All scroll screenshots in labeled grid — see the entire page at a glance |
| `screenshots/scroll-*.png` | Individual viewport screenshots if you need detail on a specific section. |
| `extracted/tokens.json` | Design tokens: 20 colors, 3 fonts, 2 headings, 1 CTAs |
| `extracted/design-styles.json` | Computed styles from live DOM: typography hierarchy, button/card/nav styles, spacing scale, border-radius, box shadows. Primary data source for DESIGN.md. |
| `extracted/asset-descriptions.md` | One-line description of every downloaded asset. Read this for asset selection — only open individual files for safe-zone checking. |
| `extracted/visible-text.txt` | Page text in DOM order, prefixed with HTML tag (`[h1]`, `[p]`, `[a]`). Use as context — rephrase freely. |
| `assets/contact-sheet.jpg` | All downloaded images in one labeled grid. |
| `assets/svgs/contact-sheet.jpg` | SVGs rendered as thumbnails in labeled grid |
| `assets/` | Individual downloaded images, SVGs, and font files. |

## Brand Summary

- **Colors**: #1D1D1F (surface-dark), #FFFFFF (bg-light), #F5F5F7 (bg-light), #64748B (neutral), #E6EDF6 (bg-light), #1463D8 (accent), #1E40AF (accent), #E2E8F0 (bg-light), #F4F6F8 (bg-light), #000000 (bg-dark)
- **Fonts**: __nextjs-Geist (400-600 variable), __nextjs-Geist Mono (400-600 variable), -apple-system (400,500,550,600,650,700,750)
