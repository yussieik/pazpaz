<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const status = ref<'loading' | 'success' | 'error'>('loading')
const errorMessage = ref<string>('')

onMounted(async () => {
  const token = route.query.token as string

  if (!token) {
    status.value = 'error'
    errorMessage.value = 'Invitation link is missing token'
    return
  }

  try {
    // Call the accept-invite endpoint with token as query parameter
    // Backend returns 200 OK with JSON and sets HttpOnly auth cookies
    const response = await apiClient.get('/auth/accept-invite', {
      params: { token },
    })

    // If we got here without error, invitation was accepted successfully
    // The backend set auth cookies and returned user data
    if (response.data && response.data.success) {
      status.value = 'success'

      // Update auth store with user data from response
      if (response.data.user) {
        authStore.setUser(response.data.user)
        console.info('[AcceptInvitation] User authenticated:', response.data.user.id)
      }

      // Redirect to home page after 2 seconds
      setTimeout(() => {
        router.push('/')
      }, 2000)
    } else {
      throw new Error('Unexpected response format')
    }
  } catch (error: unknown) {
    status.value = 'error'

    // Handle different error responses from backend
    const axiosError = error as {
      response?: { status?: number; data?: { detail?: string } }
    }

    console.error('[AcceptInvitation] Invitation acceptance failed:', error)

    // Backend returns error codes for different failure scenarios
    if (axiosError?.response?.status === 404) {
      errorMessage.value = 'Invalid invitation link'
    } else if (axiosError?.response?.status === 410) {
      errorMessage.value = 'This invitation has expired or has already been used'
    } else {
      errorMessage.value =
        axiosError?.response?.data?.detail ||
        'Failed to accept invitation. Please contact support.'
    }

    // Show error for 3 seconds before redirecting to login
    setTimeout(() => {
      router.push({
        path: '/login',
        query: { error: 'invitation_failed' },
      })
    }, 3000)
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50">
    <div class="w-full max-w-md space-y-8 p-8">
      <!-- Loading State -->
      <div v-if="status === 'loading'" class="text-center">
        <div
          class="inline-block h-12 w-12 animate-spin rounded-full border-b-2 border-indigo-600"
        ></div>
        <p class="mt-4 text-gray-600">Accepting your invitation...</p>
      </div>

      <!-- Success State -->
      <div v-else-if="status === 'success'" class="text-center">
        <div
          class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100"
        >
          <svg
            class="h-6 w-6 text-green-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <h2 class="mt-4 text-2xl font-bold text-gray-900">Welcome to PazPaz!</h2>
        <p class="mt-2 text-gray-600">Your account has been activated.</p>
        <p class="mt-1 text-sm text-gray-500">Redirecting you to the calendar...</p>
      </div>

      <!-- Error State -->
      <div v-else class="text-center">
        <div
          class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100"
        >
          <svg
            class="h-6 w-6 text-red-600"
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
        </div>
        <h2 class="mt-4 text-2xl font-bold text-gray-900">Invitation Failed</h2>
        <p class="mt-2 text-gray-600">{{ errorMessage }}</p>
        <div class="mt-6">
          <router-link
            to="/login"
            class="text-sm font-medium text-indigo-600 hover:text-indigo-500"
          >
            Go to Login
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>
