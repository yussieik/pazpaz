import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useFileUpload } from './useFileUpload'
import apiClient from '@/api/client'
import { ref } from 'vue'
import type { UploadProgress } from '@/types/attachments'

// Mock API client
vi.mock('@/api/client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
  },
}))

/**
 * Tests for useFileUpload composable
 *
 * Verifies file upload, download, delete, and validation functionality.
 */
describe('useFileUpload', () => {
  const mockApiClient = apiClient as any
  const sessionId = 'test-session-id'

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('uploadFile', () => {
    it('uploads a file successfully', async () => {
      const { uploadFile } = useFileUpload()
      const mockFile = new File(['test content'], 'test.jpg', { type: 'image/jpeg' })
      const mockResponse = {
        data: {
          id: 'attachment-id',
          session_id: sessionId,
          file_name: 'test.jpg',
          file_type: 'image/jpeg',
          file_size_bytes: 1024,
          created_at: '2025-10-16T10:00:00Z',
        },
      }

      mockApiClient.post.mockResolvedValue(mockResponse)

      const result = await uploadFile(sessionId, mockFile)

      expect(result).toEqual(mockResponse.data)
      expect(mockApiClient.post).toHaveBeenCalledWith(
        `/sessions/${sessionId}/attachments`,
        expect.any(FormData),
        expect.objectContaining({
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        })
      )
    })

    it('validates file type before upload', async () => {
      const { uploadFile } = useFileUpload()
      const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' })

      await expect(uploadFile(sessionId, mockFile)).rejects.toThrow(
        'Unsupported file type'
      )

      expect(mockApiClient.post).not.toHaveBeenCalled()
    })

    it('validates file size before upload', async () => {
      const { uploadFile } = useFileUpload()
      // Create a file larger than 10 MB
      const largeContent = new Array(11 * 1024 * 1024).fill('a').join('')
      const mockFile = new File([largeContent], 'large.jpg', { type: 'image/jpeg' })

      await expect(uploadFile(sessionId, mockFile)).rejects.toThrow('File too large')

      expect(mockApiClient.post).not.toHaveBeenCalled()
    })

    it('tracks upload progress', async () => {
      const { uploadFile } = useFileUpload()
      const mockFile = new File(['test'], 'test.jpg', { type: 'image/jpeg' })
      const progressRef = ref<UploadProgress>({
        state: 'idle',
        progress: 0,
        error: null,
      })

      mockApiClient.post.mockImplementation((url, data, config) => {
        // Simulate progress
        config.onUploadProgress?.({ loaded: 50, total: 100 })
        return Promise.resolve({
          data: {
            id: 'attachment-id',
            session_id: sessionId,
            file_name: 'test.jpg',
            file_type: 'image/jpeg',
            file_size_bytes: 100,
            created_at: '2025-10-16T10:00:00Z',
          },
        })
      })

      await uploadFile(sessionId, mockFile, progressRef)

      expect(progressRef.value.state).toBe('success')
      expect(progressRef.value.progress).toBe(100)
    })

    it('handles 413 error (file too large)', async () => {
      const { uploadFile } = useFileUpload()
      const mockFile = new File(['test'], 'test.jpg', { type: 'image/jpeg' })

      mockApiClient.post.mockRejectedValue({
        response: {
          status: 413,
          data: { detail: 'File too large' },
        },
      })

      await expect(uploadFile(sessionId, mockFile)).rejects.toThrow(
        /File too large|max 10 MB/
      )
    })

    it('handles 415 error (unsupported file type)', async () => {
      const { uploadFile } = useFileUpload()
      const mockFile = new File(['test'], 'test.jpg', { type: 'image/jpeg' })

      mockApiClient.post.mockRejectedValue({
        response: {
          status: 415,
          data: { detail: 'Unsupported file type' },
        },
      })

      await expect(uploadFile(sessionId, mockFile)).rejects.toThrow(
        /Unsupported file type/
      )
    })

    it('handles 422 error (validation failed)', async () => {
      const { uploadFile } = useFileUpload()
      const mockFile = new File(['test'], 'test.jpg', { type: 'image/jpeg' })

      mockApiClient.post.mockRejectedValue({
        response: {
          status: 422,
          data: { detail: 'File validation failed' },
        },
      })

      await expect(uploadFile(sessionId, mockFile)).rejects.toThrow(
        /File validation failed/
      )
    })

    it('handles 429 error (rate limit)', async () => {
      const { uploadFile } = useFileUpload()
      const mockFile = new File(['test'], 'test.jpg', { type: 'image/jpeg' })

      mockApiClient.post.mockRejectedValue({
        response: {
          status: 429,
          data: {},
        },
      })

      // Use maxRetries=0 to disable retries and avoid timeout
      await expect(uploadFile(sessionId, mockFile, undefined, 0)).rejects.toThrow(/rate limit/i)
    })
  })

  describe('uploadFiles', () => {
    it('uploads multiple files successfully', async () => {
      const { uploadFiles } = useFileUpload()
      const mockFiles = [
        new File(['test1'], 'test1.jpg', { type: 'image/jpeg' }),
        new File(['test2'], 'test2.png', { type: 'image/png' }),
      ]

      mockApiClient.post.mockResolvedValue({
        data: {
          id: 'attachment-id',
          session_id: sessionId,
          file_name: 'test.jpg',
          file_type: 'image/jpeg',
          file_size_bytes: 100,
          created_at: '2025-10-16T10:00:00Z',
        },
      })

      const results = await uploadFiles(sessionId, mockFiles)

      expect(results).toHaveLength(2)
      expect(mockApiClient.post).toHaveBeenCalledTimes(2)
    })

    it('continues uploading even if one file fails', async () => {
      const { uploadFiles } = useFileUpload()
      const mockFiles = [
        new File(['test1'], 'test1.jpg', { type: 'image/jpeg' }),
        new File(['test2'], 'test2.png', { type: 'image/png' }),
      ]

      // First file fails with 400 (no retries), second file succeeds
      mockApiClient.post
        .mockRejectedValueOnce({
          response: {
            status: 400,
            data: { detail: 'Upload failed' },
          },
        })
        .mockResolvedValueOnce({
          data: {
            id: 'attachment-id-2',
            session_id: sessionId,
            file_name: 'test2.png',
            file_type: 'image/png',
            file_size_bytes: 100,
            created_at: '2025-10-16T10:00:00Z',
          },
        })

      const results = await uploadFiles(sessionId, mockFiles)

      expect(results).toHaveLength(1) // Only successful upload
      expect(mockApiClient.post).toHaveBeenCalledTimes(2)
    })
  })

  describe('listAttachments', () => {
    it('fetches attachment list successfully', async () => {
      const { listAttachments } = useFileUpload()
      const mockResponse = {
        data: {
          items: [
            {
              id: 'attachment-1',
              session_id: sessionId,
              file_name: 'test1.jpg',
              file_type: 'image/jpeg',
              file_size_bytes: 1024,
              created_at: '2025-10-16T10:00:00Z',
            },
            {
              id: 'attachment-2',
              session_id: sessionId,
              file_name: 'test2.pdf',
              file_type: 'application/pdf',
              file_size_bytes: 2048,
              created_at: '2025-10-16T11:00:00Z',
            },
          ],
          total: 2,
        },
      }

      mockApiClient.get.mockResolvedValue(mockResponse)

      const result = await listAttachments(sessionId)

      expect(result).toEqual(mockResponse.data)
      expect(mockApiClient.get).toHaveBeenCalledWith(
        `/sessions/${sessionId}/attachments`
      )
    })

    it('handles list error gracefully', async () => {
      const { listAttachments } = useFileUpload()

      mockApiClient.get.mockRejectedValue({
        response: {
          status: 500,
          data: { detail: 'Server error' },
        },
      })

      await expect(listAttachments(sessionId)).rejects.toThrow(/Server error/)
    })
  })

  describe('getDownloadUrl', () => {
    it('fetches download URL successfully', async () => {
      const { getDownloadUrl } = useFileUpload()
      const attachmentId = 'attachment-id'
      const mockResponse = {
        data: {
          download_url: 'https://s3.example.com/file?signature=...',
          expires_in_seconds: 900,
        },
      }

      mockApiClient.get.mockResolvedValue(mockResponse)

      const result = await getDownloadUrl(sessionId, attachmentId)

      expect(result).toEqual(mockResponse.data)
      expect(mockApiClient.get).toHaveBeenCalledWith(
        `/sessions/${sessionId}/attachments/${attachmentId}/download`,
        {
          params: {
            expires_in_minutes: 15,
          },
        }
      )
    })

    it('uses custom expiration time', async () => {
      const { getDownloadUrl } = useFileUpload()
      const attachmentId = 'attachment-id'

      mockApiClient.get.mockResolvedValue({
        data: {
          download_url: 'https://s3.example.com/file',
          expires_in_seconds: 1800,
        },
      })

      await getDownloadUrl(sessionId, attachmentId, 30)

      expect(mockApiClient.get).toHaveBeenCalledWith(
        `/sessions/${sessionId}/attachments/${attachmentId}/download`,
        {
          params: {
            expires_in_minutes: 30,
          },
        }
      )
    })
  })

  describe('downloadAttachment', () => {
    it('opens download in new tab', async () => {
      const { downloadAttachment } = useFileUpload()
      const attachmentId = 'attachment-id'
      const filename = 'test.jpg'

      const mockWindow = { close: vi.fn() }
      global.window.open = vi.fn().mockReturnValue(mockWindow)

      mockApiClient.get.mockResolvedValue({
        data: {
          download_url: 'https://s3.example.com/file',
          expires_in_seconds: 900,
        },
      })

      await downloadAttachment(sessionId, attachmentId, filename)

      expect(global.window.open).toHaveBeenCalledWith(
        'https://s3.example.com/file',
        '_blank'
      )
    })

    it('throws error when popup is blocked', async () => {
      const { downloadAttachment } = useFileUpload()
      const attachmentId = 'attachment-id'
      const filename = 'test.jpg'

      global.window.open = vi.fn().mockReturnValue(null)

      mockApiClient.get.mockResolvedValue({
        data: {
          download_url: 'https://s3.example.com/file',
          expires_in_seconds: 900,
        },
      })

      await expect(
        downloadAttachment(sessionId, attachmentId, filename)
      ).rejects.toThrow(/Popup blocked/)
    })
  })

  describe('deleteAttachment', () => {
    it('deletes attachment successfully', async () => {
      const { deleteAttachment } = useFileUpload()
      const attachmentId = 'attachment-id'

      mockApiClient.delete.mockResolvedValue({ data: {} })

      await deleteAttachment(sessionId, attachmentId)

      expect(mockApiClient.delete).toHaveBeenCalledWith(
        `/sessions/${sessionId}/attachments/${attachmentId}`
      )
    })

    it('handles delete error gracefully', async () => {
      const { deleteAttachment } = useFileUpload()
      const attachmentId = 'attachment-id'

      mockApiClient.delete.mockRejectedValue({
        response: {
          status: 404,
          data: { detail: 'Attachment not found' },
        },
      })

      await expect(deleteAttachment(sessionId, attachmentId)).rejects.toThrow(
        /Attachment not found/
      )
    })
  })
})
