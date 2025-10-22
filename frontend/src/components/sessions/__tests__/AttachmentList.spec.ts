/**
 * AttachmentList Component Tests
 *
 * Tests for the AttachmentList component including:
 * - Loading state with skeleton
 * - Empty state
 * - Attachment list rendering
 * - Download functionality
 * - Delete confirmation flow
 * - Error handling
 * - Toast notifications
 * - ARIA attributes
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import AttachmentList from '../AttachmentList.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useFileUpload } from '@/composables/useFileUpload'
import { useToast } from '@/composables/useToast'

// Mock dependencies
vi.mock('@/composables/useFileUpload')
vi.mock('@/composables/useToast')

describe('AttachmentList', () => {
  let wrapper: VueWrapper

  const mockAttachments = [
    {
      id: 'att-1',
      file_name: 'image1.jpg',
      file_type: 'image/jpeg',
      file_size_bytes: 1024000,
      created_at: '2024-03-15T14:00:00Z',
    },
    {
      id: 'att-2',
      file_name: 'document.pdf',
      file_type: 'application/pdf',
      file_size_bytes: 512000,
      created_at: '2024-03-14T10:00:00Z',
    },
  ]

  const mockToast = {
    showSuccess: vi.fn(),
    showError: vi.fn(),
    showInfo: vi.fn(),
    showWarning: vi.fn(),
    showAppointmentSuccess: vi.fn(),
    showSuccessWithUndo: vi.fn(),
  }

  const mockFileUpload = {
    uploadFile: vi.fn(),
    uploadFiles: vi.fn(),
    listAttachments: vi.fn(),
    getDownloadUrl: vi.fn(),
    downloadAttachment: vi.fn(),
    deleteAttachment: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useToast).mockReturnValue(mockToast)
    vi.mocked(useFileUpload).mockReturnValue(mockFileUpload)
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    // Clean up teleported content
    document.body.innerHTML = ''
  })

  describe('Loading State', () => {
    it('shows skeleton loader while loading', () => {
      mockFileUpload.listAttachments.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      expect(wrapper.findComponent(SkeletonLoader).exists()).toBe(true)
      expect(wrapper.attributes('aria-busy')).toBe('true')
    })

    it('hides skeleton after loading', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.findComponent(SkeletonLoader).exists()).toBe(false)
    })
  })

  describe('Empty State', () => {
    it('shows empty state when no attachments', async () => {
      // Ensure mock is fresh and returns the right value
      mockFileUpload.listAttachments = vi.fn().mockResolvedValue({ items: [] })
      vi.mocked(useFileUpload).mockReturnValue(mockFileUpload)

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
        global: {
          stubs: {
            EmptyState: false,
            SkeletonLoader: false,
          },
        },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(mockFileUpload.listAttachments).toHaveBeenCalledWith('session-123')
      expect(wrapper.findComponent(EmptyState).exists()).toBe(true)
      expect(wrapper.text()).toContain('No attachments yet')
    })
  })

  describe('Attachment List Rendering', () => {
    it('renders all attachments', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.text()).toContain('image1.jpg')
      expect(wrapper.text()).toContain('document.pdf')
    })

    it('shows file size for each attachment', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should show formatted file sizes
      expect(wrapper.text()).toMatch(/MB|KB/)
    })

    it('shows file type badges', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.text()).toContain('jpg')
      expect(wrapper.text()).toContain('pdf')
    })
  })

  describe('Download Functionality', () => {
    it('shows download toast when download starts', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })
      mockFileUpload.downloadAttachment.mockResolvedValue(undefined)

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const downloadButtons = wrapper.findAll('button[aria-label^="Download"]')
      await downloadButtons[0].trigger('click')

      expect(mockToast.showInfo).toHaveBeenCalledWith(
        expect.stringContaining('Downloading'),
        expect.anything()
      )
    })

    it('calls downloadAttachment with correct params', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })
      mockFileUpload.downloadAttachment.mockResolvedValue(undefined)

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const downloadButtons = wrapper.findAll('button[aria-label^="Download"]')
      await downloadButtons[0].trigger('click')
      await nextTick()

      expect(mockFileUpload.downloadAttachment).toHaveBeenCalledWith(
        'session-123',
        'att-1',
        'image1.jpg'
      )
    })

    it('shows error toast on download failure', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })
      mockFileUpload.downloadAttachment.mockRejectedValue(
        new Error('Failed to download file')
      )

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const downloadButtons = wrapper.findAll('button[aria-label^="Download"]')
      await downloadButtons[0].trigger('click')
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        expect.stringContaining('Failed to download')
      )
    })
  })

  describe('Delete Functionality', () => {
    it('opens confirmation dialog on delete click', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        attachTo: document.body,
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const deleteButtons = wrapper.findAll('button[aria-label^="Delete"]')
      await deleteButtons[0].trigger('click')
      await nextTick()

      // Dialog is teleported to body
      const dialog = document.querySelector('[role="dialog"]')
      expect(dialog).toBeTruthy()
      expect(dialog?.textContent).toContain('Delete Attachment')
    })

    it('closes dialog on cancel', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        attachTo: document.body,
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const deleteButtons = wrapper.findAll('button[aria-label^="Delete"]')
      await deleteButtons[0].trigger('click')
      await nextTick()

      // Find cancel button in teleported dialog
      const buttons = document.querySelectorAll('[role="dialog"] button')
      const cancelButton = Array.from(buttons).find(
        (b) => b.textContent?.trim() === 'Cancel'
      ) as HTMLElement
      expect(cancelButton).toBeTruthy()

      // Trigger click event
      await cancelButton.dispatchEvent(new Event('click', { bubbles: true }))
      await nextTick()

      expect(document.querySelector('[role="dialog"]')).toBeFalsy()
    })

    it('calls deleteAttachment on confirm', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })
      mockFileUpload.deleteAttachment.mockResolvedValue(undefined)

      wrapper = mount(AttachmentList, {
        attachTo: document.body,
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const deleteButtons = wrapper.findAll('button[aria-label^="Delete"]')
      await deleteButtons[0].trigger('click')
      await nextTick()

      // Find delete button in teleported dialog
      const buttons = document.querySelectorAll('[role="dialog"] button')
      const confirmButton = Array.from(buttons).find(
        (b) => b.textContent?.trim() === 'Delete'
      ) as HTMLElement
      expect(confirmButton).toBeTruthy()

      // Trigger click event
      await confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
      await nextTick()

      expect(mockFileUpload.deleteAttachment).toHaveBeenCalledWith(
        'session-123',
        'att-1'
      )
    })

    it('shows success toast after deletion', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })
      mockFileUpload.deleteAttachment.mockResolvedValue(undefined)

      wrapper = mount(AttachmentList, {
        attachTo: document.body,
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const deleteButtons = wrapper.findAll('button[aria-label^="Delete"]')
      await deleteButtons[0].trigger('click')
      await nextTick()

      // Find delete button in teleported dialog
      const buttons = document.querySelectorAll('[role="dialog"] button')
      const confirmButton = Array.from(buttons).find(
        (b) => b.textContent?.trim() === 'Delete'
      ) as HTMLElement
      expect(confirmButton).toBeTruthy()

      // Trigger click event
      await confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
      await nextTick()

      expect(mockToast.showSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Deleted')
      )
    })

    it('removes attachment from list after deletion', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: [...mockAttachments] })
      mockFileUpload.deleteAttachment.mockResolvedValue(undefined)

      wrapper = mount(AttachmentList, {
        attachTo: document.body,
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.text()).toContain('image1.jpg')

      const deleteButtons = wrapper.findAll('button[aria-label^="Delete"]')
      await deleteButtons[0].trigger('click')
      await nextTick()

      // Find delete button in teleported dialog
      const buttons = document.querySelectorAll('[role="dialog"] button')
      const confirmButton = Array.from(buttons).find(
        (b) => b.textContent?.trim() === 'Delete'
      ) as HTMLElement
      expect(confirmButton).toBeTruthy()

      // Trigger click event
      await confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
      await nextTick()

      expect(wrapper.text()).not.toContain('image1.jpg')
    })
  })

  describe('Error Handling', () => {
    it('shows error state on load failure', async () => {
      mockFileUpload.listAttachments.mockRejectedValue(
        new Error('Failed to load attachments')
      )

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.text()).toContain('Failed to load attachments')
      expect(wrapper.find('button').text()).toContain('Try again')
    })

    it('retries loading on button click', async () => {
      mockFileUpload.listAttachments.mockRejectedValueOnce(
        new Error('Failed to load attachments')
      )
      mockFileUpload.listAttachments.mockResolvedValueOnce({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const retryButton = wrapper.find('button')
      await retryButton.trigger('click')
      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.text()).toContain('image1.jpg')
    })
  })

  describe('Accessibility', () => {
    it('has proper ARIA labels on action buttons', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const downloadButton = wrapper.find('button[aria-label^="Download"]')
      const deleteButton = wrapper.find('button[aria-label^="Delete"]')

      expect(downloadButton.exists()).toBe(true)
      expect(deleteButton.exists()).toBe(true)
    })

    it('has proper dialog ARIA attributes', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        attachTo: document.body,
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const deleteButtons = wrapper.findAll('button[aria-label^="Delete"]')
      await deleteButtons[0].trigger('click')
      await nextTick()

      // Dialog is teleported to body
      const dialog = document.querySelector('[role="dialog"]')
      expect(dialog?.getAttribute('aria-modal')).toBe('true')
      expect(dialog?.getAttribute('aria-labelledby')).toBeTruthy()
    })
  })

  describe('Exposed Methods', () => {
    it('exposes refresh method', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.vm.refresh).toBeDefined()
      expect(typeof wrapper.vm.refresh).toBe('function')
    })

    it('exposes attachments reactive state', async () => {
      mockFileUpload.listAttachments.mockResolvedValue({ items: mockAttachments })

      wrapper = mount(AttachmentList, {
        props: { sessionId: 'session-123' },
      })

      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.vm.attachments).toBeDefined()
      expect(wrapper.vm.attachments.length).toBe(2)
    })
  })
})
