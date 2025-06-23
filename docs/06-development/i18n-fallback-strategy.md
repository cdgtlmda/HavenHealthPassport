# Language Fallback Chain Configuration

## Overview

Haven Health Passport implements an intelligent fallback chain system to ensure users always see content in a language they can understand, even when translations are incomplete.

## Fallback Chain Priority

1. **User's Primary Language** - The language explicitly selected by the user
2. **User's Fallback Languages** - Languages the user has specified they understand
3. **Regional Fallbacks** - Languages commonly understood in the same region
4. **Script-based Fallbacks** - Languages using the same writing system
5. **Language Family Fallbacks** - Related languages from the same family
6. **English** - Universal fallback for all content

## Language Configurations

### South Asian Languages

- **Hindi (hi)**: → Urdu → Bengali → English
- **Urdu (ur)**: → Hindi → English  
- **Bengali (bn)**: → Hindi → English

### Middle Eastern Languages

- **Arabic (ar)**: → English → French
- **Persian/Farsi (fa)**: → Pashto → Arabic → English
- **Pashto (ps)**: → Persian → Urdu → English

### African Languages

- **Swahili (sw)**: → English

### European Languages

- **Spanish (es)**: → English
- **French (fr)**: → English

## Medical Content Fallbacks

For medical content, we use a more conservative approach:

1. User's primary language
2. User-specified fallbacks (only if explicitly chosen)
3. English (primary medical documentation language)
4. Major medical languages (Spanish, French, Arabic)

## Implementation Details

### Web Application

```typescript
import { getIntelligentFallbackChain } from '@i18n/fallback-chains';

const fallbacks = getIntelligentFallbackChain('ar', ['en']);
// Returns: ['ar', 'en', 'fr']
```

### Mobile Application

```typescript
import { getFallbackChain } from './i18n/fallbacks';

const fallbacks = getFallbackChain('fa', ['en']);
// Returns: ['fa', 'en', 'ps', 'ar']
```

## Quality Indicators

The system includes visual indicators to show translation quality:

- ✓ **Green Check**: Content available in current language
- ℹ️ **Blue Info**: Content using fallback language
- ⚠️ **Yellow Warning**: Content only available in distant fallback

## Configuration Options

Users can configure fallback behavior in Settings:

1. Enable/disable automatic fallbacks
2. Set preferred fallback languages
3. Choose between automatic and verified translations
4. View translation availability for current content

## Best Practices

1. Always provide English translations as the universal fallback
2. Prioritize medical accuracy over language proximity for health content
3. Show translation status indicators for transparency
4. Allow users to report translation issues
5. Regular review of fallback effectiveness through analytics