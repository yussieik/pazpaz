import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createAuthChannel, type AuthMessage } from './crossTabSync'

describe('crossTabSync', () => {
  let mockBroadcastChannel: {
    postMessage: ReturnType<typeof vi.fn>
    addEventListener: ReturnType<typeof vi.fn>
    removeEventListener: ReturnType<typeof vi.fn>
    close: ReturnType<typeof vi.fn>
  }
  let messageHandler: ((event: MessageEvent<AuthMessage>) => void) | null = null

  beforeEach(() => {
    // Mock BroadcastChannel
    mockBroadcastChannel = {
      postMessage: vi.fn(),
      addEventListener: vi.fn(
        (event: string, handler: (event: MessageEvent<AuthMessage>) => void) => {
          if (event === 'message') {
            messageHandler = handler
          }
        }
      ),
      removeEventListener: vi.fn(),
      close: vi.fn(),
    }

    // @ts-expect-error - Mocking global BroadcastChannel
    global.BroadcastChannel = vi.fn(() => mockBroadcastChannel)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    messageHandler = null
  })

  describe('Channel Creation', () => {
    it('creates BroadcastChannel with correct name', () => {
      createAuthChannel()
      expect(global.BroadcastChannel).toHaveBeenCalledWith('pazpaz_auth')
    })

    it('registers message event listener', () => {
      createAuthChannel()
      expect(mockBroadcastChannel.addEventListener).toHaveBeenCalledWith(
        'message',
        expect.any(Function)
      )
    })

    it('returns isSupported: true when BroadcastChannel is available', () => {
      const channel = createAuthChannel()
      expect(channel.isSupported).toBe(true)
    })

    it('returns no-op fallback when BroadcastChannel is not available', () => {
      // @ts-expect-error - Removing global BroadcastChannel
      delete global.BroadcastChannel

      const channel = createAuthChannel()
      expect(channel.isSupported).toBe(false)

      // All methods should be no-ops
      expect(() => channel.postLogout()).not.toThrow()
      expect(() => channel.postLogin()).not.toThrow()
      expect(() => channel.postSessionExtended()).not.toThrow()
      expect(() => channel.onLogout(() => {})).not.toThrow()
      expect(() => channel.close()).not.toThrow()
    })
  })

  describe('Logout Messages', () => {
    it('posts logout message with correct structure', () => {
      const channel = createAuthChannel()
      channel.postLogout('user123', 'workspace456')

      expect(mockBroadcastChannel.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'logout',
          userId: 'user123',
          workspaceId: 'workspace456',
          timestamp: expect.any(Number),
          tabId: expect.any(String),
        })
      )
    })

    it('receives logout messages from other tabs', () => {
      const channel = createAuthChannel()
      const handler = vi.fn()
      channel.onLogout(handler)

      // Simulate message from another tab
      const message: AuthMessage = {
        type: 'logout',
        timestamp: Date.now(),
        userId: 'user123',
        workspaceId: 'workspace456',
        tabId: 'other_tab_id',
      }

      messageHandler!({ data: message } as MessageEvent<AuthMessage>)

      expect(handler).toHaveBeenCalledWith(message)
    })

    it('ignores logout messages from same tab', () => {
      const channel = createAuthChannel()
      const handler = vi.fn()
      channel.onLogout(handler)

      // Post a message (this will use the current tab's ID)
      channel.postLogout()
      const postedMessage = mockBroadcastChannel.postMessage.mock.calls[0][0]

      // Simulate receiving the same message (echo)
      messageHandler!({ data: postedMessage } as MessageEvent<AuthMessage>)

      // Handler should NOT be called (echo prevention)
      expect(handler).not.toHaveBeenCalled()
    })

    it('supports multiple logout handlers', () => {
      const channel = createAuthChannel()
      const handler1 = vi.fn()
      const handler2 = vi.fn()

      channel.onLogout(handler1)
      channel.onLogout(handler2)

      const message: AuthMessage = {
        type: 'logout',
        timestamp: Date.now(),
        tabId: 'other_tab',
      }

      messageHandler!({ data: message } as MessageEvent<AuthMessage>)

      expect(handler1).toHaveBeenCalledWith(message)
      expect(handler2).toHaveBeenCalledWith(message)
    })
  })

  describe('Login Messages', () => {
    it('posts login message with correct structure', () => {
      const channel = createAuthChannel()
      channel.postLogin('user123', 'workspace456')

      expect(mockBroadcastChannel.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'login',
          userId: 'user123',
          workspaceId: 'workspace456',
          timestamp: expect.any(Number),
          tabId: expect.any(String),
        })
      )
    })

    it('receives login messages from other tabs', () => {
      const channel = createAuthChannel()
      const handler = vi.fn()
      channel.onLogin(handler)

      const message: AuthMessage = {
        type: 'login',
        timestamp: Date.now(),
        userId: 'user123',
        tabId: 'other_tab',
      }

      messageHandler!({ data: message } as MessageEvent<AuthMessage>)

      expect(handler).toHaveBeenCalledWith(message)
    })
  })

  describe('Session Extended Messages', () => {
    it('posts session extended message with correct structure', () => {
      const channel = createAuthChannel()
      channel.postSessionExtended('user123', 'workspace456')

      expect(mockBroadcastChannel.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'session_extended',
          userId: 'user123',
          workspaceId: 'workspace456',
          timestamp: expect.any(Number),
          tabId: expect.any(String),
        })
      )
    })

    it('receives session extended messages from other tabs', () => {
      const channel = createAuthChannel()
      const handler = vi.fn()
      channel.onSessionExtended(handler)

      const message: AuthMessage = {
        type: 'session_extended',
        timestamp: Date.now(),
        tabId: 'other_tab',
      }

      messageHandler!({ data: message } as MessageEvent<AuthMessage>)

      expect(handler).toHaveBeenCalledWith(message)
    })
  })

  describe('Message Validation', () => {
    it('ignores messages without type', () => {
      const channel = createAuthChannel()
      const handler = vi.fn()
      channel.onLogout(handler)

      // @ts-expect-error - Testing invalid message
      const invalidMessage: AuthMessage = {
        timestamp: Date.now(),
        tabId: 'other_tab',
      }

      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      messageHandler!({ data: invalidMessage } as MessageEvent<AuthMessage>)

      expect(handler).not.toHaveBeenCalled()
      expect(consoleSpy).toHaveBeenCalledWith(
        '[CrossTabSync] Invalid message received:',
        invalidMessage
      )

      consoleSpy.mockRestore()
    })

    it('ignores messages without timestamp', () => {
      const channel = createAuthChannel()
      const handler = vi.fn()
      channel.onLogout(handler)

      // @ts-expect-error - Testing invalid message
      const invalidMessage: AuthMessage = {
        type: 'logout',
        tabId: 'other_tab',
      }

      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      messageHandler!({ data: invalidMessage } as MessageEvent<AuthMessage>)

      expect(handler).not.toHaveBeenCalled()
      expect(consoleSpy).toHaveBeenCalledWith(
        '[CrossTabSync] Invalid message received:',
        invalidMessage
      )

      consoleSpy.mockRestore()
    })

    it('warns on unknown message type', () => {
      const channel = createAuthChannel()
      const handler = vi.fn()
      channel.onLogout(handler)

      const unknownMessage = {
        type: 'unknown_type',
        timestamp: Date.now(),
        tabId: 'other_tab',
      } as AuthMessage

      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      messageHandler!({ data: unknownMessage } as MessageEvent<AuthMessage>)

      expect(handler).not.toHaveBeenCalled()
      expect(consoleSpy).toHaveBeenCalledWith(
        '[CrossTabSync] Unknown message type:',
        'unknown_type'
      )

      consoleSpy.mockRestore()
    })
  })

  describe('Cleanup', () => {
    it('removes event listener on close', () => {
      const channel = createAuthChannel()
      channel.close()

      expect(mockBroadcastChannel.removeEventListener).toHaveBeenCalledWith(
        'message',
        expect.any(Function)
      )
    })

    it('closes BroadcastChannel on close', () => {
      const channel = createAuthChannel()
      channel.close()

      expect(mockBroadcastChannel.close).toHaveBeenCalled()
    })
  })

  describe('Tab ID Generation', () => {
    it('generates unique tab IDs for different channels', () => {
      const channel1 = createAuthChannel()
      const channel2 = createAuthChannel()

      channel1.postLogout()
      channel2.postLogout()

      const tabId1 = mockBroadcastChannel.postMessage.mock.calls[0][0].tabId
      const tabId2 = mockBroadcastChannel.postMessage.mock.calls[1][0].tabId

      expect(tabId1).not.toBe(tabId2)
      expect(tabId1).toMatch(/^tab_\d+_[a-z0-9]+$/)
      expect(tabId2).toMatch(/^tab_\d+_[a-z0-9]+$/)
    })
  })

  describe('Multiple Tabs Simultaneously', () => {
    it('handles multiple tabs broadcasting simultaneously', () => {
      const channel = createAuthChannel()
      const handler = vi.fn()
      channel.onLogout(handler)

      // Simulate messages from multiple tabs
      const tab1Message: AuthMessage = {
        type: 'logout',
        timestamp: Date.now(),
        tabId: 'tab1',
      }

      const tab2Message: AuthMessage = {
        type: 'logout',
        timestamp: Date.now(),
        tabId: 'tab2',
      }

      const tab3Message: AuthMessage = {
        type: 'logout',
        timestamp: Date.now(),
        tabId: 'tab3',
      }

      messageHandler!({ data: tab1Message } as MessageEvent<AuthMessage>)
      messageHandler!({ data: tab2Message } as MessageEvent<AuthMessage>)
      messageHandler!({ data: tab3Message } as MessageEvent<AuthMessage>)

      expect(handler).toHaveBeenCalledTimes(3)
      expect(handler).toHaveBeenCalledWith(tab1Message)
      expect(handler).toHaveBeenCalledWith(tab2Message)
      expect(handler).toHaveBeenCalledWith(tab3Message)
    })
  })
})
