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
    it('should create year group with "Recent Sessions" month group expanded', async () => {
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
        // Should show year header (2024)
        expect(wrapper.text()).toContain('2024')
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

    it('should expand/collapse year groups on click', async () => {
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

      // Find year header button
      let yearButton = wrapper
        .findAll('button')
        .find(
          (btn) =>
            btn.text().includes('2024') &&
            btn.attributes('aria-label')?.includes('year')
        )

      expect(yearButton).toBeDefined()

      // Initially should be expanded (rotate-90 class)
      let chevron = yearButton!.find('svg')
      expect(chevron.classes()).toContain('rotate-90')

      // Click to collapse
      await yearButton!.trigger('click')
      await nextTick()

      // Re-query after state change to get updated DOM
      yearButton = wrapper
        .findAll('button')
        .find(
          (btn) =>
            btn.text().includes('2024') &&
            btn.attributes('aria-label')?.includes('year')
        )
      chevron = yearButton!.find('svg')

      // After click, should be collapsed (no rotate-90 class)
      expect(chevron.classes()).not.toContain('rotate-90')
    })

    it('should expand/collapse month groups on click', async () => {
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
      })

      // Find "Recent Sessions" month button
      let monthButton = wrapper
        .findAll('button')
        .find(
          (btn) =>
            btn.text().includes('Recent Sessions') && btn.attributes('data-month-key')
        )

      expect(monthButton).toBeDefined()

      // Initially should be expanded (rotate-90 class)
      let chevron = monthButton!.find('svg')
      expect(chevron.classes()).toContain('rotate-90')

      // Click to collapse
      await monthButton!.trigger('click')
      await nextTick()

      // Re-query after state change
      monthButton = wrapper
        .findAll('button')
        .find(
          (btn) =>
            btn.text().includes('Recent Sessions') && btn.attributes('data-month-key')
        )
      chevron = monthButton!.find('svg')

      // After click, should be collapsed (no rotate-90 class)
      expect(chevron.classes()).not.toContain('rotate-90')
    })
  })

  describe('Jump to Date', () => {
    it('should show jump-to-date button when more than 20 sessions', async () => {
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
        expect(wrapper.text()).toContain('Jump to...')
      })

      const jumpButton = wrapper.find('button[aria-label="Jump to specific date"]')
      expect(jumpButton.exists()).toBe(true)
    })

    it('should not show jump-to-date button when 20 or fewer sessions', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockSessions.slice(0, 10),
          total: 15,
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
        expect(wrapper.find('button').exists()).toBe(true)
      })

      const jumpButton = wrapper.find('button[aria-label="Jump to specific date"]')
      expect(jumpButton.exists()).toBe(false)
    })

    it('should open date picker modal when jump button clicked', async () => {
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
        attachTo: document.body,
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('Jump to...')
      })

      const jumpButton = wrapper.find('button[aria-label="Jump to specific date"]')
      await jumpButton.trigger('click')
      await nextTick()

      // Modal should be visible (check document.body since modal is teleported)
      expect(document.body.textContent).toContain('Jump to Date')
      expect(document.body.textContent).toContain('Select Month')

      // Cleanup
      wrapper.unmount()
    })

    it('should close modal when cancel button clicked', async () => {
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
        attachTo: document.body,
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('Jump to...')
      })

      // Open modal
      const jumpButton = wrapper.find('button[aria-label="Jump to specific date"]')
      await jumpButton.trigger('click')
      await nextTick()

      // Wait for modal to appear
      await vi.waitFor(() => {
        expect(document.body.textContent).toContain('Jump to Date')
      })

      // Find and click cancel button in the modal (which is in document.body)
      const cancelButtons = document.querySelectorAll('button')
      const cancelButton = Array.from(cancelButtons).find(
        (btn) => btn.textContent?.trim() === 'Cancel'
      )
      expect(cancelButton).toBeDefined()
      cancelButton!.click()
      await nextTick()

      // Wait for modal to close
      await vi.waitFor(() => {
        expect(document.body.textContent).not.toContain('Jump to Date')
      })

      // Cleanup
      wrapper.unmount()
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

      // Should only show 9 finalized sessions in year group
      expect(wrapper.text()).toContain('2024')
      expect(wrapper.text()).toContain('(9)') // 9 finalized total
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

  describe('Backend Search', () => {
    describe('Automatic Detection', () => {
      it('should use client-side search when total sessions <= 100', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions,
            total: 50,
            page: 1,
            page_size: 10,
            total_pages: 5,
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

        // Clear any previous mocks
        vi.mocked(apiClient.get).mockClear()

        // Type in search box
        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('shoulder')
        await nextTick()

        // Wait a bit for debounce
        await new Promise((resolve) => setTimeout(resolve, 400))

        // Should NOT make backend API call (client-side search)
        expect(apiClient.get).not.toHaveBeenCalled()
      })

      it('should use backend search when total sessions > 100', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock backend search response
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: [mockSessions[0]],
            total: 1,
            page: 1,
            page_size: 50,
          },
        })

        // Type in search box
        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('shoulder')

        // Wait for debounce (300ms)
        await new Promise((resolve) => setTimeout(resolve, 400))

        // Should make backend API call with search param
        await vi.waitFor(() => {
          expect(apiClient.get).toHaveBeenCalledWith(
            '/sessions',
            expect.objectContaining({
              params: expect.objectContaining({
                client_id: mockClientId,
                search: 'shoulder',
                page: 1,
                page_size: 50,
              }),
            })
          )
        })
      })
    })

    describe('Backend Search Functionality', () => {
      it('should debounce search input (300ms)', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        vi.mocked(apiClient.get).mockClear()
        vi.mocked(apiClient.get).mockResolvedValue({
          data: {
            items: [mockSessions[0]],
            total: 1,
            page: 1,
            page_size: 50,
          },
        })

        const searchInput = wrapper.find('input[type="search"]')

        // Type "sho"
        await searchInput.setValue('sho')
        await new Promise((resolve) => setTimeout(resolve, 100))

        // Type "shoulder"
        await searchInput.setValue('shoulder')

        // Should not have called yet (debouncing)
        expect(apiClient.get).not.toHaveBeenCalled()

        // Wait for debounce to complete
        await new Promise((resolve) => setTimeout(resolve, 400))

        // Now should have called exactly once
        await vi.waitFor(() => {
          expect(apiClient.get).toHaveBeenCalledTimes(1)
        })
      })

      it('should show loading indicator during search', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock backend search with a delay
        vi.mocked(apiClient.get).mockImplementationOnce(
          () =>
            new Promise((resolve) =>
              setTimeout(
                () =>
                  resolve({
                    data: {
                      items: [mockSessions[0]],
                      total: 1,
                      page: 1,
                      page_size: 50,
                    },
                  }),
                100
              )
            )
        )

        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('shoulder')

        // Wait for debounce
        await new Promise((resolve) => setTimeout(resolve, 400))

        // Should show loading indicator
        await vi.waitFor(() => {
          expect(wrapper.text()).toContain('Searching...')
        })
      })

      it('should display search results info banner', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock backend returns 12 of 45 results
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: Array.from({ length: 12 }, (_, i) => ({
              ...mockSessions[0],
              id: `match-${i}`,
            })),
            total: 45,
            page: 1,
            page_size: 50,
          },
        })

        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('shoulder')

        // Wait for debounce and API call
        await new Promise((resolve) => setTimeout(resolve, 400))

        await vi.waitFor(() => {
          expect(wrapper.text()).toContain('Showing 12 of 45 matching sessions')
        })
      })

      it('should show "Load All Results" button when more results available', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock backend returns 50 of 120 results
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: Array.from({ length: 50 }, (_, i) => ({
              ...mockSessions[0],
              id: `match-${i}`,
            })),
            total: 120,
            page: 1,
            page_size: 50,
          },
        })

        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('pain')

        await new Promise((resolve) => setTimeout(resolve, 400))

        await vi.waitFor(() => {
          expect(wrapper.text()).toContain('Load All Results')
        })
      })

      it('should hide "Load All" button when total > 500', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock backend returns 50 of 600 results
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: Array.from({ length: 50 }, (_, i) => ({
              ...mockSessions[0],
              id: `match-${i}`,
            })),
            total: 600,
            page: 1,
            page_size: 50,
          },
        })

        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('session')

        await new Promise((resolve) => setTimeout(resolve, 400))

        await vi.waitFor(() => {
          expect(wrapper.text()).not.toContain('Load All Results')
          expect(wrapper.text()).toContain('Refine search to see more')
        })
      })

      it('should load all results when "Load All" clicked', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock initial backend search (50 of 120)
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: Array.from({ length: 50 }, (_, i) => ({
              ...mockSessions[0],
              id: `match-${i}`,
            })),
            total: 120,
            page: 1,
            page_size: 50,
          },
        })

        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('pain')

        await new Promise((resolve) => setTimeout(resolve, 400))

        await vi.waitFor(() => {
          expect(wrapper.text()).toContain('Load All Results')
        })

        // Mock "Load All" response (all 120)
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: Array.from({ length: 120 }, (_, i) => ({
              ...mockSessions[0],
              id: `match-${i}`,
            })),
            total: 120,
            page: 1,
            page_size: 120,
          },
        })

        // Click "Load All"
        const loadAllButton = wrapper
          .findAll('button')
          .find((btn) => btn.text() === 'Load All Results')
        await loadAllButton!.trigger('click')

        await nextTick()

        // Should call API with page_size=120
        await vi.waitFor(() => {
          expect(apiClient.get).toHaveBeenCalledWith(
            '/sessions',
            expect.objectContaining({
              params: expect.objectContaining({
                page_size: 120,
              }),
            })
          )
        })
      })
    })

    describe('Error Handling', () => {
      it('should show error message when backend search fails', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock API error
        vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Network error'))

        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('test')

        await new Promise((resolve) => setTimeout(resolve, 400))

        await vi.waitFor(() => {
          expect(wrapper.text()).toContain('Search failed')
        })
      })

      it('should fall back to client-side search when backend fails', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions,
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock API error
        vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Network error'))

        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('shoulder')

        await new Promise((resolve) => setTimeout(resolve, 400))

        await vi.waitFor(() => {
          // Should still show client-side filtered results
          expect(wrapper.text()).toContain('Recent Sessions')
        })
      })
    })

    describe('Search Clearing', () => {
      it('should clear search results when search input cleared', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Perform search
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: [mockSessions[0]],
            total: 1,
            page: 1,
            page_size: 50,
          },
        })

        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('shoulder')

        await new Promise((resolve) => setTimeout(resolve, 400))

        await vi.waitFor(() => {
          expect(wrapper.text()).toContain('Showing 1 of 1')
        })

        // Clear search
        await searchInput.setValue('')
        await nextTick()

        // Banner should be hidden
        expect(wrapper.text()).not.toContain('Showing')
        expect(wrapper.text()).not.toContain('matching sessions')
      })
    })

    describe('Filter Integration', () => {
      it('should apply status filter to backend search results', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 150,
            page: 1,
            page_size: 10,
            total_pages: 15,
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

        // Mock backend returns 20 sessions (10 draft, 10 finalized)
        const mixedSessions = [
          ...Array.from({ length: 10 }, (_, i) => ({
            ...mockSessions[0],
            id: `draft-${i}`,
            is_draft: true,
          })),
          ...Array.from({ length: 10 }, (_, i) => ({
            ...mockSessions[0],
            id: `finalized-${i}`,
            is_draft: false,
          })),
        ]

        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mixedSessions,
            total: 20,
            page: 1,
            page_size: 50,
          },
        })

        // Perform search
        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('test')

        await new Promise((resolve) => setTimeout(resolve, 400))

        await vi.waitFor(() => {
          expect(wrapper.text()).toContain('Showing 20 of 20')
        })

        // Click "Drafts" filter
        const draftsButton = wrapper
          .findAll('button')
          .find((btn) => btn.text().startsWith('Drafts'))
        await draftsButton!.trigger('click')

        await nextTick()

        // Should only show draft sessions in year group count
        expect(wrapper.text()).toContain('(10)')
      })
    })

    describe('Scope Warning (Client-side)', () => {
      it('should show warning when searching partial loaded sessions', async () => {
        vi.mocked(apiClient.get).mockResolvedValueOnce({
          data: {
            items: mockSessions.slice(0, 10),
            total: 50,
            page: 1,
            page_size: 10,
            total_pages: 5,
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

        // Type search query
        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('test')

        await nextTick()

        // Should show warning
        expect(wrapper.text()).toContain('Searching 10 loaded sessions')
        expect(wrapper.text()).toContain('Load all 50')
      })

      it('should hide warning when all sessions loaded', async () => {
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

        // Type search query
        const searchInput = wrapper.find('input[type="search"]')
        await searchInput.setValue('test')

        await nextTick()

        // Should NOT show warning (all sessions loaded)
        expect(wrapper.text()).not.toContain('Searching 10 loaded sessions')
      })
    })
  })
})
