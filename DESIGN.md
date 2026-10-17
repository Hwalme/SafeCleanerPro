---
name: PPSAI Cleaner
description: Windows desktop workbench for reviewable scans, selective cleanup, protected memory, duplicate inspection and verified migration.
colors:
  graphite-bg: "#101419"
  graphite-rail: "#0D1116"
  surface-panel: "#161C23"
  surface-card: "#1D252E"
  line-subtle: "#2A3541"
  tint-ice: "#203640"
  text-primary: "#F0F4F7"
  text-secondary: "#A3AFBD"
  text-muted: "#8795A5"
  text-path: "#CFD7E0"
  accent-ice: "#8CDEEF"
  accent-ice-hover: "#B1ECF7"
  state-success: "#91D5B6"
  state-review: "#E7BA7A"
  state-error: "#ECA0A6"
  progress-done: "#224334"
  action-blue: "#294652"
  action-blue-hover: "#395C68"
  error-surface: "#3D282E"
  error-button: "#633A40"
  error-button-hover: "#7A454D"
  duplicate-keep: "#20332C"
  duplicate-redundant: "#32242A"
  success-deep: "#295443"
  unlock-danger: "#59353A"
typography:
  display:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei"
    fontSize: "28px"
    fontWeight: 700
  headline:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei"
    fontSize: "23px"
    fontWeight: 700
  title:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei"
    fontSize: "18px"
    fontWeight: 700
  body:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei"
    fontSize: "13px"
    fontWeight: 400
  label:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei"
    fontSize: "11px"
    fontWeight: 400
  metric:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei"
    fontSize: "29px"
    fontWeight: 700
  mono:
    fontFamily: "Consolas"
    fontSize: "11px"
    fontWeight: 400
rounded:
  none: "0px"
  checkbox: "4px"
  button: "8px"
  disk: "9px"
  card: "10px"
  panel: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  page: "28px"
components:
  button-primary:
    backgroundColor: "{colors.accent-ice}"
    textColor: "{colors.graphite-bg}"
    typography: "{typography.body}"
    rounded: "{rounded.button}"
    padding: "0 18px"
    height: "40px"
  button-secondary:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.button}"
    padding: "0 16px"
    height: "36px"
  button-danger:
    backgroundColor: "{colors.error-button}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.button}"
    padding: "0 16px"
    height: "36px"
  nav-item-active:
    backgroundColor: "{colors.tint-ice}"
    textColor: "{colors.accent-ice}"
    typography: "{typography.body}"
    rounded: "{rounded.button}"
    padding: "0 12px"
    height: "44px"
    width: "164px"
  disk-scope-card:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.disk}"
    padding: "8px 12px"
    height: "70px"
    width: "152px"
  panel:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.panel}"
    padding: "16px"
  inspector:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.panel}"
    padding: "18px"
    width: "268px"
  search-field:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.text-primary}"
    typography: "{typography.label}"
    padding: "0 10px"
    height: "34px"
---

# Design System: PPSAI Cleaner

## Overview

**Creative North Star: "冰青空间工作台"**

PPSAI Cleaner is a quiet, precise Windows workbench for making space while keeping important paths visible. Graphite surfaces establish a low-glare field; silver text carries hierarchy; the folded P mark, ice-cyan actions and restrained status colors provide the brand signal. The home surface is the cleaning workspace: scope, measurement, list, inspector and one persistent action dock stay in view together.

The visual language is native CustomTkinter with a dark tonal stack rather than a web or mobile pattern. A narrow navigation rail gives the tools a stable home, ruled rows keep selection reviewable, and the right inspector supplies context without turning the list into a wall of controls. Amber is reserved for review-required work, green confirms completed or retained content, and red marks errors or destructive paths. No invented findings appear before a scan, and the splash hands off through real initialization phases.

**Key Characteristics:**

- Graphite workspace with ice-cyan action signal and silver hierarchy.
- Scope first, then scan, inspect, select, and explicitly clean.
- Tonal panels and ruled rows create depth without shadows or blur.
- Protection, migration and duplicate workspaces share the same grammar.
- Native Windows keyboard focus and state gating are part of the visual contract.

## Colors

The palette is a graphite foundation with cool silver text, one ice-cyan brand accent, and restrained semantic colors for review, success and failure.

### Primary

- **Ice Cyan:** the primary action and selection signal. Use on the main scan/clean buttons, selected disk outlines, active navigation, progress, focus rings and protected-state indicators.
- **Ice Cyan Hover:** the lighter response for primary button hover and other direct action feedback.

### Secondary

- **Action Blue:** a quieter blue-teal for auxiliary actions such as select-all, migration and bulk operations.
- **Action Blue Hover:** the corresponding hover response for those auxiliary actions.

### Tertiary

- **Review Amber:** the only warm accent for risk review, processing status, high-capacity disks and confirmation gates.

### Neutral

