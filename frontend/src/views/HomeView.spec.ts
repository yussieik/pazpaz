import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import HomeView from './HomeView.vue'

describe('HomeView.vue', () => {
  const createRouterForTest = () => {
    return createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: HomeView },
        {
          path: '/calendar',
          name: 'calendar',
          component: { template: '<div>Calendar</div>' },
        },
      ],
    })
  }

  it('should render the page title', () => {
    const router = createRouterForTest()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.find('h1').text()).toBe('PazPaz')
  })

  it('should render the page description', () => {
    const router = createRouterForTest()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.text()).toContain('Practice management for independent therapists')
  })

  it('should render calendar navigation link', () => {
    const router = createRouterForTest()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router],
      },
    })

    const calendarLink = wrapper.find('a[href="/calendar"]')
    expect(calendarLink.exists()).toBe(true)
    expect(calendarLink.text()).toContain('Calendar')
    expect(calendarLink.text()).toContain('Manage appointments and schedule')
  })

  it('should render clients placeholder card', () => {
    const router = createRouterForTest()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router],
      },
    })

    const clientsCard = wrapper.text()
    expect(clientsCard).toContain('Clients')
    expect(clientsCard).toContain('Coming soon - Client management')
  })

  it('should render session notes placeholder card', () => {
    const router = createRouterForTest()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router],
      },
    })

    const notesCard = wrapper.text()
    expect(notesCard).toContain('Session Notes')
    expect(notesCard).toContain('Coming soon - SOAP documentation')
  })

  it('should have responsive grid layout classes', () => {
    const router = createRouterForTest()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router],
      },
    })

    const grid = wrapper.find('.grid')
    expect(grid.exists()).toBe(true)
    expect(grid.classes()).toContain('md:grid-cols-2')
    expect(grid.classes()).toContain('lg:grid-cols-3')
  })

  it('should style coming soon cards differently', () => {
    const router = createRouterForTest()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router],
      },
    })

    const cards = wrapper.findAll('.block')
    const comingSoonCards = cards.filter((card) => card.text().includes('Coming soon'))

    comingSoonCards.forEach((card) => {
      expect(card.classes()).toContain('bg-gray-50')
      expect(card.classes()).toContain('opacity-60')
    })
  })

  it('should make calendar card interactive with hover effect', () => {
    const router = createRouterForTest()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [router],
      },
    })

    const calendarLink = wrapper.find('a[href="/calendar"]')
    expect(calendarLink.classes()).toContain('hover:shadow-md')
  })
})
