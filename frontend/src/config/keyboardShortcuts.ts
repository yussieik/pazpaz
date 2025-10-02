/**
 * Keyboard Shortcuts Registry
 *
 * Single source of truth for all keyboard shortcuts in PazPaz.
 * Used to generate the keyboard shortcuts help modal.
 */

export interface ShortcutConfig {
  keys: string
  description: string
  category: 'navigation' | 'calendar' | 'client'
}

export const KEYBOARD_SHORTCUTS: ShortcutConfig[] = [
  // Navigation
  {
    keys: 'g c',
    description: 'Go to Calendar',
    category: 'navigation',
  },
  {
    keys: 'g l',
    description: 'Go to Clients',
    category: 'navigation',
  },
  {
    keys: '?',
    description: 'Show keyboard shortcuts',
    category: 'navigation',
  },

  // Calendar shortcuts (from existing implementation)
  {
    keys: 't',
    description: 'Go to today',
    category: 'calendar',
  },
  {
    keys: 'j or ←',
    description: 'Previous period',
    category: 'calendar',
  },
  {
    keys: 'k or →',
    description: 'Next period',
    category: 'calendar',
  },
  {
    keys: 'w',
    description: 'Week view',
    category: 'calendar',
  },
  {
    keys: 'd',
    description: 'Day view',
    category: 'calendar',
  },
  {
    keys: 'm',
    description: 'Month view',
    category: 'calendar',
  },

  // Client shortcuts
  {
    keys: 'Esc',
    description: 'Back to previous view',
    category: 'client',
  },
]
