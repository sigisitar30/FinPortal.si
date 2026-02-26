# FinPortal.si – AI Coding Guidelines

## Project Overview
Slovenian financial comparison portal with interactive calculators for loans, deposits, and investments. Static HTML/CSS/JS site using Tailwind CSS and Inter font.

## Architecture
- **Frontend-only**: No backend, server, or build process
- **Single-page app**: Tab-based navigation between calculators
- **Static data**: Deposit offers hardcoded in `script.js`
- **CDN dependencies**: Tailwind CSS, Google Fonts (Inter)

## Key Conventions

### Language & Localization
- **Slovenian (sl-SI)**: All UI text, number formatting, and date handling
- Use `toLocaleString("sl-SI")` for currency formatting: `formatSI(num)` function
- Currency always displayed as "€" with 2 decimal places

### Styling Patterns
- **Primary color**: `#0B6B3A` (dark green) for buttons and accents
- **Highlight color**: `#F2C94C` (gold) for glow effects and active states
- **Glow effects**: Custom CSS classes (`glow-hover`) with multi-layer box-shadows
- **Border radius**: `0.75rem` for inputs/buttons, `1.25rem` for cards
- **Hover animations**: `translateY(-2px) scale(1.02)` with cubic-bezier transitions

### Calculator Implementation
- **Loan calculator**: Annuity formula with monthly payments
- **Deposit calculator**: Compound interest (`P * Math.pow(1 + rate, years)`)
- **Investment calculator**: Future value of lump sum + annuity formula for monthly contributions
- **Input validation**: HTML `min/max/step` attributes, no additional JS validation

### Code Structure
- **Tab switching**: Manual class toggling (no frameworks)
- **Event listeners**: Direct `addEventListener` calls
- **DOM manipulation**: InnerHTML for dynamic content (deposit table)
- **Data structure**: Simple arrays of objects for deposit offers

### File Organization
- `index.html`: Complete page structure with inline sections
- `script.js`: Calculator logic + tab switching + data rendering
- `style.css`: Custom overrides + glow effects + responsive rules
- `images/`: Static assets (PNG icons and banners)

## Development Workflow
- **No build step**: Edit files directly, refresh browser
- **Testing**: Manual input testing in browser console
- **Debugging**: `console.log` with Slovenian timestamps
- **Deployment**: Static file hosting (GitHub Pages, etc.)

## Common Patterns
- **Calculator buttons**: ID pattern `*-calc-btn` (e.g., `loan-calc-btn`)
- **Result displays**: ID pattern `*-*` (e.g., `loan-monthly`, `dep-total`)
- **Tab elements**: `tab-*` IDs for buttons, `panel-*` for content
- **CSS variables**: Defined in `:root` for colors and spacing
- **Responsive design**: Mobile-first with `md:` breakpoints

## Financial Formulas
```javascript
// Monthly loan payment (annuity)
monthlyPayment = (amount * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -months));

// Deposit final amount
finalAmount = principal * Math.pow(1 + annualRate, years);

// Investment future value
futureValue = initial * Math.pow(1 + monthlyRate, months) +
              monthly * ((Math.pow(1 + monthlyRate, months) - 1) / monthlyRate);
```

## Important Notes
- **Legal disclaimers**: Prominently displayed for all calculators
- **No financial advice**: Site explicitly states it's informational only
- **Bank data**: Static sample data, not real-time API feeds
- **Accessibility**: Basic implementation, no ARIA labels or keyboard navigation</content>
<parameter name="filePath">c:\Users\Uporabnik\Documents\FinPortal.si\.github\copilot-instructions.md