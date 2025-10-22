<script setup lang="ts">
/**
 * Settings Card Component
 *
 * Reusable card component for settings pages.
 * Provides consistent styling and structure for settings sections.
 *
 * Features:
 * - Icon, title, and description header
 * - Toggle switch integration
 * - Expandable content area (shown when enabled)
 * - Smooth transitions
 * - Customizable via slots
 *
 * @example
 * <SettingsCard
 *   title="Email Notifications"
 *   description="Receive email updates"
 *   :expanded="emailEnabled"
 * >
 *   <template #icon>
 *     <MailIcon />
 *   </template>
 *   <template #toggle>
 *     <ToggleSwitch v-model="emailEnabled" />
 *   </template>
 *   <template #content>
 *     <div>Additional settings...</div>
 *   </template>
 * </SettingsCard>
 */

import { computed } from 'vue'

interface Props {
  /**
   * Card title (required)
   */
  title: string
  /**
   * Card description (optional)
   */
  description?: string
  /**
   * Whether the card's content section is expanded
   * Controls visibility of the content slot
   */
  expanded?: boolean
  /**
   * Whether to show the content section with background
   * (only applies when expanded is true)
   */
  showContentBg?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  expanded: false,
  showContentBg: true,
})

/**
 * Determine if content should be visible
 */
const isContentVisible = computed(() => props.expanded)
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
    <!-- Header Section -->
    <div class="flex items-start justify-between gap-4">
      <!-- Icon + Title + Description -->
      <div class="flex items-start gap-4">
        <!-- Icon Slot (optional) -->
        <div v-if="$slots.icon" class="flex-shrink-0">
          <slot name="icon" />
        </div>

        <!-- Title and Description -->
        <div>
          <h2 class="text-base font-semibold text-slate-900">
            {{ title }}
          </h2>
          <p v-if="description" class="mt-1 text-sm text-slate-600">
            {{ description }}
          </p>
        </div>
      </div>

      <!-- Toggle Slot (optional) -->
      <div v-if="$slots.toggle" class="flex-shrink-0">
        <slot name="toggle" />
      </div>
    </div>

    <!-- Warning Banner Slot (optional) -->
    <div v-if="$slots.warning" class="mt-4">
      <slot name="warning" />
    </div>

    <!-- Expandable Content Section (conditional) -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 max-h-0"
      enter-to-class="opacity-100 max-h-[500px]"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100 max-h-[500px]"
      leave-to-class="opacity-0 max-h-0"
    >
      <div
        v-if="isContentVisible && $slots.content"
        class="mt-4 overflow-hidden"
        :class="{
          'rounded-md bg-slate-50 p-4': showContentBg,
        }"
      >
        <slot name="content" />
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/**
 * Custom transition styles for smooth expand/collapse
 * Using max-h with overflow-hidden for height animation
 */
.max-h-0 {
  max-height: 0;
}

.max-h-\[500px\] {
  max-height: 500px;
}
</style>
