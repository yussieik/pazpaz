/**
 * FileUpload Component Tests
 *
 * Tests for the FileUpload component including:
 * - Drag-and-drop functionality
 * - File validation (type and size)
 * - Upload progress tracking
 * - Success and error handling
 * - Toast notifications
 * - Keyboard accessibility
 * - ARIA attributes
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import FileUpload from '../FileUpload.vue'
import { useFileUpload } from '@/composables/useFileUpload'
import { useToast } from '@/composables/useToast'

// Mock dependencies
vi.mock('@/composables/useFileUpload')
vi.mock('@/composables/useToast')

describe('FileUpload', () => {
  let wrapper: VueWrapper

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
  })

  describe('Rendering and Initial State', () => {
    it('renders drop zone with instructions', () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      expect(wrapper.text()).toContain('Drop files here or click to browse')
      expect(wrapper.text()).toContain('JPEG, PNG, WebP, or PDF up to 10 MB each')
    })

    it('has correct ARIA attributes', () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const dropZone = wrapper.find('[role="button"]')
      expect(dropZone.attributes('tabindex')).toBe('0')
      expect(dropZone.attributes('aria-label')).toContain('Click or drag to upload files')
    })
  })

  describe('File Selection', () => {
    it('opens file picker on click', async () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const dropZone = wrapper.find('[role="button"]')
      const fileInput = wrapper.find('input[type="file"]')

      const clickSpy = vi.spyOn(fileInput.element as HTMLInputElement, 'click')
      await dropZone.trigger('click')

      expect(clickSpy).toHaveBeenCalled()
    })

    it('opens file picker on Enter key', async () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const dropZone = wrapper.find('[role="button"]')
      const fileInput = wrapper.find('input[type="file"]')

      const clickSpy = vi.spyOn(fileInput.element as HTMLInputElement, 'click')
      await dropZone.trigger('keydown.enter')

      expect(clickSpy).toHaveBeenCalled()
    })

    it('opens file picker on Space key', async () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const dropZone = wrapper.find('[role="button"]')
      const fileInput = wrapper.find('input[type="file"]')

      const clickSpy = vi.spyOn(fileInput.element as HTMLInputElement, 'click')
      await dropZone.trigger('keydown.space')

      expect(clickSpy).toHaveBeenCalled()
    })
  })

  describe('Drag and Drop', () => {
    it('shows drag state on dragenter', async () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const dropZone = wrapper.find('[role="button"]')
      await dropZone.trigger('dragenter')

      expect(wrapper.text()).toContain('Drop files here')
      expect(dropZone.classes()).toContain('border-blue-500')
    })

    it('removes drag state on dragleave', async () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const dropZone = wrapper.find('[role="button"]')
      await dropZone.trigger('dragenter')
      await dropZone.trigger('dragleave')

      expect(wrapper.text()).toContain('Drop files here or click to browse')
      expect(dropZone.classes()).not.toContain('border-blue-500')
    })
  })

  describe('File Validation', () => {
    it('shows error for unsupported file type', async () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const invalidFile = new File(['content'], 'test.txt', { type: 'text/plain' })
      const dropZone = wrapper.find('[role="button"]')

      await dropZone.trigger('drop', {
        dataTransfer: { files: [invalidFile] },
      })
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        expect.stringContaining('Unsupported file type')
      )
    })

    it('shows error for file too large', async () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      // Create a file larger than 10 MB
      const largeFile = new File([new ArrayBuffer(11 * 1024 * 1024)], 'large.jpg', {
        type: 'image/jpeg',
      })
      const dropZone = wrapper.find('[role="button"]')

      await dropZone.trigger('drop', {
        dataTransfer: { files: [largeFile] },
      })
      await nextTick()

      expect(mockToast.showError).toHaveBeenCalledWith(
        expect.stringContaining('File too large')
      )
    })
  })

  describe('Upload Progress', () => {
    it('shows upload progress for valid files', async () => {
      mockFileUpload.uploadFiles.mockResolvedValue([
        { id: 'att-1', file_name: 'test.jpg' },
      ])

      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const validFile = new File(['content'], 'test.jpg', { type: 'image/jpeg' })
      const dropZone = wrapper.find('[role="button"]')

      await dropZone.trigger('drop', {
        dataTransfer: { files: [validFile] },
      })
      await nextTick()

      // Check aria-busy is set
      expect(dropZone.attributes('aria-busy')).toBe('true')
    })

    it('emits upload-complete on successful upload', async () => {
      mockFileUpload.uploadFiles.mockResolvedValue([
        { id: 'att-1', file_name: 'test.jpg' },
      ])

      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const validFile = new File(['content'], 'test.jpg', { type: 'image/jpeg' })
      const dropZone = wrapper.find('[role="button"]')

      await dropZone.trigger('drop', {
        dataTransfer: { files: [validFile] },
      })
      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(wrapper.emitted('upload-complete')).toBeTruthy()
    })

    it('shows success toast on upload completion', async () => {
      mockFileUpload.uploadFiles.mockResolvedValue([
        { id: 'att-1', file_name: 'test.jpg' },
      ])

      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const validFile = new File(['content'], 'test.jpg', { type: 'image/jpeg' })
      const dropZone = wrapper.find('[role="button"]')

      await dropZone.trigger('drop', {
        dataTransfer: { files: [validFile] },
      })
      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(mockToast.showSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Uploaded')
      )
    })
  })

  describe('Multiple File Upload', () => {
    it('handles multiple files', async () => {
      mockFileUpload.uploadFiles.mockResolvedValue([
        { id: 'att-1', file_name: 'test1.jpg' },
        { id: 'att-2', file_name: 'test2.png' },
      ])

      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const file1 = new File(['content1'], 'test1.jpg', { type: 'image/jpeg' })
      const file2 = new File(['content2'], 'test2.png', { type: 'image/png' })
      const dropZone = wrapper.find('[role="button"]')

      await dropZone.trigger('drop', {
        dataTransfer: { files: [file1, file2] },
      })
      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(mockToast.showSuccess).toHaveBeenCalledWith(
        expect.stringContaining('2 files')
      )
    })
  })

  describe('Accessibility', () => {
    it('has proper focus visible styles', () => {
      wrapper = mount(FileUpload, {
        props: { sessionId: 'session-123' },
      })

      const dropZone = wrapper.find('[role="button"]')
      // Check that focus-visible styles are defined in scoped CSS
      expect(wrapper.html()).toContain('focus-visible')
    })
  })
})
