<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()

const status = ref<'loading' | 'success' | 'error'>('loading')
const errorMessage = ref<string>('')

onMounted(async () => {
  const token = route.query.token as string

  if (!token) {
    status.value = 'error'
    errorMessage.value = 'No token provided'
    return
  }

  try {
    // Call the verify endpoint - this sets the JWT cookie
    // Changed to POST per backend security requirements (CSRF middleware ordering)
    await apiClient.post('/auth/verify', {
      token,
    })

    status.value = 'success'

    // Redirect to calendar after successful authentication
    setTimeout(() => {
      router.push('/')
    }, 1500)
  } catch (error: any) {
    status.value = 'error'
    errorMessage.value =
      error?.response?.data?.detail || 'Invalid or expired magic link'
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
        <p class="mt-4 text-gray-600">Verifying your login...</p>
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
        <h2 class="mt-4 text-2xl font-bold text-gray-900">Login Successful!</h2>
        <p class="mt-2 text-gray-600">Redirecting you to the calendar...</p>
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
        <h2 class="mt-4 text-2xl font-bold text-gray-900">Verification Failed</h2>
        <p class="mt-2 text-gray-600">{{ errorMessage }}</p>
        <p class="mt-4 text-sm text-gray-500">
          The magic link may have expired. Please request a new one.
        </p>
      </div>
    </div>
  </div>
</template>