- **Graphite Background:** the application canvas and main workspace.
- **Graphite Rail:** the left navigation rail and the deepest supporting surface.
- **Panel Surface:** scrollable lists, inspectors, dialogs and table containers.
- **Card Surface:** buttons, option menus, row controls, table headings and compact cards.
- **Subtle Line:** one-pixel dividers, borders and progress tracks.
- **Ice Tint:** selected navigation, selected disks and protected status backgrounds.
- **Primary Silver:** headings, values and primary body text.
- **Secondary Silver:** supporting copy, path descriptions and muted controls.
- **Muted Silver:** empty states, disabled labels and low-priority metadata.
- **Path Silver:** file paths and dense table content that need a little more contrast than helper text.

### Named Rules

**The One Signal Rule.** Ice cyan marks the next meaningful action or current selection; do not scatter it across decorative text.

**The Warm Review Rule.** Amber means a user must review or confirm scope. Keep it away from ordinary navigation and safe-cleanup affordances.

## Typography

**Display Font:** Microsoft YaHei UI (with Microsoft YaHei fallback)
**Body Font:** Microsoft YaHei UI / Microsoft YaHei
**Label/Mono Font:** Consolas for dense paths and activity text

**Character:** Chinese-first system typography is compact, legible and matter-of-fact. Bold weights carry page and metric hierarchy; labels stay quiet so capacity and selection state remain the visual focus. The shared font cache normalizes the fallback to Microsoft YaHei where required by Tk, while the branded factory uses Microsoft YaHei UI.

### Hierarchy

- **Display** (700, 28px): the main cleaning-workspace title at the default width; it drops to 23px below the compact layout threshold.
- **Headline** (700, 23px): secondary-workspace and popup headers with the folded P mark.
- **Title** (700, 18px): placeholder, inspector and section titles.
- **Body** (400, 13px): descriptions, navigation labels and ordinary controls.
- **Label** (400, 11px): status notes, metadata, badges and supporting copy.
- **Metric** (700, 29px): scan, protection and released-space values; tool windows use a 26px metric variant.
- **Mono** (400, 11px): paths and compact operational text where alignment matters.

### Named Rules

**The Measurement Leads Rule.** Large values and selected scope should be readable before the user reads the explanatory copy beneath them.

## Layout

The primary window opens at 1380×860 and accepts a minimum of 1120×740. A fixed 200px navigation rail sits beside a flexible workspace with a minimum 500px list region and a right inspector that is 268px wide at the default layout. The main page uses 28px outer gutters, a three-part unboxed metric strip, a horizontal drive-scope rail, a search and sort row, a flexible ruled list, a contextual inspector, and one persistent bottom action dock. The dock contains the current selection summary, status line, rescan control, primary action and a 3px progress track.

At reverse-scaled widths below 1200px, the title becomes 23px, the inspector becomes 252px, and its grid column uses a 264px minimum. Horizontal disk cards remain 152×70px and expose previous/next group controls plus keyboard focus scrolling. Deep cleaning and memory migration use 1300×820 windows with the same 1120×740 minimum; duplicate inspection uses the 1380×860 workspace pattern. DPI scaling is left to CustomTkinter and Windows.

The home sequence is intentionally linear: choose disks, scan one tier, inspect paths and sizes, select results, then confirm the destructive action. Secondary tools open as branded native workspaces and share the same rail, panel, table and action treatment.

## Elevation & Depth

The system is flat at rest and uses tonal layering instead of shadows. The canvas and rail establish the deepest levels; panel and card surfaces lift lists, inspectors and controls by color alone. One-pixel subtle lines separate rows and card boundaries, while the ice tint identifies selected or protected regions. Progress strips and state fills provide momentary depth during scanning and cleaning. There is no backdrop blur, glass effect, gradient, or hard offset shadow vocabulary in the shipped UI.

### Shadow Vocabulary

- **No shadow token:** depth is carried by surface tone, border and spacing. Do not add a box shadow to future native workspaces.

### Named Rules

**The Tonal Stack Rule.** Use the graphite → panel → card stack to establish hierarchy; reserve bright accents for state and action.

## Shapes

The form language is gently rounded at working surfaces and compact controls: 12px panels, 10px table and dialog wrappers, 9px drive cards, 8px buttons and 4px checkboxes. The rail and main frame are square-edged at 0px so the workspace reads as one stable desktop surface. Borders are usually one pixel in the subtle line color. Rows remain flat and rectangular, with a one-pixel rule and an optional full-width state fill below their content.

## Components

### Buttons

- **Shape:** compact rounded controls with an 8px corner radius; the shared button factory defaults to 36px height, while the persistent primary action and dialog actions use 40px.
- **Primary:** ice-cyan background, graphite text, bold when it is the page's main action, with a right-facing line arrow where the action advances the workflow.
- **Secondary:** card surface with silver text and a subtle-line hover; use for rescan, return, detail and navigation-adjacent actions.
- **Auxiliary:** action blue is used for bulk selection, migration and other reversible tool actions.
- **Review / destructive:** amber confirms risk work after the acknowledgement gate; error red is reserved for stop, delete, unlock and failure states.
- **Hover / Focus:** primary hover moves to Ice Cyan Hover. Every branded button binds Return and Space to invoke and shows a 1px ice-cyan focus border; focus out removes the border.

### Chips

