import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import App from './App.vue'

describe('App.vue', () => {
  it('should render the app container', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div>Home</div>' },
        },
      ],
    })

    const pinia = createPinia()

    const wrapper = mount(App, {
      global: {
        plugins: [router, pinia],
      },
    })

    expect(wrapper.find('#app').exists()).toBe(true)
  })

  it('should have correct container classes', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div>Home</div>' },
        },
      ],
    })

    const pinia = createPinia()

    const wrapper = mount(App, {
      global: {
        plugins: [router, pinia],
      },
    })

    const appContainer = wrapper.find('#app')
    expect(appContainer.classes()).toContain('min-h-screen')
    expect(appContainer.classes()).toContain('bg-gray-50')
  })

  it('should render RouterView for route content', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div class="test-content">Test Route</div>' },
        },
      ],
    })

    await router.push('/')
    await router.isReady()

    const pinia = createPinia()

    const wrapper = mount(App, {
      global: {
        plugins: [router, pinia],
      },
    })

    expect(wrapper.html()).toContain('test-content')
  })
})
