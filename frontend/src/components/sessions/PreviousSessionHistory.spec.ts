import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import PreviousSessionHistory from './PreviousSessionHistory.vue'
import apiClient from '@/api/client'

vi.mock('@/api/client')

describe('PreviousSessionHistory', () => {
  const mockClientId = 'client-123'
  const mockCurrentSessionId = 'session-current'

  const mockSessions = [
    {
      id: 'session-1',
      client_id: mockClientId,
      session_date: '2024-10-15T10:00:00Z',
      is_draft: false,
      subjective: 'Patient reports shoulder pain',
      objective: 'ROM: 90 degrees',
      assessment: 'Improving',
      plan: 'Continue exercises',
    },
    {
      id: 'session-2',
      client_id: mockClientId,
      session_date: '2024-10-10T10:00:00Z',
      is_draft: true,
      subjective: 'Follow-up session',
      objective: null,
      assessment: null,
      plan: null,
    },
    // Add 8 more for total of 10
    ...Array.from({ length: 8 }, (_, i) => ({
      id: `session-${i + 3}`,
      client_id: mockClientId,
      session_date: `2024-09-${25 - i}T10:00:00Z`,
      is_draft: false,
      subjective: `Session ${i + 3}`,
      objective: null,
      assessment: null,
      plan: null,
    })),
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Initial Load', () => {
    it('should load 10 most recent sessions on mount', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 52,
          page: 1,
          page_size: 10,
          total_pages: 6,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith(
          expect.stringContaining('page=1&page_size=10')
        )
      })

      // Should show total count
      expect(wrapper.text()).toContain('52 sessions total')
    })

    it('should display loading skeleton during initial load', () => {
      vi.mocked(apiClient.get).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      )

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      // Should show 3 skeleton loaders
      expect(wrapper.findAll('.animate-pulse')).toHaveLength(3)
    })

    it('should display error state on API failure', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('API Error'))

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('Failed to load session history')
      })
    })

    it('should display empty state when no sessions exist', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: [],
          total: 0,
          page: 1,
          page_size: 10,
          total_pages: 0,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('No sessions found')
        expect(wrapper.text()).toContain('Session notes will appear here')
      })
    })
  })

  describe('Timeline Grouping', () => {
    it('should create "Recent Sessions" group with first 10 sessions expanded', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('Recent Sessions')
        expect(wrapper.text()).toContain('(10)')
      })

      // Recent group should be expanded (showing individual sessions)
      const sessionButtons = wrapper.findAll('button[type="button"]')
      const sessionItems = sessionButtons.filter(
        (btn) => btn.text().includes('Oct') || btn.text().includes('Sep')
      )
      expect(sessionItems.length).toBeGreaterThan(0)
    })

    it('should group older sessions by month when collapsed', async () => {
      const sessionsAcrossMonths = [
        ...mockSessions.slice(0, 10), // Recent (Oct 2024)
        {
          id: 'session-sept-1',
          client_id: mockClientId,
          session_date: '2024-09-15T10:00:00Z',
          is_draft: false,
          subjective: 'September session',
        },
        {
          id: 'session-sept-2',
          client_id: mockClientId,
          session_date: '2024-09-10T10:00:00Z',
          is_draft: false,
          subjective: 'Another September session',
        },
      ]

      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: sessionsAcrossMonths,
          total: 12,
          page: 1,
          page_size: 10,
          total_pages: 2,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('September 2024')
        expect(wrapper.text()).toContain('(2)') // 2 sessions in September
      })
    })

    it('should expand/collapse groups on click', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.find('button').exists()).toBe(true)
      })

      // Find "Recent Sessions" group button
      let groupButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Recent Sessions'))

      expect(groupButton).toBeDefined()

      // Initially should be expanded (rotate-90 class)
      let chevron = groupButton!.find('svg')
      expect(chevron.classes()).toContain('rotate-90')

      // Click to collapse
      await groupButton!.trigger('click')
      await nextTick()

      // Re-query after state change to get updated DOM
      groupButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Recent Sessions'))
      chevron = groupButton!.find('svg')

      // After click, should be collapsed (no rotate-90 class)
      expect(chevron.classes()).not.toContain('rotate-90')
    })
  })

  describe('Pagination', () => {
    it('should show "Load More" button when more sessions exist', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions.slice(0, 10),
          total: 52,
          page: 1,
          page_size: 10,
          total_pages: 6,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('Load More Sessions')
        expect(wrapper.text()).toContain('(42 older)') // 52 - 10 = 42
      })
    })

    it('should load next 20 sessions when "Load More" clicked', async () => {
      // Initial load: 10 sessions
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions.slice(0, 10),
          total: 52,
          page: 1,
          page_size: 10,
          total_pages: 6,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.find('button').exists()).toBe(true)
      })

      // Mock second page load
      const next20Sessions = Array.from({ length: 20 }, (_, i) => ({
        id: `session-page2-${i}`,
        client_id: mockClientId,
        session_date: `2024-08-${20 - i}T10:00:00Z`,
        is_draft: false,
        subjective: `Session ${i}`,
      }))

      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: next20Sessions,
          total: 52,
          page: 2,
          page_size: 20,
          total_pages: 3,
        },
      })

      // Click "Load More"
      const loadMoreButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Load More Sessions'))
      await loadMoreButton!.trigger('click')

      await nextTick()
      await vi.waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith(
          expect.stringContaining('page=2&page_size=20')
        )
      })

      // Should now show 30 total sessions loaded
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('(22 older)') // 52 - 30 = 22
      })
    })

    it('should hide "Load More" when all sessions loaded', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        const loadMoreButton = wrapper
          .findAll('button')
          .find((btn) => btn.text().includes('Load More'))
        expect(loadMoreButton).toBeUndefined()
      })

      // Should NOT show "All X sessions loaded" message when we have 10 or fewer sessions
      // (Message only shows when > 10 sessions)
      expect(wrapper.text()).not.toContain('All 10 sessions loaded')
    })
  })

  describe('Quick Filters', () => {
    it('should display filter buttons with counts', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('All')
        expect(wrapper.text()).toContain('Finalized')
        expect(wrapper.text()).toContain('Drafts')
      })

      // Check counts
      expect(wrapper.text()).toContain('(10)') // All
      expect(wrapper.text()).toContain('(9)') // Finalized (10 - 1 draft)
      expect(wrapper.text()).toContain('(1)') // Drafts
    })

    it('should filter sessions when "Finalized" clicked', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.find('button').exists()).toBe(true)
      })

      // Click "Finalized" filter
      const finalizedButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().startsWith('Finalized'))
      await finalizedButton!.trigger('click')

      await nextTick()

      // Should only show 9 finalized sessions
      expect(wrapper.text()).toContain('Recent Sessions')
      expect(wrapper.text()).toContain('(9)') // 9 finalized in recent
    })

    it('should filter sessions when "Drafts" clicked', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.find('button').exists()).toBe(true)
      })

      // Click "Drafts" filter
      const draftsButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().startsWith('Drafts'))
      await draftsButton!.trigger('click')

      await nextTick()

      // Should only show 1 draft session
      expect(wrapper.text()).toContain('(1)')
    })
  })

  describe('Search Functionality', () => {
    it('should display search input', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()

      const searchInput = wrapper.find('input[type="search"]')
      expect(searchInput.exists()).toBe(true)
      expect(searchInput.attributes('placeholder')).toBe('Search sessions...')
    })

    it('should filter sessions by search query', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.find('input[type="search"]').exists()).toBe(true)
      })

      const searchInput = wrapper.find('input[type="search"]')
      await searchInput.setValue('shoulder')

      await nextTick()

      // Should filter to only show session-1 which contains "shoulder pain"
      // Count should be (1) for recent sessions
      expect(wrapper.text()).toContain('Recent Sessions')
      expect(wrapper.text()).toContain('(1)')
    })

    it('should show "no results" message when search returns no matches', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()

      const searchInput = wrapper.find('input[type="search"]')
      await searchInput.setValue('nonexistent term xyz')

      await nextTick()

      expect(wrapper.text()).toContain('No sessions found')
      expect(wrapper.text()).toContain('Try adjusting your search terms')
    })

    it('should show search scope warning when not all sessions loaded', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions.slice(0, 10),
          total: 52,
          page: 1,
          page_size: 10,
          total_pages: 6,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()

      const searchInput = wrapper.find('input[type="search"]')
      await searchInput.setValue('shoulder')

      await nextTick()

      expect(wrapper.text()).toContain('Searching 10 loaded sessions')
      expect(wrapper.text()).toContain('Load all 52')
    })

    it('should clear search when "Clear search" button clicked', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()

      const searchInput = wrapper.find('input[type="search"]')
      await searchInput.setValue('nonexistent')

      await nextTick()

      const clearButton = wrapper
        .findAll('button')
        .find((btn) => btn.text() === 'Clear search')
      await clearButton!.trigger('click')

      await nextTick()

      expect((searchInput.element as HTMLInputElement).value).toBe('')
    })
  })

  describe('Session Selection', () => {
    it('should emit "select-session" event when session clicked', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions.slice(0, 1),
          total: 1,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()
      await vi.waitFor(() => {
        // Look for session cards (buttons that are NOT group headers or filters)
        const sessionButtons = wrapper.findAll('button').filter((btn) => {
          const text = btn.text()
          return text.includes('October 15') && !text.includes('Recent Sessions')
        })
        expect(sessionButtons.length).toBeGreaterThan(0)
      })

      const sessionButton = wrapper.findAll('button').find((btn) => {
        const text = btn.text()
        return text.includes('October 15') && !text.includes('Recent Sessions')
      })
      await sessionButton!.trigger('click')

      expect(wrapper.emitted('select-session')).toBeTruthy()
      expect(wrapper.emitted('select-session')![0]).toEqual(['session-1'])
    })

    it('should emit "back" event when back button clicked', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()

      const backButton = wrapper.find('button[aria-label="Go back"]')
      await backButton.trigger('click')

      expect(wrapper.emitted('back')).toBeTruthy()
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA labels on buttons', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()

      const backButton = wrapper.find('button[aria-label="Go back"]')
      expect(backButton.exists()).toBe(true)
    })

    it('should have proper heading hierarchy', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions,
          total: 10,
          page: 1,
          page_size: 10,
          total_pages: 1,
        },
      })

      const wrapper = mount(PreviousSessionHistory, {
        props: {
          clientId: mockClientId,
          currentSessionId: mockCurrentSessionId,
        },
      })

      await nextTick()

      const heading = wrapper.find('h3')
      expect(heading.text()).toBe('Treatment Context')
    })
  })
})
