/**
 * SessionCard Component Tests
 *
 * Tests for the SessionCard component including:
 * - KebabMenu component integration
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
import KebabMenu from '@/components/common/KebabMenu.vue'
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
   * Helper function to open the kebab menu
   */
  async function openKebabMenu() {
    const kebabButton = wrapper
      .findComponent(KebabMenu)
      .find('button[aria-haspopup="true"]')
    await kebabButton.trigger('click')
    await nextTick()
  }

  /**
   * Helper function to get menu items
   */
  function getMenuItems() {
    return wrapper.findComponent(KebabMenu).findAll('[role="menuitem"]')
  }

  describe('Rendering and Initial State', () => {
    it('renders session card in normal state', () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      expect(wrapper.find('.group').exists()).toBe(true)
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    })

    it('renders KebabMenu component with correct props', () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      const kebabMenu = wrapper.findComponent(KebabMenu)
      expect(kebabMenu.exists()).toBe(true)
      expect(kebabMenu.props('ariaLabel')).toContain('More actions')
      expect(kebabMenu.props('position')).toBe('bottom-right')
      expect(kebabMenu.props('alwaysVisibleOnMobile')).toBe(true)
    })

    it('renders slot content', () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
        slots: {
          content: '<div class="test-content">Test Content</div>',
        },
      })

      expect(wrapper.find('.test-content').exists()).toBe(true)
      expect(wrapper.text()).toContain('Test Content')
    })
  })

  describe('Kebab Menu Interactions', () => {
    it('opens menu when kebab button clicked', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()

      expect(wrapper.findComponent(KebabMenu).find('[role="menu"]').exists()).toBe(true)
    })

    it('shows View Full Note and Delete Note menu items', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()

      const menuItems = getMenuItems()
      expect(menuItems).toHaveLength(2)
      expect(menuItems[0].text()).toContain('View Full Note')
      expect(menuItems[1].text()).toContain('Delete Note')
    })

    it('emits view event when View Full Note clicked', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[0].trigger('click')

      expect(wrapper.emitted('view')).toBeTruthy()
      expect(wrapper.emitted('view')![0]).toEqual([mockSession.id])
    })

    it('closes menu and opens confirmation when Delete Note clicked', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      // Menu should close (handled by KebabMenu component)
      // Confirmation dialog should open
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    })
  })

  describe('Delete Confirmation State', () => {
    it('shows confirmation dialog with correct title for draft note', async () => {
      const draftSession = { ...mockSession, is_draft: true, finalized_at: null }
      wrapper = mount(SessionCard, {
        props: { session: draftSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      expect(wrapper.text()).toContain('Delete this session note?')
      expect(wrapper.text()).not.toContain('medical record')
    })

    it('shows extra warning for finalized notes', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession }, // finalized_at is set
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      expect(wrapper.text()).toContain('Delete this finalized session note?')
      expect(wrapper.text()).toContain('⚠️ This is a medical record')
    })

    it('shows 30-day grace period message', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      expect(wrapper.text()).toContain('30 days')
      expect(wrapper.text()).toContain('restore')
    })

    it('shows Cancel and Delete Note buttons', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const cancelButton = buttons.find((b) => b.text() === 'Cancel')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')

      expect(cancelButton).toBeTruthy()
      expect(deleteButton).toBeTruthy()
    })

    it('reverts to normal state when Cancel clicked', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const cancelButton = buttons.find((b) => b.text() === 'Cancel')
      await cancelButton?.trigger('click')

      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
      expect(wrapper.find('.group').exists()).toBe(true)
    })
  })

  describe('Deletion Flow', () => {
    it('calls DELETE API when Delete Note confirmed', async () => {
      const deleteSpy = vi.spyOn(apiClient, 'delete').mockResolvedValue({})

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')

      expect(deleteSpy).toHaveBeenCalledWith(`/api/v1/sessions/${mockSession.id}`)
    })

    it('emits deleted event on successful deletion', async () => {
      vi.spyOn(apiClient, 'delete').mockResolvedValue({})

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')
      await nextTick()

      expect(wrapper.emitted('deleted')).toBeTruthy()
      expect(wrapper.emitted('deleted')![0]).toEqual([mockSession.id])
    })

    it('shows success toast on successful deletion', async () => {
      vi.spyOn(apiClient, 'delete').mockResolvedValue({})

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')
      await nextTick()

      expect(mockToast.showSuccess).toHaveBeenCalledWith(
        'Session note deleted. Undo available for 30 days.'
      )
    })

    it('shows loading state while deleting', async () => {
      vi.spyOn(apiClient, 'delete').mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')

      expect(wrapper.text()).toContain('Deleting...')
      expect(deleteButton?.attributes('disabled')).toBeDefined()
    })

    it('disables buttons while deleting', async () => {
      vi.spyOn(apiClient, 'delete').mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')

      const confirmationButtons = wrapper.findAll('button')
      confirmationButtons.forEach((button) => {
        expect(button.attributes('disabled')).toBeDefined()
      })
    })
  })

  describe('Error Handling', () => {
    it('handles 404 error (note not found)', async () => {
      vi.spyOn(apiClient, 'delete').mockRejectedValue({
        response: { status: 404 },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith('Session note no longer exists')
      expect(wrapper.emitted('deleted')).toBeTruthy()
    })

    it('handles 403 error (permission denied)', async () => {
      vi.spyOn(apiClient, 'delete').mockRejectedValue({
        response: { status: 403 },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        "You don't have permission to delete this note"
      )
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    })

    it('handles 410 error (already deleted)', async () => {
      vi.spyOn(apiClient, 'delete').mockRejectedValue({
        response: { status: 410 },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        'This note has already been deleted'
      )
      expect(wrapper.emitted('deleted')).toBeTruthy()
    })

    it('handles 422 error (amended note)', async () => {
      vi.spyOn(apiClient, 'delete').mockRejectedValue({
        response: { status: 422 },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        'Cannot delete amended notes due to medical-legal requirements'
      )
    })

    it('handles generic server error', async () => {
      vi.spyOn(apiClient, 'delete').mockRejectedValue({
        response: { status: 500, data: { detail: 'Internal server error' } },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith('Internal server error')
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    })

    it('shows fallback error message when detail not provided', async () => {
      vi.spyOn(apiClient, 'delete').mockRejectedValue({
        response: { status: 500 },
      })

      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      const buttons = wrapper.findAll('button')
      const deleteButton = buttons.find((b) => b.text() === 'Delete Note')
      await deleteButton?.trigger('click')
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        'Failed to delete note - please try again'
      )
    })
  })

  describe('Keyboard Accessibility', () => {
    it('handles Escape key in confirmation dialog', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      // Confirmation should be visible
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)

      // Press Escape
      await wrapper.find('[role="alertdialog"]').trigger('keydown', { key: 'Escape' })

      // Should revert to normal state
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    })

    it('does not close on other keys', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      await wrapper.find('[role="alertdialog"]').trigger('keydown', { key: 'Enter' })

      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    })
  })

  describe('ARIA Attributes', () => {
    it('has proper ARIA attributes on confirmation dialog', async () => {
      wrapper = mount(SessionCard, {
        props: { session: mockSession },
      })

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

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

      await openKebabMenu()
      await getMenuItems()[1].trigger('click')
      await nextTick()

      expect(wrapper.find('#delete-confirmation-title').exists()).toBe(true)
      expect(wrapper.find('#delete-confirmation-description').exists()).toBe(true)
    })
  })
})
