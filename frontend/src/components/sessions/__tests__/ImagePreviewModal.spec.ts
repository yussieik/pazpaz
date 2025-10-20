/**
 * ImagePreviewModal Component Tests
 *
 * Tests for the ImagePreviewModal component including:
 * - Modal open/close functionality
 * - Image navigation (previous/next)
 * - Keyboard shortcuts (Escape, Arrow keys)
 * - Download functionality
 * - Focus trap
 * - ARIA attributes and screen reader support
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import ImagePreviewModal from '../ImagePreviewModal.vue'

// Mock @vueuse/core
vi.mock('@vueuse/core', () => ({
  onKeyStroke: vi.fn(),
}))

// Mock focus trap composable
vi.mock('@/composables/useFocusTrap', () => ({
  useFocusTrap: () => ({
    activate: vi.fn(),
    deactivate: vi.fn(),
  }),
}))

describe('ImagePreviewModal', () => {
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
      file_name: 'image2.png',
      file_type: 'image/png',
      file_size_bytes: 512000,
      created_at: '2024-03-14T10:00:00Z',
    },
    {
      id: 'att-3',
      file_name: 'document.pdf',
      file_type: 'application/pdf',
      file_size_bytes: 256000,
      created_at: '2024-03-13T12:00:00Z',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Modal Visibility', () => {
    it('does not render when open is false', () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: false,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    })

    it('renders when open is true', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    })

    it('filters to only show images', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      // Should show 2 images (excluding PDF)
      expect(wrapper.text()).toContain('1 / 2')
    })
  })

  describe('Image Display', () => {
    it('displays current image info', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      expect(wrapper.text()).toContain('image1.jpg')
      expect(wrapper.text()).toMatch(/MB|KB/) // File size
    })

    it('shows correct image counter', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      expect(wrapper.text()).toContain('1 / 2')
    })

    it('displays image with correct src', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const img = wrapper.find('img')
      expect(img.attributes('src')).toContain(
        '/sessions/session-123/attachments/att-1/download'
      )
    })

    it('has proper alt text on image', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const img = wrapper.find('img')
      expect(img.attributes('alt')).toBe('image1.jpg')
    })
  })

  describe('Navigation', () => {
    it('shows previous button when not at first image', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 1,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const prevButton = wrapper.find('button[aria-label="Previous image"]')
      expect(prevButton.exists()).toBe(true)
    })

    it('hides previous button at first image', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const prevButton = wrapper.find('button[aria-label="Previous image"]')
      expect(prevButton.exists()).toBe(false)
    })

    it('shows next button when not at last image', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const nextButton = wrapper.find('button[aria-label="Next image"]')
      expect(nextButton.exists()).toBe(true)
    })

    it('hides next button at last image', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 1, // Last image (index 1 of 2 images)
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const nextButton = wrapper.find('button[aria-label="Next image"]')
      expect(nextButton.exists()).toBe(false)
    })

    it('emits update:current-index on previous click', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 1,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const prevButton = wrapper.find('button[aria-label="Previous image"]')
      await prevButton.trigger('click')

      expect(wrapper.emitted('update:current-index')).toBeTruthy()
      expect(wrapper.emitted('update:current-index')![0]).toEqual([0])
    })

    it('emits update:current-index on next click', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const nextButton = wrapper.find('button[aria-label="Next image"]')
      await nextButton.trigger('click')

      expect(wrapper.emitted('update:current-index')).toBeTruthy()
      expect(wrapper.emitted('update:current-index')![0]).toEqual([1])
    })
  })

  describe('Close Functionality', () => {
    it('emits close event on close button click', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const closeButton = wrapper.find('button[aria-label="Close image preview"]')
      await closeButton.trigger('click')

      expect(wrapper.emitted('close')).toBeTruthy()
    })

    it('emits close event on backdrop click', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const backdrop = wrapper.find('[role="dialog"]')
      // Trigger click.self event
      await backdrop.trigger('click')

      expect(wrapper.emitted('close')).toBeTruthy()
    })
  })

  describe('Download Functionality', () => {
    it('emits download event with current attachment', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const downloadButton = wrapper.find('button[aria-label="Download image"]')
      await downloadButton.trigger('click')

      expect(wrapper.emitted('download')).toBeTruthy()
      expect(wrapper.emitted('download')![0][0]).toMatchObject({
        id: 'att-1',
        file_name: 'image1.jpg',
      })
    })
  })

  describe('Accessibility', () => {
    it('has proper dialog ARIA attributes', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const dialog = wrapper.find('[role="dialog"]')
      expect(dialog.attributes('aria-modal')).toBe('true')
      expect(dialog.attributes('aria-labelledby')).toBe('image-preview-title')
    })

    it('has keyboard shortcuts hint visible', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      expect(wrapper.text()).toContain('Navigate')
      expect(wrapper.text()).toContain('Close')
    })

    it('has screen reader announcement', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const srAnnouncement = wrapper.find('[role="status"]')
      expect(srAnnouncement.exists()).toBe(true)
      expect(srAnnouncement.attributes('aria-live')).toBe('polite')
      expect(srAnnouncement.text()).toContain('Viewing image 1 of 2')
    })

    it('updates screen reader announcement on navigation', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      // Navigate to next image
      await wrapper.setProps({ currentIndex: 1 })
      await nextTick()

      const srAnnouncement = wrapper.find('[role="status"]')
      expect(srAnnouncement.text()).toContain('Viewing image 2 of 2')
      expect(srAnnouncement.text()).toContain('image2.png')
    })

    it('has proper button labels with keyboard hints', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      const closeButton = wrapper.find('button[aria-label="Close image preview"]')
      expect(closeButton.attributes('title')).toContain('Esc')

      const nextButton = wrapper.find('button[aria-label="Next image"]')
      expect(nextButton.attributes('title')).toContain('→')
    })
  })

  describe('Body Scroll Lock', () => {
    it('prevents body scroll when modal opens', async () => {
      const originalOverflow = document.body.style.overflow

      wrapper = mount(ImagePreviewModal, {
        props: {
          open: false,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await wrapper.setProps({ open: true })
      await nextTick()

      expect(document.body.style.overflow).toBe('hidden')

      // Cleanup
      document.body.style.overflow = originalOverflow
    })

    it('restores body scroll when modal closes', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      await wrapper.setProps({ open: false })
      await nextTick()

      expect(document.body.style.overflow).toBe('')
    })

    it('restores body scroll on unmount', () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      wrapper.unmount()

      expect(document.body.style.overflow).toBe('')
    })
  })

  describe('Reduced Motion', () => {
    it('has reduced motion styles', async () => {
      wrapper = mount(ImagePreviewModal, {
        props: {
          open: true,
          attachments: mockAttachments,
          currentIndex: 0,
          sessionId: 'session-123',
        },
      })

      await nextTick()

      // Check that component has reduced motion CSS
      const html = wrapper.html()
      expect(html).toContain('prefers-reduced-motion')
    })
  })
})
