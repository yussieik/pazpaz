<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const mobileMenuOpen = ref(false)

function toggleMobileMenu() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

function closeMobileMenu() {
  mobileMenuOpen.value = false
}

function isActive(path: string): boolean {
  // Exact match for root
  if (path === '/') {
    return route.path === '/'
  }
  // Prefix match for other paths
  return route.path === path || route.path.startsWith(path + '/')
}

// Close mobile menu on Escape key
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && mobileMenuOpen.value) {
    closeMobileMenu()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <nav class="border-b border-gray-200 bg-white">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div class="flex h-16 items-center justify-between">
        <!-- Logo and primary navigation -->
        <div class="flex items-center gap-8">
          <!-- Logo -->
          <RouterLink
            to="/"
            class="flex items-center gap-2 rounded-md text-lg font-semibold text-emerald-600 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
          >
            <svg class="h-6 w-6" fill="currentColor" viewBox="0 0 24 24">
              <path
                d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2zm-7 5h5v5h-5z"
              />
            </svg>
            <span>PazPaz</span>
          </RouterLink>

          <!-- Desktop navigation items -->
          <div class="hidden space-x-1 md:flex">
            <RouterLink
              to="/"
              :class="[
                'rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
                isActive('/')
                  ? 'border-b-2 border-emerald-600 text-emerald-600'
                  : 'text-gray-600 hover:text-gray-900',
              ]"
            >
              Calendar
            </RouterLink>
            <RouterLink
              to="/clients"
              :class="[
                'rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
                isActive('/clients')
                  ? 'border-b-2 border-emerald-600 text-emerald-600'
                  : 'text-gray-600 hover:text-gray-900',
              ]"
            >
              Clients
            </RouterLink>
            <RouterLink
              to="/settings"
              :class="[
                'rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
                isActive('/settings')
                  ? 'border-b-2 border-emerald-600 text-emerald-600'
                  : 'text-gray-600 hover:text-gray-900',
              ]"
            >
              Settings
            </RouterLink>
          </div>
        </div>

        <!-- Right side: User menu + mobile toggle -->
        <div class="flex items-center gap-4">
          <!-- User menu placeholder -->
          <div class="hidden text-sm text-gray-600 md:block">
            <span>Account</span>
          </div>

          <!-- Mobile menu button -->
          <button
            class="rounded-md p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none md:hidden"
            @click="toggleMobileMenu"
            aria-label="Toggle mobile menu"
          >
            <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                v-if="!mobileMenuOpen"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 6h16M4 12h16M4 18h16"
              />
              <path
                v-else
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile menu (slide-out drawer) -->
    <Transition name="mobile-menu">
      <div v-if="mobileMenuOpen" class="md:hidden">
        <!-- Backdrop -->
        <div
          class="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
          @click="closeMobileMenu"
          aria-hidden="true"
        ></div>

        <!-- Drawer -->
        <div class="fixed inset-y-0 right-0 z-50 w-64 bg-white shadow-xl">
          <div class="flex h-full flex-col">
            <!-- Close button -->
            <div class="flex items-center justify-end border-b border-gray-200 p-4">
              <button
                class="rounded-md p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:outline-none"
                @click="closeMobileMenu"
                aria-label="Close menu"
              >
                <svg
                  class="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <!-- Navigation items -->
            <nav class="flex-1 space-y-1 p-4">
              <RouterLink
                to="/"
                :class="[
                  'block rounded-md px-3 py-2 text-base font-medium transition-colors',
                  isActive('/')
                    ? 'bg-emerald-50 text-emerald-600'
                    : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900',
                ]"
                @click="closeMobileMenu"
              >
                Calendar
              </RouterLink>
              <RouterLink
                to="/clients"
                :class="[
                  'block rounded-md px-3 py-2 text-base font-medium transition-colors',
                  isActive('/clients')
                    ? 'bg-emerald-50 text-emerald-600'
                    : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900',
                ]"
                @click="closeMobileMenu"
              >
                Clients
              </RouterLink>
              <RouterLink
                to="/settings"
                :class="[
                  'block rounded-md px-3 py-2 text-base font-medium transition-colors',
                  isActive('/settings')
                    ? 'bg-emerald-50 text-emerald-600'
                    : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900',
                ]"
                @click="closeMobileMenu"
              >
                Settings
              </RouterLink>
            </nav>

            <!-- Sign out button (placeholder) -->
            <div class="border-t border-gray-200 p-4">
              <button
                class="w-full rounded-md bg-gray-100 px-3 py-2 text-base font-medium text-gray-700 hover:bg-gray-200"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </nav>
</template>

<style scoped>
.mobile-menu-enter-active,
.mobile-menu-leave-active {
  transition: opacity 200ms ease-out;
}

.mobile-menu-enter-from,
.mobile-menu-leave-to {
  opacity: 0;
}
</style>
