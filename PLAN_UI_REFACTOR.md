# UI Refactor Plan: Minimalista Profissional (Vercel/Linear/Notion style)

**Goal:** Transform Sokol frontend from compact/naive to elegant, professional design with proper spacing, refined colors, smooth interactions, and improved component hierarchy.

**Scope:** All pages (Login, Cases, CaseDetail with all tabs)

**Design System Reference:** Inspired by Vercel, Linear, and Notion — clean typography, generous whitespace, subtle shadows, smooth transitions, intentional color hierarchy.

---

## Phase 0: Design System Foundation

**What:** Define comprehensive design tokens (spacing, colors, typography, shadows, borders, transitions)

**Tokens to Implement:**

### Spacing Scale
- `xs`: 4px (use sparingly)
- `sm`: 8px 
- `md`: 12px
- `lg`: 16px (default spacing)
- `xl`: 24px (section spacing)
- `2xl`: 32px (major sections)

### Color Palette (expand beyond current)
```
Primary (Accent): #3b82f6 (blue) - keep current
Hover: #60a5fa (lighter blue)
Pressed: #2563eb (darker blue)

Background: #f8fafc (light mode reference, but stay dark)
Surface: #1e293b (dark surface - more refined than #111827)
Surface Alt: #334155 (slightly lighter)

Text: #f1f5f9 (pure white-ish)
Text Muted: #cbd5e1 (for secondary)
Text Dim: #94a3b8 (for tertiary/disabled)

Border: #334155 (refined, more visible)

Success: #10b981 (keep current)
Warning: #f59e0b (adjust for better visibility)
Danger: #ef4444 (keep current)
Info: #06b6d4 (keep current)
```

### Shadows (for depth)
```
- sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05)
- md: 0 4px 6px -1px rgba(0, 0, 0, 0.1)
- lg: 0 10px 15px -3px rgba(0, 0, 0, 0.15)
- xl: 0 20px 25px -5px rgba(0, 0, 0, 0.2)
```

### Border Radius
- `sm`: 6px (small elements)
- `md`: 8px (default buttons, small cards)
- `lg`: 12px (cards, modals, inputs)
- `xl`: 16px (large components)

### Transitions
- Fast: 150ms (hover states)
- Normal: 300ms (default transitions)
- Slow: 500ms (major layout changes)

**Files to Update:**
- `web/src/index.css` - Add new tokens, update existing ones

**Verification:**
- [ ] Tailwind @theme section includes all new tokens
- [ ] CSS variables defined and accessible

---

## Phase 1: Update Global Styling & Colors

**What:** Refactor `index.css` with refined color palette, improved typography, better scrollbar, enhanced focus states.

**Changes:**
1. Update color theme with refined palette
2. Improve font stack (add -apple-system for better rendering)
3. Add focus ring styles for better accessibility
4. Improve scrollbar styling
5. Add subtle background pattern (optional gradient/noise)

**Files to Change:**
- `web/src/index.css`

**Implementation Details:**
- Replace color variables with refined values
- Add `:focus-visible` styles for keyboard navigation
- Improve scrollbar with better colors and hover states

**Verification:**
- [ ] Open app and verify colors are refined
- [ ] Tab through inputs and see better focus rings
- [ ] Scrollbar looks more polished

---

## Phase 2: Input & Button Components (Style Enhancements)

**What:** Create consistent, polished input and button styles with better sizing and visual feedback.

**Changes in CaseDetail.tsx, Cases.tsx, Login.tsx:**
1. **Inputs:** Increase padding from `py-2.5` to `py-3` (buttons/selects), add subtle background transitions
2. **Buttons:** Increase padding, add shadow on hover, refine colors
3. **Selects:** Match input styling
4. **Consistency:** All inputs/buttons use same visual language

**Examples to Update:**
- Login page inputs: Line 46, 56
- Cases page search: Line 117
- CaseDetail modals: Line 133, 146
- All button states

**Key Sizing Updates:**
- Button padding: `px-4 py-2` → `px-5 py-2.5` (default), `px-6 py-3` (prominent)
- Input padding: `px-4 py-2.5` → `px-4 py-3` (standard)
- Gap between elements: `gap-2` → `gap-3`, `gap-3` → `gap-4`

**Verification:**
- [ ] All buttons/inputs have consistent sizing
- [ ] Hover/focus states are smooth
- [ ] Visual hierarchy is clear

---

## Phase 3: Chat Tab Refactor (Priority)

**What:** Redesign Chat tab for elegance and usability. Main improvements:
1. Larger input area with better visual prominence
2. Send button with icon + text (or prominent icon)
3. Better message spacing and visual separation
4. Improved tool call and source badges
5. Better loading state

**Current Issues (Lines 467-549):**
- Input `py-3` is OK but needs `px-4` → `px-5`
- Button is icon-only: add visual weight
- Messages gap is `space-y-6` but could use better container styling
- Tool/source badges are too small

**Changes:**
1. Input container: Add subtle background, border refinement, larger padding
2. Button: `px-5 py-3` with "Enviar" text (or keep icon but add hover text)
3. Message bubbles: Better padding (`p-5` → `p-6`), improved separation
4. Badges: Larger, better colors, improve readability
5. Loading state: Better visual feedback

**Spacing Improvements:**
- Message container gap: `space-y-6` (keep, but add better structure)
- Input group: `gap-3` → `gap-4`
- Input padding: `px-4 py-3` → `px-5 py-4` 
- Button: `px-5 py-3` (increase width with text)

