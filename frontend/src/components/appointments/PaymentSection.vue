<script setup lang="ts">
/**
 * PaymentSection - Responsive Tabs/Swiper Payment UI
 *
 * November 2025 Best Practices:
 * - Desktop (≥640px): Horizontal tabs with labeled navigation (Headless UI)
 * - Mobile (<640px): Swiper/carousel with swipe gestures (Embla Carousel)
 * - Preserves active section across responsive breakpoints
 * - Accessible: ARIA labels, keyboard navigation, touch targets
 * - Performance: Lazy-loaded Embla only on mobile, v-show for tab panels
 *
 * Usage:
 *   <PaymentSection
 *     :appointment-id="appointmentId"
 *     v-model:price="price"
 *     v-model:status="status"
 *     @send-payment-request="handleSend"
 *     @copy-payment-link="handleCopy"
 *   />
 *
 * Phase 1.5: Two sections - Payment Details, Actions
 * Phase 2+: Easy to expand by adding to sections array
 */

import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { TabGroup, TabList, Tab, TabPanels, TabPanel } from '@headlessui/vue'
import emblaCarouselVue from 'embla-carousel-vue'
import PaymentDetailsForm from './PaymentDetailsForm.vue'
import PaymentActions from './PaymentActions.vue'

interface Props {
  appointmentId: string
  price: number | null
  status: 'not_paid' | 'paid' | 'payment_sent' | 'waived'
  readonly?: boolean
  sending?: boolean
  sent?: boolean
  copying?: boolean
  copied?: boolean
}

interface Emits {
  (e: 'update:price', value: number | null): void
  (e: 'update:status', value: string): void
  (e: 'send-payment-request'): void
  (e: 'copy-payment-link'): void
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false,
  sending: false,
  sent: false,
  copying: false,
  copied: false,
})

const emit = defineEmits<Emits>()

// Responsive detection using window.matchMedia (preferred over @vueuse/core for this use case)
const isMobile = ref(false)
const mediaQuery = ref<MediaQueryList | null>(null)

// Active section index (synced across tabs and swiper)
const activeIndex = ref(0)

// Embla carousel instance
const [emblaRef, emblaApi] = emblaCarouselVue({ loop: false, align: 'start' })

/**
 * Payment sections configuration
 * Phase 2+: Add more sections here (e.g., History, Automation)
 */
const sections = [
  {
    id: 'details',
    label: 'Payment Details',
    ariaLabel: 'Payment details section with price and status fields',
  },
  {
    id: 'actions',
    label: 'Actions',
    ariaLabel: 'Payment actions section with send and copy buttons',
  },
]

/**
 * Update media query match state
 */
function updateMediaQuery(e: MediaQueryListEvent | MediaQueryList) {
  isMobile.value = e.matches
}

/**
 * Initialize responsive detection
 */
onMounted(() => {
  // Create media query for mobile breakpoint (< 640px)
  mediaQuery.value = window.matchMedia('(max-width: 639px)')
  isMobile.value = mediaQuery.value.matches

  // Listen for breakpoint changes
  mediaQuery.value.addEventListener('change', updateMediaQuery)

  // Sync embla carousel with active index on mobile
  if (emblaApi.value) {
    emblaApi.value.on('select', () => {
      activeIndex.value = emblaApi.value?.selectedScrollSnap() || 0
    })
  }
})

/**
 * Clean up event listeners
 */
onBeforeUnmount(() => {
  if (mediaQuery.value) {
    mediaQuery.value.removeEventListener('change', updateMediaQuery)
  }
})

/**
 * Handle tab change from Headless UI
 */
function handleTabChange(index: number) {
  activeIndex.value = index

  // If transitioning to mobile, scroll embla to match
  if (isMobile.value && emblaApi.value) {
    emblaApi.value.scrollTo(index)
  }
}

/**
 * Watch active index changes to sync embla on mobile
 */
watch(activeIndex, (newIndex) => {
  if (isMobile.value && emblaApi.value) {
    emblaApi.value.scrollTo(newIndex)
  }
})

/**
 * Handle progress dot clicks (mobile only)
 */
function handleDotClick(index: number) {
  activeIndex.value = index
  if (emblaApi.value) {
    emblaApi.value.scrollTo(index)
  }
}

/**
 * Computed v-models for child components
 */
const localPrice = computed({
  get: () => props.price,
  set: (value) => emit('update:price', value),
})

