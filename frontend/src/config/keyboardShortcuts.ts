/**
 * Keyboard Shortcuts Registry
 *
 * Single source of truth for all keyboard shortcuts in PazPaz.
 * Used to generate the keyboard shortcuts help modal.
 */

export interface ShortcutConfig {
  keys: string
  description: string
  category: 'navigation' | 'calendar' | 'client' | 'clients-list'
  scope: 'global' | 'page'
  page?: string
}

export const KEYBOARD_SHORTCUTS: ShortcutConfig[] = [
  // Navigation (Global shortcuts)
  {
    keys: 'g c',
    description: 'Go to Calendar',
    category: 'navigation',
    scope: 'global',
  },
  {
    keys: 'g l',
    description: 'Go to Clients',
    category: 'navigation',
    scope: 'global',
  },
  {
    keys: '?',
    description: 'Show keyboard shortcuts',
    category: 'navigation',
    scope: 'global',
  },

  // Calendar shortcuts (Page-specific)
  {
    keys: '⌘N',
    description: 'New appointment',
    category: 'calendar',
    scope: 'page',
    page: 'Calendar',
  },
  {
    keys: 't',
    description: 'Go to today',
    category: 'calendar',
    scope: 'page',
    page: 'Calendar',
  },
  {
    keys: '←',
    description: 'Previous period',
    category: 'calendar',
    scope: 'page',
    page: 'Calendar',
  },
  {
    keys: '→',
    description: 'Next period',
    category: 'calendar',
    scope: 'page',
    page: 'Calendar',
  },
  {
    keys: 'w',
    description: 'Week view',
    category: 'calendar',
    scope: 'page',
    page: 'Calendar',
  },
  {
    keys: 'd',
    description: 'Day view',
    category: 'calendar',
    scope: 'page',
    page: 'Calendar',
  },
  {
    keys: 'm',
    description: 'Month view',
    category: 'calendar',
    scope: 'page',
    page: 'Calendar',
  },

  // Clients List shortcuts (Page-specific)
  {
    keys: '/',
    description: 'Focus client search',
    category: 'clients-list',
    scope: 'page',
    page: 'Clients',
  },
  {
    keys: '↑/↓',
    description: 'Navigate client list',
    category: 'clients-list',
    scope: 'page',
    page: 'Clients',
  },
  {
    keys: 'Home',
    description: 'Jump to first client',
    category: 'clients-list',
    scope: 'page',
    page: 'Clients',
  },
  {
    keys: 'End',
    description: 'Jump to last client',
    category: 'clients-list',
    scope: 'page',
    page: 'Clients',
  },
  {
    keys: 'Enter',
    description: 'Open client details',
    category: 'clients-list',
    scope: 'page',
    page: 'Clients',
  },
  {
    keys: 'Esc',
    description: 'Clear search / Back to list',
    category: 'clients-list',
    scope: 'page',
    page: 'Clients',
  },

  // Client Detail shortcuts (Page-specific)
  {
    keys: 'Esc',
    description: 'Back to previous view',
    category: 'client',
    scope: 'page',
    page: 'Client Detail',
  },
  {
    keys: '1',
    description: 'Overview tab',
    category: 'client',
    scope: 'page',
    page: 'Client Detail',
  },
  {
    keys: '2',
    description: 'History tab',
    category: 'client',
    scope: 'page',
    page: 'Client Detail',
  },
  {
    keys: '3',
    description: 'Plan of Care tab',
    category: 'client',
    scope: 'page',
    page: 'Client Detail',
  },
  {
    keys: '4',
    description: 'Files tab',
    category: 'client',
    scope: 'page',
    page: 'Client Detail',
  },
  {
    keys: 'e',
    description: 'Edit client',
    category: 'client',
    scope: 'page',
    page: 'Client Detail',
  },
  {
    keys: 'n',
    description: 'New session note',
    category: 'client',
    scope: 'page',
    page: 'Client Detail',
  },
  {
    keys: 's',
    description: 'Schedule appointment',
    category: 'client',
    scope: 'page',
    page: 'Client Detail',
  },
]