**Verification:**
- [ ] Input area looks prominent and inviting
- [ ] Messages have clear separation
- [ ] Button is visually distinct
- [ ] All text is readable

---

## Phase 4: Media Tab Refactor (Critical Image Fix)

**What:** Fix image rendering issues and improve media gallery layout.

**Current Issue (Line 846):**
- `minHeight: '160px', maxHeight: '300px'` with `object-contain` creates empty space
- Images appear small in large containers
- Should use aspect ratio to maintain proportions

**Changes:**
1. Use `aspect-square` (1:1) for consistent grid
2. Replace `object-contain` with `object-cover` or `object-fill`
3. Improve image container structure
4. Add loading skeleton states
5. Better detection badge positioning

**Implementation:**
- Change container from inline style to Tailwind classes
- Use `aspect-square` with `overflow-hidden`
- Change `object-contain` to `object-cover`
- Increase media grid gap: `gap-5` → `gap-6`
- Better badge positioning with absolute positioning

**Verification:**
- [ ] Images fill containers evenly
- [ ] Aspect ratio is consistent
- [ ] Detection badges are visible and well-positioned
- [ ] No weird clipping or filters

---

## Phase 5: Cases Page Refactor

**What:** Improve Cases list page with better spacing, clearer hierarchy, more elegant case cards.

**Changes:**
1. **Header:** Better spacing and typography
2. **Search:** Larger, more prominent `py-3` → `py-3.5`
3. **Case Cards:** 
   - Increase padding `p-4` → `p-5` or `p-6`
   - Add subtle shadow on hover
   - Better gap between items `gap-2` → `gap-3`
   - Improve typography hierarchy

**Verification:**
- [ ] Case cards feel more substantial
- [ ] Search bar is easier to interact with
- [ ] Hover effects are smooth

---

## Phase 6: Login Page Refactor

**What:** Make login page more elegant and inviting.

**Changes:**
1. **Logo area:** Increase spacing
2. **Inputs:** `py-3` → `py-4`, better focus states
3. **Button:** Larger `py-3` → `py-4`, add shadow
4. **Form spacing:** `gap-5` → `gap-6`

**Verification:**
- [ ] Form feels more spacious
- [ ] Button is inviting to click
- [ ] Typography is clear

---

## Phase 7: CaseDetail - Sidebar & Navigation

**What:** Refine sidebar and navigation elements.

**Changes:**
1. **Nav items:** Increase padding `py-2.5` → `py-3`
2. **Gap between items:** `gap-1` → `gap-2`
3. **Icons:** Ensure consistent sizing
4. **Active state:** Better visual feedback
5. **Logout button:** Better spacing/styling

**Verification:**
- [ ] Navigation feels less cramped
- [ ] Active tab is clearly indicated
- [ ] Hover states are smooth

---

## Phase 8: CaseDetail - Timeline & Search Tabs

**What:** Improve spacing and layout of Timeline and Search tabs.

**Changes:**
1. **Timeline events:**
   - Event cards: `p-5` → `p-6`
   - Gap: `gap-3` → `gap-4`
   - Better icon sizing
2. **Search results:**
   - Result cards: `p-5` → `p-5` or `p-6`
   - Better score badge styling
   - Improved text hierarchy

**Verification:**
- [ ] Content is less cramped
- [ ] Cards have good breathing room
- [ ] Typography hierarchy is clear

---

## Phase 9: CaseDetail - Other Tabs (Data, Bookmarks, Watchlists, etc)

**What:** Consistent spacing improvements across remaining tabs.

**Changes:**
1. **Stat cards (Data tab):** `p-5` → `p-6`, better icons
2. **List items:** Consistent spacing pattern
3. **Badges and tags:** Better sizing and colors
4. **Container padding:** `p-8` is good, but ensure internal spacing is refined

**Verification:**
- [ ] All tabs have consistent visual language
- [ ] No cramped elements

---

## Phase 10: Polish & Refinement

**What:** Final touches for elegance.

**Changes:**
1. Review all hover states - ensure smooth transitions
2. Check all shadow usage - add subtle shadows where appropriate
3. Verify color consistency across all tabs
4. Test focus states for accessibility
5. Ensure loading states are elegant

**Verification:**
- [ ] All hover effects are smooth (150-300ms)
- [ ] Focus rings are visible but subtle
- [ ] Colors are consistent
- [ ] No visual glitches

---

## Execution Order

1. **Phase 0-1:** Update design tokens in index.css (foundation)
2. **Phase 3:** Chat tab (priority - most used)
3. **Phase 4:** Media tab (critical fix)
4. **Phase 2:** Buttons/inputs (used everywhere)
5. **Phase 5-9:** Page-by-page refinement
6. **Phase 10:** Polish pass

---

## Files to Modify (Summary)

- `web/src/index.css` - Colors, tokens
- `web/src/pages/Login.tsx` - Spacing updates
- `web/src/pages/Cases.tsx` - Spacing updates
- `web/src/pages/CaseDetail.tsx` - All tabs

---

## Design Principles (Throughout)

1. **Generous Whitespace:** Use space intentionally, not as filler
2. **Clear Hierarchy:** Typography, size, and color establish importance
3. **Subtle Interactions:** Shadows, transitions, hover states should be felt, not seen
4. **Consistency:** Every button, input, card follows the same rules
5. **Accessibility:** Ensure focus states and contrast are maintained