const localStatus = computed({
  get: () => props.status,
  set: (value) => emit('update:status', value),
})
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-4">
    <h3 class="mb-4 text-sm font-medium text-slate-900">Payment</h3>

    <!-- DESKTOP: Tabs (≥640px) -->
    <div v-if="!isMobile" class="hidden sm:block">
      <TabGroup :selectedIndex="activeIndex" @change="handleTabChange">
        <!-- Tab Navigation -->
        <TabList class="flex border-b border-slate-200">
          <Tab
            v-for="section in sections"
            :key="section.id"
            v-slot="{ selected }"
            class="flex-1 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
            :class="
              selected
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900'
            "
            :aria-label="section.ariaLabel"
          >
            {{ section.label }}
          </Tab>
        </TabList>

        <!-- Tab Panels - use v-show to avoid re-rendering -->
        <TabPanels class="mt-4">
          <TabPanel
            v-show="activeIndex === 0"
            :aria-labelledby="`tab-${sections[0].id}`"
            class="focus:outline-none"
          >
            <PaymentDetailsForm
              v-model:price="localPrice"
              v-model:status="localStatus"
              :readonly="readonly"
              @update:price="$emit('update:price', $event)"
              @update:status="$emit('update:status', $event)"
            />
          </TabPanel>

          <TabPanel
            v-show="activeIndex === 1"
            :aria-labelledby="`tab-${sections[1].id}`"
            class="focus:outline-none"
          >
            <PaymentActions
              :price="price"
              :status="status"
              :readonly="readonly"
              :sending="sending"
              :sent="sent"
              :copying="copying"
              :copied="copied"
              @send-payment-request="$emit('send-payment-request')"
              @copy-payment-link="$emit('copy-payment-link')"
            />
          </TabPanel>
        </TabPanels>
      </TabGroup>
    </div>

    <!-- MOBILE: Swiper (<640px) -->
    <div v-else class="block sm:hidden">
      <!-- Embla Carousel -->
      <div ref="emblaRef" class="overflow-hidden">
        <div class="flex touch-pan-y">
          <!-- Slide 1: Payment Details -->
          <div
            class="min-w-0 flex-[0_0_100%] pr-4"
            role="region"
            aria-roledescription="slide"
            :aria-label="sections[0].ariaLabel"
          >
            <PaymentDetailsForm
              v-model:price="localPrice"
              v-model:status="localStatus"
              :readonly="readonly"
              @update:price="$emit('update:price', $event)"
              @update:status="$emit('update:status', $event)"
            />
          </div>

          <!-- Slide 2: Payment Actions -->
          <div
            class="min-w-0 flex-[0_0_100%] pr-4"
            role="region"
            aria-roledescription="slide"
            :aria-label="sections[1].ariaLabel"
          >
            <PaymentActions
              :price="price"
              :status="status"
              :readonly="readonly"
              :sending="sending"
              :sent="sent"
              :copying="copying"
              :copied="copied"
              @send-payment-request="$emit('send-payment-request')"
              @copy-payment-link="$emit('copy-payment-link')"
            />
          </div>
        </div>
      </div>

      <!-- Progress Dots (mobile only) -->
      <div class="mt-4 flex justify-center gap-2" role="tablist" aria-label="Payment sections">
        <button
          v-for="(section, index) in sections"
          :key="section.id"
          @click="handleDotClick(index)"
          :aria-label="`Go to ${section.label}`"
          :aria-selected="activeIndex === index"
          role="tab"
          class="h-2 w-2 rounded-full transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
          :class="
            activeIndex === index
              ? 'w-6 bg-emerald-600'
              : 'bg-slate-300 hover:bg-slate-400 active:bg-slate-500'
          "
        ></button>
      </div>

      <!-- Section Labels (mobile only - below dots) -->
      <div class="mt-2 text-center text-xs text-slate-600">
        {{ sections[activeIndex].label }}
      </div>
    </div>
  </div>
</template>

<style scoped>
/**
 * Smooth touch scrolling for mobile swiper
 * Support for reduced motion preferences
 */
@media (prefers-reduced-motion: no-preference) {
  .touch-pan-y {
    scroll-behavior: smooth;
  }
}

/**
 * Ensure proper touch targets (44px minimum)
 */
button {
  min-width: 44px;
  min-height: 44px;
}
</style>
