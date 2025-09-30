<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppointmentsStore } from '@/stores/appointments'

/**
 * Calendar View
 *
 * Weekly calendar view for appointment scheduling.
 * Uses FullCalendar for drag-and-drop appointment management.
 *
 * TODO: Implement FullCalendar component
 * TODO: Add appointment creation/editing modal
 * TODO: Implement drag-and-drop rescheduling
 * TODO: Add conflict detection
 */

const appointmentsStore = useAppointmentsStore()

onMounted(async () => {
  // Fetch appointments for the current week
  const today = new Date()
  const startOfWeek = new Date(today.setDate(today.getDate() - today.getDay()))
  const endOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + 6))

  await appointmentsStore.fetchAppointments(
    startOfWeek.toISOString().split('T')[0],
    endOfWeek.toISOString().split('T')[0]
  )
})
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <header class="mb-8">
      <h1 class="mb-2 text-3xl font-bold text-gray-900">Calendar</h1>
      <p class="text-gray-600">Weekly appointment schedule</p>
    </header>

    <div v-if="appointmentsStore.loading" class="text-center text-gray-600">
      Loading appointments...
    </div>

    <div
      v-else-if="appointmentsStore.error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      Error: {{ appointmentsStore.error }}
    </div>

    <div v-else class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <!-- TODO: Replace with FullCalendar component -->
      <div class="text-center text-gray-600">
        <p class="mb-4 text-lg font-medium">Calendar component coming soon</p>
        <p class="text-sm">
          Appointments loaded: {{ appointmentsStore.appointments.length }}
        </p>
        <div v-if="appointmentsStore.hasAppointments" class="mt-6">
          <h3 class="mb-3 text-left text-lg font-semibold">Current Appointments:</h3>
          <ul class="space-y-2 text-left">
            <li
              v-for="appointment in appointmentsStore.appointments"
              :key="appointment.id"
              class="rounded border border-gray-200 p-3"
            >
              <div class="font-medium">{{ appointment.title }}</div>
              <div class="text-sm text-gray-600">
                {{ new Date(appointment.start_time).toLocaleString() }} -
                {{ new Date(appointment.end_time).toLocaleString() }}
              </div>
              <div v-if="appointment.notes" class="mt-1 text-sm text-gray-500">
                {{ appointment.notes }}
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>