- **Style:** status badges are compact text labels inside the row rather than pill controls. They use success green for routine cache, ice cyan for immune/locked, amber for review and red for error.
- **State:** selected navigation and selected disk cards use the Ice Tint surface with an ice-cyan edge; status text must continue to explain the state in Chinese.

### Cards / Containers

- **Corner Style:** 12px for primary panels and inspectors; 10px for table/dialog wrappers; 9px for disk cards.
- **Background:** Panel Surface for lists, inspectors, dialogs and tool tables; Card Surface for controls and compact table headings.
- **Shadow Strategy:** no shadow; refer to the tonal stack in Elevation & Depth.
- **Border:** subtle line at one pixel on drive cards, search fields and table boundaries; the selected drive changes the edge to ice cyan.
- **Internal Padding:** 12px for compact controls, 18px for inspectors, 24px for popup headers and outer content, and 28px for the home workspace gutter.

### Inputs / Fields

- **Style:** search fields are 34px high with Panel Surface, a subtle-line border and 10px horizontal padding. License and migration root fields use the same dark field treatment at 40px and 30px respectively.
- **Focus:** focus remains visible through the native control border and the shared ice-cyan focus treatment; Ctrl+F moves focus to the home search field.
- **Error / Disabled:** invalid activation copy uses the error color. Empty migration targets disable the migration action, and no selected AppData cache item disables the cache-clean action.

### Navigation

- **Style:** a 200px rail holds a 48px brand mark, PPSAI wordmark, six 44px tool items, settings and update actions, and the footer version. Items are 164px wide with 14px side gutters and use generated line icons rather than emoji.
- **States:** the active item uses Ice Tint and Ice Cyan text; inactive items are transparent with secondary silver and hover to Panel Surface. Settings remains visibly selected when its page is open.
- **Keyboard:** Ctrl+1 opens 空间清理, Ctrl+2 opens 深度清理, Ctrl+F focuses search, and F5 requests a fresh scan. Busy work freezes conflicting navigation and actions.

### Disk Scope Card

Each 152×70px card exposes a drive letter, free/total capacity, a 3px usage bar and a visible 已选 state. Clicking any child toggles the card. Return and Space toggle the focused card, focus scrolls the horizontal rail to that card, and 上一组 / 下一组 move the rail by pages.

### Ruled Result Row

Each cleaning row is 64px tall and binds its checkbox, name, size, badge and range control to the same app record. Clicking the row opens the inspector. The range control expands one subpath panel at a time; each non-immune path has its own checkbox and the selection persists when sorting or rebuilding the list. Immune rows show read-only paths and cannot be selected for cleaning.

### Dark Treeview

Duplicate, migration and AppData tools use a dark ttk Treeview inside a rounded panel. Headings use Card Surface and secondary silver; rows use Panel Surface with 28–36px row heights; selected rows use Ice Tint; duplicate keep/redundant and migration success/error states use their semantic fills. The migration status column is concise pure text, and group rows own the group selection and collapse behavior.

### Review Gate Dialog

Risk cleanup opens a 600×540 branded confirmation dialog with an amber summary, a scrollable selected-item list and a disabled confirm button. The checkbox acknowledgement enables the action. Returning to inspection closes the dialog without changing selection. Activation dialogs are 640×590, preserve the scan result, accept Return in the authorization field and close on Escape.

## Do's and Don'ts

### Do:

- **Do** use the folded P mark, PPSAI wordmark and the graphite / silver / ice-cyan identity across the main window, splash and auxiliary workspaces.
- **Do** keep scope, measurement, selection, inspector context and the persistent action dock visible in the home workspace.
- **Do** preserve the sequence of scan → inspect → select → explicit clean; scanning and cleaning remain off the UI thread and no destructive operation starts automatically.
- **Do** keep Agent memory, system immunity and manual locks visible and reviewable; immune rows remain read-only and do not participate in cleaning.
- **Do** bind each file checkbox to its file record, each app checkbox to the app selection state, and each migration group row to its child selection state.
- **Do** disable AppData cleanup when nothing is selected, disable migration when the target drive/root is unavailable, and keep migration status as concise text.
- **Do** preserve keyboard focus: Return/Space activate branded buttons and drive cards; Ctrl+1, Ctrl+2, Ctrl+F and F5 remain available; Escape closes activation dialogs.
- **Do** use tonal panels and one-pixel rules for structure, with the accent reserved for action and state.

### Don't:

- **Don't** add web, mobile, glass-blur, gradient or shadow components to this Windows desktop system.
- **Don't** use emoji or font icons for navigation; use the existing line-icon generator or the supplied folded P assets.
- **Don't** invent findings before a scan, silently start a scan or cleaning pass, or make a destructive control available without its required review gate.
- **Don't** use amber for routine navigation or safe cleanup, or red as a general emphasis color.
- **Don't** hide protected memory paths, discard persistent locks, or replace the engine's scope and state authority with presentation-only state.
- **Don't** allow busy work to switch into conflicting workspaces or leave controls that imply an unavailable target or empty selection can run.
- **Don't** turn a one-off screenshot composition into a new global layout; extend the rail, panel, ruled-list and inspector grammar instead.
