/**
 * SessionCard Component Tests
 *
 * Tests for the SessionCard component including:
 * - Trash icon deletion UI
 * - Delete confirmation flow (normal and finalized notes)
 * - Deletion API calls and error handling
 * - Keyboard accessibility (Escape in confirmation dialog)
 * - ARIA attributes and screen reader support
 * - Animation states and transitions
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import SessionCard from '../SessionCard.vue'
import apiClient from '@/api/client'
import { useToast } from '@/composables/useToast'

// Mock dependencies
vi.mock('@/api/client')
vi.mock('@/composables/useToast')

describe('SessionCard', () => {
  let wrapper: VueWrapper

  const mockSession = {
    id: 'session-123',
    client_id: 'client-456',
    appointment_id: null,
    subjective: 'Client reported lower back pain',
    objective: 'Muscle tension in lumbar region',
    assessment: 'Acute lower back strain',
    plan: 'Massage therapy, stretching exercises',
    session_date: '2024-03-15T14:00:00Z',
    duration_minutes: 60,
    is_draft: false,
    draft_last_saved_at: null,
    finalized_at: '2024-03-15T15:00:00Z',
  }

  const mockDraftSession = {
    ...mockSession,
    is_draft: true,
    finalized_at: null,
  }

  const mockToast = {
    showSuccess: vi.fn(),
    showError: vi.fn(),
    showInfo: vi.fn(),
    showWarning: vi.fn(),
    showAppointmentSuccess: vi.fn(),
    showSuccessWithUndo: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useToast).mockReturnValue(mockToast)
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  /**
   * Helper function to click the delete trash icon
   */
  async function clickDeleteButton() {
    const deleteButton = wrapper.find('button[aria-label="Delete session note"]')
    await deleteButton.trigger('click')
    await nextTick()
  }

  /**
   * Helper function to click the cancel button in confirmation dialog
   */
  async function clickCancelButton() {
    const cancelButton = wrapper
      .findAll('button')
      .find((btn) => btn.text() === 'Cancel')
    if (cancelButton) {
      await cancelButton.trigger('click')
      await nextTick()
    }
  }

  /**
   * Helper function to click the delete confirm button
   */
  async function clickConfirmButton() {
    const deleteButton = wrapper
      .findAll('button')
      .find((btn) => btn.text() === 'Delete Note' || btn.text() === 'Deleting...')
    if (deleteButton) {
      await deleteButton.trigger('click')
      await nextTick()
    }
  }

  describe('Rendering and Initial State', () => {
    it('renders session card in normal state', () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      expect(wrapper.find('.group').exists()).toBe(true)
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    })

    it('renders trash icon delete button', () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      const deleteButton = wrapper.find('button[aria-label="Delete session note"]')
      expect(deleteButton.exists()).toBe(true)
      expect(deleteButton.find('svg').exists()).toBe(true) // Trash icon
    })

    it('renders slot content', () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
        slots: {
          content: '<div class="test-content">Test Content</div>',
        },
      })

      expect(wrapper.find('.test-content').exists()).toBe(true)
      expect(wrapper.find('.test-content').text()).toBe('Test Content')
    })
  })

  describe('Trash Icon Delete Interactions', () => {
    it('shows confirmation dialog when delete button clicked', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
      await clickDeleteButton()
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    })

    it('emits view event when card clicked', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      const cardButton = wrapper.find('.group')
      await cardButton.trigger('click')

      expect(wrapper.emitted('view')).toBeTruthy()
      expect(wrapper.emitted('view')?.[0]).toEqual([mockSession.id])
    })

    it('does not emit view when delete button clicked', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()

      expect(wrapper.emitted('view')).toBeFalsy()
    })
  })

  describe('Delete Confirmation State', () => {
    it('shows confirmation dialog with correct title for finalized note', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()

      const title = wrapper.find('#delete-confirmation-title')
      expect(title.text()).toContain('finalized')
      expect(title.text()).toContain('session note')
    })

    it('shows confirmation dialog with correct title for draft note', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockDraftSession },
      })

      await clickDeleteButton()

      const title = wrapper.find('#delete-confirmation-title')
      expect(title.text()).not.toContain('finalized')
      expect(title.text()).toContain('session note')
    })

    it('shows extra warning for finalized notes', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()

      const description = wrapper.find('#delete-confirmation-description')
      expect(description.text()).toContain('medical record')
      expect(description.text()).toContain('⚠️')
    })

    it('shows 30-day grace period message', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()

      const description = wrapper.find('#delete-confirmation-description')
      expect(description.text()).toContain('30 days')
      expect(description.text()).toContain('restore')
    })

    it('shows Cancel and Delete Note buttons', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()

      const buttons = wrapper.findAll('button')
      const buttonTexts = buttons.map((btn) => btn.text())
      expect(buttonTexts).toContain('Cancel')
      expect(buttonTexts).toContain('Delete Note')
    })

    it('reverts to normal state when Cancel clicked', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)

      await clickCancelButton()
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
      expect(wrapper.find('.group').exists()).toBe(true)
    })
  })

  describe('Deletion Flow', () => {
    it('calls DELETE API when Delete Note confirmed', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({})

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()

      expect(apiClient.delete).toHaveBeenCalledWith(`/sessions/${mockSession.id}`)
    })

    it('emits deleted event on successful deletion', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({})

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      expect(wrapper.emitted('deleted')).toBeTruthy()
      expect(wrapper.emitted('deleted')?.[0]).toEqual([mockSession.id])
    })

    it('shows success toast on successful deletion', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({})

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      expect(mockToast.showSuccess).toHaveBeenCalledWith(
        expect.stringContaining('deleted')
      )
      expect(mockToast.showSuccess).toHaveBeenCalledWith(
        expect.stringContaining('30 days')
      )
    })

    it('shows loading state while deleting', async () => {
      let resolveDelete: () => void
      const deletePromise = new Promise<void>((resolve) => {
        resolveDelete = resolve
      })
      vi.mocked(apiClient.delete).mockReturnValue(deletePromise as any)

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      const deleteButton = wrapper
        .findAll('button')
        .find((btn) => btn.text() === 'Deleting...')
      expect(deleteButton).toBeTruthy()

      // Resolve
      resolveDelete!()
      await nextTick()
    })

    it('disables buttons while deleting', async () => {
      let resolveDelete: () => void
      const deletePromise = new Promise<void>((resolve) => {
        resolveDelete = resolve
      })
      vi.mocked(apiClient.delete).mockReturnValue(deletePromise as any)

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      const buttons = wrapper.findAll('button')
      buttons.forEach((btn) => {
        expect(btn.attributes('disabled')).toBeDefined()
      })

      // Resolve
      resolveDelete!()
      await nextTick()
    })
  })

  describe('Error Handling', () => {
    it('handles 404 error (note not found)', async () => {
      vi.mocked(apiClient.delete).mockRejectedValue({
        response: { status: 404, data: { detail: 'Not found' } },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        expect.stringContaining('no longer exists')
      )
      expect(wrapper.emitted('deleted')).toBeTruthy() // Should still remove from UI
    })

    it('handles 403 error (permission denied)', async () => {
      vi.mocked(apiClient.delete).mockRejectedValue({
        response: { status: 403, data: { detail: 'Forbidden' } },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        expect.stringContaining('permission')
      )
    })

    it('handles 410 error (already deleted)', async () => {
      vi.mocked(apiClient.delete).mockRejectedValue({
        response: { status: 410, data: { detail: 'Gone' } },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        expect.stringContaining('already been deleted')
      )
      expect(wrapper.emitted('deleted')).toBeTruthy()
    })

    it('handles 422 error (amended note)', async () => {
      vi.mocked(apiClient.delete).mockRejectedValue({
        response: {
          status: 422,
          data: { detail: 'Note has been amended' },
        },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        expect.stringContaining('amended')
      )
    })

    it('handles generic server error', async () => {
      vi.mocked(apiClient.delete).mockRejectedValue({
        response: { status: 500, data: { detail: 'Internal server error' } },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      // When server provides detail, it shows that exact message
      expect(mockToast.showError).toHaveBeenCalledWith('Internal server error')
    })

    it('shows fallback error message when detail not provided', async () => {
      vi.mocked(apiClient.delete).mockRejectedValue({
        response: { status: 500, data: {} },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      await clickConfirmButton()
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalled()
    })
  })

  describe('Keyboard Accessibility', () => {
    it('handles Escape key in confirmation dialog', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)

      const dialog = wrapper.find('[role="alertdialog"]')
      await dialog.trigger('keydown', { key: 'Escape' })
      await nextTick()

      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    })

    it('does not close on other keys', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)

      const dialog = wrapper.find('[role="alertdialog"]')
      await dialog.trigger('keydown', { key: 'Enter' })
      await nextTick()

      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    })
  })

  describe('ARIA Attributes', () => {
    it('has proper ARIA attributes on confirmation dialog', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()

      const dialog = wrapper.find('[role="alertdialog"]')
      expect(dialog.attributes('aria-labelledby')).toBe('delete-confirmation-title')
      expect(dialog.attributes('aria-describedby')).toBe(
        'delete-confirmation-description'
      )
    })

    it('has proper labels for title and description', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await clickDeleteButton()

      const title = wrapper.find('#delete-confirmation-title')
      const description = wrapper.find('#delete-confirmation-description')

      expect(title.exists()).toBe(true)
      expect(description.exists()).toBe(true)
    })
  })
})
