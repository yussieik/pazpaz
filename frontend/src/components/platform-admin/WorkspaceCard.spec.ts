import { describe, it, expect, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import WorkspaceCard, { type Workspace } from './WorkspaceCard.vue'

describe('WorkspaceCard', () => {
  let wrapper: VueWrapper

  const mockWorkspace: Workspace = {
    id: '1',
    name: "Sarah's Massage Therapy",
    email: 'sarah@example.com',
    status: 'active',
    createdAt: '2025-10-01T00:00:00Z',
    userCount: 1,
    activeUsers: 1,
    appointmentCount: 12,
  }

  beforeEach(() => {
    // Reset DOM
    document.body.innerHTML = ''
  })

  describe('Rendering', () => {
    it('renders workspace name and email', () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      expect(wrapper.text()).toContain("Sarah's Massage Therapy")
      expect(wrapper.text()).toContain('sarah@example.com')
    })

    it('renders workspace avatar with first letter', () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const avatar = wrapper.find('.bg-emerald-100')
      expect(avatar.text()).toBe('S')
    })

    it('renders stats row with user count', () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      expect(wrapper.text()).toContain('1 user')
      expect(wrapper.text()).toContain('1 active')
      expect(wrapper.text()).toContain('12 appointments')
    })

    it('pluralizes user count correctly', () => {
      const multiUserWorkspace = { ...mockWorkspace, userCount: 3 }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: multiUserWorkspace,
        },
      })

      expect(wrapper.text()).toContain('3 users')
    })

    it('pluralizes appointment count correctly', () => {
      const singleAppointment = { ...mockWorkspace, appointmentCount: 1 }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: singleAppointment,
        },
      })

      expect(wrapper.text()).toContain('1 appointment')
    })

    it('renders formatted creation date', () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      expect(wrapper.text()).toMatch(/Created.*Oct.*2025/)
    })
  })

  describe('Status Badge', () => {
    it('shows active status badge with green color', () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const badge = wrapper.find('[role="status"]')
      expect(badge.text()).toContain('Active')
      expect(badge.classes()).toContain('bg-emerald-100')
      expect(badge.classes()).toContain('text-emerald-700')
    })

    it('shows pending status badge with amber color', () => {
      const pendingWorkspace = { ...mockWorkspace, status: 'pending' as const }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: pendingWorkspace,
        },
      })

      const badge = wrapper.find('[role="status"]')
      expect(badge.text()).toContain('Pending')
      expect(badge.classes()).toContain('bg-amber-100')
      expect(badge.classes()).toContain('text-amber-700')
    })

    it('shows suspended status badge with red color', () => {
      const suspendedWorkspace = { ...mockWorkspace, status: 'suspended' as const }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: suspendedWorkspace,
        },
      })

      const badge = wrapper.find('[role="status"]')
      expect(badge.text()).toContain('Suspended')
      expect(badge.classes()).toContain('bg-red-100')
      expect(badge.classes()).toContain('text-red-700')
    })
  })

  describe('Actions Menu', () => {
    it('shows actions menu button', () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      expect(actionsButton.exists()).toBe(true)
    })

    it('toggles menu visibility when actions button clicked', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      // Menu should be hidden initially
      expect(wrapper.find('[role="menu"]').exists()).toBe(false)

      // Click to show menu
      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')
      expect(wrapper.find('[role="menu"]').exists()).toBe(true)

      // Click again to hide menu
      await actionsButton.trigger('click')
      expect(wrapper.find('[role="menu"]').exists()).toBe(false)
    })

    it('shows View Details option in menu', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const viewDetailsItem = menuItems.find((item) =>
        item.text().includes('View Details')
      )
      expect(viewDetailsItem).toBeTruthy()
    })

    it('shows Suspend option for active workspace', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const suspendItem = menuItems.find((item) =>
        item.text().includes('Suspend Workspace')
      )
      expect(suspendItem).toBeTruthy()
    })

    it('shows Reactivate option for suspended workspace', async () => {
      const suspendedWorkspace = { ...mockWorkspace, status: 'suspended' as const }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: suspendedWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const reactivateItem = menuItems.find((item) =>
        item.text().includes('Reactivate Workspace')
      )
      expect(reactivateItem).toBeTruthy()
    })

    it('shows Resend Invitation option for pending workspace', async () => {
      const pendingWorkspace = { ...mockWorkspace, status: 'pending' as const }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: pendingWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const resendItem = menuItems.find((item) =>
        item.text().includes('Resend Invitation')
      )
      expect(resendItem).toBeTruthy()
    })

    it('does not show Suspend option for pending workspace', async () => {
      const pendingWorkspace = { ...mockWorkspace, status: 'pending' as const }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: pendingWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const suspendItem = menuItems.find((item) =>
        item.text().includes('Suspend Workspace')
      )
      expect(suspendItem).toBeFalsy()
    })
  })

  describe('Events', () => {
    it('emits view-details event when View Details clicked', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const viewDetailsItem = menuItems.find((item) =>
        item.text().includes('View Details')
      )
      await viewDetailsItem?.trigger('click')

      expect(wrapper.emitted('view-details')).toBeTruthy()
      expect(wrapper.emitted('view-details')?.[0]).toEqual(['1'])
    })

    it('emits suspend event when Suspend clicked', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const suspendItem = menuItems.find((item) =>
        item.text().includes('Suspend Workspace')
      )
      await suspendItem?.trigger('click')

      expect(wrapper.emitted('suspend')).toBeTruthy()
      expect(wrapper.emitted('suspend')?.[0]).toEqual(['1'])
    })

    it('emits reactivate event when Reactivate clicked', async () => {
      const suspendedWorkspace = { ...mockWorkspace, status: 'suspended' as const }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: suspendedWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const reactivateItem = menuItems.find((item) =>
        item.text().includes('Reactivate Workspace')
      )
      await reactivateItem?.trigger('click')

      expect(wrapper.emitted('reactivate')).toBeTruthy()
      expect(wrapper.emitted('reactivate')?.[0]).toEqual(['1'])
    })

    it('emits resend event when Resend Invitation clicked', async () => {
      const pendingWorkspace = { ...mockWorkspace, status: 'pending' as const }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: pendingWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const resendItem = menuItems.find((item) =>
        item.text().includes('Resend Invitation')
      )
      await resendItem?.trigger('click')

      expect(wrapper.emitted('resend')).toBeTruthy()
      expect(wrapper.emitted('resend')?.[0]).toEqual(['1'])
    })

    it('closes menu after action is clicked', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')
      expect(wrapper.find('[role="menu"]').exists()).toBe(true)

      const menuItems = wrapper.findAll('[role="menuitem"]')
      const viewDetailsItem = menuItems.find((item) =>
        item.text().includes('View Details')
      )
      await viewDetailsItem?.trigger('click')

      // Wait for next tick
      await wrapper.vm.$nextTick()
      expect(wrapper.find('[role="menu"]').exists()).toBe(false)
    })
  })

  describe('Accessibility', () => {
    it('has correct ARIA attributes on card', () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const card = wrapper.find('.rounded-xl')
      expect(card.attributes('aria-label')).toBe("Workspace: Sarah's Massage Therapy")
    })

    it('has correct ARIA attributes on actions button', () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      expect(actionsButton.attributes('aria-label')).toContain(
        "Sarah's Massage Therapy"
      )
      expect(actionsButton.attributes('aria-expanded')).toBe('false')
    })

    it('updates aria-expanded when menu opens', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      expect(actionsButton.attributes('aria-expanded')).toBe('true')
    })

    it('menu has correct role and orientation', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menu = wrapper.find('[role="menu"]')
      expect(menu.attributes('aria-orientation')).toBe('vertical')
    })

    it('menu items have menuitem role', async () => {
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: mockWorkspace,
        },
      })

      const actionsButton = wrapper.find('[aria-haspopup="true"]')
      await actionsButton.trigger('click')

      const menuItems = wrapper.findAll('[role="menuitem"]')
      expect(menuItems.length).toBeGreaterThan(0)
    })
  })

  describe('Edge Cases', () => {
    it('handles workspace with no name gracefully', () => {
      const noNameWorkspace = { ...mockWorkspace, name: '' }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: noNameWorkspace,
        },
      })

      const avatar = wrapper.find('.bg-emerald-100')
      expect(avatar.text()).toBe('W')
    })

    it('handles zero counts', () => {
      const zeroCountsWorkspace = {
        ...mockWorkspace,
        userCount: 0,
        activeUsers: 0,
        appointmentCount: 0,
      }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: zeroCountsWorkspace,
        },
      })

      expect(wrapper.text()).toContain('0 users')
      expect(wrapper.text()).toContain('0 active')
      expect(wrapper.text()).toContain('0 appointments')
    })

    it('handles long workspace names', () => {
      const longNameWorkspace = {
        ...mockWorkspace,
        name: 'This is a very long workspace name that should still display properly',
      }
      wrapper = mount(WorkspaceCard, {
        props: {
          workspace: longNameWorkspace,
        },
      })

      expect(wrapper.text()).toContain('This is a very long workspace name')
    })
  })
})
